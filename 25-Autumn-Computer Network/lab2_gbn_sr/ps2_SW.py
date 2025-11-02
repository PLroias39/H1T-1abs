"""
实验 2：实现单向 Stop-and-Wait 协议
学习目标
理解可靠传输的基本原理：超时与重传、ACK 确认机制
掌握停等协议的工作流程和实现方法
为后续 GBN 协议打下基础

协议原理
停等协议特点：
发送方发送一个包后等待 ACK
收到 ACK 后才发送下一个包
超时未收到 ACK 则重传
简单但效率低
"""

import socket
import time
import random
import threading
from ps1_utils import make_data_packet, make_ack_packet, parse_packet, ProtocolLogger


class StopAndWaitSender:
    def __init__(self, host, port, target_host, target_port, timeout=2.0, loss_prob=0.3):
        self.host = host
        self.port = port
        self.target_host = target_host
        self.target_port = target_port
        self.timeout = timeout
        self.loss_prob = loss_prob

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(1.0)  # 短的超时用于检查停止条件

        self.logger = ProtocolLogger("Sender")
        self.is_running = True

    def send_packets(self, data_list):
        """发送数据包列表"""
        seq_num = 0
        total_packets = len(data_list)
        sent_count = 0
        retransmit_count = 0

        self.logger.log_event("START", None, f"开始传输 {total_packets} 个数据包")

        for data in data_list:
            success = False
            attempts = 0
            max_attempts = 5

            while not success and attempts < max_attempts:
                attempts += 1

                # 创建并发送数据包
                packet = make_data_packet(seq_num, data)
                self._maybe_send(seq_num, packet,(self.target_host, self.target_port))

                send_time = time.time()

                # 等待 ACK
                ack_received = False
                while time.time() - send_time < self.timeout:
                    try:
                        ack_data, addr = self.sock.recvfrom(1024)
                        ack_packet = parse_packet(ack_data)

                        if ack_packet and ack_packet.ack_flag and ack_packet.seq_num == seq_num:
                            ack_received = True
                            self.logger.recv_ack(seq_num)
                            success = True
                            sent_count += 1
                            break

                    except socket.timeout:
                        continue

                if not ack_received:
                    self.logger.timeout(seq_num)
                    if attempts < max_attempts:
                        self.logger.retransmit(seq_num)
                        retransmit_count += 1
                    else:
                        self.logger.log_event("ERROR", seq_num, "达到最大重试次数，放弃该包")

            seq_num += 1

        # 统计信息
        self.logger.log_event("COMPLETE", None,
                              f"传输完成: 成功 {sent_count}/{total_packets}, 重传 {retransmit_count} 次")
        return sent_count, retransmit_count

    def _maybe_send(self, seq_num, data, addr):
        """模拟网络丢包：按概率决定是否发送"""
        if random.random() > self.loss_prob:
            self.sock.sendto(data, addr)
            self.logger.send_data(seq_num, len(data))
        else:
            self.logger.log_event("DROP", None, "模拟丢包 - 未发送数据包")

    def close(self):
        self.is_running = False
        self.sock.close()


class StopAndWaitReceiver:
    def __init__(self, host, port, target_host, target_port, loss_prob=0.3):
        self.host = host
        self.port = port
        self.target_host = target_host
        self.target_port = target_port
        self.loss_prob = loss_prob

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))

        self.logger = ProtocolLogger("Receiver")
        self.expected_seq = 0
        self.received_packets = []
        self.is_running = True

    def start(self):
        """开始接收数据包"""
        self.logger.log_event("START", None, "开始监听数据包")

        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(1024)
                packet = parse_packet(data)

                if packet and not packet.ack_flag:  # 数据包（非ACK）
                    self._handle_data_packet(packet, addr)

            except socket.timeout:
                continue
            except Exception as e:
                self.logger.log_event("ERROR", None, f"接收错误: {e}")

    def _handle_data_packet(self, packet, addr):
        """处理接收到的数据包"""
        self.logger.recv_data(packet.seq_num, len(packet.payload))

        if packet.seq_num == self.expected_seq:
            # 按序接收
            self.received_packets.append(packet)
            self.logger.log_event("DELIVER", packet.seq_num, "按序交付")
            self.expected_seq += 1

            # 发送 ACK
            ack_packet = make_ack_packet(packet.seq_num)
            self._maybe_send(ack_packet, addr)
            self.logger.send_ack(packet.seq_num)

        else:
            # 乱序包（停等协议中不应该出现，但处理一下）
            self.logger.log_event("OUT_OF_ORDER", packet.seq_num,
                                  f"期望 {self.expected_seq}，收到 {packet.seq_num}")
            # 仍然发送上一个期望序列号的 ACK
            ack_packet = make_ack_packet(self.expected_seq - 1)
            self._maybe_send(ack_packet, addr)

    def _maybe_send(self, data, addr):
        """模拟网络丢包：按概率决定是否发送ACK"""
        if random.random() > self.loss_prob:
            self.sock.sendto(data, addr)
        else:
            self.logger.log_event("DROP_ACK", None, "模拟ACK丢包 - 未发送ACK")

    def get_received_data(self):
        """获取接收到的数据"""
        return [packet.payload for packet in self.received_packets]

    def close(self):
        self.is_running = False
        self.sock.close()


