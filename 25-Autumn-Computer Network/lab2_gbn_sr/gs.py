import socket
import time
import random
import os
import threading
import datetime


class GBNServer:
    def __init__(self, host='0.0.0.0', port=12340):
        self.host = host
        self.port = port
        self.seq_size = 20
        self.window_size = 4
        self.buffer_size = 1026
        self.socket = None

    def get_timestamp(self):
        """获取当前时间戳"""
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def handle_download(self, client_addr, packet_loss=0.2, ack_loss=0.2):
        """服务器发送文件给客户端"""
        print(f"[{self.get_timestamp()}] 开始下载传输，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        try:
            with open("server.txt", "rb") as f:
                data = f.read()
        except FileNotFoundError:
            print("server.txt 文件不存在")
            return

        total_packets = (len(data) + 1023) // 1024
        print(f"[{self.get_timestamp()}] 文件大小: {len(data)}字节, 总包数: {total_packets}")

        # GBN协议实现
        base = 0
        next_seq = 0
        acks_received = [False] * self.seq_size

        print(f"[{self.get_timestamp()}] 开始传输文件...")

        while base < total_packets:
            # 发送窗口内的包
            while next_seq < base + self.window_size and next_seq < total_packets:
                if not acks_received[next_seq % self.seq_size]:
                    start = next_seq * 1024
                    end = min(start + 1024, len(data))
                    packet_data = data[start:end]

                    # 构建数据包: [序列号(1-20)] + 数据
                    packet = bytes([(next_seq % self.seq_size) + 1]) + packet_data

                    # 模拟丢包
                    if random.random() > packet_loss:
                        self.socket.sendto(packet, client_addr)
                        print(f"[{self.get_timestamp()}] 发送包 {next_seq % self.seq_size + 1}, 序列: {next_seq}")

                    acks_received[next_seq % self.seq_size] = False
                    next_seq += 1

            # 接收ACK
            try:
                self.socket.settimeout(1)
                ack_data, _ = self.socket.recvfrom(self.buffer_size)

                # 模拟ACK丢包
                if random.random() > ack_loss:
                    ack_seq = ack_data[0] - 1
                    print(f"[{self.get_timestamp()}] 收到ACK: {ack_seq + 1}")

                    # 累积确认
                    for i in range(base, next_seq):
                        if i % self.seq_size == ack_seq:
                            base = i + 1
                            acks_received[ack_seq] = True
                            break

            except socket.timeout:
                print(f"[{self.get_timestamp()}] 超时，从包 {base} 开始重传")
                next_seq = base  # 回退N步重传

        # 传输完成
        self.socket.sendto(b"Transfer done", client_addr)
        print(f"[{self.get_timestamp()}] 文件传输完成")

    def handle_upload(self, client_addr, packet_loss=0.2, ack_loss=0.2):
        """服务器接收客户端文件"""
        print(f"[{self.get_timestamp()}] 开始上传传输，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        received_data = bytearray()
        expected_seq = 1

        print(f"[{self.get_timestamp()}] 开始接收文件...")

        while True:
            try:
                self.socket.settimeout(1)
                packet, addr = self.socket.recvfrom(self.buffer_size)

                if packet == b"Transfer done":
                    break

                # 模拟丢包
                if random.random() <= packet_loss:
                    print(f"[{self.get_timestamp()}] 包 {packet[0]} 丢失")
                    continue

                seq_num = packet[0]
                packet_data = packet[1:]

                print(f"[{self.get_timestamp()}] 收到包: {seq_num}, 数据长度: {len(packet_data)}")

                # 如果是期望的序列号
                if seq_num == expected_seq:
                    received_data.extend(packet_data)
                    expected_seq = expected_seq % self.seq_size + 1

                # 发送ACK (总是确认最近正确接收的包)
                ack_to_send = expected_seq - 1 if expected_seq > 1 else self.seq_size

                # 模拟ACK丢包
                if random.random() > ack_loss:
                    self.socket.sendto(bytes([ack_to_send]), client_addr)
                    print(f"[{self.get_timestamp()}] 发送ACK: {ack_to_send}")

            except socket.timeout:
                continue

        # 保存文件
        with open("server.txt", "wb") as f:
            f.write(received_data)
        print(f"[{self.get_timestamp()}] 文件接收完成，大小: {len(received_data)}字节")

    def start(self):
        """启动服务器"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))

        print(f"[{self.get_timestamp()}] GBN服务器启动在 {self.host}:{self.port}")
        print("等待命令: -time, -dl, -up, -quit")

        while True:
            try:
                data, addr = self.socket.recvfrom(self.buffer_size)
                if not data:
                    continue

                message = data.decode('utf-8', errors='ignore').strip()
                parts = message.split()

                if not parts:
                    continue

                cmd = parts[0]

                if cmd == "-time":
                    current_time = time.strftime("%Y/%m/%d %H:%M:%S")
                    self.socket.sendto(current_time.encode(), addr)
                    print(f"时间请求来自 {addr}")

                elif cmd == "-quit":
                    self.socket.sendto(b"bye", addr)
                    print(f"客户端 {addr} 退出")

                elif cmd == "-dl":
                    packet_loss = 0.2
                    ack_loss = 0.2
                    if len(parts) >= 3:
                        packet_loss = float(parts[1])
                        ack_loss = float(parts[2])
                    threading.Thread(target=self.handle_download, args=(addr, packet_loss, ack_loss)).start()

                elif cmd == "-up":
                    packet_loss = 0.2
                    ack_loss = 0.2
                    if len(parts) >= 3:
                        packet_loss = float(parts[1])
                        ack_loss = float(parts[2])
                    threading.Thread(target=self.handle_upload, args=(addr, packet_loss, ack_loss)).start()

            except Exception as e:
                print(f"{e}")


if __name__ == "__main__":
    server = GBNServer()
    server.start()