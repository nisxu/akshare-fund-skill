#!/usr/bin/env python3
"""
用户持仓管理
支持持仓的增删改查、盈亏计算、汇总展示。
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.storage import (
    add_holding, update_holding, remove_holding,
    get_holding, get_all_holdings
)
from utils.akshare_client import get_fund_info, get_fund_list
from utils.data_models import HoldingRecord, PortfolioSummary
import pandas as pd
from datetime import datetime


def _get_current_nav(fund_code: str) -> float:
    """获取基金当前净值"""
    try:
        nav_df = get_fund_info(fund_code, indicator="单位净值走势")
        if not nav_df.empty:
            return float(nav_df.iloc[-1, 1])
    except Exception:
        pass
    return 0.0


def _get_fund_name(fund_code: str) -> str:
    """获取基金名称"""
    try:
        fund_list = get_fund_list()
        if not fund_list.empty:
            matched = fund_list[fund_list.iloc[:, 0].astype(str) == str(fund_code)]
            if not matched.empty:
                return str(matched.iloc[0, 1])
    except Exception:
        pass
    return ""


def cmd_add(args):
    """添加持仓"""
    if args.shares <= 0:
        print("❌ 份额必须为正数")
        return
    if args.cost <= 0:
        print("❌ 买入成本价必须为正数")
        return
    name = args.name or _get_fund_name(args.code)
    holding = add_holding(
        code=args.code,
        name=name,
        shares=args.shares,
        cost_price=args.cost,
        buy_date=args.date or "",
        target_weight=args.weight or 0,
        notes=args.notes or "",
    )
    print(f"✅ 已添加持仓: [{args.code}] {name}")
    print(f"   份额: {holding['shares']:.2f}, 成本: {holding['cost_price']:.4f}")
    print(f"   总投入: {holding['total_cost']:.2f}")


def cmd_update(args):
    """更新持仓"""
    kwargs = {}
    if args.shares is not None:
        kwargs["shares"] = args.shares
    if args.cost is not None:
        kwargs["cost_price"] = args.cost
    if args.weight is not None:
        kwargs["target_weight"] = args.weight
    if args.notes is not None:
        kwargs["notes"] = args.notes

    if not kwargs:
        print("❌ 未指定更新内容")
        return

    result = update_holding(args.code, **kwargs)
    if result:
        print(f"✅ 已更新持仓: [{args.code}] {result.get('name', '')}")
        for k, v in kwargs.items():
            print(f"   {k}: {v}")


def cmd_remove(args):
    """删除持仓"""
    holding = get_holding(args.code)
    if holding:
        name = holding.get("name", "")
        if remove_holding(args.code):
            print(f"✅ 已删除持仓: [{args.code}] {name}")
    else:
        print(f"❌ 持仓中不存在基金 {args.code}")


def cmd_list(args):
    """列出所有持仓"""
    holdings = get_all_holdings()
    if not holdings:
        print("📭 当前无持仓记录")
        return

    print(f"\n{'='*70}")
    print(f"📋 我的持仓 (共 {len(holdings)} 只基金)")
    print(f"{'='*70}")

    total_cost = 0
    total_value = 0

    for code, h in holdings.items():
        nav = _get_current_nav(code)
        shares = h.get("shares", 0)
        cost_price = h.get("cost_price", 0)
        current_value = shares * nav if nav > 0 else 0
        invested = shares * cost_price
        profit = current_value - invested
        profit_rate = (profit / invested * 100) if invested > 0 else 0

        total_cost += invested
        total_value += current_value

        profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
        rate_str = f"+{profit_rate:.2f}%" if profit_rate >= 0 else f"{profit_rate:.2f}%"
        emoji = "🟢" if profit >= 0 else "🔴"

        print(f"\n{emoji} [{code}] {h.get('name', '')}")
        print(f"   份额: {shares:.2f} | 成本: {cost_price:.4f} | 现价: {nav:.4f}")
        print(f"   投入: {invested:.2f} | 市值: {current_value:.2f}")
        print(f"   盈亏: {profit_str} ({rate_str})")
        if h.get("buy_date"):
            print(f"   买入日期: {h['buy_date']}")
        if h.get("target_weight"):
            print(f"   目标配比: {h['target_weight']:.1f}%")

    total_profit = total_value - total_cost
    total_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0

    print(f"\n{'='*70}")
    emoji = "🟢" if total_profit >= 0 else "🔴"
    print(f"{emoji} 总投入: {total_cost:.2f} | 总市值: {total_value:.2f}")
    profit_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    rate_str = f"+{total_rate:.2f}%" if total_rate >= 0 else f"{total_rate:.2f}%"
    print(f"   总盈亏: {profit_str} ({rate_str})")
    print(f"{'='*70}")


def cmd_summary(args):
    """持仓汇总（JSON 输出）"""
    holdings = get_all_holdings()
    if not holdings:
        print(json.dumps({"message": "无持仓数据"}, ensure_ascii=False))
        return

    summary = PortfolioSummary()
    summary.holding_count = len(holdings)

    for code, h in holdings.items():
        nav = _get_current_nav(code)
        record = HoldingRecord(
            code=code,
            name=h.get("name", ""),
            shares=h.get("shares", 0),
            cost_price=h.get("cost_price", 0),
            current_nav=nav,
            buy_date=h.get("buy_date", ""),
            target_weight=h.get("target_weight", 0),
        )
        record.update_profit()
        summary.holdings.append(record)
        summary.total_cost += record.total_cost
        summary.total_value += record.current_value
        summary.total_profit += record.profit

    if summary.total_cost > 0:
        summary.total_profit_rate = (summary.total_profit / summary.total_cost) * 100
    summary.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="持仓管理")
    subparsers = parser.add_subparsers(dest="command", help="操作命令")

    # add
    p_add = subparsers.add_parser("add", help="添加持仓")
    p_add.add_argument("--code", required=True, help="基金代码")
    p_add.add_argument("--shares", type=float, required=True, help="持有份额")
    p_add.add_argument("--cost", type=float, required=True, help="买入成本价(每份)")
    p_add.add_argument("--name", default="", help="基金名称(可选，自动获取)")
    p_add.add_argument("--date", default="", help="买入日期(YYYY-MM-DD)")
    p_add.add_argument("--weight", type=float, default=0, help="目标配比(%)")
    p_add.add_argument("--notes", default="", help="备注")
    p_add.set_defaults(func=cmd_add)

    # update
    p_update = subparsers.add_parser("update", help="更新持仓")
    p_update.add_argument("--code", required=True, help="基金代码")
    p_update.add_argument("--shares", type=float, default=None, help="新份额")
    p_update.add_argument("--cost", type=float, default=None, help="新成本价")
    p_update.add_argument("--weight", type=float, default=None, help="目标配比(%)")
    p_update.add_argument("--notes", default=None, help="备注")
    p_update.set_defaults(func=cmd_update)

    # remove
    p_remove = subparsers.add_parser("remove", help="删除持仓")
    p_remove.add_argument("--code", required=True, help="基金代码")
    p_remove.set_defaults(func=cmd_remove)

    # list
    p_list = subparsers.add_parser("list", help="查看持仓")
    p_list.set_defaults(func=cmd_list)

    # summary
    p_summary = subparsers.add_parser("summary", help="持仓汇总(JSON)")
    p_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
