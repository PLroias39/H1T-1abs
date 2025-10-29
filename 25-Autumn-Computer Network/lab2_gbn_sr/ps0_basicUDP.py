"""
学习目标
熟悉 Python 的 UDP socket API
理解 UDP 的无连接特性
掌握基本的网络编程调试方法

最小 UDP 客户端与服务器：
服务器监听某端口并回显收到的消息；
客户端向服务器发送字符串并打印回应。

python ps0_basicUDP.py server --host 0.0.0.0 --port 12345 --loss-prob 0.2

python ps0_basicUDP.py client --host 127.0.0.1 --port 12345 --num-messages 5 --timeout 1.5
"""

import socket
import time
import random
import argparse
import sys


def udp_client(server_host='localhost', server_port=8888, num_messages=10, timeout=2.0):
    """
    简单的 UDP 客户端，发送消息并等待回复
    """
    # 创建 UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 设置超时时间
    sock.settimeout(timeout)

    server_address = (server_host, server_port)

    success_count = 0
    timeout_count = 0

    print(f"连接到服务器 {server_host}:{server_port}")
    print(f"计划发送 {num_messages} 条消息\n")

    for i in range(num_messages):
        message = f"Hello Server! 消息 #{i + 1}"

        try:
            # 发送消息
            print(f"发送: {message}")
            start_time = time.time()
            sock.sendto(message.encode('utf-8'), server_address)

            # 等待回复
            data, _ = sock.recvfrom(1024)
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # 转换为毫秒
            print(f"✅ 收到回复: {data.decode('utf-8')}")
            print(f"   响应时间: {response_time:.2f}ms")
            success_count += 1

        except socket.timeout:
            print("❌ 请求超时 - 未收到服务器回复")
            timeout_count += 1

        # 消息间延迟
        time.sleep(1)

    # 统计结果
    print("\n" + "=" * 50)
    print("传输统计:")
    print(f"总发送消息: {num_messages}")
    print(f"成功接收: {success_count}")
    print(f"超时/丢包: {timeout_count}")
    print(f"成功率: {(success_count / num_messages) * 100:.1f}%")

    sock.close()


def udp_server(host='localhost', port=8888, loss_prob=0.3):
    """
    简单的 UDP 服务器，会随机丢弃部分数据包来模拟网络丢包
    """
    # 创建 UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 绑定地址和端口
    server_address = (host, port)
    sock.bind(server_address)

    print(f"UDP 服务器启动在 {host}:{port}")
    print(f"丢包概率: {loss_prob * 100}%")
    print("按 Ctrl+C 停止服务器")

    packet_count = 0
    received_count = 0

    try:
        while True:
            # 接收数据
            data, client_address = sock.recvfrom(1024)
            packet_count += 1

            print(f"\n收到来自 {client_address} 的数据包 #{packet_count}")
            print(f"数据: {data.decode('utf-8')}")

            # 模拟随机丢包
            if random.random() < loss_prob:
                print("❌ 模拟丢包 - 不回复此数据包")
                continue

            # 回显数据
            received_count += 1
            response = f"ECHO: {data.decode('utf-8')} (包#{received_count})"
            sock.sendto(response.encode('utf-8'), client_address)
            print(f"✅ 已回复: {response}")

    except KeyboardInterrupt:
        print("\n服务器关闭")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description='UDP 客户端/服务器工具')

    # 选择模式
    parser.add_argument('mode', choices=['client', 'server'],
                        help='运行模式: client (客户端) 或 server (服务器)')

    # 通用参数
    parser.add_argument('--host', default='localhost',
                        help='服务器地址 (默认: localhost)')
    parser.add_argument('--port', type=int, default=8888,
                        help='端口号 (默认: 8888)')

    # 客户端专用参数
    parser.add_argument('--num-messages', type=int, default=10,
                        help='客户端发送的消息数量 (默认: 10)')
    parser.add_argument('--timeout', type=float, default=2.0,
                        help='客户端超时时间(秒) (默认: 2.0)')

    # 服务器专用参数
    parser.add_argument('--loss-prob', type=float, default=0.3,
                        help='服务器丢包概率 (默认: 0.3)')

    args = parser.parse_args()

    if args.mode == 'client':
        print("启动 UDP 客户端...")
        udp_client(
            server_host=args.host,
            server_port=args.port,
            num_messages=args.num_messages,
            timeout=args.timeout
        )
    else:  # server mode
        print("启动 UDP 服务器...")
        udp_server(
            host=args.host,
            port=args.port,
            loss_prob=args.loss_prob
        )


if __name__ == "__main__":
    main()