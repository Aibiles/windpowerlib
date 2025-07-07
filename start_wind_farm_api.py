#!/usr/bin/env python3
"""
风机集群API服务器启动脚本
"""
import os
import sys
import subprocess
import time

def check_dependencies():
    """检查依赖包是否安装"""
    required_packages = [
        'flask',
        'flask_cors',
        'flask_socketio',
        'pandas',
        'numpy',
        'matplotlib',
        'requests',
        'windpowerlib'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n缺少以下依赖包: {', '.join(missing_packages)}")
        print("请运行以下命令安装：")
        print("pip install -r requirements.txt")
        return False
    
    return True

def check_weather_data():
    """检查天气数据文件是否存在"""
    weather_file = "weather.csv"
    if not os.path.exists(weather_file):
        print(f"❌ 天气数据文件 {weather_file} 不存在")
        print("程序会自动下载示例天气数据")
        return False
    else:
        print(f"✅ 天气数据文件 {weather_file} 已存在")
        return True

def start_api_server():
    """启动API服务器"""
    print("🚀 启动风机集群API服务器...")
    print("=" * 60)
    
    try:
        # 启动Flask-SocketIO服务器
        from wind_farm_api import app, socketio, create_simulator
        
        # 创建模拟器
        create_simulator()
        
        # 启动服务器
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=False,
                    allow_unsafe_werkzeug=True)
                    
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("🌪️  风机集群API服务器")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        print("\n请先安装依赖包")
        return
    
    # 检查天气数据
    check_weather_data()
    
    # 启动服务器
    print("\n🌐 服务器信息:")
    print("   HTTP API: http://localhost:5000")
    print("   SocketIO: ws://localhost:5000")
    print("   风机数量: 20个")
    print("   基于windpowerlib的真实物理模型")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    start_api_server()

if __name__ == "__main__":
    main() 