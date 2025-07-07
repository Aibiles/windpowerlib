import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from windpowerlib import WindTurbine, ModelChain
from windpowerlib import data as wt_data
import os
import requests
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import paho.mqtt.client as mqtt

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class WindTurbineData:
    """单个风机数据类"""
    def __init__(self, turbine_id: int, name: str, x_pos: float, y_pos: float):
        self.id = turbine_id
        self.name = name
        self.x_position = x_pos  # 风机在风场中的X坐标(米)
        self.y_position = y_pos  # 风机在风场中的Y坐标(米)
        self.status = 'running'  # running, maintenance, stopped
        self.power = 0.0  # 当前发电量(kW)
        self.total_generation = 0.0  # 累计发电量(kWh)
        self.wind_speed = 0.0  # 当前风速(m/s)
        self.rotation_speed = 0.0  # 转速(rpm)
        self.temperature = 0.0  # 温度(°C)
        self.pressure = 0.0  # 气压(kPa)
        self.air_density = 0.0  # 空气密度(kg/m³)
        self.power_density = 0.0  # 功率密度(W/m²)
        self.last_maintenance = datetime.now() - timedelta(days=np.random.randint(1, 30))
        self.efficiency = 0.0  # 当前效率(%)
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'power': round(self.power, 2),
            'totalGeneration': round(self.total_generation, 2),
            'windSpeed': round(self.wind_speed, 2),
            'rotationSpeed': round(self.rotation_speed, 2),
            'temperature': round(self.temperature, 2),
            'pressure': round(self.pressure, 2),
            'airDensity': round(self.air_density, 4),
            'powerDensity': round(self.power_density, 1),
            'lastMaintenance': self.last_maintenance.strftime('%Y-%m-%d %H:%M:%S'),
            'efficiency': round(self.efficiency, 1),
            'position': {'x': self.x_position, 'y': self.y_position},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

