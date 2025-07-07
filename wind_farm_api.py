from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
import logging
from wind_farm_cluster_simulator import WindFarmClusterSimulator
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'wind_farm_secret_key'
CORS(app)

# 创建SocketIO实例
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量
simulator = None
simulation_thread = None
simulation_running = False

def create_simulator():
    """创建风机集群模拟器"""
    global simulator
    simulator = WindFarmClusterSimulator(turbine_count=20)
    logger.info("风机集群模拟器已创建 - 20个风机")

def background_simulation():
    """后台模拟任务"""
    global simulation_running
    
    while simulation_running:
        try:
            # 更新模拟数据
            simulator.update_simulation()
            farm_data = simulator.get_farm_data()
            
            # 通过SocketIO发送数据
            socketio.emit('farm-data', farm_data, broadcast=True)
            
            # 记录日志
            logger.info(f"发送数据: 总功率={farm_data['totalPower']:.1f}kW, "
                       f"运行风机={farm_data['statistics']['runningTurbines']}/20")
            
            # 等待更新间隔
            time.sleep(5)  # 5秒更新一次
            
        except Exception as e:
            logger.error(f"模拟过程中出错: {e}")
            time.sleep(1)

@app.route('/')
def index():
    """API根路径"""
    return jsonify({
        'service': 'Wind Farm API',
        'version': '1.0.0',
        'description': '风机集群数据模拟API',
        'endpoints': {
            '/api/farm-data': 'GET - 获取当前风场数据',
            '/api/start-simulation': 'POST - 启动模拟',
            '/api/stop-simulation': 'POST - 停止模拟',
            '/api/turbine/<int:turbine_id>': 'GET - 获取特定风机数据',
            '/api/statistics': 'GET - 获取统计数据'
        }
    })

@app.route('/api/farm-data', methods=['GET'])
def get_farm_data():
    """获取当前风场数据"""
    try:
        if simulator is None:
            return jsonify({'error': '模拟器未初始化'}), 500
            
        farm_data = simulator.get_farm_data()
        return jsonify(farm_data)
        
    except Exception as e:
        logger.error(f"获取风场数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-simulation', methods=['POST'])
def start_simulation():
    """启动模拟"""
    global simulation_thread, simulation_running
    
    try:
        if simulation_running:
            return jsonify({'message': '模拟已在运行'}), 200
            
        simulation_running = True
        simulation_thread = threading.Thread(target=background_simulation)
        simulation_thread.daemon = True
        simulation_thread.start()
        
        logger.info("模拟已启动")
        return jsonify({'message': '模拟已启动', 'running': True})
        
    except Exception as e:
        logger.error(f"启动模拟失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-simulation', methods=['POST'])
def stop_simulation():
    """停止模拟"""
    global simulation_running
    
    try:
        simulation_running = False
        logger.info("模拟已停止")
        return jsonify({'message': '模拟已停止', 'running': False})
        
    except Exception as e:
        logger.error(f"停止模拟失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/turbine/<int:turbine_id>', methods=['GET'])
def get_turbine_data(turbine_id):
    """获取特定风机数据"""
    try:
        if simulator is None:
            return jsonify({'error': '模拟器未初始化'}), 500
            
        # 查找指定的风机
        turbine = None
        for t in simulator.turbines:
            if t.id == turbine_id:
                turbine = t
                break
                
        if turbine is None:
            return jsonify({'error': f'风机 {turbine_id} 不存在'}), 404
            
        return jsonify(turbine.to_dict())
        
    except Exception as e:
        logger.error(f"获取风机数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取统计数据"""
    try:
        if simulator is None:
            return jsonify({'error': '模拟器未初始化'}), 500
            
        farm_data = simulator.get_farm_data()
        statistics = farm_data['statistics']
        
        # 添加更多统计信息
        turbines_by_status = {
            'running': [],
            'maintenance': [],
            'stopped': []
        }
        
        for turbine in simulator.turbines:
            turbines_by_status[turbine.status].append({
                'id': turbine.id,
                'name': turbine.name,
                'power': turbine.power
            })
            
        statistics['turbinesByStatus'] = turbines_by_status
        statistics['timestamp'] = farm_data['timestamp']
        
        return jsonify(statistics)
        
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/turbines', methods=['GET'])
def get_all_turbines():
    """获取所有风机列表"""
    try:
        if simulator is None:
            return jsonify({'error': '模拟器未初始化'}), 500
            
        turbines = [t.to_dict() for t in simulator.turbines]
        return jsonify({'turbines': turbines, 'count': len(turbines)})
        
    except Exception as e:
        logger.error(f"获取风机列表失败: {e}")
        return jsonify({'error': str(e)}), 500

# SocketIO事件处理
@socketio.on('connect')
def handle_connect():
    """客户端连接事件"""
    logger.info(f"客户端已连接: {request.sid}")
    
    # 发送初始数据
    if simulator is not None:
        farm_data = simulator.get_farm_data()
        emit('farm-data', farm_data)
        emit('simulator-status', {'running': simulation_running})

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接事件"""
    logger.info(f"客户端已断开连接: {request.sid}")

@socketio.on('start-simulator')
def handle_start_simulator(data=None):
    """启动模拟器事件"""
    global simulation_thread, simulation_running
    
    try:
        if simulation_running:
            emit('simulator-status', {'running': True, 'message': '模拟已在运行'})
            return
            
        simulation_running = True
        simulation_thread = threading.Thread(target=background_simulation)
        simulation_thread.daemon = True
        simulation_thread.start()
        
        logger.info("通过SocketIO启动模拟")
        emit('simulator-status', {'running': True, 'message': '模拟已启动'})
        
    except Exception as e:
        logger.error(f"SocketIO启动模拟失败: {e}")
        emit('error', {'message': str(e)})

@socketio.on('stop-simulator')
def handle_stop_simulator():
    """停止模拟器事件"""
    global simulation_running
    
    try:
        simulation_running = False
        logger.info("通过SocketIO停止模拟")
        emit('simulator-status', {'running': False, 'message': '模拟已停止'})
        
    except Exception as e:
        logger.error(f"SocketIO停止模拟失败: {e}")
        emit('error', {'message': str(e)})

@socketio.on('get-farm-data')
def handle_get_farm_data():
    """获取风场数据事件"""
    try:
        if simulator is not None:
            farm_data = simulator.get_farm_data()
            emit('farm-data', farm_data)
        else:
            emit('error', {'message': '模拟器未初始化'})
            
    except Exception as e:
        logger.error(f"获取风场数据失败: {e}")
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    # 初始化模拟器
    create_simulator()
    
    # 启动Flask-SocketIO服务器
    logger.info("启动风机集群API服务器...")
    logger.info("API端点:")
    logger.info("  HTTP API: http://localhost:5000")
    logger.info("  SocketIO: ws://localhost:5000")
    logger.info("  风机数量: 20个")
    
    try:
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=False,
                    allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("服务器已停止")
        simulation_running = False 