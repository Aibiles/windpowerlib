# 风机数据MQTT集成完整指南

## 概述

本项目已完全集成MQTT功能，可以将风机模拟数据实时推送到Windows本地MQTT服务器。系统包含以下组件：

1. **simulator.py** - 单风机模拟器，支持MQTT发布
2. **wind_farm_cluster_simulator.py** - 20台风机集群模拟器，支持MQTT发布  
3. **mqtt_subscriber.py** - MQTT数据订阅客户端
4. **MQTT Broker** - Mosquitto MQTT服务器

## 快速开始指南

### 步骤1：安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt
```

### 步骤2：设置MQTT Broker

参考 `MQTT_SETUP_GUIDE.md` 详细说明，快速设置：

```powershell
# 方法1：直接下载安装 Mosquitto
# 访问 https://mosquitto.org/download/

# 方法2：使用Chocolatey安装
choco install mosquitto

# 启动Mosquitto服务
net start mosquitto
```

### 步骤3：运行数据发布端

选择以下任一方式：

```bash
# 方式1：运行单风机模拟器
python simulator.py

# 方式2：运行20风机集群模拟器（推荐）
python wind_farm_cluster_simulator.py
```

### 步骤4：运行数据订阅端

```bash
# 启动MQTT订阅客户端
python mqtt_subscriber.py
```

## 详细使用说明

### 1. 单风机模拟器 (simulator.py)

**功能特点：**
- 基于windpowerlib的Enercon E-126/4200风机
- 真实物理模型和天气数据
- 支持MQTT实时数据发布
- 自动时间戳更新

**使用方法：**
```bash
python simulator.py
```

运行时会提示：
1. 是否启用MQTT发布
2. MQTT Broker配置（地址、端口、主题前缀）
3. 是否运行实时模拟

**MQTT主题：**
- `windpower/turbine_01/data` - 风机数据

### 2. 风机集群模拟器 (wind_farm_cluster_simulator.py)

**功能特点：**
- 20台风机5×4网格布局
- 考虑尾流效应的风速分布
- 随机状态变化（运行/维护/停机）
- 风场汇总统计数据
- 支持MQTT实时数据发布

**使用方法：**
```bash
python wind_farm_cluster_simulator.py
```

**MQTT主题结构：**
```
windfarm/
├── farm_summary          # 风场汇总数据
├── turbine/01            # 风机01数据
├── turbine/02            # 风机02数据
└── ...
    └── turbine/20        # 风机20数据
```

### 3. MQTT订阅客户端 (mqtt_subscriber.py)

**功能特点：**
- 实时接收风机数据
- 交互式命令界面
- 数据统计和分析
- CSV数据导出
- 多线程安全处理

**使用方法：**
```bash
python mqtt_subscriber.py
```

**交互命令：**
- `stats` - 显示统计信息
- `farm` - 显示风场汇总
- `list` - 列出所有风机
- `turbine <id>` - 显示指定风机详情
- `csv` - 启用CSV记录
- `quit` - 退出程序

## 数据格式说明

### 风场汇总数据格式

```json
{
  "timestamp": "2024-01-20 15:30:00",
  "totalPower": 45230.5,
  "efficiency": 87.3,
  "weather": {
    "windSpeed": 12.5,
    "windDirection": 180,
    "temperature": 18.5,
    "humidity": 65,
    "pressure": 1013.2
  },
  "statistics": {
    "runningTurbines": 19,
    "maintenanceTurbines": 1,
    "stoppedTurbines": 0,
    "totalGeneration": 125640.8,
    "averagePowerDensity": 215.3,
    "capacityFactor": 53.8
  }
}
```

### 单个风机数据格式

```json
{
  "id": 1,
  "name": "WT-01",
  "status": "running",
  "power": 2850.5,
  "totalGeneration": 8547.2,
  "windSpeed": 11.8,
  "rotationSpeed": 9.2,
  "temperature": 18.2,
  "pressure": 101.3,
  "airDensity": 1.2245,
  "powerDensity": 225.0,
  "lastMaintenance": "2024-01-15T08:00:00",
  "efficiency": 85.5,
  "position": {"x": 0, "y": 0}
}
```

## 配置选项

### MQTT连接配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| broker_host | localhost | MQTT Broker地址 |
| broker_port | 1883 | MQTT Broker端口 |
| topic_prefix | windfarm | 主题前缀 |

### 模拟器配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| turbine_count | 20 | 风机数量 |
| update_interval | 3.0 | 数据更新间隔(秒) |
| enable_mqtt | False | 是否启用MQTT |

## 监控和测试

### 使用命令行工具监控

```powershell
# 监控所有风机数据
mosquitto_sub.exe -h localhost -t "windfarm/+/+" -v

