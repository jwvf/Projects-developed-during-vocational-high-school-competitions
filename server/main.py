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
        return
    
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
                    # ---- 读请求 0x40 ----
                    if cmd == 0x40:
                        val = self.var_table.get(idx)
                        writer.write(struct.pack('!BBHI', 0x41, idx, 0, val))
                        await writer.drain()
                    # ---- 读确认 0x42 ----
                    elif cmd == 0x42:
                        print(f'SERVER: read idx={idx} confirmed, close')
                        return
                    # ---- 写请求 0x50 ----
                    elif cmd == 0x50:
                        writer.write(struct.pack('!BBHI', 0x51, idx, 0, 0))
                    # ---- 写数据 0x52 ----
                    elif cmd == 0x52:
                        cmd, idx, _, val = struct.unpack_from('!BBHI', data, offset)
                        self.var_table.set(idx, val)
                        writer.write(struct.pack('!BBHI', 0x53, idx, 0, 0))
                        print(f'SERVER: write idx={idx} confirmed, close')
                    else:
                        pass   # 容错
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