#!/usr/bin/env python3
# main.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from Communication import read_var, write_var
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Dict
from enum import Enum
import json
import threading
import time
import uuid
from collections import deque

app = FastAPI(title="工厂监视与订单系统")

# ---------- 产品类型与寄存器映射 ----------
class Product(str, Enum):
    A = "A"
    B = "B"
    C = "C"

# 寄存器映射：16-18 为订单寄存器
EXEC_REG_MAP: Dict[Product, int] = {Product.A: 16, Product.B: 17, Product.C: 18}

# ---------- 订单模型 ----------
class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # 支持三种产品分别设置数量
    quantity_a: int = Field(ge=0, default=0)
    quantity_b: int = Field(ge=0, default=0)
    quantity_c: int = Field(ge=0, default=0)
    priority: str = "normal"
    deliveryDate: str
    customer: str
    status: str = "pending"  # pending(待执行) / executed(已生产) / returned(已退回)
    createdAt: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # 计算总数量
    def total_quantity(self) -> int:
        return self.quantity_a + self.quantity_b + self.quantity_c

ORDER_FILE = Path("orders.json")

def _load_orders() -> List[Order]:
    if ORDER_FILE.exists():
        return [Order(**o) for o in json.loads(ORDER_FILE.read_text(encoding="utf-8"))]
    return []

def _save_orders(orders: List[Order]) -> None:
    ORDER_FILE.write_text(
        json.dumps([o.model_dump() for o in orders], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

orders = _load_orders()

# ---------- 订单接口 ----------
@app.post("/api/orders", response_model=Order)
def create_order(order: Order):
    # 验证至少有一种产品数量大于0
    if order.total_quantity() == 0:
        raise HTTPException(status_code=400, detail="订单中所有产品数量都为0")
    orders.append(order)
    _save_orders(orders)
    return order

@app.get("/api/orders", response_model=List[Order])
def list_orders():
    return orders

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str, force: bool = False):
    """
    删除订单
    - force=false: 只能删除pending状态的订单
    - force=true: 可以删除任何状态的订单（已累加的值不回退）
    """
    global orders
    # ✅ 修复：使用 == 而不是 !=
    order = next((o for o in orders if o.id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if not force and order.status != "pending":
        raise HTTPException(status_code=409, detail="只能删除待执行的订单，或强制删除")
    
    orders = [o for o in orders if o.id != order_id]
    _save_orders(orders)
    return {"ok": True}

# ---------- 核心：执行订单（生产/退回）----------
@app.post("/api/orders/{order_id}/exec")
def exec_order(order_id: str, action: str = "produce"):
    """
    执行订单：生产(produce)或退回(return)
    - 生产：累加寄存器值
    - 退回：累减寄存器值（确保不小于0）
    """
    order = next((o for o in orders if o.id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 检查状态
    if action == "produce" and order.status != "pending":
        raise HTTPException(status_code=409, detail="订单已处理过，不能重复生产")
    if action == "return" and order.status != "executed":
        raise HTTPException(status_code=409, detail="只能退回已生产的订单")
    
    # 验证至少有一种产品
    if order.total_quantity() == 0:
        raise HTTPException(status_code=400, detail="订单中所有产品数量都为0")
    
    # 处理每个产品类型
    results = {}
    for product, reg in EXEC_REG_MAP.items():
        quantity = getattr(order, f"quantity_{product.lower()}")
        if quantity <= 0:
            continue
            
        old_val = read_var(reg)
        
        if action == "produce":
            new_val = old_val + quantity
        else:  # return
            new_val = max(0, old_val - quantity)  # 确保不为负数
            
        write_var(reg, new_val)
        
        results[product.value] = {
            "reg": reg,
            "old": old_val,
            "new": new_val,
            "quantity": quantity
        }
    
    # 更新状态
    if action == "produce":
        order.status = "executed"
    elif action == "return":
        order.status = "returned"
    
    _save_orders(orders)
    
    return {"ok": True, "action": action, "results": results}

# ---------- 监控接口：包含寄存器0-18 ----------
REG_LIST = list(range(0, 19))

@app.get("/api/registers")
def get_registers():
    """读取所有监控寄存器"""
    return {addr: read_var(addr) for addr in REG_LIST}

@app.post("/api/write")
def write_register(reg: int, val: int):
    write_var(reg, val)
    return {"ok": True, "reg": reg, "val": val}

# ---------- 历史产量数据 ----------
HISTORY_LEN = 144
history = deque(maxlen=HISTORY_LEN)

def init_history():
    now = datetime.now()
    for i in range(HISTORY_LEN):
        history.appendleft({"t": (now - timedelta(minutes=5*i)).strftime("%H:%M"), "v": 0})

def collector():
    while True:
        time.sleep(300)
        history.append({"t": datetime.now().strftime("%H:%M"), "v": read_var(7)})

init_history()
threading.Thread(target=collector, daemon=True).start()

@app.get("/api/history")
def get_history():
    return list(history)

# ---------- 静态文件 & 首页 ----------
@app.get("/")
def root():
    return RedirectResponse("/static/index.html")

app.mount("/static", StaticFiles(directory="static", html=True), name="static")