import socket, struct, logging, threading, config, time

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger('Comm')

cfg = config.ConfigManager()
HOST = cfg.get("server", {}).get("ip", "127.0.0.1")
PORT = int(cfg.get("server", {}).get("port", 1400))
RETRY_MAX = int(cfg.get("server", {}).get("retry_max", 5))
TIMEOUT = int(cfg.get("server", {}).get("timeout", 5))

_sock_lock = threading.Lock()

def _txn(req: bytes, expect: int) -> bytes:
    """增强版通信函数，支持asyncio服务器"""
    with _sock_lock:
        for attempt in range(RETRY_MAX):
            try:
                with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as s:
                    # 新版asyncio服务器需要精确帧长
                    s.sendall(req)
                    buf = b''
                    while len(buf) < expect:
                        chunk = s.recv(expect - len(buf))
                        if not chunk:
                            raise ConnectionError("PLC断开连接")
                        buf += chunk
                    return buf
            except Exception as e:
                logger.warning('尝试 %d/%d 失败: %s', attempt + 1, RETRY_MAX, e)
                if attempt < RETRY_MAX - 1:
                    time.sleep(0.5 * (attempt + 1))
        logger.error('通信失败: %s:%d', HOST, PORT)
        return b''

def write_var(idx: int, val: int) -> bool:
    """写入寄存器（兼容asyncio服务器）"""
    for attempt in range(RETRY_MAX):
        # 写请求 0x50
        req = struct.pack('!BBHI', 0x50, idx, 0, 0)
        rsp = _txn(req, 8)
        if len(rsp) != 8 or struct.unpack('!BB', rsp[:2])[0] != 0x51:
            continue
        
        # 写数据 0x52
        wreq = struct.pack('!BBHI', 0x52, idx, 0, int(val))
        wrsp = _txn(wreq, 8)
        if len(wrsp) == 8 and struct.unpack('!BB', wrsp[:2])[0] == 0x53:
            logger.info('写入成功: 寄存器=%d 值=%d', idx, val)
            return True
    
    logger.error('写入失败: 寄存器=%d 值=%d', idx, val)
    return False

def read_var(idx: int) -> int:
    """读取单个寄存器"""
    try:
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as s:
            # 0x40 读请求
            s.sendall(struct.pack('!BBHI', 0x40, idx, 0, 0))
            buf = b''
            while len(buf) < 8:
                chunk = s.recv(8 - len(buf))
                if not chunk:
                    raise ConnectionError("PLC断开连接")
                buf += chunk
            
            cmd, reg_idx, _, val = struct.unpack('!BBHI', buf)
            if cmd != 0x41:
                raise ValueError(f"命令码错误: 0x{cmd:X}")
            
            # 0x42 确认（asyncio服务器需要）
            s.sendall(struct.pack('!BBHI', 0x42, idx, 0, 0))
            return val
    except Exception as e:
        logger.error('读取失败: 寄存器=%d 错误: %s', idx, e)
        return -1