"""
实验 3：实现单向 GBN（Go-Back-N）协议（单文件版）

学习目标
实现单文件版本的 GBN 协议，通过命令行参数控制角色
改进日志系统，使用当前时间戳
理解滑动窗口协议和累计确认机制

python ps3_GBN sender
"""

import socket
import time
import random
import threading
from ps1_utils import make_data_packet, make_ack_packet, parse_packet, ProtocolLogger

random.seed(39)

class GBNSender:
    def __init__(self, host, port, target_host, target_port,
                 window_size=4, timeout=2.0, loss_prob=0.2):
        self.host = host
        self.port = port
        self.target_host = target_host
        self.target_port = target_port
        self.window_size = window_size
        self.timeout = timeout
        self.loss_prob = loss_prob

        # GBN 协议状态变量
        self.base = 0  # 窗口起始序列号
        self.next_seq = 0  # 下一个要发送的序列号
        self.expected_ack = 0  # 期望的ACK号

        # 数据存储
        self.packets = []  # 所有数据包
        self.ack_received = []  # ACK接收状态
        self.timers = []  # 每个包的发送时间

        # 网络和日志
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.1)  # 短超时用于非阻塞检查

        self.logger = ProtocolLogger("GBN-Send")
        self.is_running = True
        self.ack_thread = None

        self.stats = {
            'total_sent': 0,
            'total_retrans': 0,
            'timeout_count': 0
        }

    def send_data(self, data_list):
        """发送数据包列表"""
        self.packets = data_list
        self.ack_received = [False] * len(data_list)
        self.timers = [0] * len(data_list)

        self.logger.log_event("START", None,
                              f"开始传输 {len(data_list)} 个数据包, 窗口大小={self.window_size}")

        # 启动ACK接收线程
        self.ack_thread = threading.Thread(target=self._receive_acks)
        self.ack_thread.daemon = True
        self.ack_thread.start()

        # 主发送循环
        while self.base < len(self.packets) and self.is_running:
            # 发送窗口内的数据包
            while self.next_seq < self.base + self.window_size and self.next_seq < len(self.packets):
                if not self.ack_received[self.next_seq]:
                    self._send_packet(self.next_seq)
                self.next_seq += 1

            # 检查超时
            self._check_timeouts()

            # 短暂休眠避免CPU占用过高
            time.sleep(0.01)

        # 等待最后一个ACK
        time.sleep(self.timeout)

        # 输出统计信息
        success_count = sum(self.ack_received)
        self.logger.log_event("COMPLETE", None,
                              f"传输完成: 成功 {success_count}/{len(self.packets)}, "
                              f"重传 {self.stats['total_retrans']} 次, "
                              f"超时 {self.stats['timeout_count']} 次")

        return success_count, self.stats['total_retrans']

    def _send_packet(self, seq_num):
        """发送单个数据包"""
        packet_data = make_data_packet(seq_num, self.packets[seq_num])

        # 模拟网络丢包
        if random.random() > self.loss_prob:
            self.sock.sendto(packet_data, (self.target_host, self.target_port))
            self.stats['total_sent'] += 1

            # 记录发送时间
            self.timers[seq_num] = time.time()

            if seq_num >= self.base:  # 只记录窗口内的包
                self.logger.send_data(seq_num, len(self.packets[seq_num]))
        else:
            self.logger.log_event("DROP_SEND", seq_num, "模拟数据包丢包")

    def _receive_acks(self):
        """接收ACK的线程函数"""
        while self.is_running and self.base < len(self.packets):
            try:
                data, addr = self.sock.recvfrom(1024)
                packet = parse_packet(data)

                if packet and packet.ack_flag:
                    ack_seq = packet.seq_num
                    self._handle_ack(ack_seq)

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.logger.log_event("ERROR", None, f"接收ACK错误: {e}")

    def _handle_ack(self, ack_seq):
        """处理接收到的ACK"""
        self.logger.recv_ack(ack_seq)

        # GBN使用累计确认：ACK n表示所有<=n的包都已收到
        if ack_seq >= self.base and ack_seq < len(self.ack_received):
            # 标记所有<=ack_seq的包为已确认
            for i in range(self.base, ack_seq + 1):
                if i < len(self.ack_received):
                    self.ack_received[i] = True

            old_base = self.base
            # 移动窗口基址到第一个未确认的包
            while self.base < len(self.ack_received) and self.ack_received[self.base]:
                self.base += 1

            # 如果窗口移动了，更新下一个要发送的序列号
            if self.base > old_base:
                self.next_seq = max(self.next_seq, self.base)
                self.logger.window_update(self.base, self.next_seq, self.window_size)

    def _check_timeouts(self):
        """检查超时并重传"""
        current_time = time.time()

        # 检查窗口内未确认的包是否超时
        timeout_occurred = False
        for seq in range(self.base, min(self.base + self.window_size, len(self.packets))):
            if not self.ack_received[seq] and self.timers[seq] > 0:
                if current_time - self.timers[seq] > self.timeout:
                    timeout_occurred = True
                    break

        if timeout_occurred:
            self.stats['timeout_count'] += 1
            self.logger.timeout(self.base)
            self.logger.log_event("RETRANS_WINDOW", None,
                                  f"重传窗口 [{self.base}-{min(self.base + self.window_size - 1, len(self.packets) - 1)}]")

            # 重传整个窗口
            for seq in range(self.base, min(self.base + self.window_size, len(self.packets))):
                if not self.ack_received[seq]:
                    self._send_packet(seq)
                    self.stats['total_retrans'] += 1
                    self.logger.retransmit(seq)

            # 重置定时器
            for seq in range(self.base, min(self.base + self.window_size, len(self.packets))):
                if not self.ack_received[seq]:
                    self.timers[seq] = time.time()

    def close(self):
        self.is_running = False
        if self.ack_thread and self.ack_thread.is_alive():
            self.ack_thread.join(timeout=1.0)
        self.sock.close()


