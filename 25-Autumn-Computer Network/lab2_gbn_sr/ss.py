# gs.py
import socket
import time
import random
import os
import threading
import datetime


class SRServer:
    def __init__(self, host='0.0.0.0', port=12350):
        self.host = host
        self.port = port
        self.seq_size = 20
        self.window_size = 4
        self.buffer_size = 1026
        self.socket = None
        self.timeout = 1  # 超时时间

    def get_timestamp(self):
        """获取当前时间戳"""
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def handle_download(self, client_addr, packet_loss=0.2, ack_loss=0.2):
        """服务器发送文件给客户端 - SR发送方"""
        print(f"[{self.get_timestamp()}] 开始下载传输，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        try:
            with open("server.txt", "rb") as f:
                data = f.read()
        except FileNotFoundError:
            print("server.txt 文件不存在")
            return

        total_packets = (len(data) + 1023) // 1024
        print(f"[{self.get_timestamp()}] 文件大小: {len(data)}字节, 总包数: {total_packets}")

        # SR协议实现
        base = 0
        next_seq = 0
        acks_received = [False] * (self.seq_size + 1)  # 索引从1开始
        packet_timers = {}  # 包的定时器
        packet_data_cache = {}  # 缓存已发送的包数据

        print(f"[{self.get_timestamp()}] 开始传输文件...")

        while base < total_packets:
            current_time = time.time()

            # 发送窗口内的包
            while next_seq < base + self.window_size and next_seq < total_packets:
                if not acks_received[next_seq % self.seq_size + 1]:
                    start = next_seq * 1024
                    end = min(start + 1024, len(data))
                    packet_data = data[start:end]

                    # 构建数据包
                    seq_num = next_seq % self.seq_size + 1
                    packet = bytes([seq_num]) + packet_data

                    # 缓存包数据用于重传
                    packet_data_cache[seq_num] = packet

                    # 模拟丢包
                    if random.random() > packet_loss:
                        self.socket.sendto(packet, client_addr)
                        packet_timers[seq_num] = current_time  # 记录发送时间
                        print(f"[{self.get_timestamp()}] 发送包 {seq_num}, 序列: {next_seq}")

                    next_seq += 1

            # 接收ACK
            try:
                self.socket.settimeout(2)
                ack_data, _ = self.socket.recvfrom(self.buffer_size)

                # 模拟ACK丢包
                if random.random() > ack_loss:
                    ack_seq = ack_data[0]
                    print(f"[{self.get_timestamp()}] 收到ACK: {ack_seq}")

                    # 标记该包已确认
                    if 1 <= ack_seq <= self.seq_size:
                        acks_received[ack_seq] = True

                        # 如果确认的是窗口基序号，移动窗口
                        while base < total_packets and acks_received[base % self.seq_size + 1]:
                            base += 1

            except socket.timeout:
                pass

            # 检查超时重传
            for seq_num, send_time in list(packet_timers.items()):
                if current_time - send_time > self.timeout and not acks_received[seq_num]:
                    # 重传超时的包
                    if random.random() > packet_loss:  # 重传时也可能丢包
                        self.socket.sendto(packet_data_cache[seq_num], client_addr)
                        packet_timers[seq_num] = current_time  # 重置定时器
                        print(f"[{self.get_timestamp()}] 超时重发包: {seq_num}")

        # 传输完成
        self.socket.sendto(b"Transfer done", client_addr)
        print(f"[{self.get_timestamp()}] 文件传输完成")

    def handle_upload(self, client_addr, packet_loss=0.2, ack_loss=0.2):
        """服务器接收客户端文件 - SR接收方"""
        print(f"[{self.get_timestamp()}] 开始上传传输，丢包率: 数据{packet_loss}, ACK{ack_loss}")

        received_data = bytearray()
        expected_seq = 1
        window_buffer = {}  # 缓存乱序到达的包

        print(f"[{self.get_timestamp()}] 开始接收文件...")

        while True:
            try:
                self.socket.settimeout(2)
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

                    # 检查缓冲区中是否有连续的包
                    while expected_seq in window_buffer:
                        received_data.extend(window_buffer[expected_seq])
                        del window_buffer[expected_seq]
                        expected_seq = expected_seq % self.seq_size + 1
                else:
                    # 缓存乱序到达的包
                    window_buffer[seq_num] = packet_data

                # 发送ACK - SR协议中对每个收到的包都发送ACK
                ack_to_send = seq_num  # ACK确认收到的包序号

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

        print(f"[{self.get_timestamp()}] SR服务器启动在 {self.host}:{self.port}")
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
    server = SRServer()
    server.start()