class WindFarmClusterSimulator:
    """风机集群模拟器"""
    
    def __init__(self, turbine_count: int = 20, enable_mqtt: bool = False, mqtt_config: Dict = None):
        self.turbine_count = turbine_count
        self.turbines: List[WindTurbineData] = []
        self.weather_data = None
        self.current_index = 0
        self.turbine_model = None
        self.rotor_area = 12666  # E-126/4200的扫风面积 m²
        
        # MQTT配置
        self.enable_mqtt = enable_mqtt
        self.mqtt_client = None
        self.mqtt_connected = False
        self.mqtt_config = mqtt_config or {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'topic_prefix': 'windfarm'
        }
        
        # 初始化风机布局
        self._initialize_turbines()
        
        # 加载天气数据
        self._load_weather_data()
        
        # 创建风机模型
        self._create_turbine_model()
        
        # 初始化MQTT连接
        if self.enable_mqtt:
            self._initialize_mqtt()
        
    def _initialize_turbines(self):
        """初始化风机布局 - 5x4网格排列"""
        rows = 4
        cols = 5
        spacing_x = 500  # 风机间距500米
        spacing_y = 600  # 风机间距600米
        
        turbine_id = 1
        for row in range(rows):
            for col in range(cols):
                x_pos = col * spacing_x
                y_pos = row * spacing_y
                name = f"WT-{turbine_id:02d}"
                
                turbine = WindTurbineData(turbine_id, name, x_pos, y_pos)
                
                # 随机设置一些风机状态
                if np.random.random() < 0.05:  # 5%概率维护状态
                    turbine.status = 'maintenance'
                elif np.random.random() < 0.02:  # 2%概率停机状态
                    turbine.status = 'stopped'
                    
                self.turbines.append(turbine)
                turbine_id += 1
                
    def _load_weather_data(self):
        """加载并更新天气数据时间戳"""
        # 使用现有的天气数据加载函数
        weather_df = self.get_weather_data()
        
        # 将天气数据时间更新为当前时间
        weather_df_updated = self.update_weather_to_current_time(weather_df)
        
        self.weather_data = weather_df_updated
        
    def get_weather_data(self, filename="weather.csv", **kwargs):
        """导入天气数据"""
        if "datapath" not in kwargs:
            kwargs["datapath"] = os.path.dirname(__file__)

        file = os.path.join(kwargs["datapath"], filename)

        # 如果文件不存在，下载示例天气数据
        if not os.path.isfile(file):
            logging.debug("Download weather data for example.")
            req = requests.get("https://osf.io/59bqn/download")
            with open(file, "wb") as fout:
                fout.write(req.content)

        # 读取CSV文件
        weather_df = pd.read_csv(file, index_col=0, header=[0, 1])
        weather_df.index = pd.to_datetime(weather_df.index, utc=True)
        weather_df.index = weather_df.index.tz_convert("Europe/Berlin")

        return weather_df
        
    def update_weather_to_current_time(self, weather_df):
        """将历史天气数据的时间戳更新为当前时间"""
        current_time = datetime.now()
        
        # 创建新的时间索引，从当前时间开始
        time_delta = weather_df.index[1] - weather_df.index[0]
        new_index = pd.date_range(
            start=current_time, 
            periods=len(weather_df), 
            freq=time_delta,
            tz='Asia/Shanghai'
        )
        
        weather_df_updated = weather_df.copy()
        weather_df_updated.index = new_index
        
        return weather_df_updated
        
    def get_current_time_data(self):
        """获取当前时间对应的天气数据"""
        if self.current_index >= len(self.weather_data):
            self.current_index = 0  # 循环使用数据
            
        # 更新当前时间到天气数据
        current_time = datetime.now()
        self.weather_data.index = pd.date_range(
            start=current_time,
            periods=len(self.weather_data),
            freq=self.weather_data.index[1] - self.weather_data.index[0],
            tz='Asia/Shanghai'
        )
        
        return self.weather_data.iloc[self.current_index]
        
    def _create_turbine_model(self):
        """创建风机模型"""
        turbine_params = {
            'turbine_type': 'E-126/4200',
            'hub_height': 135,
        }
        self.turbine_model = WindTurbine(**turbine_params)
        
    def _initialize_mqtt(self):
        """初始化MQTT连接"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_publish = self._on_mqtt_publish
            
            print(f"🔗 正在连接MQTT broker: {self.mqtt_config['broker_host']}:{self.mqtt_config['broker_port']}")
            self.mqtt_client.connect(
                self.mqtt_config['broker_host'], 
                self.mqtt_config['broker_port'], 
                60
            )
            self.mqtt_client.loop_start()
            
            # 等待连接完成
            timeout = 10
            start_time = time.time()
            while not self.mqtt_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if not self.mqtt_connected:
                print("❌ MQTT连接超时")
                self.enable_mqtt = False
            
        except Exception as e:
            print(f"❌ MQTT初始化失败: {e}")
            self.enable_mqtt = False
            
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            self.mqtt_connected = True
            print(f"✅ MQTT连接成功: {self.mqtt_config['broker_host']}:{self.mqtt_config['broker_port']}")
            print(f"📝 主题前缀: {self.mqtt_config['topic_prefix']}")
        else:
            self.mqtt_connected = False
            print(f"❌ MQTT连接失败，错误码: {rc}")
            
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        self.mqtt_connected = False
        print(f"🔌 MQTT连接断开，错误码: {rc}")
        
    def _on_mqtt_publish(self, client, userdata, mid):
        """MQTT发布回调"""
        pass  # 静默处理，避免输出太多信息
        
    def _publish_mqtt_data(self, data_type: str, data: Dict):
        """发布MQTT数据"""
        if not self.enable_mqtt or not self.mqtt_connected:
            return False
            
        try:
            topic = f"{self.mqtt_config['topic_prefix']}/{data_type}"
            payload = json.dumps(data, ensure_ascii=False, default=str)
            result = self.mqtt_client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"❌ MQTT发布失败: {e}")
            return False
            
    def _publish_turbine_data(self, turbine: WindTurbineData):
        """发布单个风机数据"""
        turbine_data = turbine.to_dict()
        topic_suffix = f"turbine/{turbine.id:02d}"
        return self._publish_mqtt_data(topic_suffix, turbine_data)
        
    def _publish_farm_summary(self, farm_data: Dict):
        """发布风场汇总数据"""
        return self._publish_mqtt_data("farm_summary", farm_data)
        
    def disconnect_mqtt(self):
        """断开MQTT连接"""
        if self.mqtt_client and self.mqtt_connected:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("🔌 MQTT连接已关闭")
        
    def _calculate_local_wind_speed(self, turbine: WindTurbineData, base_wind_speed: float) -> float:
        """计算局部风速 - 考虑尾流效应和地形影响"""
        # 基础风速
        local_wind_speed = base_wind_speed
        
        # 添加随机变化 (±10%)
        variation = np.random.normal(0, 0.1)
        local_wind_speed *= (1 + variation)
        
        # 简化的尾流效应计算
        # 检查上风向是否有其他风机
        for other_turbine in self.turbines:
            if other_turbine.id != turbine.id and other_turbine.status == 'running':
                # 计算距离
                dx = turbine.x_position - other_turbine.x_position
                dy = turbine.y_position - other_turbine.y_position
                distance = np.sqrt(dx**2 + dy**2)
                
                # 简化的尾流衰减模型
                if distance < 1000 and dx > 0:  # 下风向1km内
                    wake_effect = max(0, 0.3 * np.exp(-distance/300))
                    local_wind_speed *= (1 - wake_effect)
                    
        return max(0, local_wind_speed)
        
    def _estimate_rotation_speed(self, wind_speed: float) -> float:
        """估算风机转速"""
        cut_in = 2.5
        cut_out = 28.0
        nominal = 13.0
        max_rpm = 11.6
        
        if wind_speed < cut_in or wind_speed > cut_out:
            return 0.0
        elif wind_speed < nominal:
            return max_rpm * (wind_speed - cut_in) / (nominal - cut_in)
        else:
            return max_rpm
            
    def _calculate_turbine_efficiency(self, turbine: WindTurbineData) -> float:
        """计算风机效率"""
        if turbine.status != 'running' or turbine.wind_speed < 2.5:
            return 0.0
            
        # 基于风速的效率曲线
        if turbine.wind_speed < 5:
            efficiency = 20 + turbine.wind_speed * 10
        elif turbine.wind_speed < 12:
            efficiency = 90 + (turbine.wind_speed - 5) * 2
        elif turbine.wind_speed < 25:
            efficiency = 95 - (turbine.wind_speed - 12) * 1
        else:
            efficiency = 0
            
        # 考虑设备状态影响
        if turbine.status == 'maintenance':
            efficiency = 0
        elif turbine.status == 'stopped':
            efficiency = 0
            
        return min(100, max(0, efficiency))
        
    def update_simulation(self):
        """更新模拟数据"""
        # 获取当前时间点的天气数据（使用真实时间）
        current_weather = self.get_current_time_data()
        
        # 提取天气参数
        base_wind_speed = current_weather[('wind_speed', '80')]
        temperature_k = current_weather[('temperature', '10')]
        pressure_pa = current_weather[('pressure', '0')]
        
        # 单位转换
        temperature_c = temperature_k - 273.15
        pressure_kpa = pressure_pa / 1000
        
        # 计算空气密度
        air_density = pressure_pa / (287.1 * temperature_k)
        
        # 使用windpowerlib计算基准发电量
        try:
            # 创建临时天气数据框用于modelchain
            temp_weather = pd.DataFrame(
                index=[current_weather.name],
                data={
                    ('wind_speed', '80'): [base_wind_speed],
                    ('temperature', '10'): [temperature_k],
                    ('pressure', '0'): [pressure_pa],
                    ('roughness_length', '0'): [0.15]
                }
            )
            temp_weather.columns = pd.MultiIndex.from_tuples(temp_weather.columns)
            
            modelchain = ModelChain(self.turbine_model).run_model(temp_weather)
            base_power_kw = modelchain.power_output.iloc[0] / 1000
        except:
            # 如果windpowerlib计算失败，使用简化模型
            base_power_kw = self._simplified_power_calculation(base_wind_speed)
            
        # 更新每个风机的数据
        for turbine in self.turbines:
            # 更新状态（随机状态变化）
            self._update_turbine_status(turbine)
            
            # 计算局部风速
            local_wind_speed = self._calculate_local_wind_speed(turbine, base_wind_speed)
            
            # 更新风机参数
            turbine.wind_speed = local_wind_speed
            turbine.temperature = temperature_c + np.random.normal(0, 2)
            turbine.pressure = pressure_kpa
            turbine.air_density = air_density
            
            if turbine.status == 'running':
                # 计算发电量（基于局部风速调整）
                wind_ratio = local_wind_speed / base_wind_speed if base_wind_speed > 0 else 0
                turbine.power = base_power_kw * wind_ratio * np.random.uniform(0.9, 1.1)
                turbine.power = max(0, min(4200, turbine.power))  # 限制在0-4200kW范围
                
                # 计算转速
                turbine.rotation_speed = self._estimate_rotation_speed(local_wind_speed)
                
                # 累计发电量
                turbine.total_generation += turbine.power / 60  # 假设每分钟更新一次
                
            else:
                turbine.power = 0
                turbine.rotation_speed = 0
                
            # 计算功率密度
            turbine.power_density = (turbine.power * 1000) / self.rotor_area
            
            # 计算效率
            turbine.efficiency = self._calculate_turbine_efficiency(turbine)
            
        self.current_index += 1
        
    def _simplified_power_calculation(self, wind_speed: float) -> float:
        """简化的功率计算模型"""
        if wind_speed < 2.5:
            return 0
        elif wind_speed > 28:
            return 0
        elif wind_speed < 13:
            # 三次方关系
            return 4200 * ((wind_speed - 2.5) / (13 - 2.5)) ** 3
        else:
            return 4200
            
    def _update_turbine_status(self, turbine: WindTurbineData):
        """更新风机状态"""
        # 随机状态变化
        if turbine.status == 'running':
            if np.random.random() < 0.001:  # 0.1%概率进入维护
                turbine.status = 'maintenance'
            elif np.random.random() < 0.0005:  # 0.05%概率停机
                turbine.status = 'stopped'
        elif turbine.status == 'maintenance':
            if np.random.random() < 0.01:  # 1%概率恢复运行
                turbine.status = 'running'
                turbine.last_maintenance = datetime.now()
        elif turbine.status == 'stopped':
            if np.random.random() < 0.005:  # 0.5%概率恢复运行
                turbine.status = 'running'
                
    def get_farm_data(self) -> Dict[str, Any]:
        """获取风场数据"""
        total_power = sum(t.power for t in self.turbines)
        running_turbines = sum(1 for t in self.turbines if t.status == 'running')
        
        # 计算风场效率
        if running_turbines > 0:
            avg_efficiency = sum(t.efficiency for t in self.turbines if t.status == 'running') / running_turbines
        else:
            avg_efficiency = 0
            
        # 获取平均天气数据
        avg_wind_speed = np.mean([t.wind_speed for t in self.turbines])
        avg_temperature = np.mean([t.temperature for t in self.turbines])
        avg_pressure = np.mean([t.pressure for t in self.turbines])
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'totalPower': round(total_power, 2),
            'efficiency': round(avg_efficiency, 1),
            'weather': {
                'windSpeed': round(avg_wind_speed, 2),
                'windDirection': 180 + np.random.normal(0, 30),  # 随机风向
                'temperature': round(avg_temperature, 1),
                'humidity': 60 + np.random.normal(0, 10),
                'pressure': round(avg_pressure * 10, 1),  # 转换为hPa
            },
            'turbines': [t.to_dict() for t in self.turbines],
            'statistics': {
                'runningTurbines': running_turbines,
                'maintenanceTurbines': sum(1 for t in self.turbines if t.status == 'maintenance'),
                'stoppedTurbines': sum(1 for t in self.turbines if t.status == 'stopped'),
                'totalGeneration': round(sum(t.total_generation for t in self.turbines), 2),
                'averagePowerDensity': round(np.mean([t.power_density for t in self.turbines]), 1),
                'capacityFactor': round((total_power / (self.turbine_count * 4200)) * 100, 1)
            }
        }
        
    def run_continuous_simulation(self, update_interval: float = 5.0):
        """运行连续模拟"""
        print(f"🌪️  启动风机集群模拟器 - {self.turbine_count}个风机")
        if self.enable_mqtt:
            print(f"📡 MQTT发布已启用")
        print("按 Ctrl+C 停止模拟")
        print("=" * 80)
        
        published_turbines = 0
        published_summaries = 0
        
        try:
            while True:
                self.update_simulation()
                farm_data = self.get_farm_data()
                
                # 显示实时数据
                print(f"🕐 时间: {farm_data['timestamp'][:19]}")
                print(f"⚡ 总发电量: {farm_data['totalPower']:.1f} kW")
                print(f"📊 风场效率: {farm_data['efficiency']:.1f}%")
                print(f"🌬️  平均风速: {farm_data['weather']['windSpeed']:.1f} m/s")
                print(f"🔄 运行中风机: {farm_data['statistics']['runningTurbines']}/{self.turbine_count}")
                print(f"📈 容量因子: {farm_data['statistics']['capacityFactor']:.1f}%")
                
                # MQTT数据发布
                if self.enable_mqtt and self.mqtt_connected:
                    # 发布风场汇总数据
                    if self._publish_farm_summary(farm_data):
                        published_summaries += 1
                        
                    # 发布每个风机数据
                    successful_turbines = 0
                    for turbine in self.turbines:
                        if self._publish_turbine_data(turbine):
                            successful_turbines += 1
                            
                    published_turbines += successful_turbines
                    print(f"📤 MQTT发布: 风场汇总 {published_summaries} 条, 风机数据 {published_turbines} 条")
                elif self.enable_mqtt:
                    print("⚠️ MQTT未连接，跳过数据发布")
                    
                print("-" * 80)
                
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            print(f"\n模拟已停止")
            if self.enable_mqtt:
                print(f"📊 总计发布: 风场汇总 {published_summaries} 条, 风机数据 {published_turbines} 条")
        finally:
            if self.enable_mqtt:
                self.disconnect_mqtt()

# 主程序
if __name__ == "__main__":
    print("🌪️  风机集群模拟器配置")
    print("=" * 50)
    
    # 询问是否启用MQTT
    print("是否启用MQTT发布？(y/n): ", end='')
    mqtt_choice = input().lower()
    enable_mqtt = mqtt_choice == 'y'
    
    mqtt_config = None
    if enable_mqtt:
        print("\n请输入MQTT配置 (直接回车使用默认值):")
        broker_host = input("MQTT Broker地址 [localhost]: ").strip()
        if not broker_host:
            broker_host = 'localhost'
            
        broker_port_str = input("MQTT Broker端口 [1883]: ").strip()
        if not broker_port_str:
            broker_port = 1883
        else:
            try:
                broker_port = int(broker_port_str)
            except ValueError:
                broker_port = 1883
                
        topic_prefix = input("主题前缀 [windfarm]: ").strip()
        if not topic_prefix:
            topic_prefix = 'windfarm'
            
        mqtt_config = {
            'broker_host': broker_host,
            'broker_port': broker_port,
            'topic_prefix': topic_prefix
        }
        
        print(f"\n📡 MQTT配置:")
        print(f"  Broker: {broker_host}:{broker_port}")
        print(f"  主题前缀: {topic_prefix}")
        
        # 询问更新间隔
        interval_str = input("\n数据更新间隔(秒) [3.0]: ").strip()
        if not interval_str:
            update_interval = 3.0
        else:
            try:
                update_interval = float(interval_str)
            except ValueError:
                update_interval = 3.0
    else:
        update_interval = 3.0
    
    print("\n" + "=" * 50)
    
    # 创建20个风机的模拟器
    simulator = WindFarmClusterSimulator(
        turbine_count=20, 
        enable_mqtt=enable_mqtt, 
        mqtt_config=mqtt_config
    )
    
    # 运行连续模拟
    simulator.run_continuous_simulation(update_interval=update_interval) 