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
import time
from datetime import datetime
import paho.mqtt.client as mqtt
# from windpowerlib.tools import power_curve_plot

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

def get_weather_data(filename="weather.csv", **kwargs):
    r"""
    Imports weather data from a file.

    The data include wind speed at two different heights in m/s, air
    temperature in two different heights in K, surface roughness length in m
    and air pressure in Pa. The height in m for which the data applies is
    specified in the second row.
    In case no weather data file exists, an example weather data file is
    automatically downloaded and stored in the same directory as this example.

    Parameters
    ----------
    filename : str
        Filename of the weather data file. Default: 'weather.csv'.

    Other Parameters
    ----------------
    datapath : str, optional
        Path where the weather data file is stored.
        Default is the same directory this example is stored in.

    Returns
    -------
    :pandas:`pandas.DataFrame<frame>`
        DataFrame with time series for wind speed `wind_speed` in m/s,
        temperature `temperature` in K, roughness length `roughness_length`
        in m, and pressure `pressure` in Pa.
        The columns of the DataFrame are a MultiIndex where the first level
        contains the variable name as string (e.g. 'wind_speed') and the
        second level contains the height as integer at which it applies
        (e.g. 10, if it was measured at a height of 10 m). The index is a
        DateTimeIndex.

    """

    if "datapath" not in kwargs:
        kwargs["datapath"] = os.path.dirname(__file__)

    file = os.path.join(kwargs["datapath"], filename)

    # download example weather data file in case it does not yet exist
    if not os.path.isfile(file):
        logging.debug("Download weather data for example.")
        req = requests.get("https://osf.io/59bqn/download")
        with open(file, "wb") as fout:
            fout.write(req.content)

    # read csv file
    weather_df = pd.read_csv(
        file,
        index_col=0,
        header=[0, 1],
    )
    weather_df.index = pd.to_datetime(weather_df.index, utc=True)

    # change time zone
    weather_df.index = weather_df.index.tz_convert("Europe/Berlin")

    return weather_df

def create_weather_data():
    """创建模拟的气象数据 - 使用当前时间"""
    from datetime import datetime, timedelta
    
    # 生成从当前时间开始的一周数据（168小时）
    start_time = datetime.now()
    index = pd.date_range(start=start_time, periods=168, freq='h', tz='Asia/Shanghai')
    
    # 生成风速数据（威布尔分布）
    shape = 2.0
    scale = 8.0
    wind_speeds = np.random.weibull(shape, 168) * scale
    
    # 生成温度数据（正弦波动）
    temperatures = 10 + 10 * np.sin(np.linspace(0, 2 * np.pi, 168)) + np.random.normal(0, 3, 168)
    
    # 生成气压数据（随温度变化）
    pressures = 101.3 - 0.01 * (temperatures - 15)
    
    # 创建DataFrame
    weather_df = pd.DataFrame(
        index=index,
        data={
            'wind_speed': wind_speeds,
            'temperature': temperatures,
            'pressure': pressures
        }
    )
    
    return weather_df

def update_weather_to_current_time(weather_df):
    """将历史天气数据的时间戳更新为当前时间"""
    from datetime import datetime, timedelta
    
    # 获取当前时间
    current_time = datetime.now()
    
    # 创建新的时间索引，保持原有的数据间隔
    time_delta = weather_df.index[1] - weather_df.index[0]
    new_index = pd.date_range(
        start=current_time, 
        periods=len(weather_df), 
        freq=time_delta,
        tz='Asia/Shanghai'
    )
    
    # 更新索引
    weather_df_updated = weather_df.copy()
    weather_df_updated.index = new_index
    
    return weather_df_updated

def get_turbine_parameters():
    """定义风机参数 - 使用windpowerlib中的已有风机"""
    # 使用windpowerlib数据库中的风机
    turbine_data = {
        'turbine_type': 'E-126/4200',  # 使用已有的风机型号
        'hub_height': 135,  # 轮毂高度(m)
    }
    return turbine_data

