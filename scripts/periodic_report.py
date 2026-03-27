#!/usr/bin/env python3
"""
定期投资报告
生成日报、周报、月报，综合市场行情与持仓状态给出操作建议。
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.storage import get_all_holdings
from utils.akshare_client import get_fund_info, get_index_daily
from utils.indicators import (
    calc_return, calc_volatility, calc_max_drawdown,
    calc_sharpe_ratio, classify_trend
)
from utils.constants import REPORT_INDICES
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _get_market_snapshot(days: int = 5) -> list[dict]:
    """获取市场快照"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    snapshots = []

    for code, name in REPORT_INDICES.items():
        df = get_index_daily(symbol=code, start_date=start_date, end_date=end_date)
        if df.empty:
            continue
        prices = pd.to_numeric(df["close"] if "close" in df.columns else df.iloc[:, -2],
                               errors="coerce").dropna()
        if prices.empty:
            continue
        current = float(prices.iloc[-1])
        ret = calc_return(prices, days)
        trend = classify_trend(prices)
        snapshots.append({
            "name": name, "current": current,
            "return": ret, "trend": trend
        })
    return snapshots


def _get_portfolio_snapshot(include_prices: bool = False) -> dict:
    """获取持仓快照，include_prices=True 时额外返回净值序列供月报复用"""
    holdings = get_all_holdings()
    if not holdings:
        return {"count": 0, "total_cost": 0, "total_value": 0, "details": []}

    total_cost = 0
    total_value = 0
    details = []

    for code, h in holdings.items():
        nav_df = get_fund_info(code, indicator="累计净值走势")
        current_nav = 0
        ret_recent = 0
        prices = None
        if not nav_df.empty:
            prices = pd.to_numeric(nav_df.iloc[:, 1], errors="coerce").dropna()
            if not prices.empty:
                current_nav = float(prices.iloc[-1])
                ret_recent = calc_return(prices, 5)
            else:
                prices = None

        shares = h.get("shares", 0)
        cost_price = h.get("cost_price", 0)
        invested = shares * cost_price
        value = shares * current_nav

        total_cost += invested
        total_value += value

        profit_rate = ((current_nav - cost_price) / cost_price * 100) if cost_price > 0 else 0

        detail = {
            "code": code,
            "name": h.get("name", ""),
            "value": value,
            "profit_rate": profit_rate,
            "ret_recent": ret_recent,
        }
        if include_prices and prices is not None:
            detail["prices"] = prices
        details.append(detail)

    return {
        "count": len(holdings),
        "total_cost": total_cost,
        "total_value": total_value,
        "total_profit": total_value - total_cost,
        "total_profit_rate": ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0,
        "details": details,
    }


def generate_daily():
    """生成日报"""
    now = datetime.now()
    print(f"\n{'='*60}")
    print(f"📋 每日投资简报 ({now.strftime('%Y-%m-%d')})")
    print(f"{'='*60}")

    # 市场行情
    print(f"\n📊 今日市场:")
    snapshots = _get_market_snapshot(days=1)
    for s in snapshots:
        emoji = "🟢" if s["return"] >= 0 else "🔴"
        print(f"   {emoji} {s['name']}: {s['current']:.2f} ({s['return']:+.2f}%) [{s['trend']}]")

    # 持仓概况
    portfolio = _get_portfolio_snapshot()
    if portfolio["count"] > 0:
        print(f"\n💼 持仓概况:")
        emoji = "🟢" if portfolio["total_profit"] >= 0 else "🔴"
        print(f"   {emoji} 总市值: {portfolio['total_value']:.2f} | 总盈亏: {portfolio['total_profit']:+.2f} ({portfolio['total_profit_rate']:+.2f}%)")

        # 今日变动最大的
        if portfolio["details"]:
            sorted_by_ret = sorted(portfolio["details"], key=lambda x: abs(x["ret_recent"]), reverse=True)
            top = sorted_by_ret[0]
            if abs(top["ret_recent"]) > 0.5:
                emoji = "📈" if top["ret_recent"] > 0 else "📉"
                print(f"   {emoji} 今日变动最大: [{top['code']}] {top['name']} ({top['ret_recent']:+.2f}%)")

    print(f"\n{'='*60}")


