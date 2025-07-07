#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风机数据可视化Web应用
提供API接口和Web界面展示风机实时数据
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import pandas as pd
import json
import threading
import time
from datetime import datetime
from werkzeug.utils import secure_filename
import logging

# 导入风机模拟器
from wind_farm_cluster_simulator import WindFarmClusterSimulator

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'wind_farm_secret_key_2024'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 启用CORS和SocketIO
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 确保上传文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 全局变量
wind_farm_simulator = None
simulation_thread = None
simulation_running = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_weather_csv(filepath):
    """验证天气CSV文件格式"""
    try:
        # 读取CSV文件
        df = pd.read_csv(filepath, header=[0, 1], index_col=0)
        
        # 检查必要的列
        required_columns = [
            ('wind_speed', '80'),
            ('temperature', '10'),
            ('pressure', '0')
        ]
        
        for col in required_columns:
            if col not in df.columns:
                return False, f"缺少必要列: {col}"
                
        # 检查数据量
        if len(df) < 100:
            return False, "数据量太少，至少需要100行数据"
            
        return True, "文件格式正确"
        
    except Exception as e:
        return False, f"文件格式错误: {str(e)}"

def background_simulation():
    """后台模拟线程"""
    global simulation_running, wind_farm_simulator
    
    logger.info("开始后台模拟...")
    
    while simulation_running:
        try:
            if wind_farm_simulator:
                # 更新模拟数据
                wind_farm_simulator.update_simulation()
                
                # 获取风场数据
                farm_data = wind_farm_simulator.get_farm_data()
                
                # 通过WebSocket发送数据
                socketio.emit('farm_data_update', farm_data)
                
                # 发送每个风机的数据
                for turbine in wind_farm_simulator.turbines:
                    turbine_data = turbine.to_dict()
                    socketio.emit('turbine_data_update', turbine_data)
                
                logger.info(f"数据更新: 总发电量 {farm_data['totalPower']:.1f} kW")
                
        except Exception as e:
            logger.error(f"模拟更新错误: {e}")
            
        time.sleep(3)  # 3秒更新一次
        
    logger.info("后台模拟已停止")

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API状态"""
    global wind_farm_simulator, simulation_running
    
    return jsonify({
        'status': 'running' if simulation_running else 'stopped',
        'simulator_initialized': wind_farm_simulator is not None,
        'turbine_count': len(wind_farm_simulator.turbines) if wind_farm_simulator else 0,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/farm-data')
def api_farm_data():
    """获取风场数据"""
    global wind_farm_simulator
    
    if not wind_farm_simulator:
        return jsonify({'error': '模拟器未初始化'}), 400
        
    try:
        farm_data = wind_farm_simulator.get_farm_data()
        return jsonify(farm_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/turbines')
def api_turbines():
    """获取所有风机数据"""
    global wind_farm_simulator
    
    if not wind_farm_simulator:
        return jsonify({'error': '模拟器未初始化'}), 400
        
    try:
        turbines_data = [turbine.to_dict() for turbine in wind_farm_simulator.turbines]
        return jsonify(turbines_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/turbine/<int:turbine_id>')
def api_turbine(turbine_id):
    """获取指定风机数据"""
    global wind_farm_simulator
    
    if not wind_farm_simulator:
        return jsonify({'error': '模拟器未初始化'}), 400
        
    try:
        turbine = next((t for t in wind_farm_simulator.turbines if t.id == turbine_id), None)
        if not turbine:
            return jsonify({'error': f'风机{turbine_id}不存在'}), 404
            
        return jsonify(turbine.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-simulation', methods=['POST'])
def api_start_simulation():
    """启动模拟"""
    global wind_farm_simulator, simulation_thread, simulation_running
    
    try:
        data = request.get_json() or {}
        turbine_count = data.get('turbine_count', 20)
        enable_mqtt = data.get('enable_mqtt', False)
        
        # 停止现有模拟
        if simulation_running:
            simulation_running = False
            if simulation_thread:
                simulation_thread.join()
                
        # 创建新的模拟器
        wind_farm_simulator = WindFarmClusterSimulator(
            turbine_count=turbine_count,
            enable_mqtt=enable_mqtt
        )
        
        # 启动后台模拟
        simulation_running = True
        simulation_thread = threading.Thread(target=background_simulation)
        simulation_thread.daemon = True
        simulation_thread.start()
        
        logger.info(f"模拟已启动: {turbine_count}个风机")
        
        return jsonify({
            'status': 'started',
            'turbine_count': turbine_count,
            'enable_mqtt': enable_mqtt,
            'message': f'模拟已启动，共{turbine_count}个风机'
        })
        
    except Exception as e:
        logger.error(f"启动模拟失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-simulation', methods=['POST'])
def api_stop_simulation():
    """停止模拟"""
    global simulation_running, simulation_thread, wind_farm_simulator
    
    try:
        simulation_running = False
        
        if simulation_thread:
            simulation_thread.join(timeout=5)
            
        if wind_farm_simulator and hasattr(wind_farm_simulator, 'disconnect_mqtt'):
            wind_farm_simulator.disconnect_mqtt()
            
        logger.info("模拟已停止")
        
        return jsonify({
            'status': 'stopped',
            'message': '模拟已停止'
        })
        
    except Exception as e:
        logger.error(f"停止模拟失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-weather', methods=['POST'])
def api_upload_weather():
    """上传天气数据CSV文件"""
    global wind_farm_simulator
    
    try:
        # 检查文件
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': '只允许CSV文件'}), 400
            
        # 保存文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"weather_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 验证文件格式
        is_valid, message = validate_weather_csv(filepath)
        if not is_valid:
            os.remove(filepath)  # 删除无效文件
            return jsonify({'error': message}), 400
            
        # 备份原始天气文件
        original_weather = 'weather.csv'
        if os.path.exists(original_weather):
            backup_name = f"weather_backup_{timestamp}.csv"
            os.rename(original_weather, backup_name)
            
        # 使用新的天气文件
        os.rename(filepath, original_weather)
        
        # 如果模拟器正在运行，重新加载天气数据
        if wind_farm_simulator:
            wind_farm_simulator._load_weather_data()
            wind_farm_simulator.current_index = 0
            
        logger.info(f"天气数据已更新: {filename}")
        
        return jsonify({
            'status': 'success',
            'message': f'天气数据已更新: {file.filename}',
            'filename': filename
        })
        
    except Exception as e:
        logger.error(f"上传天气数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload')
def upload_page():
    """上传页面"""
    return render_template('upload.html')

@app.route('/dashboard')
def dashboard():
    """仪表板页面"""
    return render_template('dashboard.html')

@app.route('/turbines')
def turbines_page():
    """风机列表页面"""
    return render_template('turbines.html')

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    logger.info('客户端已连接')
    emit('status', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    logger.info('客户端已断开连接')

@socketio.on('request_data')
def handle_request_data():
    """客户端请求数据"""
    global wind_farm_simulator
    
    if wind_farm_simulator:
        try:
            farm_data = wind_farm_simulator.get_farm_data()
            emit('farm_data_update', farm_data)
            
            for turbine in wind_farm_simulator.turbines:
                turbine_data = turbine.to_dict()
                emit('turbine_data_update', turbine_data)
                
        except Exception as e:
            emit('error', {'message': str(e)})
    else:
        emit('error', {'message': '模拟器未初始化'})

def create_app():
    """应用工厂函数"""
    return app

if __name__ == '__main__':
    logger.info("启动风机数据可视化Web应用...")
    
    # 创建模板文件夹
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # 启动应用
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        allow_unsafe_werkzeug=True
    ) 