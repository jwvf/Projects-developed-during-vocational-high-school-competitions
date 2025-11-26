#!/usr/bin/env python3
"""
严格格式检查的 TCP 客户端（配置由 config.py 统一管理）
  1. 发送 "s 0"  → 必须收到 b'OK\r'
  2. 发送 "m"     → 必须收到 b'OK\r*\r'
  3. 格式不符立即重试，直到成功
"""
import socket
import time
import logging
from config import ConfigManager      # 复用现成的 ConfigManager
import Communication

# ---------- 日志 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# ---------- 读取配置 ----------
cfg = ConfigManager()                       # 单例，自动加载 config.json
HOST: str        = cfg.get("visual", {}).get("ip", "127.0.0.1")
PORT: int        = cfg.get("visual", {}).get("port", 9876)
BUF_SIZE: int    = cfg.get("visual", {}).get("buff_size", 32768)
TIMEOUT: int     = cfg.get("visual",  {}).get("timeout", 5)
RETRY_DELAY: float = cfg.get("visual", {}).get("retry_delay", 0.5)

# ---------- 工具函数 ----------
def connect() -> socket.socket:
    """建立 TCP 连接，带超时"""
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TIMEOUT)
            sock.connect((HOST, PORT))
            logging.info("TCP 连接成功  %s:%s", HOST, PORT)
            return sock
        except Exception as exc:
            logging.error("连接失败: %s，%.1f 秒后重试", exc, RETRY_DELAY)
            time.sleep(RETRY_DELAY)

def send_exact(sock: socket.socket, data: bytes) -> None:
    sock.sendall(data)

def recv_exact(sock: socket.socket, n: int) -> bytes:
    """精确接收 n 字节"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("对端关闭连接")
        buf.extend(chunk)
    return bytes(buf)

def recv_until(sock: socket.socket, delimiter: bytes = b'\r') -> bytes:
    """读到分隔符为止，返回含分隔符的完整字节串"""
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            raise ConnectionError("对端关闭连接")
        buf.extend(b)
        if buf.endswith(delimiter):
            return bytes(buf)

# ---------- 业务逻辑 ----------
def trigger_detection(sock: socket.socket) -> None:
    while True:
        try:
            send_exact(sock, b"s 0")
            resp = recv_exact(sock, 3)
            if resp == b"OK\r":
                logging.info("检测触发成功: %r", resp)
                return
            logging.warning("检测触发格式错误: %r，重试", resp)
        except (socket.timeout, ConnectionError) as exc:
            logging.error("检测触发异常: %s，重试", exc)
        time.sleep(RETRY_DELAY)

def fetch_data(sock: socket.socket) -> bytes:
    """返回完整报文 b'OK\r*\r'"""
    while True:
        try:
            send_exact(sock, b"m")
            prefix = recv_exact(sock, 3)
            if prefix != b"OK\r":
                logging.warning("数据请求前缀错误: %r，重试", prefix)
                continue
            payload = recv_until(sock, b'\r')   # 包含末尾 \r
            full = prefix + payload
            logging.info("数据接收成功: %r", full)
            return full
        except (socket.timeout, ConnectionError) as exc:
            logging.error("数据请求异常: %s，重试", exc)
        time.sleep(RETRY_DELAY)

def parse_response(raw: bytes) -> str:
    """
    把 b'OK\r*\r' 解析成 {'prefix':'OK', 'payload': '*', 'raw': ...}
    格式不对就抛 ValueError，触发重试
    """
    if not raw.endswith(b"\r"):
        raise ValueError("响应必须以 \\r 结尾")
    parts = raw[:-1].split(b"\r", 1)          # 去掉末尾 \r 再切分
    if len(parts) != 2 or parts[0] != b"OK":
        raise ValueError(f"响应格式错误：{raw!r}")
    return parts[1].decode(errors="ignore")

def main() -> None:
    try:
        while True:
            if Communication.read_var(9) == 1:
                sock = connect()
                trigger_detection(sock)
                logging.info("请求发送完成")
                data = fetch_data(sock)
                logging.info("一轮交互完成，原始数据: %r", data)
                data = parse_response(data)
                logging.info("解析后的数据：%r", data)
                sock.close()
                Communication.write_var(10,int(data))
                Communication.write_var(9,0)
            else:
                time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("用户中断")

if __name__ == "__main__":
    main()