"""
数据持久化模块
负责用户持仓数据的读写与管理。
"""

import json
import os
import re
import tempfile
from typing import Optional
from datetime import datetime

# 数据文件路径（相对于脚本所在目录）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_SCRIPT_DIR)), "data")
PORTFOLIO_FILE = os.path.join(_DATA_DIR, "portfolio.json")


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(_DATA_DIR, exist_ok=True)


def load_portfolio() -> dict:
    """
    加载持仓数据
    返回格式: {
        "holdings": { "基金代码": { ...持仓信息... }, ... },
        "update_time": "2024-01-01 12:00:00"
    }
    """
    _ensure_data_dir()
    if not os.path.exists(PORTFOLIO_FILE):
        return {"holdings": {}, "update_time": ""}
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "holdings" not in data:
                data = {"holdings": data, "update_time": ""}
            return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"[警告] 读取持仓数据失败: {e}")
        return {"holdings": {}, "update_time": ""}


def _validate_fund_code(code: str) -> bool:
    """校验基金代码格式（6位数字）"""
    return bool(re.match(r"^\d{6}$", str(code)))


def save_portfolio(data: dict):
    """保存持仓数据（原子写入：先写临时文件再 rename，避免写入中断导致数据丢失）"""
    _ensure_data_dir()
    data["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        fd, tmp_path = tempfile.mkstemp(dir=_DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, PORTFOLIO_FILE)
        except Exception:
            os.unlink(tmp_path)
            raise
    except IOError as e:
        print(f"[错误] 保存持仓数据失败: {e}")


def add_holding(code: str, name: str = "", shares: float = 0,
                cost_price: float = 0, buy_date: str = "",
                target_weight: float = 0, notes: str = "") -> dict:
    """添加持仓记录"""
    if not _validate_fund_code(code):
        raise ValueError(f"基金代码格式无效: '{code}'，应为6位数字")
    if shares <= 0:
        raise ValueError(f"份额必须为正数，当前值: {shares}")
    if cost_price <= 0:
        raise ValueError(f"成本价必须为正数，当前值: {cost_price}")
    data = load_portfolio()
    if not buy_date:
        buy_date = datetime.now().strftime("%Y-%m-%d")

    holding = {
        "code": code,
        "name": name,
        "shares": shares,
        "cost_price": cost_price,
        "total_cost": shares * cost_price,
        "buy_date": buy_date,
        "target_weight": target_weight,
        "notes": notes,
    }

    if code in data["holdings"]:
        # 合并持仓：加权平均成本
        existing = data["holdings"][code]
        old_shares = existing.get("shares", 0)
        old_cost = existing.get("cost_price", 0)
        new_total_shares = old_shares + shares
        if new_total_shares > 0:
            holding["cost_price"] = (old_shares * old_cost + shares * cost_price) / new_total_shares
            holding["shares"] = new_total_shares
            holding["total_cost"] = new_total_shares * holding["cost_price"]
        if not name:
            holding["name"] = existing.get("name", "")
        # 合并时保留原始买入日期
        holding["buy_date"] = existing.get("buy_date", buy_date)

    data["holdings"][code] = holding
    save_portfolio(data)
    return holding


def update_holding(code: str, **kwargs) -> Optional[dict]:
    """更新持仓信息"""
    data = load_portfolio()
    if code not in data["holdings"]:
        print(f"[错误] 持仓中不存在基金 {code}")
        return None
    holding = data["holdings"][code]
    # 禁止修改 code 字段，防止 key 与 value 不一致
    immutable_fields = {"code"}
    for key, value in kwargs.items():
        if key in immutable_fields:
            print(f"[警告] 字段 '{key}' 不允许修改")
            continue
        if key in holding:
            holding[key] = value
    # 重算总成本
    holding["total_cost"] = holding["shares"] * holding["cost_price"]
    data["holdings"][code] = holding
    save_portfolio(data)
    return holding


def remove_holding(code: str) -> bool:
    """删除持仓"""
    data = load_portfolio()
    if code not in data["holdings"]:
        print(f"[错误] 持仓中不存在基金 {code}")
        return False
    del data["holdings"][code]
    save_portfolio(data)
    return True


def get_holding(code: str) -> Optional[dict]:
    """获取单只基金持仓"""
    data = load_portfolio()
    return data["holdings"].get(code)


def get_all_holdings() -> dict:
    """获取全部持仓"""
    data = load_portfolio()
    return data["holdings"]


def clear_all_holdings() -> bool:
    """清空所有持仓"""
    save_portfolio({"holdings": {}, "update_time": ""})
    return True
