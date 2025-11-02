"""
实验 1：设计数据包格式与工具函数
学习目标
设计统一的数据包格式，为后续 GBN/SR 协议打下基础
实现数据包的打包/解包工具函数
建立统一的日志系统，便于后续实验调试

设计思路
为了后续实验的衔接，我们设计一个支持多种协议的数据包格式：
基础字段：类型、序列号、长度、载荷 - 支持单向 GBN
扩展字段：确认标志、时间戳 - 为双向传输和 SR 协议做准备
灵活性：同一格式支持数据包和 ACK 包
"""

import time
import struct
from dataclasses import dataclass
from typing import Optional

@dataclass
class Packet:
    """
    数据包格式
    """
    # 基础字段
    ptype: int          # 包类型: 0=数据, 1=ACK, 2=FIN, 3=START
    seq_num: int        # 序列号 (4字节)
    length: int         # 载荷长度 (2字节)
    payload: bytes      # 实际数据

    # 扩展字段
    ack_flag: bool = False      # 确认标志（双向传输）
    timestamp: float = 0.0      # 时间戳（性能分析）

    # 窗口相关（SR协议需要）
    window_size: int = 0        # 窗口大小

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

def make_packet(ptype: int, seq_num: int, payload: bytes = b'',
                ack_flag: bool = False, window_size: int = 0) -> bytes:
    """
    创建数据包字节流

    数据包格式:
    [类型(1B)][标志(1B)][序列号(4B)][长度(2B)][窗口(2B)][时间戳(8B)][载荷]

    总头部大小: 18字节
    """
    # 计算载荷长度
    payload_length = len(payload)

    # 打包标志位
    flags = 0
    if ack_flag:
        flags |= 0x01  # 第0位表示ACK

    # 使用struct打包固定字段
    header = struct.pack('!BBIHHd',
                         ptype,  # 1字节 - 包类型
                         flags,  # 1字节 - 标志位
                         seq_num,  # 4字节 - 序列号
                         payload_length,  # 2字节 - 载荷长度
                         window_size,  # 2字节 - 窗口大小
                         time.time())  # 8字节 - 时间戳

    return header + payload


def make_data_packet(seq_num: int, data: bytes, window_size: int = 0) -> bytes:
    """创建数据包"""
    return make_packet(ptype=0, seq_num=seq_num, payload=data,
                       ack_flag=False, window_size=window_size)


def make_ack_packet(seq_num: int, window_size: int = 0) -> bytes:
    """创建ACK包"""
    return make_packet(ptype=1, seq_num=seq_num, payload=b'',
                       ack_flag=True, window_size=window_size)


def make_fin_packet(seq_num: int) -> bytes:
    """创建结束包"""
    return make_packet(ptype=2, seq_num=seq_num, payload=b'FIN')


def parse_packet(data: bytes) -> Optional[Packet]:
    """
    解析接收到的数据包
    返回 Packet 对象，如果解析失败返回 None
    """
    try:
        # 检查最小长度
        if len(data) < 18:
            return None

        # 解析头部
        header = data[:18]
        ptype, flags, seq_num, length, window_size, timestamp = struct.unpack('!BBIHHd', header)

        # 解析载荷
        payload = data[18:18 + length] if length > 0 else b''

        # 解析标志位
        ack_flag = bool(flags & 0x01)

        return Packet(
            ptype=ptype,
            seq_num=seq_num,
            length=length,
            payload=payload,
            ack_flag=ack_flag,
            timestamp=timestamp,
            window_size=window_size
        )

    except Exception as e:
        print(f"数据包解析错误: {e}")
        return None


def is_ack_packet(packet: Packet) -> bool:
    """检查是否为ACK包"""
    return packet.ack_flag or packet.ptype == 1


def is_data_packet(packet: Packet) -> bool:
    """检查是否为数据包"""
    return packet.ptype == 0 and not packet.ack_flag


def is_fin_packet(packet: Packet) -> bool:
    """检查是否为结束包"""
    return packet.ptype == 2


def split_file_into_packets(filename: str, chunk_size: int = 1024) -> list:
    """
    将文件分割为多个数据包载荷
    为后续文件传输实验准备
    """
    packets_data = []

    try:
        with open(filename, 'rb') as f:
            chunk_index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                packets_data.append((chunk_index, chunk))
                chunk_index += 1

        print(f"文件 '{filename}' 分割为 {len(packets_data)} 个数据包")
        return packets_data

    except FileNotFoundError:
        print(f"文件未找到: {filename}")
        return []


def reassemble_file(packets: list, output_filename: str):
    """
    从数据包列表重组文件
    为后续文件传输实验准备
    """
    # 按序列号排序
    packets.sort(key=lambda x: x.seq_num if hasattr(x, 'seq_num') else x[0])

    try:
        with open(output_filename, 'wb') as f:
            for packet in packets:
                if hasattr(packet, 'payload'):
                    f.write(packet.payload)
                else:
                    f.write(packet[1])
        print(f"文件已重组为: {output_filename}")

    except Exception as e:
        print(f"文件重组错误: {e}")