class GBNReceiver:
    def __init__(self, host, port, target_host, target_port, loss_prob=0.2):
        self.host = host
        self.port = port
        self.target_host = target_host
        self.target_port = target_port
        self.loss_prob = loss_prob

        # GBN 接收端状态
        self.expected_seq = 0
        self.received_packets = []

        # 网络和日志
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(1.0)

        self.logger = ProtocolLogger("GBN-Recv")
        self.is_running = True

    def start(self):
        """开始接收数据包"""
        self.logger.log_event("START", None, "开始监听数据包")

        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(1024)
                packet = parse_packet(data)

                if packet and not packet.ack_flag:  # 数据包
                    self._handle_data_packet(packet, addr)

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.logger.log_event("ERROR", None, f"接收错误: {e}")

    def _handle_data_packet(self, packet, addr):
        """处理接收到的数据包"""
        seq_num = packet.seq_num
        self.logger.recv_data(seq_num, len(packet.payload))

        if seq_num == self.expected_seq:
            # 按序接收，交付数据
            self.received_packets.append(packet)
            # self.logger.log_event("DELIVER", seq_num, "按序交付")
            self.expected_seq += 1

            # 发送累计ACK
            ack_seq = self.expected_seq - 1  # 最后连续接收的序号
            self._send_ack(ack_seq, addr)

        else:
            # 乱序包，丢弃并重新发送最近确认的ACK
            self.logger.log_event("OUT_OF_ORDER", seq_num,
                                  f"期望 {self.expected_seq}，丢弃并重发ACK {self.expected_seq - 1}")
            ack_seq = self.expected_seq - 1  # 累计确认
            self._send_ack(ack_seq, addr)

    def _send_ack(self, ack_seq, addr):
        """发送ACK包"""
        ack_packet = make_ack_packet(ack_seq)

        # 模拟ACK丢包
        if random.random() > self.loss_prob:
            self.sock.sendto(ack_packet, addr)
            self.logger.send_ack(ack_seq)
        else:
            self.logger.log_event("DROP_ACK", ack_seq, "模拟ACK丢包")

    def get_received_data(self):
        """获取接收到的数据"""
        # 按序列号排序并提取载荷
        packets_sorted = sorted(self.received_packets, key=lambda p: p.seq_num)
        return [packet.payload for packet in packets_sorted]

    def get_received_count(self):
        """获取成功接收的数据包数量"""
        return len(self.received_packets)

    def close(self):
        self.is_running = False
        self.sock.close()


