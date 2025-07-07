#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT风机数据订阅客户端
用于接收和显示风机模拟器通过MQTT发送的数据
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from typing import Dict, Any
import os
import csv
from collections import defaultdict, deque
import threading

class WindFarmMQTTSubscriber:
    """风机MQTT数据订阅客户端"""
    
    def __init__(self, broker_host='localhost', broker_port=1883, topic_prefix='windfarm'):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client()
        self.connected = False
        
        # 数据存储
        self.turbine_data = {}  # 存储最新的风机数据
        self.farm_summary = {}  # 存储最新的风场汇总数据
        self.message_count = defaultdict(int)  # 消息计数
        self.data_history = defaultdict(lambda: deque(maxlen=100))  # 历史数据（最近100条）
        
        # 统计信息
        self.start_time = datetime.now()
        self.total_messages = 0
        self.last_update_time = None
        
        # 数据保存配置
        self.save_to_file = False
        self.csv_file = None
        self.csv_writer = None
        
        # 线程锁
        self.data_lock = threading.Lock()
        
        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc):
        """连接回调"""
        if rc == 0:
            self.connected = True
            print(f"✅ MQTT连接成功: {self.broker_host}:{self.broker_port}")
            
            # 订阅所有相关主题
            topics = [
                f"{self.topic_prefix}/farm_summary",
                f"{self.topic_prefix}/turbine/+",
                f"{self.topic_prefix}/+/+",  # 备用通配符
            ]
            
            for topic in topics:
                client.subscribe(topic, qos=1)
                print(f"📡 订阅主题: {topic}")
                
        else:
            self.connected = False
            print(f"❌ MQTT连接失败，错误码: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        self.connected = False
        print(f"🔌 MQTT连接断开，错误码: {rc}")
        
    def _on_message(self, client, userdata, msg):
        """消息接收回调"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            
            with self.data_lock:
                self.total_messages += 1
                self.last_update_time = datetime.now()
                self.message_count[topic] += 1
                
                # 根据主题类型处理数据
                if topic.endswith('farm_summary'):
                    self._handle_farm_summary(data)
                elif '/turbine/' in topic:
                    self._handle_turbine_data(topic, data)
                else:
                    print(f"⚠️ 未知主题: {topic}")
                    
                # 保存到文件（如果启用）
                if self.save_to_file and self.csv_writer:
                    self._save_to_csv(topic, data)
                    
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
        except Exception as e:
            print(f"❌ 处理消息时出错: {e}")
            
    def _handle_farm_summary(self, data: Dict[str, Any]):
        """处理风场汇总数据"""
        self.farm_summary = data
        self.data_history['farm_summary'].append({
            'timestamp': self.last_update_time,
            'data': data.copy()
        })
        
        print(f"\n🌪️  风场汇总更新 - {data.get('timestamp', 'N/A')}")
        print(f"⚡ 总发电量: {data.get('totalPower', 0):.1f} kW")
        print(f"📊 效率: {data.get('efficiency', 0):.1f}%")
        
        if 'statistics' in data:
            stats = data['statistics']
            print(f"🔄 运行状态: {stats.get('runningTurbines', 0)}/{stats.get('runningTurbines', 0) + stats.get('maintenanceTurbines', 0) + stats.get('stoppedTurbines', 0)}")
            print(f"📈 容量因子: {stats.get('capacityFactor', 0):.1f}%")
            
    def _handle_turbine_data(self, topic: str, data: Dict[str, Any]):
        """处理单个风机数据"""
        turbine_id = data.get('id', 'unknown')
        self.turbine_data[turbine_id] = data
        self.data_history[f'turbine_{turbine_id}'].append({
            'timestamp': self.last_update_time,
            'data': data.copy()
        })
        
        # 简化显示（避免刷屏）
        if self.total_messages % 20 == 1:  # 每20条消息显示一次风机详情
            print(f"\n🔧 风机{turbine_id:02d} - {data.get('name', 'N/A')}")
            print(f"   状态: {data.get('status', 'unknown')} | 发电量: {data.get('power', 0):.1f}kW | 风速: {data.get('windSpeed', 0):.1f}m/s")
            
    def _save_to_csv(self, topic: str, data: Dict[str, Any]):
        """保存数据到CSV文件"""
        try:
            timestamp = datetime.now().isoformat()
            
            if '/farm_summary' in topic:
                row = [
                    timestamp, 'farm_summary', 
                    data.get('totalPower', 0),
                    data.get('efficiency', 0),
                    data.get('weather', {}).get('windSpeed', 0),
                    data.get('weather', {}).get('temperature', 0),
                    data.get('statistics', {}).get('runningTurbines', 0),
                    data.get('statistics', {}).get('capacityFactor', 0)
                ]
            elif '/turbine/' in topic:
                row = [
                    timestamp, f"turbine_{data.get('id', 0)}",
                    data.get('power', 0),
                    data.get('efficiency', 0),
                    data.get('windSpeed', 0),
                    data.get('temperature', 0),
                    data.get('status', 'unknown'),
                    data.get('rotationSpeed', 0)
                ]
            else:
                return
                
            self.csv_writer.writerow(row)
            
        except Exception as e:
            print(f"❌ 保存CSV时出错: {e}")
            
    def connect(self):
        """连接到MQTT broker"""
        try:
            print(f"🔗 正在连接MQTT broker: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # 等待连接完成
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            return self.connected
            
        except Exception as e:
            print(f"❌ MQTT连接出错: {e}")
            return False
            
    def disconnect(self):
        """断开MQTT连接"""
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()
            print("🔌 MQTT连接已关闭")
            
        # 关闭CSV文件
        if self.csv_file:
            self.csv_file.close()
            print(f"📁 CSV文件已保存")
            
    def enable_csv_logging(self, filename: str = None):
        """启用CSV数据记录"""
        if filename is None:
            filename = f"windfarm_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        try:
            self.csv_file = open(filename, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            
            # 写入表头
            headers = [
                'timestamp', 'type', 'power', 'efficiency', 
                'wind_speed', 'temperature', 'status_or_running', 'rotation_or_capacity'
            ]
            self.csv_writer.writerow(headers)
            
            self.save_to_file = True
            print(f"📁 CSV记录已启用: {filename}")
            
        except Exception as e:
            print(f"❌ 启用CSV记录失败: {e}")
            
    def print_statistics(self):
        """打印统计信息"""
        with self.data_lock:
            running_time = (datetime.now() - self.start_time).total_seconds()
            
            print(f"\n" + "="*60)
            print(f"📊 MQTT订阅统计")
            print(f"="*60)
            print(f"📡 运行时间: {running_time:.1f} 秒")
            print(f"📨 总消息数: {self.total_messages}")
            print(f"📈 消息频率: {self.total_messages/running_time:.2f} 消息/秒")
            print(f"🕐 最后更新: {self.last_update_time.strftime('%H:%M:%S') if self.last_update_time else 'N/A'}")
            
            print(f"\n📝 主题消息统计:")
            for topic, count in self.message_count.items():
                print(f"  {topic}: {count} 条")
                
            print(f"\n🔧 当前风机状态:")
            if self.turbine_data:
                running = sum(1 for t in self.turbine_data.values() if t.get('status') == 'running')
                maintenance = sum(1 for t in self.turbine_data.values() if t.get('status') == 'maintenance')
                stopped = sum(1 for t in self.turbine_data.values() if t.get('status') == 'stopped')
                total_power = sum(t.get('power', 0) for t in self.turbine_data.values())
                
                print(f"  运行中: {running} 台")
                print(f"  维护中: {maintenance} 台")
                print(f"  停机: {stopped} 台")
                print(f"  总发电量: {total_power:.1f} kW")
                
            print(f"="*60)
            
    def run_interactive_mode(self):
        """运行交互模式"""
        print(f"\n🎛️  进入交互模式")
        print(f"命令列表:")
        print(f"  stats  - 显示统计信息")
        print(f"  farm   - 显示风场汇总")
        print(f"  list   - 列出所有风机")
        print(f"  turbine <id> - 显示指定风机详情")
        print(f"  csv    - 启用CSV记录")
        print(f"  quit   - 退出程序")
        print(f"" + "-"*50)
        
        while self.connected:
            try:
                command = input("MQTT订阅器> ").strip().lower()
                
                if command == 'quit' or command == 'exit':
                    break
                elif command == 'stats':
                    self.print_statistics()
                elif command == 'farm':
                    self._show_farm_summary()
                elif command == 'list':
                    self._list_turbines()
                elif command.startswith('turbine '):
                    try:
                        turbine_id = int(command.split()[1])
                        self._show_turbine_details(turbine_id)
                    except (IndexError, ValueError):
                        print("❌ 请提供正确的风机ID，例如: turbine 1")
                elif command == 'csv':
                    if not self.save_to_file:
                        self.enable_csv_logging()
                    else:
                        print("CSV记录已启用")
                elif command == 'help':
                    print("命令: stats, farm, list, turbine <id>, csv, quit")
                else:
                    print("❌ 未知命令，输入 'help' 查看可用命令")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ 命令执行出错: {e}")
                
    def _show_farm_summary(self):
        """显示风场汇总信息"""
        with self.data_lock:
            if not self.farm_summary:
                print("⚠️ 暂无风场汇总数据")
                return
                
            data = self.farm_summary
            print(f"\n🌪️  风场汇总信息")
            print(f"📅 时间: {data.get('timestamp', 'N/A')}")
            print(f"⚡ 总发电量: {data.get('totalPower', 0):.2f} kW")
            print(f"📊 效率: {data.get('efficiency', 0):.1f}%")
            
            weather = data.get('weather', {})
            print(f"\n🌤️  天气信息:")
            print(f"  风速: {weather.get('windSpeed', 0):.1f} m/s")
            print(f"  温度: {weather.get('temperature', 0):.1f} °C")
            print(f"  湿度: {weather.get('humidity', 0):.1f} %")
            print(f"  气压: {weather.get('pressure', 0):.1f} hPa")
            
            stats = data.get('statistics', {})
            print(f"\n📈 运行统计:")
            print(f"  运行中: {stats.get('runningTurbines', 0)} 台")
            print(f"  维护中: {stats.get('maintenanceTurbines', 0)} 台")
            print(f"  停机: {stats.get('stoppedTurbines', 0)} 台")
            print(f"  累计发电: {stats.get('totalGeneration', 0):.1f} kWh")
            print(f"  容量因子: {stats.get('capacityFactor', 0):.1f}%")
            
    def _list_turbines(self):
        """列出所有风机"""
        with self.data_lock:
            if not self.turbine_data:
                print("⚠️ 暂无风机数据")
                return
                
            print(f"\n🔧 风机列表 (共{len(self.turbine_data)}台):")
            print(f"{'ID':<4} {'名称':<8} {'状态':<10} {'发电量(kW)':<12} {'风速(m/s)':<10} {'效率(%)':<8}")
            print(f"-" * 60)
            
            for turbine_id in sorted(self.turbine_data.keys()):
                data = self.turbine_data[turbine_id]
                print(f"{data.get('id', 0):<4} {data.get('name', 'N/A'):<8} {data.get('status', 'unknown'):<10} "
                      f"{data.get('power', 0):<12.1f} {data.get('windSpeed', 0):<10.1f} {data.get('efficiency', 0):<8.1f}")
                      
    def _show_turbine_details(self, turbine_id: int):
        """显示指定风机详情"""
        with self.data_lock:
            if turbine_id not in self.turbine_data:
                print(f"❌ 风机{turbine_id}数据不存在")
                return
                
            data = self.turbine_data[turbine_id]
            print(f"\n🔧 风机{turbine_id:02d}详细信息")
            print(f"📋 基本信息:")
            print(f"  名称: {data.get('name', 'N/A')}")
            print(f"  状态: {data.get('status', 'unknown')}")
            print(f"  位置: X={data.get('position', {}).get('x', 0)}m, Y={data.get('position', {}).get('y', 0)}m")
            
            print(f"\n⚡ 发电信息:")
            print(f"  当前发电量: {data.get('power', 0):.2f} kW")
            print(f"  累计发电量: {data.get('totalGeneration', 0):.2f} kWh")
            print(f"  效率: {data.get('efficiency', 0):.1f}%")
            print(f"  功率密度: {data.get('powerDensity', 0):.1f} W/m²")
            
            print(f"\n🌬️  环境参数:")
            print(f"  风速: {data.get('windSpeed', 0):.1f} m/s")
            print(f"  温度: {data.get('temperature', 0):.1f} °C")
            print(f"  气压: {data.get('pressure', 0):.1f} kPa")
            print(f"  空气密度: {data.get('airDensity', 0):.4f} kg/m³")
            
            print(f"\n🔄 机械参数:")
            print(f"  转速: {data.get('rotationSpeed', 0):.1f} rpm")
            print(f"  最后维护: {data.get('lastMaintenance', 'N/A')}")

def main():
    """主程序"""
    print("🌪️  风机MQTT数据订阅客户端")
    print("=" * 50)
    
    # 获取连接配置
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
        
    # 询问是否启用CSV记录
    csv_choice = input("是否启用CSV数据记录？(y/n) [n]: ").strip().lower()
    enable_csv = csv_choice == 'y'
    
    print(f"\n📡 连接配置:")
    print(f"  Broker: {broker_host}:{broker_port}")
    print(f"  主题前缀: {topic_prefix}")
    print(f"  CSV记录: {'启用' if enable_csv else '禁用'}")
    
    # 创建订阅客户端
    subscriber = WindFarmMQTTSubscriber(broker_host, broker_port, topic_prefix)
    
    # 启用CSV记录
    if enable_csv:
        subscriber.enable_csv_logging()
    
    try:
        # 连接MQTT broker
        if subscriber.connect():
            print(f"\n✅ 开始接收数据...")
            print(f"提示: 按 Ctrl+C 进入交互模式")
            
            # 等待数据或用户中断
            try:
                time.sleep(5)  # 等待一些初始数据
                subscriber.run_interactive_mode()
            except KeyboardInterrupt:
                subscriber.run_interactive_mode()
                
        else:
            print(f"❌ 无法连接到MQTT broker")
            
    except KeyboardInterrupt:
        print(f"\n程序被用户中断")
    finally:
        subscriber.disconnect()
        print(f"🔌 程序已退出")

if __name__ == "__main__":
    main() 