import selectors
import socket

class ByteStream:
    """高性能非阻塞字节流"""
    __slots__ = ('_sock', '_sel', '_rx_buf', '_tx_buf', '_closed', '_addr')
    
    def __init__(self, sock: socket.socket, selector: selectors.BaseSelector, addr):
        self._sock = sock
        self._sel = selector
        self._rx_buf = bytearray()  # 使用bytearray减少拷贝
        self._tx_buf = bytearray()
        self._closed = False
        self._addr = addr
        sock.setblocking(False)
        self._sel.register(sock, selectors.EVENT_READ, self)

    def _io_cb(self, mask):
        if self._closed: 
            return
        
        # 读事件：批量接收
        if mask & selectors.EVENT_READ:
            try:
                # 使用memory view减少分配
                chunk = self._sock.recv(8192)  # 增大缓冲区
                if chunk:
                    self._rx_buf.extend(chunk)
                else:
                    self.close()
                    return
            except (BlockingIOError, ConnectionError):
                pass
        
        # 写事件：批量发送
        if mask & selectors.EVENT_WRITE and self._tx_buf:
            try:
                # 直接发送，避免切片拷贝
                sent = self._sock.send(self._tx_buf)
                del self._tx_buf[:sent]
            except (BlockingIOError, ConnectionError):
                pass
            
            # 数据发完取消写关注
            if not self._tx_buf:
                self._sel.modify(self._sock, selectors.EVENT_READ, self)

    def recv(self) -> bytes | None:
        """返回所有累积数据并清空缓冲区"""
        if self._rx_buf:
            data = bytes(self._rx_buf)
            self._rx_buf.clear()
            return data
        return None

    def send(self, data: bytes) -> None:
        """零拷贝写入"""
        if not data or self._closed:
            return
        
        # 合并小数据包
        self._tx_buf.extend(data)
        
        # 注册写事件（仅当未注册时）
        try:
            current = self._sel.get_key(self._sock).events
            if not (current & selectors.EVENT_WRITE):
                self._sel.modify(self._sock, selectors.EVENT_READ | selectors.EVENT_WRITE, self)
        except KeyError:
            pass  # 可能已被关闭

    def close(self):
        if self._closed:
            return
        self._closed = True
        
        try:
            self._sel.unregister(self._sock)
        except:
            pass
        
        try:
            if self._sock.fileno() != -1:
                self._sock.close()
        except:
            pass