class ProtocolLogger:
    """
    统一协议日志系统
    为后续实验提供一致的日志输出格式
    """

    def __init__(self, node_name="Node"):
        self.node_name = node_name

    def _get_current_time(self):
        """获取当前格式化的时间字符串"""
        return time.strftime("%H:%M:%S", time.localtime()) + f".{int(time.time() * 1000) % 1000:03d}"

    def log_event(self, event_type: str, seq: int = None, info: str = ""):
        """记录协议事件"""
        current_time = self._get_current_time()
        seq_info = f" seq={seq}" if seq is not None else ""
        print(f"[{self.node_name}] [{current_time}] {event_type:8}{seq_info} {info}")

    # 预定义常用日志类型
    def send_data(self, seq: int, length: int):
        self.log_event("SEND", seq, f"数据包 length={length}")

    def send_ack(self, seq: int):
        self.log_event("SEND_ACK", seq, "确认包")

    def recv_data(self, seq: int, length: int):
        self.log_event("RECV_DATA", seq, f"数据包 length={length}")

    def recv_ack(self, seq: int):
        self.log_event("RECV_ACK", seq, "确认包")

    def timeout(self, seq: int):
        self.log_event("TIMEOUT", seq, "超时")

    def retransmit(self, seq: int):
        self.log_event("RETRANS", seq, "重传")

    def window_update(self, base: int, next_seq: int, window_size: int):
        self.log_event("WINDOW", None, f"base={base} next={next_seq} size={window_size}")

    def corrupt_packet(self, seq: int = None):
        self.log_event("CORRUPT", seq, "数据包损坏")


def test_packet_functions():
    """测试数据包工具函数"""
    print("=" * 50)
    print("数据包工具函数测试")
    print("=" * 50)

    logger = ProtocolLogger("Test")

    # 测试1: 数据包创建与解析
    print("\n1. 数据包创建与解析测试")
    test_data = b"Hello, this is a test payload!"
    packet_bytes = make_data_packet(seq_num=5, data=test_data, window_size=4)
    packet = parse_packet(packet_bytes)

    assert packet is not None, "数据包解析失败"
    assert packet.seq_num == 5, f"序列号错误: {packet.seq_num}"
    assert packet.payload == test_data, "载荷不匹配"
    assert packet.window_size == 4, f"窗口大小错误: {packet.window_size}"
    assert is_data_packet(packet), "应该识别为数据包"
    print("✅ 数据包测试通过")

    # 测试2: ACK包测试
    print("\n2. ACK包测试")
    ack_bytes = make_ack_packet(seq_num=10, window_size=8)
    ack_packet = parse_packet(ack_bytes)

    assert ack_packet is not None, "ACK包解析失败"
    assert ack_packet.seq_num == 10, f"ACK序列号错误: {ack_packet.seq_num}"
    assert ack_packet.length == 0, "ACK包应该有0长度载荷"
    assert is_ack_packet(ack_packet), "应该识别为ACK包"
    print("✅ ACK包测试通过")

    # 测试3: 日志系统测试
    print("\n3. 日志系统测试")
    logger.send_data(seq=1, length=100)
    logger.recv_ack(seq=1)
    logger.timeout(seq=2)
    logger.retransmit(seq=2)
    logger.window_update(base=1, next_seq=5, window_size=4)
    print("✅ 日志系统测试通过")

    # 测试4: 文件分割测试（为后续实验准备）
    print("\n4. 文件处理工具测试")
    # 创建测试文件
    test_str = "这是一个测试文件内容，用于验证文件分割功能。" * 20
    test_content = test_str.encode('utf-8')
    with open("test_file.txt", "wb") as f:
        f.write(test_content)

    packets_data = split_file_into_packets("test_file.txt", chunk_size=50)
    assert len(packets_data) > 0, "文件分割失败"
    print(f"✅ 文件分割测试通过: 生成 {len(packets_data)} 个数据包")

    # 清理
    import os
    os.remove("test_file.txt")

    print("\n🎉 所有测试通过！工具函数准备就绪。")


def performance_test():
    """性能测试：验证数据包处理效率"""
    print("\n" + "=" * 50)
    print("性能测试")
    print("=" * 50)

    start_time = time.time()
    test_payload = b"x" * 1024  # 1KB 数据

    # 测试打包性能
    packets_created = 0
    for i in range(1000):
        make_data_packet(seq_num=i, data=test_payload)
        packets_created += 1

    pack_time = time.time() - start_time

    # 测试解析性能
    packet_bytes = make_data_packet(seq_num=1, data=test_payload)
    parse_start = time.time()

    packets_parsed = 0
    for i in range(1000):
        parse_packet(packet_bytes)
        packets_parsed += 1

    parse_time = time.time() - parse_start

    print(f"数据包创建: {packets_created} 个, 耗时: {pack_time:.3f}s")
    print(f"数据包解析: {packets_parsed} 个, 耗时: {parse_time:.3f}s")
    print(f"平均创建时间: {pack_time / packets_created * 1000:.3f}ms/包")
    print(f"平均解析时间: {parse_time / packets_parsed * 1000:.3f}ms/包")


if __name__ == "__main__":
    # 运行测试
    test_packet_functions()
    performance_test()