def test_stop_and_wait():
    """测试停等协议"""
    print("=" * 60)
    print("停等协议测试")
    print("=" * 60)

    # 配置参数
    sender_host = 'localhost'
    sender_port = 12345
    receiver_host = 'localhost'
    receiver_port = 12346

    # 测试数据
    test_messages = [
        b"Message 1: Hello World!",
        b"Message 2: Stop and Wait Protocol",
        b"Message 3: Testing reliability",
        b"Message 4: With packet loss",
        b"Message 5: ACK mechanism",
        b"Message 6: Timeout and retransmission",
        b"Message 7: Simple but effective",
        b"Message 8: Foundation for GBN",
        b"Message 9: Almost done",
        b"Message 10: Final message"
    ]

    # 启动接收方（在后台线程）
    receiver = StopAndWaitReceiver(receiver_host, receiver_port, sender_host, sender_port, loss_prob=0.2)
    receiver_thread = threading.Thread(target=receiver.start)
    receiver_thread.daemon = True
    receiver_thread.start()

    time.sleep(1)  # 确保接收方先启动

    # 启动发送方
    sender = StopAndWaitSender(sender_host, sender_port, receiver_host, receiver_port,
                               timeout=2.0, loss_prob=0.2)

    print("\n开始传输测试...")
    start_time = time.time()

    # 发送数据
    success_count, retransmit_count = sender.send_packets(test_messages)

    end_time = time.time()
    transmission_time = end_time - start_time

    # 等待接收完成
    time.sleep(2)

    # 获取接收到的数据
    received_data = receiver.get_received_data()

    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    print(f"发送数据包: {len(test_messages)}")
    print(f"成功接收: {len(received_data)}")
    print(f"重传次数: {retransmit_count}")
    print(f"传输时间: {transmission_time:.2f} 秒")
    print(f"成功率: {(len(received_data) / len(test_messages)) * 100:.1f}%")

    # 验证数据完整性
    print("\n数据完整性验证:")
    all_correct = True
    for i, (sent, received) in enumerate(zip(test_messages, received_data)):
        if sent == received:
            print(f"  数据包 {i}: ✅ 正确")
        else:
            print(f"  数据包 {i}: ❌ 错误")
            all_correct = False

    if all_correct and len(received_data) == len(test_messages):
        print("\n🎉 所有数据包正确传输！")
    else:
        print(f"\n⚠️  数据传输不完整: {len(received_data)}/{len(test_messages)}")

    # 清理
    sender.close()
    receiver.close()

    return success_count, retransmit_count, transmission_time


def performance_comparison():
    """性能对比：不同丢包率下的表现"""
    print("\n" + "=" * 60)
    print("性能对比测试")
    print("=" * 60)

    test_messages = [f"Message {i}".encode() for i in range(20)]

    loss_probabilities = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    results = []

    for loss_prob in loss_probabilities:
        print(f"\n测试丢包率: {loss_prob * 100}%")

        # 简化的性能测试（不启动完整接收方）
        success_count = 0
        retransmit_count = 0

        for i, message in enumerate(test_messages):
            # 模拟发送过程
            attempts = 0
            while attempts < 3:  # 最大重试3次
                attempts += 1
                # 模拟ACK接收（有丢包概率）
                if random.random() > loss_prob:
                    success_count += 1
                    break
                else:
                    retransmit_count += 1

        efficiency = len(test_messages) / (len(test_messages) + retransmit_count)
        results.append((loss_prob, success_count, retransmit_count, efficiency))

        print(f"  成功率: {success_count}/{len(test_messages)}")
        print(f"  重传率: {retransmit_count / len(test_messages):.2f}")
        print(f"  效率: {efficiency:.2f}")

    # 输出性能分析
    print("\n" + "=" * 60)
    print("性能分析")
    print("=" * 60)

    for loss_prob, success, retransmit, efficiency in results:
        print(
            f"丢包率 {loss_prob * 100:2.0f}%: 成功率 {success:2d}/20, 重传率 {retransmit / 20:.2f}, 效率 {efficiency:.2f}")


def demo_no_loss():
    """无丢包演示"""
    print("\n" + "=" * 60)
    print("无丢包演示")
    print("=" * 60)

    sender_host = 'localhost'
    sender_port = 12345
    receiver_host = 'localhost'
    receiver_port = 12346

    test_messages = [
        b"Packet 1",
        b"Packet 2",
        b"Packet 3"
    ]

    # 无丢包测试
    receiver = StopAndWaitReceiver(receiver_host, receiver_port, sender_host, sender_port, loss_prob=0.0)
    receiver_thread = threading.Thread(target=receiver.start)
    receiver_thread.daemon = True
    receiver_thread.start()

    time.sleep(1)

    sender = StopAndWaitSender(sender_host, sender_port, receiver_host, receiver_port,
                               timeout=1.0, loss_prob=0.0)

    print("无丢包环境下的传输:")
    sender.send_packets(test_messages)

    time.sleep(1)
    received = receiver.get_received_data()
    print(f"\n接收结果: {len(received)}/{len(test_messages)} 个数据包")

    sender.close()
    receiver.close()


if __name__ == "__main__":
    # 运行测试
    test_stop_and_wait()

    # 性能对比
    # performance_comparison()

    # 无丢包演示
    # demo_no_loss()