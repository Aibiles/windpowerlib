# 风机集群模拟器集成说明

## 概述

这个集成系统将windpowerlib的真实物理模型集成到wind-farm-simulator的Web界面中，提供20个风机的实时数据模拟。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     风机集群模拟系统                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │   Python API    │    │   Node.js API   │    │   Web前端      │  │
│  │   (端口5000)    │◄──►│   (端口3000)    │◄──►│   (React)     │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
│           │                                                     │
│  ┌─────────────────┐                                            │
│  │  WindPowerLib   │                                            │
│  │  真实物理模型   │                                            │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 功能特性

### 🌪️ 真实物理模型
- 基于windpowerlib的Enercon E-126/4200风机模型
- 真实天气数据驱动（温度、气压、风速）
- 空气密度计算（理想气体定律）
- 功率密度和效率计算

### 🏭 风机集群模拟
- 20个风机的5x4网格布局
- 每个风机间距500-600米
- 考虑尾流效应的风速分布
- 随机状态变化（运行/维护/停机）

### 📊 实时数据
- 实时发电量、风速、转速数据
- 风机位置坐标
- 运行状态监控
- 统计数据（容量因子、效率等）

### 🔄 多种接口
- HTTP REST API
- WebSocket实时推送
- 与Node.js后端集成

## 安装和运行

### 1. 安装Python依赖

```bash
# 在windpowerlib目录下
pip install -r requirements.txt
```

### 2. 启动Python API服务器

```bash
# 方式1：使用启动脚本
python start_wind_farm_api.py

# 方式2：直接运行API服务器
python wind_farm_api.py

# 方式3：运行单独的集群模拟器
python wind_farm_cluster_simulator.py
```

### 3. 启动Node.js服务器

```bash
# 在wind-farm-simulator目录下
cd ../wind-farm-simulator
npm install
npm run dev
```

### 4. 访问Web界面

打开浏览器访问：http://localhost:3000

## API端点

### Python API (端口5000)

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | API信息 |
| `/api/farm-data` | GET | 获取风场数据 |
| `/api/start-simulation` | POST | 启动模拟 |
| `/api/stop-simulation` | POST | 停止模拟 |
| `/api/turbine/<id>` | GET | 获取单个风机数据 |
| `/api/statistics` | GET | 获取统计数据 |
| `/api/turbines` | GET | 获取所有风机列表 |

### WebSocket事件

| 事件 | 描述 |
|------|------|
| `connect` | 客户端连接 |
| `farm-data` | 风场数据推送 |
| `start-simulator` | 启动模拟 |
| `stop-simulator` | 停止模拟 |
| `simulator-status` | 模拟器状态 |

## 数据格式

### 风机数据结构

```typescript
interface WindTurbine {
  id: number;                    // 风机ID
  name: string;                  // 风机名称 (WT-01, WT-02, ...)
  status: 'running' | 'maintenance' | 'stopped';
  power: number;                 // 当前发电量 (kW)
  totalGeneration: number;       // 累计发电量 (kWh)
  windSpeed: number;             // 风速 (m/s)
  rotationSpeed: number;         // 转速 (rpm)
  temperature: number;           // 温度 (°C)
  pressure: number;              // 气压 (kPa)
  airDensity: number;           // 空气密度 (kg/m³)
  powerDensity: number;         // 功率密度 (W/m²)
  efficiency: number;           // 效率 (%)
  position: {x: number, y: number}; // 位置坐标 (米)
  lastMaintenance: string;      // 上次维护时间
}
```

### 风场数据结构

```typescript
interface FarmData {
  timestamp: string;            // 时间戳
  totalPower: number;          // 总发电量 (kW)
  efficiency: number;          // 风场效率 (%)
  weather: {
    windSpeed: number;         // 平均风速 (m/s)
    windDirection: number;     // 风向 (度)
    temperature: number;       // 温度 (°C)
    humidity: number;          // 湿度 (%)
    pressure: number;          // 气压 (hPa)
  };
  turbines: WindTurbine[];     // 风机列表
  statistics: {
    runningTurbines: number;   // 运行中风机数
    maintenanceTurbines: number; // 维护中风机数
    stoppedTurbines: number;   // 停机风机数
    totalGeneration: number;   // 总发电量 (kWh)
    averagePowerDensity: number; // 平均功率密度 (W/m²)
    capacityFactor: number;    // 容量因子 (%)
  };
}
```

## 配置参数

### 风机参数 (Enercon E-126/4200)
- **额定功率**: 4200 kW
- **转子直径**: 127 m
- **轮毂高度**: 135 m
- **扫风面积**: 12,666 m²
- **切入风速**: 2.5 m/s
- **切出风速**: 28 m/s
- **额定风速**: 13 m/s
- **最大转速**: 11.6 rpm

### 风场布局
- **风机数量**: 20个
- **布局**: 5列 × 4行
- **间距**: 500m (X方向) × 600m (Y方向)
- **总面积**: 2000m × 1800m

## 故障排除

### 常见问题

1. **Python API连接失败**
   - 检查端口5000是否被占用
   - 确认Python依赖包已安装
   - 检查weather.csv文件是否存在

2. **天气数据文件缺失**
   - 程序会自动下载示例天气数据
   - 或手动复制weather.csv文件

3. **windpowerlib模型失败**
   - 检查网络连接（需要下载风机数据）
   - 使用备用的简化功率模型

### 日志查看

Python API服务器会显示详细的运行日志：
- 连接状态
- 数据更新频率
- 错误信息
- 性能统计

### 调试模式

启动时添加调试参数：
```bash
python wind_farm_api.py --debug
```

## 性能优化

### 更新频率
- 默认5秒更新一次
- 可调整为1-60秒之间
- 更高频率需要更多CPU资源

### 内存使用
- 天气数据约50MB
- 风机数据约1MB
- 总内存使用约100MB

### 网络带宽
- 每次数据推送约10KB
- 20个风机的完整数据约2KB
- WebSocket连接开销较小

## 扩展功能

### 增加风机数量
修改`wind_farm_cluster_simulator.py`中的参数：
```python
simulator = WindFarmClusterSimulator(turbine_count=50)
```

### 自定义风机模型
修改风机参数：
```python
turbine_params = {
    'turbine_type': 'V90/2000',  # 更换风机型号
    'hub_height': 100,           # 调整轮毂高度
}
```

### 添加新的API端点
在`wind_farm_api.py`中添加：
```python
@app.route('/api/custom-endpoint', methods=['GET'])
def custom_endpoint():
    # 自定义功能
    return jsonify({'message': 'Custom data'})
```

## 许可证

本项目基于MIT许可证，详见LICENSE文件。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 创建GitHub Issue
- 发送邮件至项目维护者 