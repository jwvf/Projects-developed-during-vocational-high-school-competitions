#!/usr/bin/env python3
"""
main.py  方案 A + 命令-响应-确认读写
100 个 int32 公共变量，网络同步
读：0x40→0x41→0x42→关闭
写：0x50→0x51→0x52→0x53→关闭
所有帧固定 8 字节 Big-Endian
"""
import socket
import selectors
import struct
import time
import threading
from byte_stream import ByteStream
from var_table import VarTable

HOST = '0.0.0.0'
PORT = 1400
TABLE_SIZE = 100

SEL = selectors.DefaultSelector()
g_table = VarTable(TABLE_SIZE)   # 全局变量表
clients = set()                  # 当前所有 ByteStream

# ------------------------------------------------------
# 工具：广播 8 字节帧（写更新用）
# ------------------------------------------------------
def broadcast(frame: bytes):
    for s in list(clients):
        try:
            s.send(frame)
        except OSError:
            clients.discard(s)

# ------------------------------------------------------
# 服务端入口
# ------------------------------------------------------
def server():
    lsock = socket.socket()
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind((HOST, PORT))
    lsock.listen()
    lsock.setblocking(False)
    print(f'SERVER: listening on {HOST}:{PORT}')

    def _accept(sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        print('SERVER: accepted', addr)
        stream = ByteStream(conn, SEL)
        clients.add(stream)

        # 接收循环
        def _recv_loop():
            while True:
                data = stream.recv()
                if data:
                    # 粘包：8 字节一条
                    off = 0
                    while off + 8 <= len(data):
                        cmd, idx = struct.unpack_from('!BB', data, off)
                        # ---- 读请求 0x40 ----
                        if cmd == 0x40:
                            val = g_table.get(idx)
                            resp = struct.pack('!BBHI', 0x41, idx, 0, val)
                            stream.send(resp)
                        # ---- 读确认 0x42 ----
                        elif cmd == 0x42:
                            print(f'SERVER: read idx={idx} confirmed, close')
                            return
                        # ---- 写请求 0x50 ----
                        elif cmd == 0x50:
                            stream.send(struct.pack('!BBHI', 0x51, idx, 0, 0))
                        # ---- 写数据 0x52 ----
                        elif cmd == 0x52:
                            cmd, idx, _, val = struct.unpack_from('!BBHI', data, off)
                            g_table.set(idx, val)
                            stream.send(struct.pack('!BBHI', 0x53, idx, 0, 0))
                            print(f'SERVER: write idx={idx} confirmed, close')
                        else:
                            pass   # 容错
                        off += 8
                else:
                    time.sleep(0.001)
                if stream._closed:
                    clients.discard(stream)
                    #print('SERVER: disconnected', addr)
                    break
        threading.Thread(target=_recv_loop, daemon=True).start()

    SEL.register(lsock, selectors.EVENT_READ, _accept)

# ------------------------------------------------------
# 控制台：手动改变量（直接写，会广播）
# ------------------------------------------------------
def console():
    while True:
        try:
            idx = int(input('var idx(0-99): '))
            val = int(input('new val: '))
            g_table.set(idx, val)          # 触发 on_change → 广播
        except (EOFError, KeyboardInterrupt):
            break

# ------------------------------------------------------
# 主循环
# ------------------------------------------------------
if __name__ == '__main__':
    server()
    threading.Thread(target=console, daemon=True).start()
    #print('SERVER: event loop running ...')
    try:
        while True:
            for key, mask in SEL.select(timeout=0.01):
                key.data(key.fileobj, mask)
    except KeyboardInterrupt:
        print('\nSERVER: shutdown')







#!/usr/bin/env python3
"""
高性能asyncio版本 - 彻底解决select()限制
支持Windows IOCP和Linux epoll
"""
import asyncio
import socket
import struct
import sys
from var_table import VarTable

class AsyncServer:
    FRAME_SIZE = 8
    
    def __init__(self, host='0.0.0.0', port=1400):
        self.host = host
        self.port = port
        self.var_table = VarTable(100)
        self.clients = set()
        self.var_table.on_change = self._broadcast_change
    
    def _broadcast_change(self, idx: int, val: int):
        """广播变更"""
        frame = struct.pack('!BBHI', 0x30, idx, 0, val)
        dead = set()
        for client in self.clients:
            try:
                client.write(frame)
            except:
                dead.add(client)
        if dead:
            self.clients -= dead
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """单客户端协程"""
        addr = writer.get_extra_info('peername')
        print(f'✅ CLIENT {addr}')
        self.clients.add(writer)
        
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                
                offset = 0
                while offset + self.FRAME_SIZE <= len(data):
                    cmd, idx = struct.unpack_from('!BB', data, offset)
                    
                    if cmd == 0x40:  # 读
                        val = self.var_table.get(idx)
                        writer.write(struct.pack('!BBHI', 0x41, idx, 0, val))
                        await writer.drain()
                    
                    elif cmd == 0x42:  # 读确认
                        return
                    
                    elif cmd == 0x52:  # 写
                        _, idx, _, val = struct.unpack_from('!BBHI', data, offset)
                        self.var_table.set(idx, val)
                        writer.write(struct.pack('!BBHI', 0x53, idx, 0, 0))
                        await writer.drain()
                    
                    offset += self.FRAME_SIZE
        finally:
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            print(f'❌ CLIENT {addr}')
    
    async def start(self):
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port,
            backlog=1024, reuse_address=True
        )
        print(f'🚀 SERVER {self.host}:{self.port}')
        
        # 优化TCP参数
        for sock in server.sockets:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128 * 1024)
        
        async with server:
            await server.serve_forever()

async def console(server: AsyncServer):
    loop = asyncio.get_event_loop()
    while True:
        try:
            idx = int(await loop.run_in_executor(None, input, '📌 var idx: '))
            val = int(await loop.run_in_executor(None, input, '📌 new val: '))
            server.var_table.set(idx, val)
        except:
            break

async def main():
    server = AsyncServer()
    await asyncio.gather(
        server.start(),
        console(server)
    )

if __name__ == '__main__':
    asyncio.run(main())