# 只监控风场汇总
mosquitto_sub.exe -h localhost -t "windfarm/farm_summary" -v

# 监控特定风机
mosquitto_sub.exe -h localhost -t "windfarm/turbine/01" -v
```

### 性能测试

**典型性能指标：**
- 20个风机 + 1个汇总 = 21条消息/周期
- 更新频率：3秒/周期
- 消息发布频率：7 消息/秒
- 单条消息大小：~500字节
- 总带宽：~3.5KB/秒

## 故障排除

### 常见问题

1. **MQTT连接失败**
   ```bash
   # 检查Mosquitto服务状态
   net start mosquitto
   
   # 检查端口占用
   netstat -an | findstr :1883
   ```

2. **数据发布失败**
   - 检查网络连接
   - 验证MQTT配置
   - 查看错误日志

3. **数据订阅无响应**
   - 确认主题名称正确
   - 检查QoS设置
   - 验证JSON格式

### 调试命令

```bash
# 启用详细日志
python simulator.py --verbose

# 测试MQTT连接
mosquitto_pub.exe -h localhost -t "test" -m "hello"
mosquitto_sub.exe -h localhost -t "test" -v
```

## 集成到现有系统

### WebSocket集成

可以创建MQTT到WebSocket桥接器：

```python
# mqtt_websocket_bridge.py
import asyncio
import websockets
import paho.mqtt.client as mqtt
import json

class MQTTWebSocketBridge:
    def __init__(self):
        self.websocket_clients = set()
        self.mqtt_client = mqtt.Client()
        
    async def websocket_handler(self, websocket, path):
        self.websocket_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.websocket_clients.remove(websocket)
            
    def on_mqtt_message(self, client, userdata, msg):
        message = {
            'topic': msg.topic,
            'payload': json.loads(msg.payload.decode('utf-8'))
        }
        
        # 广播到所有WebSocket客户端
        asyncio.create_task(self.broadcast_to_websockets(message))
```

### 数据库存储

可以创建MQTT到数据库的数据持久化：

```python
# mqtt_database_logger.py
import sqlite3
import paho.mqtt.client as mqtt
import json
from datetime import datetime

class MQTTDatabaseLogger:
    def __init__(self, db_path="windfarm.db"):
        self.db = sqlite3.connect(db_path)
        self.create_tables()
        
    def create_tables(self):
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS turbine_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                turbine_id INTEGER,
                power REAL,
                wind_speed REAL,
                status TEXT
            )
        ''')
```

## 部署建议

### 生产环境配置

1. **安全配置**
   - 启用MQTT用户认证
   - 配置SSL/TLS加密
   - 设置访问控制列表

2. **性能优化**
   - 调整消息QoS级别
   - 配置消息持久化
   - 设置合适的更新频率

3. **监控告警**
   - 设置性能监控
   - 配置异常告警
   - 日志审计记录

### 扩展性考虑

- 支持更多风机数量
- 添加更多数据指标
- 集成天气预报API
- 支持多风场管理

现在您的风机MQTT集成系统已完全准备就绪！ 