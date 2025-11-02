import socket
import time
import random
import os
import datetime


class GBNClient:
    def __init__(self, server_ip='127.0.0.1', server_port=12340):
        self.server_ip = server_ip
        self.server_port = server_port
        self.buffer_size = 1026
        self.seq_size = 20
        self.window_size = 4
        self.socket = None

    def get_timestamp(self):
        """获取当前时间戳"""
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def print_help(self):
        print("\n可用命令:")
        print("  -time                   获取服务器时间")
        print("  -dl [数据丢包率] [ACK丢包率]  下载文件")
        print("  -up [数据丢包率] [ACK丢包率]  上传文件")
        print("  -quit                   退出")
        print("示例: -dl 0.2 0.3")

    def handle_download(self, packet_loss=0.2, ack_loss=0.2):
        """从服务器下载文件"""
        print(f"[{self.get_timestamp()}]开始下载，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        # 发送下载请求
        self.socket.sendto(f"-dl {packet_loss} {ack_loss}".encode(),
                           (self.server_ip, self.server_port))

        received_data = bytearray()
        expected_seq = 1

        while True:
            try:
                self.socket.settimeout(1)
                packet, addr = self.socket.recvfrom(self.buffer_size)

                if packet == b"Transfer done":
                    break

                # 模拟丢包
                if random.random() <= packet_loss:
                    print(f"[{self.get_timestamp()}]包 {packet[0]} 丢失")
                    continue

                seq_num = packet[0]
                packet_data = packet[1:]

                print(f"[{self.get_timestamp()}]收到包: {seq_num}, 数据长度: {len(packet_data)}")

                # 如果是期望的序列号
                if seq_num == expected_seq:
                    received_data.extend(packet_data)
                    expected_seq = expected_seq % self.seq_size + 1

                # 发送ACK
                ack_to_send = expected_seq - 1 if expected_seq > 1 else self.seq_size

                # 模拟ACK丢包
                if random.random() > ack_loss:
                    self.socket.sendto(bytes([ack_to_send]), (self.server_ip, self.server_port))
                    print(f"[{self.get_timestamp()}]发送ACK: {ack_to_send}")

            except socket.timeout:
                continue

        # 保存文件
        with open("client.txt", "wb") as f:
            f.write(received_data)
        print(f"[{self.get_timestamp()}]下载完成，文件大小: {len(received_data)}字节")

    def handle_upload(self, packet_loss=0.2, ack_loss=0.2):
        """上传文件到服务器"""
        print(f"[{self.get_timestamp()}]开始上传，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        try:
            with open("client.txt", "rb") as f:
                data = f.read()
        except FileNotFoundError:
            print("client.txt 文件不存在")
            return

        total_packets = (len(data) + 1023) // 1024
        print(f"[{self.get_timestamp()}]文件大小: {len(data)}字节, 总包数: {total_packets}")

        # 发送上传请求
        self.socket.sendto(f"-up {packet_loss} {ack_loss}".encode(),
                           (self.server_ip, self.server_port))

        # GBN协议实现
        base = 0
        next_seq = 0
        acks_received = [False] * self.seq_size

        print("开始传输文件...")

        while base < total_packets:
            # 发送窗口内的包
            while next_seq < base + self.window_size and next_seq < total_packets:
                if not acks_received[next_seq % self.seq_size]:
                    start = next_seq * 1024
                    end = min(start + 1024, len(data))
                    packet_data = data[start:end]

                    # 构建数据包
                    packet = bytes([(next_seq % self.seq_size) + 1]) + packet_data

                    # 模拟丢包
                    if random.random() > packet_loss:
                        self.socket.sendto(packet, (self.server_ip, self.server_port))
                        print(f"[{self.get_timestamp()}]发送包 {next_seq % self.seq_size + 1}, 序列: {next_seq}")

                    acks_received[next_seq % self.seq_size] = False
                    next_seq += 1

            # 接收ACK
            try:
                self.socket.settimeout(1)
                ack_data, _ = self.socket.recvfrom(self.buffer_size)

                # 模拟ACK丢包
                if random.random() > ack_loss:
                    ack_seq = ack_data[0] - 1
                    print(f"[{self.get_timestamp()}]收到ACK: {ack_seq + 1}")

                    # 累积确认
                    for i in range(base, next_seq):
                        if i % self.seq_size == ack_seq:
                            base = i + 1
                            acks_received[ack_seq] = True
                            break

            except socket.timeout:
                print(f"[{self.get_timestamp()}]超时，从包 {base} 开始重传")
                next_seq = base  # 回退N步重传

        # 传输完成
        self.socket.sendto(b"Transfer done", (self.server_ip, self.server_port))
        print("文件上传完成")

    def start(self):
        """启动客户端"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        print(f"[{self.get_timestamp()}]连接到服务器 {self.server_ip}:{self.server_port}")
        self.print_help()

        while True:
            try:
                command = input("\n输入命令: ").strip()
                if not command:
                    continue

                parts = command.split()
                cmd = parts[0]

                if cmd == "-time":
                    self.socket.sendto(b"-time", (self.server_ip, self.server_port))
                    response, _ = self.socket.recvfrom(self.buffer_size)
                    print(f"服务器时间: {response.decode()}")

                elif cmd == "-quit":
                    self.socket.sendto(b"-quit", (self.server_ip, self.server_port))
                    response, _ = self.socket.recvfrom(self.buffer_size)
                    print(response.decode())
                    break

                elif cmd == "-dl":
                    packet_loss = 0.2
                    ack_loss = 0.2
                    if len(parts) >= 3:
                        packet_loss = float(parts[1])
                        ack_loss = float(parts[2])
                    self.handle_download(packet_loss, ack_loss)

                elif cmd == "-up":
                    packet_loss = 0.2
                    ack_loss = 0.2
                    if len(parts) >= 3:
                        packet_loss = float(parts[1])
                        ack_loss = float(parts[2])
                    self.handle_upload(packet_loss, ack_loss)

                else:
                    print("未知命令")
                    self.print_help()

            except KeyboardInterrupt:
                print("\n客户端退出")
                break
            except Exception as e:
                print(f"错误: {e}")

        self.socket.close()


if __name__ == "__main__":
    client = GBNClient()
    client.start()