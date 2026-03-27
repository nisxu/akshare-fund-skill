#!/usr/bin/env python3
"""
智能调仓建议
提供止盈止损、再平衡、优化替换等调仓建议。
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.portfolio_helpers import load_holdings_with_prices
from utils.indicators import (
    calc_return, calc_sharpe_ratio, calc_max_drawdown, calc_volatility
)
import numpy as np


def check_all(args=None):
    """综合检查所有调仓信号"""
    data = load_holdings_with_prices()
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("🔍 调仓信号全面检查")
    print(f"{'='*60}")

    alerts = []

    for code, info in data.items():
        # 止盈检查
        if info["profit_rate"] >= 30:
            alerts.append({
                "type": "🟢 止盈",
                "code": code,
                "name": info["name"],
                "detail": f"浮盈 {info['profit_rate']:.1f}%，建议考虑部分止盈",
                "priority": "high"
            })

        # 止损检查
        if info["profit_rate"] <= -15:
            alerts.append({
                "type": "🔴 止损",
                "code": code,
                "name": info["name"],
                "detail": f"浮亏 {info['profit_rate']:.1f}%，建议评估是否止损",
                "priority": "high"
            })

        # 回撤预警
        dd = calc_max_drawdown(info["prices"].tail(60))
        if dd < -20:
            alerts.append({
                "type": "⚠️ 回撤",
                "code": code,
                "name": info["name"],
                "detail": f"近60日最大回撤 {dd:.1f}%，需关注",
                "priority": "medium"
            })

        # 夏普比率预警
        sharpe = calc_sharpe_ratio(info["prices"])
        if sharpe < 0:
            alerts.append({
                "type": "📉 质量",
                "code": code,
                "name": info["name"],
                "detail": f"夏普比率 {sharpe:.2f}，风险收益比不佳",
                "priority": "medium"
            })

    # 配置偏离检查
    total_value = sum(info["current_value"] for info in data.values())
    for code, info in data.items():
        if info["target_weight"] > 0 and total_value > 0:
            actual_weight = (info["current_value"] / total_value) * 100
            deviation = actual_weight - info["target_weight"]
            if abs(deviation) > 5:
                direction = "超配" if deviation > 0 else "低配"
                alerts.append({
                    "type": "⚖️ 偏离",
                    "code": code,
                    "name": info["name"],
                    "detail": f"实际 {actual_weight:.1f}% vs 目标 {info['target_weight']:.1f}% ({direction} {abs(deviation):.1f}%)",
                    "priority": "low"
                })

    if not alerts:
        print("\n✅ 当前持仓状态良好，无需调仓")
    else:
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda x: priority_order.get(x["priority"], 9))

        for alert in alerts:
            print(f"\n{alert['type']} [{alert['code']}] {alert['name']}")
            print(f"   {alert['detail']}")

    print(f"\n{'='*60}")


def check_stop_loss(threshold: float = -10):
    """止损检查"""
    data = load_holdings_with_prices()
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print(f"🔴 止损检查 (阈值: {threshold}%)")
    print(f"{'='*60}")

    found = False
    for code, info in data.items():
        if info["profit_rate"] <= threshold:
            found = True
            loss = info["invested"] - info["current_value"]
            print(f"\n⚠️  [{code}] {info['name']}")
            print(f"   浮亏: {info['profit_rate']:.2f}% (亏损金额: {loss:.2f})")
            print(f"   成本: {info['cost_price']:.4f} → 现价: {info['current_nav']:.4f}")
            print(f"   建议: 评估基金基本面，若无好转迹象建议止损")

    if not found:
        print(f"\n✅ 无基金触发止损线 ({threshold}%)")
    print(f"{'='*60}")


def check_take_profit(threshold: float = 30):
    """止盈检查"""
    data = load_holdings_with_prices()
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print(f"🟢 止盈检查 (阈值: +{threshold}%)")
    print(f"{'='*60}")

    found = False
    for code, info in data.items():
        if info["profit_rate"] >= threshold:
            found = True
            gain = info["current_value"] - info["invested"]
            print(f"\n🎯 [{code}] {info['name']}")
            print(f"   浮盈: +{info['profit_rate']:.2f}% (盈利金额: {gain:.2f})")
            print(f"   成本: {info['cost_price']:.4f} → 现价: {info['current_nav']:.4f}")
            print(f"   建议: 可考虑卖出 30-50% 锁定利润，剩余继续持有")

    if not found:
        print(f"\n📊 无基金触发止盈线 (+{threshold}%)")
    print(f"{'='*60}")


def check_rebalance():
    """再平衡建议"""
    data = load_holdings_with_prices()
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("⚖️  再平衡建议")
    print(f"{'='*60}")

    total_value = sum(info["current_value"] for info in data.values())
    if total_value <= 0:
        print("总市值为零，无法计算")
        return

    has_target = any(info["target_weight"] > 0 for info in data.values())
    if not has_target:
        print("\n未设置目标配比，建议先为各持仓设置目标权重")
        print("使用: python3 scripts/portfolio_manager.py update --code <代码> --weight <比例>")
        print(f"{'='*60}")
        return

    print(f"\n{'代码':>8}  {'名称':<14} {'实际':>6} {'目标':>6} {'偏离':>7} {'操作':>8}")
    print(f"   {'-'*60}")

    for code, info in data.items():
        if info["target_weight"] <= 0:
            continue
        actual = (info["current_value"] / total_value) * 100
        target = info["target_weight"]
        deviation = actual - target
        amount = abs(deviation) / 100 * total_value

        if deviation > 3:
            action = f"卖出 {amount:.0f}"
        elif deviation < -3:
            action = f"买入 {amount:.0f}"
        else:
            action = "持有"

        name = info["name"][:7]
        print(f"   {code:>8}  {name:<14} {actual:>5.1f}% {target:>5.1f}% {deviation:>+6.1f}% {action:>8}")

    print(f"\n💡 偏离超过 ±3% 的建议调整")
    print(f"{'='*60}")


def check_optimize():
    """优化替换建议"""
    data = load_holdings_with_prices()
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("🔄 优化替换建议")
    print(f"{'='*60}")

    for code, info in data.items():
        sharpe = calc_sharpe_ratio(info["prices"])
        vol = calc_volatility(info["prices"])
        dd = calc_max_drawdown(info["prices"])
        ret_6m = calc_return(info["prices"], 132)

        print(f"\n📋 [{code}] {info['name']}")
        print(f"   类型: {info['fund_type']} | 近6月: {ret_6m:+.2f}% | 夏普: {sharpe:.2f} | 最大回撤: {dd:.2f}%")

        # 判断是否需要优化
        needs_optimize = False
        reasons = []

        if sharpe < 0.3:
            needs_optimize = True
            reasons.append("夏普比率偏低")
        if dd < -30:
            needs_optimize = True
            reasons.append("回撤过大")
        if ret_6m < -10:
            needs_optimize = True
            reasons.append("近期收益较差")

        if needs_optimize:
            print(f"   ⚠️ 建议关注: {', '.join(reasons)}")
            print(f"   💡 可考虑在同类基金中寻找更优替代品")
            print(f"   🔍 使用: python3 scripts/fund_screener.py --type {info['fund_type']} --sort return_6m --top 10")
        else:
            print(f"   ✅ 表现良好，建议继续持有")

    print(f"\n{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="智能调仓建议")
    subparsers = parser.add_subparsers(dest="command", help="建议类型")

    subparsers.add_parser("check", help="综合检查")

    p_sl = subparsers.add_parser("stop-loss", help="止损检查")
    p_sl.add_argument("--threshold", type=float, default=-10, help="止损阈值(%)")

    p_tp = subparsers.add_parser("take-profit", help="止盈检查")
    p_tp.add_argument("--threshold", type=float, default=30, help="止盈阈值(%)")

    subparsers.add_parser("rebalance", help="再平衡建议")
    subparsers.add_parser("optimize", help="优化替换建议")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "check":
        check_all()
    elif args.command == "stop-loss":
        check_stop_loss(args.threshold)
    elif args.command == "take-profit":
        check_take_profit(args.threshold)
    elif args.command == "rebalance":
        check_rebalance()
    elif args.command == "optimize":
        check_optimize()


if __name__ == "__main__":
    main()