def generate_weekly():
    """生成周报"""
    now = datetime.now()
    print(f"\n{'='*60}")
    print(f"📋 每周投资周报 ({now.strftime('%Y-%m-%d')})")
    print(f"{'='*60}")

    # 本周市场回顾
    print(f"\n📊 本周市场回顾:")
    snapshots = _get_market_snapshot(days=5)
    for s in snapshots:
        emoji = "🟢" if s["return"] >= 0 else "🔴"
        print(f"   {emoji} {s['name']}: {s['current']:.2f} (周涨幅: {s['return']:+.2f}%)")

    # 持仓表现
    portfolio = _get_portfolio_snapshot()
    if portfolio["count"] > 0:
        print(f"\n💼 持仓本周表现:")
        for d in sorted(portfolio["details"], key=lambda x: x["ret_recent"], reverse=True):
            emoji = "🟢" if d["ret_recent"] >= 0 else "🔴"
            print(f"   {emoji} [{d['code']}] {d['name']}: 周涨幅 {d['ret_recent']:+.2f}% | 总盈亏 {d['profit_rate']:+.2f}%")

        # 汇总
        print(f"\n📈 持仓汇总:")
        emoji = "🟢" if portfolio["total_profit"] >= 0 else "🔴"
        print(f"   {emoji} 总市值: {portfolio['total_value']:.2f} | 总盈亏: {portfolio['total_profit']:+.2f} ({portfolio['total_profit_rate']:+.2f}%)")

    # 下周展望
    print(f"\n🔮 操作提示:")
    if snapshots:
        avg_ret = np.mean([s["return"] for s in snapshots])
        if avg_ret > 3:
            print("   • 本周市场大幅上涨，注意高位风险")
            print("   • 可适当止盈获利较多的品种")
        elif avg_ret > 0:
            print("   • 市场温和上行，维持现有配置")
            print("   • 关注结构性机会")
        elif avg_ret > -3:
            print("   • 市场小幅调整，不必恐慌")
            print("   • 可考虑逢低加仓优质基金")
        else:
            print("   • 市场大幅回调，控制仓位")
            print("   • 关注低估值品种的布局机会")

    print(f"{'='*60}")


def generate_monthly():
    """生成月报"""
    now = datetime.now()
    print(f"\n{'='*60}")
    print(f"📋 月度投资报告 ({now.strftime('%Y年%m月')})")
    print(f"{'='*60}")

    # 本月市场回顾
    print(f"\n📊 本月市场回顾:")
    end_date = now.strftime("%Y%m%d")
    start_date = (now - timedelta(days=365)).strftime("%Y%m%d")

    for code, name in REPORT_INDICES.items():
        df = get_index_daily(symbol=code, start_date=start_date, end_date=end_date)
        if df.empty:
            continue
        prices = pd.to_numeric(df["close"] if "close" in df.columns else df.iloc[:, -2],
                               errors="coerce").dropna()
        if prices.empty:
            continue

        ret_1m = calc_return(prices, 22)
        ret_3m = calc_return(prices, 66)
        vol = calc_volatility(prices.tail(22))
        dd = calc_max_drawdown(prices.tail(22))

        emoji = "🟢" if ret_1m >= 0 else "🔴"
        print(f"   {emoji} {name}:")
        print(f"     月涨幅: {ret_1m:+.2f}% | 季涨幅: {ret_3m:+.2f}% | 月波动: {vol:.2f}% | 月回撤: {dd:.2f}%")

    # 持仓深度分析（include_prices=True 避免月报重复调用 API）
    portfolio = _get_portfolio_snapshot(include_prices=True)
    if portfolio["count"] > 0:
        print(f"\n💼 持仓月度表现:")
        print(f"{'':>4} {'代码':>8}  {'名称':<14} {'市值':>10} {'总盈亏':>8} {'月收益':>8}")
        print(f"   {'-'*56}")

        for d in portfolio["details"]:
            ret_monthly = 0
            if "prices" in d and d["prices"] is not None and not d["prices"].empty:
                ret_monthly = calc_return(d["prices"], 22)

            name = d["name"][:7]
            print(f"   {d['code']:>8}  {name:<14} {d['value']:>10.2f} {d['profit_rate']:>+7.2f}% {ret_monthly:>+7.2f}%")

        emoji = "🟢" if portfolio["total_profit"] >= 0 else "🔴"
        print(f"\n   {emoji} 汇总: 总市值 {portfolio['total_value']:.2f} | "
              f"总盈亏 {portfolio['total_profit']:+.2f} ({portfolio['total_profit_rate']:+.2f}%)")

    # 下月展望与建议
    print(f"\n🔮 下月展望与建议:")
    if snapshots := _get_market_snapshot(days=22):
        avg_monthly = np.mean([s["return"] for s in snapshots])
        avg_trend = max(set(s["trend"] for s in snapshots), key=lambda x: [s["trend"] for s in snapshots].count(x))

        print(f"   📈 市场趋势: {avg_trend}")
        print(f"   📊 月均涨幅: {avg_monthly:+.2f}%")

        if avg_trend == "上涨":
            print(f"\n   💡 建议:")
            print("   • 市场处于上升趋势，可维持偏多配置")
            print("   • 注意把握节奏，避免追高")
            print("   • 可关注滞涨的低估值品种")
        elif avg_trend == "下跌":
            print(f"\n   💡 建议:")
            print("   • 市场处于下行趋势，控制整体仓位")
            print("   • 增配债券型基金降低组合波动")
            print("   • 优质基金可分批定投，摊低成本")
        else:
            print(f"\n   💡 建议:")
            print("   • 市场方向不明，建议均衡配置")
            print("   • 关注基本面变化和政策信号")
            print("   • 适合网格交易或定投策略")

    print(f"\n⚠️  声明: 以上分析基于历史数据，仅供参考，不构成投资建议")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="定期投资报告")
    subparsers = parser.add_subparsers(dest="command", help="报告类型")

    subparsers.add_parser("daily", help="日报")
    subparsers.add_parser("weekly", help="周报")
    subparsers.add_parser("monthly", help="月报")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "daily": generate_daily,
        "weekly": generate_weekly,
        "monthly": generate_monthly,
    }

    func = cmd_map.get(args.command)
    if func:
        func()


if __name__ == "__main__":
    main()