def test_gbn_basic():
    """基础GBN协议测试"""
    print("=" * 70)
    print("GBN 协议基础测试")
    print("=" * 70)

    # 配置参数
    sender_host = 'localhost'
    sender_port = 12345
    receiver_host = 'localhost'
    receiver_port = 12346

    # 测试数据
    test_messages = [f"GBN Packet {i}".encode() for i in range(15)]

    # 启动接收方
    receiver = GBNReceiver(receiver_host, receiver_port, sender_host, sender_port, loss_prob=0.2)
    receiver_thread = threading.Thread(target=receiver.start)
    receiver_thread.daemon = True
    receiver_thread.start()

    time.sleep(1)  # 确保接收方先启动

    # 启动发送方并发送数据
    sender = GBNSender(sender_host, sender_port, receiver_host, receiver_port,
                       window_size=4, timeout=2.0, loss_prob=0.2)

    print("开始GBN传输测试...")
    start_time = time.time()

    success_count, retrans_count = sender.send_data(test_messages)

    end_time = time.time()
    transmission_time = end_time - start_time

    # 等待接收完成
    time.sleep(2)

    # 获取结果
    received_data = receiver.get_received_data()
    received_count = receiver.get_received_count()

    # 输出结果
    print("\n" + "=" * 70)
    print("GBN 测试结果")
    print("=" * 70)

    print(f"总数据包: {len(test_messages)}")
    print(f"窗口大小: 4")
    print(f"成功接收: {received_count}")
    print(f"重传次数: {retrans_count}")
    print(f"传输时间: {transmission_time:.2f} 秒")
    print(f"成功率: {(received_count / len(test_messages)) * 100:.1f}%")

    # 验证数据完整性
    print("\n数据完整性验证:")
    all_correct = True
    for i, (sent, received) in enumerate(zip(test_messages, received_data)):
        if i < len(received_data) and sent == received:
            print(f"  数据包 {i}: ✅ 正确")
        elif i < len(received_data):
            print(f"  数据包 {i}: ❌ 错误")
            all_correct = False
        else:
            print(f"  数据包 {i}: ❌ 丢失")
            all_correct = False

    if all_correct and received_count == len(test_messages):
        print("\n🎉 GBN协议测试成功！所有数据包正确传输")
    else:
        print(f"\n⚠️ GBN协议传输不完整: {received_count}/{len(test_messages)}")

    # 清理
    sender.close()
    receiver.close()

    return success_count, retrans_count, transmission_time


def compare_window_sizes():
    """比较不同窗口大小的性能"""
    print("\n" + "=" * 70)
    print("不同窗口大小性能比较")
    print("=" * 70)

    sender_host = 'localhost'
    receiver_host = 'localhost'

    test_messages = [f"Test Packet {i}".encode() for i in range(20)]

    window_sizes = [1, 2, 4, 8]
    loss_prob = 0.2

    results = []

    for window_size in window_sizes:
        print(f"\n测试窗口大小: {window_size}")

        sender_port = 7100 + window_size
        receiver_port = 7200 + window_size

        # 启动接收方
        receiver = GBNReceiver(receiver_host, receiver_port, sender_host, sender_port, loss_prob=loss_prob)
        receiver_thread = threading.Thread(target=receiver.start)
        receiver_thread.daemon = True
        receiver_thread.start()

        time.sleep(0.5)

        # 启动发送方
        sender = GBNSender(sender_host, sender_port, receiver_host, receiver_port,
                           window_size=window_size, timeout=2.0, loss_prob=loss_prob)

        start_time = time.time()
        success_count, retrans_count = sender.send_data(test_messages)
        end_time = time.time()

        transmission_time = end_time - start_time
        received_count = receiver.get_received_count()

        efficiency = received_count / (received_count + retrans_count) if (received_count + retrans_count) > 0 else 0

        results.append({
            'window_size': window_size,
            'success_count': success_count,
            'received_count': received_count,
            'retrans_count': retrans_count,
            'time': transmission_time,
            'efficiency': efficiency
        })

        print(f"  接收: {received_count}/20")
        print(f"  重传: {retrans_count}")
        print(f"  时间: {transmission_time:.2f}s")
        print(f"  效率: {efficiency:.3f}")

        sender.close()
        receiver.close()

        time.sleep(1)  # 等待端口释放

    # 输出比较结果
    print("\n" + "=" * 70)
    print("窗口大小性能比较总结")
    print("=" * 70)

    for result in results:
        print(f"窗口 {result['window_size']}: "
              f"接收 {result['received_count']}/20, "
              f"重传 {result['retrans_count']}, "
              f"时间 {result['time']:.2f}s, "
              f"效率 {result['efficiency']:.3f}")

    return results