def simulate_turbine_performance():
    """使用windpowerlib模拟风机性能"""
    # 从CSV文件加载实际气象数据
    real_weather = get_weather_data()
    
    # 将天气数据时间更新为当前时间
    real_weather = update_weather_to_current_time(real_weather)
    
    # 获取风机参数
    turbine_params = get_turbine_parameters()
    
    # 创建风机对象
    turbine = WindTurbine(**turbine_params)
    
    # 创建模型链
    modelchain = ModelChain(turbine).run_model(real_weather)

    a = modelchain.density_model
    b = modelchain.power_output_model
    c = modelchain.density_correction
    d = modelchain.obstacle_height
    e = modelchain.hellman_exp
    f = modelchain.power_output
    
    # 正确访问多层索引的天气数据
    # 选择合适的高度层数据
    wind_speed_data = real_weather[('wind_speed', '80')]  # 80米高度的风速
    temperature_data = real_weather[('temperature', '10')]  # 10米高度的温度
    pressure_data = real_weather[('pressure', '0')]  # 地面气压
    
    # 创建包含所有结果的数据框
    df = pd.DataFrame({
        '时间': real_weather.index,
        '风速(m/s)': wind_speed_data,
        '温度(K)': temperature_data,
        '气压(Pa)': pressure_data,
        '发电量(kW)': modelchain.power_output / 1000,  # 转换为kW
    })
    
    # 温度转换为摄氏度
    df['温度(°C)'] = df['温度(K)'] - 273.15
    
    # 气压转换为kPa
    df['气压(kPa)'] = df['气压(Pa)'] / 1000
    
    # 估算转速 - windpowerlib不直接提供转速，我们可以基于物理关系估算
    df['转速(rpm)'] = df.apply(
        lambda row: estimate_rotation_speed(row['风速(m/s)'], turbine), axis=1
    )
    
    # 计算空气密度
    # 使用理想气体定律计算空气密度: ρ = p / (R * T)
    # 其中 R = 287.1 J/(kg·K) 是空气的特定气体常数
    df['空气密度(kg/m³)'] = df['气压(Pa)'] / (287.1 * df['温度(K)'])
    
    # 添加功率密度验证
    rotor_area = 12666  # E-126/4200的扫风面积 m²
    df['功率密度(W/m²)'] = df['发电量(kW)'] * 1000 / rotor_area
    
    return df, turbine

def estimate_rotation_speed(wind_speed, turbine):
    """估算风机转速 - 基于E-126/4200实际参数"""
    # E-126/4200的实际参数
    cut_in = 2.5  # 切入风速
    cut_out = 28.0  # 切出风速  
    nominal = 13.0  # 额定风速
    max_rpm = 11.6  # 最大转速（根据数据库）
    
    if wind_speed < cut_in or wind_speed > cut_out:
        return 0.0
    elif wind_speed < nominal:
        # 低于额定风速时，转速随风速非线性增加
        # 使用更真实的转速曲线
        return max_rpm * (wind_speed - cut_in) / (nominal - cut_in)
    else:
        # 达到或超过额定风速时，保持最大转速
        return max_rpm

