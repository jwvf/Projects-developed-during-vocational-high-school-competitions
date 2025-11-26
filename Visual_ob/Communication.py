import socket, struct, logging, threading, config

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger('Comm')

cfg = config.ConfigManager()
HOST = cfg.get("server", {}).get("ip", "127.0.0.1")
PORT = int(cfg.get("server", {}).get("port", 1400))
RETRY_MAX = int(cfg.get("server", {}).get("retry_max", 5))
TIMEOUT = int(cfg.get("server", {}).get("timeout", 3))

_sock_lock = threading.Lock()

# ---------- 底层：一次完整收发 ----------
def _txn(req: bytes, expect: int) -> bytes:
    with _sock_lock:
        try:
            s = socket.socket()
            s.settimeout(TIMEOUT)
            s.connect((HOST, PORT))
            s.sendall(req)
            buf = b''
            while len(buf) < expect:
                buf += s.recv(expect - len(buf))
            return buf
        except Exception as e:
            logger.debug('txn err: %s', e)
            return b''
        finally:
            s.close()

# ---------- 写：四步握手 ----------
def write_var(idx: int, val: int) -> None:
    for attempt in range(RETRY_MAX):
        # 1. 写请求 0x50
        req = struct.pack('!BBHI', 0x50, idx, 0, 0)
        rsp = _txn(req, 8)
        if len(rsp) != 8:
            continue
        cmd, _ = struct.unpack('!BBHI', rsp)[:2]
        if cmd != 0x51:
            continue
        # 2. 写数据 0x52
        wreq = struct.pack('!BBHI', 0x52, idx, 0, int(val))
        wrsp = _txn(wreq, 8)
        if len(wrsp) != 8:
            continue
        w_ack, _ = struct.unpack('!BBHI', wrsp)[:2]
        if w_ack == 0x53:
            logger.info('write reg=%s val=%s  success', idx, val)
            return
    logger.error('write_var(%s,%s) finally failed', idx, val)


def read_var(idx: int) -> int:
    """读单个寄存器：0x40->0x41->0x42，返回 val"""
    with socket.create_connection((HOST, PORT), timeout=2) as s:
        # 0x40 读请求
        s.sendall(struct.pack('!BBHI', 0x40, idx, 0, 0))
        buf = b''
        while len(buf) < 8:
            buf += s.recv(8 - len(buf))
        cmd, _, _, val = struct.unpack('!BBHI', buf)
        assert cmd == 0x41
        # 0x42 确认
        s.sendall(struct.pack('!BBHI', 0x42, idx, 0, 0))
        return val