@echo off
chcp 65001 >nul
cls

echo =========================================
echo         风机MQTT数据传输系统
echo =========================================
echo.

echo 请选择要运行的程序:
echo.
echo 1. 启动单风机模拟器 (simulator.py)
echo 2. 启动20风机集群模拟器 (wind_farm_cluster_simulator.py) [推荐]
echo 3. 启动MQTT数据订阅客户端 (mqtt_subscriber.py)
echo 4. 安装Python依赖包
echo 5. 检查MQTT服务状态
echo 6. 启动Mosquitto MQTT服务
echo 7. 测试MQTT连接
echo 8. 查看帮助文档
echo 9. 退出
echo.

set /p choice="请输入选择 (1-9): "

if "%choice%"=="1" goto single_turbine
if "%choice%"=="2" goto cluster_turbine
if "%choice%"=="3" goto mqtt_subscriber
if "%choice%"=="4" goto install_deps
if "%choice%"=="5" goto check_mqtt
if "%choice%"=="6" goto start_mqtt
if "%choice%"=="7" goto test_mqtt
if "%choice%"=="8" goto help
if "%choice%"=="9" goto exit

echo 无效选择，请重新选择
pause
goto start

:single_turbine
cls
echo ========================================
echo       启动单风机模拟器
echo ========================================
echo.
echo 正在启动单风机模拟器...
echo 该程序将提示您配置MQTT设置
echo.
python simulator.py
pause
goto start

:cluster_turbine
cls
echo ========================================
echo      启动20风机集群模拟器
echo ========================================
echo.
echo 正在启动20风机集群模拟器...
echo 该程序将提示您配置MQTT设置
echo.
python wind_farm_cluster_simulator.py
pause
goto start

:mqtt_subscriber
cls
echo ========================================
echo     启动MQTT数据订阅客户端
echo ========================================
echo.
echo 正在启动MQTT订阅客户端...
echo 该程序将连接到MQTT服务器接收数据
echo.
python mqtt_subscriber.py
pause
goto start

:install_deps
cls
echo ========================================
echo       安装Python依赖包
echo ========================================
echo.
echo 正在安装依赖包...
pip install -r requirements.txt
echo.
echo 依赖包安装完成!
pause
goto start

:check_mqtt
cls
echo ========================================
echo      检查MQTT服务状态
echo ========================================
echo.
echo 检查Mosquitto服务状态...
sc query mosquitto
echo.
echo 检查1883端口占用情况...
netstat -an | findstr :1883
echo.
pause
goto start

:start_mqtt
cls
echo ========================================
echo     启动Mosquitto MQTT服务
echo ========================================
echo.
echo 正在启动Mosquitto服务...
net start mosquitto
if %errorlevel%==0 (
    echo ✅ Mosquitto服务启动成功!
) else (
    echo ❌ Mosquitto服务启动失败，请检查安装是否正确
    echo 可能需要以管理员身份运行此脚本
)
echo.
pause
goto start

:test_mqtt
cls
echo ========================================
echo        测试MQTT连接
echo ========================================
echo.
echo 测试MQTT连接...
echo 如果看到消息"Hello MQTT"，说明MQTT服务正常
echo.

echo 发布测试消息...
mosquitto_pub.exe -h localhost -t "test/message" -m "Hello MQTT"

echo.
echo 订阅测试消息 (按Ctrl+C停止):
mosquitto_sub.exe -h localhost -t "test/message" -v
echo.
pause
goto start

:help
cls
echo ========================================
echo          帮助文档
echo ========================================
echo.
echo 📋 系统组件说明:
echo.
echo 1. simulator.py - 单风机模拟器
echo    - 基于windpowerlib的真实物理模型
echo    - 支持MQTT数据发布
echo    - 适合测试和学习
echo.
echo 2. wind_farm_cluster_simulator.py - 风机集群模拟器
echo    - 模拟20台风机的风场
echo    - 包含尾流效应和状态变化
echo    - 支持MQTT数据发布
echo    - 推荐用于实际演示
echo.
echo 3. mqtt_subscriber.py - 数据订阅客户端
echo    - 接收并显示MQTT数据
echo    - 交互式命令界面
echo    - 支持CSV数据导出
echo.
echo 📡 MQTT主题结构:
echo    windfarm/farm_summary     - 风场汇总
echo    windfarm/turbine/01       - 风机01数据
echo    windfarm/turbine/02       - 风机02数据
echo    ...
echo    windfarm/turbine/20       - 风机20数据
echo.
echo 🔧 故障排除:
echo    - 确保Mosquitto已安装并启动
echo    - 检查防火墙1883端口设置
echo    - 验证Python依赖包已安装
echo.
echo 📖 详细文档:
echo    - MQTT_SETUP_GUIDE.md - MQTT服务器设置指南
echo    - MQTT_INTEGRATION_README.md - 完整集成指南
echo.
pause
goto start

:exit
echo.
echo 感谢使用风机MQTT数据传输系统!
echo.
pause
exit

:start 