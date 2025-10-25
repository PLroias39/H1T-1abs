# -*- coding: utf-8 -*-
"""
HTTP代理服务器

基本 HTTP 代理
Cache 缓存 + If-Modified-Since 验证
网站过滤 / 用户过滤
钓鱼重定向
"""

import os, socket, threading, time, requests
from urllib.parse import urlparse
from datetime import datetime

HOST, PORT = '127.0.0.1', 8888
CACHE_DIR = './cache'
BUFFER = 4096

# --- 配置 ---
BLOCKED_SITES = ['www.blocked.com']
BLOCKED_USERS = {'127.0.0.1': ['www.baidu.com']}
REDIRECT = {'www.jwts.hit.edu.cn': 'www.cmathc.cn'}

TESTING_SITES =['www.example.com','hcl.baidu.com',
                'info.cern.ch/',
                'httpbin.org/cache',
                ]

# ---------------- Cache 模块 ----------------
class Cache:
    def __init__(self, url):
        self.url = url
        self.path = os.path.join(CACHE_DIR, url.replace('/', '%'))
        os.makedirs(CACHE_DIR, exist_ok=True)

    def exists(self): return os.path.exists(self.path)

    def last_modified(self):
        if not self.exists(): return None
        ts = os.path.getmtime(self.path)
        return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(ts))

    def update(self, content):
        with open(self.path, 'wb') as f: f.write(content)

    def read(self):
        with open(self.path, 'rb') as f: return f.read()

    def validate(self):
        headers = {}
        if self.exists(): headers['If-Modified-Since'] = self.last_modified()
        try:
            r = requests.get(self.url, headers=headers, timeout=5, stream=True, proxies={"http": None})
            if r.status_code == 304:
                print(f'[Cache] 命中缓存: {self.url}')
                return True, self.read()
            else:
                body = r.content
                self.update(body)
                print(f'[Cache] 缓存更新: {self.url}')
                return False, body
        except:
            return False, b''


def parse_request_info(request_text: str):
        """解析请求首行与头部，返回 (method, host, url)"""
        lines = request_text.split('\r\n')
        if not lines or ' ' not in lines[0]:
            return '', '', ''
        method, target, _ = lines[0].split()

        headers = {}
        for line in lines[1:]:
            if ': ' in line:
                k, v = line.split(': ', 1)
                headers[k] = v.strip()

        # CONNECT方法（HTTPS）
        if method.upper() == 'CONNECT':
            host, port = (target.split(':') + ['443'])[:2]
            return method.upper(), host, f'https://{host}:{port}'

        # HTTP
        p = urlparse(target)
        host = p.netloc or headers.get('Host', '')
        url = target if p.scheme else f"http://{host}{p.path or '/'}"
        return method.upper(), host, url

# ---------------- Proxy 主体 ----------------
class Proxy:
    def __init__(self, host=HOST, port=PORT):
        self.host, self.port = host, port
        os.makedirs(CACHE_DIR, exist_ok=True)


    def handle_client(self, conn, addr):
        ip = addr[0]
        req = conn.recv(BUFFER).decode(errors='ignore')
        if not req: return
        method, host, url = parse_request_info(req)

        print(f'\n[Request] {ip} -> {host}')

        # 网站过滤
        if host in BLOCKED_SITES:
            conn.send(b'HTTP/1.1 403 Forbidden\r\n\r\nBlocked Site')
            print(f'[Filter] 拦截网站 {host}')
            conn.close(); return

        # 用户过滤
        if ip in BLOCKED_USERS and host in BLOCKED_USERS[ip]:
            conn.send(b'HTTP/1.1 403 Forbidden\r\n\r\nUser blocked')
            print(f'[Filter] 用户 {ip} 禁止访问 {host}')
            conn.close(); return

        # 钓鱼重定向
        if host in REDIRECT:
            redirect = REDIRECT[host]
            html = f'HTTP/1.1 302 Found\r\nLocation: http://{redirect}\r\n\r\n'
            conn.send(html.encode())
            print(f'[Phish] {host} -> {redirect}')
            conn.close(); return

        # GET 请求走缓存
        if method.upper() == 'GET':
            """
             1. 对url创建Cache 对象
             2. 若缓存不存在 -> 向原服务器请求，转发响应并缓存
             3. 若缓存存在 -> 调用 validate_with_server()，以 If-Modified-Since 验证：
                  a) 若服务器返回 304 -> 读取并返回缓存（命中）
                  b) 若服务器返回 200 -> 更新缓存并返回新内容（视为未命中但已更新）
            """
            cache = Cache(url)
            hit, data = cache.validate() if cache.exists() else (False, self.fetch(url, cache))
            conn.send(b'HTTP/1.1 200 OK\r\n\r\n' + data)
        elif method.upper() == 'CONNECT':
            print(f'[HTTPS]跳过https')
            conn.close
        else:
            data = self.fetch(url)
            conn.send(b'HTTP/1.1 200 OK\r\n\r\n' + data)
        conn.close()

    def fetch(self, url, cache=None):
        try:
            r = requests.get(url, timeout=5, proxies={"http": None})
            data = r.content
            if cache: cache.update(data)
            print(f'[Fetch] 缓存未命中: {url}')
            return data
        except Exception as e:
            print(f'[Error] 请求失败: {e}')
            return b''

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(5)
        print(f'[*] 代理服务器运行于 {self.host}:{self.port}')
        while True:
            conn, addr = s.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    print('[Init] 清空缓存目录')
    if os.path.exists(CACHE_DIR): [os.remove(os.path.join(CACHE_DIR, f)) for f in os.listdir(CACHE_DIR)]
    Proxy().start()
