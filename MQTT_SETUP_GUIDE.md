# MQTT服务器设置指南 (Windows)

## 1. 安装Mosquitto MQTT Broker

### 方法一：下载安装包（推荐）

1. **下载Mosquitto**
   - 访问官网：https://mosquitto.org/download/
   - 下载Windows版本：`mosquitto-2.0.x-install-windows-x64.exe`

2. **安装过程**
   ```bash
   # 以管理员身份运行安装包
   # 默认安装路径：C:\Program Files\mosquitto
   ```

3. **添加环境变量**
   - 将 `C:\Program Files\mosquitto` 添加到系统PATH
   - 或者直接在命令行中切换到mosquitto目录

### 方法二：使用Chocolatey

```powershell
# 安装Chocolatey（如果没有安装）
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安装Mosquitto
choco install mosquitto
```

## 2. 配置Mosquitto

### 创建配置文件

在 `C:\Program Files\mosquitto\` 目录下创建 `mosquitto.conf`：

```ini
# mosquitto.conf
port 1883
allow_anonymous true
log_type all
log_dest file C:\Program Files\mosquitto\mosquitto.log

# 监听所有网络接口
listener 1883 0.0.0.0

# 启用WebSocket支持（可选）
listener 9001
protocol websockets

# 持久化配置
persistence true
persistence_location C:\Program Files\mosquitto\data\
```

### 创建数据目录

```powershell
# 创建数据目录
mkdir "C:\Program Files\mosquitto\data"
```

## 3. 启动MQTT Broker

### 方法一：命令行启动

```powershell
# 打开PowerShell（管理员模式）
cd "C:\Program Files\mosquitto"

# 启动mosquitto
mosquitto.exe -c mosquitto.conf -v
```

### 方法二：安装为Windows服务

```powershell
# 以管理员身份运行PowerShell
cd "C:\Program Files\mosquitto"

# 安装服务
mosquitto.exe install

# 启动服务
net start mosquitto

# 设置自动启动
sc config mosquitto start= auto
```

## 4. 验证MQTT服务

### 使用命令行工具测试

```powershell
# 订阅主题（新开一个命令行窗口）
mosquitto_sub.exe -h localhost -t "windfarm/+/+" -v

# 发布测试消息（再开一个命令行窗口）
mosquitto_pub.exe -h localhost -t "windfarm/test" -m "Hello MQTT"
```

### 防火墙设置

```powershell
# 添加防火墙规则允许1883端口
netsh advfirewall firewall add rule name="MQTT" dir=in action=allow protocol=TCP localport=1883

# 如果启用了WebSocket，也添加9001端口
netsh advfirewall firewall add rule name="MQTT WebSocket" dir=in action=allow protocol=TCP localport=9001
```

## 5. 常用MQTT主题结构

本项目使用的MQTT主题结构：

```
windfarm/                       # 根主题
├── farm_summary                # 风场汇总数据
├── turbine/01/                # 风机01数据
├── turbine/02/                # 风机02数据
└── ...
    └── turbine/20/            # 风机20数据
```

### 数据格式示例

**风场汇总数据** (`windfarm/farm_summary`)：
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

**单个风机数据** (`windfarm/turbine/01`)：
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

## 6. 故障排除

### 常见问题

1. **端口被占用**
   ```powershell
   # 检查端口占用
   netstat -an | findstr :1883
   
   # 找到并终止占用进程
   tasklist | findstr mosquitto
   taskkill /f /im mosquitto.exe
   ```

2. **权限问题**
   - 确保以管理员身份运行mosquitto
   - 检查mosquitto目录的写入权限

3. **配置文件问题**
   - 检查mosquitto.conf语法
   - 查看日志文件：`C:\Program Files\mosquitto\mosquitto.log`

### 有用的监控命令

```powershell
# 监控所有主题
mosquitto_sub.exe -h localhost -t "#" -v

# 只监控风机数据
mosquitto_sub.exe -h localhost -t "windfarm/turbine/+/+" -v

# 监控风场汇总
mosquitto_sub.exe -h localhost -t "windfarm/farm_summary" -v
```

## 7. 生产环境配置

### 安全配置（推荐）

在 `mosquitto.conf` 中添加：

```ini
# 启用用户认证
allow_anonymous false
password_file C:\Program Files\mosquitto\passwd

# 启用访问控制
acl_file C:\Program Files\mosquitto\acl.conf

# SSL配置（可选）
# cafile C:\Program Files\mosquitto\ca.crt
# certfile C:\Program Files\mosquitto\server.crt
# keyfile C:\Program Files\mosquitto\server.key
```

### 创建用户

```powershell
# 创建用户密码文件
cd "C:\Program Files\mosquitto"
mosquitto_passwd -c passwd windfarm_user

# 添加更多用户
mosquitto_passwd passwd admin_user
```

### 访问控制

创建 `acl.conf` 文件：

```ini
# 管理员用户全权限
user admin_user
topic readwrite #

# 风机用户只能发布数据
user windfarm_user
topic write windfarm/+/+
topic read windfarm/farm_summary
```

现在MQTT broker就配置完成了，可以接收风机模拟器的数据推送。 