def plot_results(df, turbine):
    """可视化模拟结果"""
    plt.figure(figsize=(15, 12))
    
    # 风速和发电量
    plt.subplot(3, 1, 1)
    plt.plot(df['时间'], df['风速(m/s)'], 'b-', label='风速 (m/s)')
    plt.ylabel('风速 (m/s)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='upper left')
    
    ax2 = plt.gca().twinx()
    ax2.plot(df['时间'], df['发电量(kW)'], 'r-', label='发电量 (kW)')
    ax2.set_ylabel('发电量 (kW)')
    plt.title('风速与发电量随时间变化')
    plt.legend(loc='upper right')
    
    # 温度和转速
    plt.subplot(3, 1, 2)
    plt.plot(df['时间'], df['温度(°C)'], 'g-', label='温度 (°C)')
    plt.ylabel('温度 (°C)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='upper left')
    
    ax2 = plt.gca().twinx()
    ax2.plot(df['时间'], df['转速(rpm)'], 'm-', label='转速 (rpm)')
    ax2.set_ylabel('转速 (rpm)')
    plt.title('温度与转速随时间变化')
    plt.legend(loc='upper right')
    
    # 气压和空气密度
    plt.subplot(3, 1, 3)
    plt.plot(df['时间'], df['气压(kPa)'], 'c-', label='气压 (kPa)')
    plt.ylabel('气压 (kPa)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='upper left')
    
    ax2 = plt.gca().twinx()
    ax2.plot(df['时间'], df['空气密度(kg/m³)'], 'orange', label='空气密度 (kg/m³)')
    ax2.set_ylabel('空气密度 (kg/m³)')
    plt.title('气压与空气密度随时间变化')
    plt.legend(loc='upper right')
    
    # 格式化x轴日期
    for ax in plt.gcf().axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    plt.savefig('wind_turbine_simulation.png', dpi=300)
    plt.show()

def print_statistics(df):
    """打印统计结果"""
    print("\n=== 风机性能统计 (E-126/4200) ===")
    print(f"时间范围: {df['时间'].min().strftime('%Y-%m-%d %H:%M')} 至 {df['时间'].max().strftime('%Y-%m-%d %H:%M')}")
    print(f"数据点数量: {len(df)} 个")
    print()
    
    print("📊 风速统计:")
    print(f"  平均风速: {df['风速(m/s)'].mean():.2f} m/s")
    print(f"  最大风速: {df['风速(m/s)'].max():.2f} m/s")
    print(f"  最小风速: {df['风速(m/s)'].min():.2f} m/s")
    print()
    
    print("⚡ 发电量统计:")
    print(f"  平均发电量: {df['发电量(kW)'].mean():.2f} kW")
    print(f"  最大发电量: {df['发电量(kW)'].max():.2f} kW")
    print(f"  最小发电量: {df['发电量(kW)'].min():.2f} kW")
    print(f"  总发电量: {df['发电量(kW)'].sum():.2f} kWh")
    print(f"  容量因子: {(df['发电量(kW)'].mean() / 4200) * 100:.2f}%")
    print()
    
    print("🌡️  环境参数:")
    print(f"  平均温度: {df['温度(°C)'].mean():.2f} °C")
    print(f"  平均气压: {df['气压(kPa)'].mean():.2f} kPa")
    print(f"  平均空气密度: {df['空气密度(kg/m³)'].mean():.4f} kg/m³")
    print()
    
    print("🔄 机械参数:")
    print(f"  平均转速: {df['转速(rpm)'].mean():.2f} rpm")
    print(f"  最大转速: {df['转速(rpm)'].max():.2f} rpm")
    print()
    
    print("📈 功率密度:")
    print(f"  平均功率密度: {df['功率密度(W/m²)'].mean():.1f} W/m²")
    print(f"  最大功率密度: {df['功率密度(W/m²)'].max():.1f} W/m²")
    print(f"  理论最大功率密度: 331 W/m² (E-126/4200规格)")
    
    # 检查异常值
    print("\n⚠️  数据合理性检查:")
    high_power_density = df[df['功率密度(W/m²)'] > 350]
    if len(high_power_density) > 0:
        print(f"  发现 {len(high_power_density)} 个功率密度异常值 (>350 W/m²)")
    
    low_rpm_high_power = df[(df['转速(rpm)'] < 5) & (df['发电量(kW)'] > 1000)]
    if len(low_rpm_high_power) > 0:
        print(f"  发现 {len(low_rpm_high_power)} 个转速异常值 (低转速高发电量)")
    
    if len(high_power_density) == 0 and len(low_rpm_high_power) == 0:
        print("  ✅ 所有数据均在合理范围内")

class MQTTPublisher:
    """MQTT数据发布器"""
    
    def __init__(self, broker_host='localhost', broker_port=1883, topic_prefix='windpower'):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client()
        self.connected = False
        
        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"✅ MQTT连接成功: {self.broker_host}:{self.broker_port}")
        else:
            self.connected = False
            print(f"❌ MQTT连接失败，错误码: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"🔌 MQTT连接断开，错误码: {rc}")
        
    def _on_publish(self, client, userdata, mid):
        # print(f"📤 数据发布成功，消息ID: {mid}")
        pass
        
    def connect(self):
        """连接到MQTT broker"""
        try:
            print(f"🔗 正在连接MQTT broker: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()  # 启动后台线程处理网络流量
            
            # 等待连接完成
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                print("❌ MQTT连接超时")
                return False
                
            return True
        except Exception as e:
            print(f"❌ MQTT连接出错: {e}")
            return False
            
    def disconnect(self):
        """断开MQTT连接"""
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()
            
    def publish_turbine_data(self, turbine_data, turbine_id='turbine_01'):
        """发布单个风机数据"""
        if not self.connected:
            print("⚠️ MQTT未连接，跳过数据发布")
            return False
            
        try:
            # 构建数据包
            message = {
                'turbine_id': turbine_id,
                'timestamp': turbine_data['时间'].strftime('%Y-%m-%d %H:%M:%S'),
                'wind_speed': float(turbine_data['风速(m/s)']),
                'temperature': float(turbine_data['温度(°C)']),
                'pressure': float(turbine_data['气压(kPa)']),
                'power_output': float(turbine_data['发电量(kW)']),
                'rotation_speed': float(turbine_data['转速(rpm)']),
                'air_density': float(turbine_data['空气密度(kg/m³)']),
                'power_density': float(turbine_data['功率密度(W/m²)']),
                'status': 'normal' if turbine_data['功率密度(W/m²)'] <= 350 else 'alert'
            }
            
            # 发布到主题
            topic = f"{self.topic_prefix}/{turbine_id}/data"
            payload = json.dumps(message, ensure_ascii=False)
            
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            else:
                print(f"❌ 数据发布失败，错误码: {result.rc}")
                return False
                
        except Exception as e:
            print(f"❌ 发布数据时出错: {e}")
            return False
            
    def publish_farm_summary(self, summary_data):
        """发布风电场汇总数据"""
        if not self.connected:
            return False
            
        try:
            topic = f"{self.topic_prefix}/farm/summary"
            payload = json.dumps(summary_data, ensure_ascii=False)
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"❌ 发布汇总数据时出错: {e}")
            return False

def simulate_realtime_data(df, interval=5, enable_mqtt=True, mqtt_config=None):
    """模拟实时数据输出，支持MQTT发布"""
    
    # 初始化MQTT发布器
    mqtt_publisher = None
    if enable_mqtt:
        if mqtt_config is None:
            mqtt_config = {
                'broker_host': 'localhost',
                'broker_port': 1883,
                'topic_prefix': 'windpower'
            }
        
        mqtt_publisher = MQTTPublisher(**mqtt_config)
        if not mqtt_publisher.connect():
            print("⚠️ MQTT连接失败，将仅在控制台显示数据")
            mqtt_publisher = None
    
    print("\n==== 实时风机数据模拟 (E-126/4200) ====")
    if mqtt_publisher:
        print(f"📡 MQTT发布已启用: {mqtt_config['broker_host']}:{mqtt_config['broker_port']}")
        print(f"📝 主题前缀: {mqtt_config['topic_prefix']}")
    print("按 Ctrl+C 停止模拟")
    print("=" * 70)
    
    published_count = 0
    
    try:
        for i, row in df.iterrows():
            current_time = row['时间'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"🕐 时间: {current_time}")
            print(f"🌬️  风速: {row['风速(m/s)']:.2f} m/s")
            print(f"🌡️  温度: {row['温度(°C)']:.2f} °C")
            print(f"📊 气压: {row['气压(kPa)']:.2f} kPa")
            print(f"⚡ 发电量: {row['发电量(kW)']:.2f} kW")
            print(f"🔄 转速: {row['转速(rpm)']:.2f} rpm")
            print(f"💨 空气密度: {row['空气密度(kg/m³)']:.4f} kg/m³")
            print(f"📈 功率密度: {row['功率密度(W/m²)']:.1f} W/m²")
            
            # 状态指示
            if row['功率密度(W/m²)'] > 350:
                print("⚠️  功率密度异常高")
            elif row['转速(rpm)'] < 5 and row['发电量(kW)'] > 1000:
                print("⚠️  转速异常低")
            else:
                print("✅ 运行正常")
            
            # MQTT数据发布
            if mqtt_publisher:
                success = mqtt_publisher.publish_turbine_data(row, 'turbine_01')
                if success:
                    published_count += 1
                    print(f"📤 MQTT发布成功 (第{published_count}条)")
                else:
                    print("❌ MQTT发布失败")
                    
            print("-" * 70)
            
            time.sleep(interval)  # 等待指定秒数
            
    except KeyboardInterrupt:
        print(f"\n实时模拟已停止，共发布了 {published_count} 条MQTT消息")
    finally:
        if mqtt_publisher:
            mqtt_publisher.disconnect()
            print("🔌 MQTT连接已关闭")

# 主程序
if __name__ == "__main__":
    # 运行模拟
    df, turbine = simulate_turbine_performance()
    
    # 显示前10行数据
    print("🔍 模拟数据预览:")
    print(df[['时间', '风速(m/s)', '温度(°C)', '发电量(kW)', '转速(rpm)', '功率密度(W/m²)']].head(10))
    
    # 打印统计信息
    print_statistics(df)
    
    # 保存结果到CSV
    df.to_csv('wind_turbine_simulation_results.csv', index=False)
    print("\n结果已保存到 wind_turbine_simulation_results.csv")
    
    # # 可视化结果（可选）
    # try:
    #     plot_results(df, turbine)
    # except Exception as e:
    #     print(f"绘图时出现错误: {e}")
    #     print("跳过绘图，继续运行...")
    
    # 询问是否运行实时模拟
    print("\n是否运行实时数据模拟？(y/n): ", end='')
    choice = input().lower()
    if choice == 'y':
        # 询问是否启用MQTT
        print("是否启用MQTT发布？(y/n): ", end='')
        mqtt_choice = input().lower()
        enable_mqtt = mqtt_choice == 'y'
        
        mqtt_config = None
        if enable_mqtt:
            print("请输入MQTT配置 (直接回车使用默认值):")
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
                    
            topic_prefix = input("主题前缀 [windpower]: ").strip()
            if not topic_prefix:
                topic_prefix = 'windpower'
                
            mqtt_config = {
                'broker_host': broker_host,
                'broker_port': broker_port,
                'topic_prefix': topic_prefix
            }
            
            print(f"\n📡 MQTT配置:")
            print(f"  Broker: {broker_host}:{broker_port}")
            print(f"  主题前缀: {topic_prefix}")
        
        # 使用前100个数据点进行实时模拟
        simulate_realtime_data(df.head(100), interval=2, enable_mqtt=enable_mqtt, mqtt_config=mqtt_config)