def compare_gbn_vs_stop_wait():
    """GBN与停等协议性能对比"""
    print("\n" + "=" * 70)
    print("GBN vs 停等协议性能对比")
    print("=" * 70)

    test_messages = [f"Compare Packet {i}".encode() for i in range(10)]
    loss_prob = 0.3

    # 模拟GBN性能（窗口大小=4）
    print("\nGBN协议模拟 (窗口大小=4):")
    gbn_time = 0
    gbn_retrans = 0

    # 简化的GBN模拟
    base = 0
    window_size = 4
    total_packets = len(test_messages)

    while base < total_packets:
        # 发送窗口内的包
        sent_count = min(window_size, total_packets - base)
        gbn_time += 1  # 每个窗口一个RTT

        # 模拟丢包和重传
        for i in range(sent_count):
            if random.random() < loss_prob:
                gbn_retrans += 1

        # 移动窗口
        base += 1  # 简化：每次移动一个包

    print(f"  估计时间: {gbn_time} RTT")
    print(f"  估计重传: {gbn_retrans} 次")

    # 模拟停等协议性能
    print("\n停等协议模拟:")
    stop_wait_time = 0
    stop_wait_retrans = 0

    for i in range(len(test_messages)):
        stop_wait_time += 1  # 每个包至少一个RTT

        # 模拟重传
        while random.random() < loss_prob:
            stop_wait_retrans += 1
            stop_wait_time += 1

    print(f"  估计时间: {stop_wait_time} RTT")
    print(f"  估计重传: {stop_wait_retrans} 次")

    speedup = stop_wait_time / gbn_time if gbn_time > 0 else 0
    print(f"\n性能提升: GBN比停等协议快 {speedup:.2f} 倍")


def demo_gbn_retransmission():
    """演示GBN的重传机制"""
    print("\n" + "=" * 70)
    print("GBN 重传机制演示")
    print("=" * 70)

    print("场景: 序列号 2 的ACK丢失，导致整个窗口 [2,3,4,5] 被重传")
    print()
    print("发送端日志示例:")
    print("  [GBN-Sender] SEND     seq=2")
    print("  [GBN-Sender] SEND     seq=3")
    print("  [GBN-Sender] SEND     seq=4")
    print("  [GBN-Sender] SEND     seq=5")
    print("  [GBN-Sender] RECV_ACK seq=1")
    print("  [GBN-Sender] TIMEOUT  seq=2")
    print("  [GBN-Sender] RETRANS_WINDOW 重传窗口 [2-5]")
    print("  [GBN-Sender] RETRANS  seq=2")
    print("  [GBN-Sender] RETRANS  seq=3")
    print("  [GBN-Sender] RETRANS  seq=4")
    print("  [GBN-Sender] RETRANS  seq=5")
    print()
    print("关键特点: 单个包超时导致整个窗口重传，这是GBN的效率瓶颈")


if __name__ == "__main__":
    # 运行基础测试
    test_gbn_basic()

    # 比较不同窗口大小
    # compare_window_sizes()

    # 协议对比
    # compare_gbn_vs_stop_wait()

    # 重传机制演示
    # demo_gbn_retransmission()