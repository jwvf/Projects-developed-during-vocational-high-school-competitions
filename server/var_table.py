import struct
import threading
from typing import List, Callable

class VarTable:
    """读写锁优化的变量表"""
    def __init__(self, size: int = 100):
        self._vals = [0] * size
        self.on_change: Callable[[int, int], None] = None
        self._lock = threading.RLock()  # 使用可重入锁
        self._size = size

    def set(self, idx: int, val: int):
        if not 0 <= idx < self._size:
            raise IndexError(f"Index {idx} out of range [0, {self._size})")
        
        # 快速路径：无变化直接返回
        if self._vals[idx] == val:
            return
        
        with self._lock:
            self._vals[idx] = val
        
        # 回调在锁外执行
        if self.on_change:
            self.on_change(idx, val)

    def get(self, idx: int) -> int:
        # 读操作无锁（int读取是原子的）
        return self._vals[idx]

    @property
    def size(self) -> int:
        return self._size
        
    def encode_change(self, idx: int, val: int) -> bytes:
        return struct.pack('!BBHI', 0x30, idx, 0, val)