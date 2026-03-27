#!/usr/bin/env python3
"""
持仓分析与诊断
提供资产配置分析、风险评估、相关性分析和健康度评分。
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.portfolio_helpers import load_holdings_with_prices
from utils.indicators import (
    calc_return, calc_volatility, calc_max_drawdown, calc_sharpe_ratio,
    calc_correlation_matrix, calc_var
)
import pandas as pd
import numpy as np


def analyze_overview():
    """持仓概览分析"""
    data = load_holdings_with_prices(calc_profit=False)
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("📊 持仓概览分析")
    print(f"{'='*60}")

    total_value = 0
    total_cost = 0
    fund_values = {}

    for code, info in data.items():
        value = info["shares"] * info["current_nav"]
        cost = info["shares"] * info["cost_price"]
        total_value += value
        total_cost += cost
        fund_values[code] = value

    # 各基金占比
    print(f"\n💰 总市值: {total_value:.2f} | 总投入: {total_cost:.2f}")
    profit = total_value - total_cost
    rate = (profit / total_cost * 100) if total_cost > 0 else 0
    emoji = "🟢" if profit >= 0 else "🔴"
    print(f"{emoji} 总盈亏: {profit:+.2f} ({rate:+.2f}%)")

    print(f"\n📈 持仓配置:")
    for code, info in data.items():
        value = fund_values[code]
        weight = (value / total_value * 100) if total_value > 0 else 0
        target = info["target_weight"]
        deviation = weight - target if target > 0 else 0

        print(f"   [{code}] {info['name']}")
        print(f"     类型: {info['fund_type']} | 市值: {value:.2f} | 占比: {weight:.1f}%", end="")
        if target > 0:
            print(f" (目标: {target:.1f}%, 偏离: {deviation:+.1f}%)")
        else:
            print()

    # 类型分布
    type_dist = {}
    for code, info in data.items():
        ft = info["fund_type"] or "未知"
        type_dist[ft] = type_dist.get(ft, 0) + fund_values.get(code, 0)

    print(f"\n🏷️  类型分布:")
    for ft, val in sorted(type_dist.items(), key=lambda x: -x[1]):
        pct = (val / total_value * 100) if total_value > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"   {ft:>8}: {pct:5.1f}% {bar}")

    print(f"{'='*60}")


def analyze_risk():
    """风险评估"""
    data = load_holdings_with_prices(calc_profit=False)
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("⚠️  持仓风险评估")
    print(f"{'='*60}")

    total_value = sum(info["shares"] * info["current_nav"] for info in data.values())

    # 组合收益率序列
    weighted_returns = None
    all_prices = {}

    for code, info in data.items():
        prices = info["prices"]
        weight = (info["shares"] * info["current_nav"]) / total_value if total_value > 0 else 0
        returns = prices.pct_change().dropna()

        all_prices[f"{code} {info['name']}"] = prices

        if weighted_returns is None:
            weighted_returns = returns * weight
        else:
            aligned = returns.reindex(weighted_returns.index, fill_value=0)
            weighted_returns = weighted_returns + aligned * weight

    if weighted_returns is not None and not weighted_returns.empty:
        # 组合层面指标
        cum_returns = (1 + weighted_returns).cumprod()
        portfolio_prices = cum_returns

        port_vol = calc_volatility(portfolio_prices)
        port_dd = calc_max_drawdown(portfolio_prices)
        port_sharpe = calc_sharpe_ratio(portfolio_prices)
        port_var = calc_var(portfolio_prices)

        print(f"\n📊 组合整体风险:")
        print(f"   年化波动率: {port_vol:.2f}%")
        print(f"   最大回撤: {port_dd:.2f}%")
        print(f"   夏普比率: {port_sharpe}")
        print(f"   95% VaR: {port_var:.2f}%")

    # 单基金风险
    print(f"\n📋 个基风险指标:")
    print(f"   {'代码':>8}  {'名称':<16} {'波动率':>8} {'最大回撤':>8} {'夏普':>6}")
    print(f"   {'-'*56}")

    for code, info in data.items():
        vol = calc_volatility(info["prices"])
        dd = calc_max_drawdown(info["prices"])
        sharpe = calc_sharpe_ratio(info["prices"])
        name = info["name"][:8]
        print(f"   {code:>8}  {name:<16} {vol:>7.2f}% {dd:>7.2f}% {sharpe:>6.2f}")

    print(f"{'='*60}")


def analyze_correlation():
    """相关性分析"""
    data = load_holdings_with_prices(calc_profit=False)
    if not data or len(data) < 2:
        print("📭 需要至少 2 只基金才能进行相关性分析")
        return

    print(f"\n{'='*60}")
    print("🔗 持仓相关性分析")
    print(f"{'='*60}")

    price_dict = {}
    name_map = {}
    for code, info in data.items():
        short_key = code
        price_dict[short_key] = info["prices"]
        name_map[short_key] = info["name"]

    corr_matrix = calc_correlation_matrix(price_dict)
    if corr_matrix.empty:
        print("数据不足，无法计算相关性")
        return

    # 打印相关性矩阵
    codes = list(corr_matrix.columns)
    header = f"{'':>10}" + "".join(f"{c:>10}" for c in codes)
    print(f"\n{header}")
    print(f"   {'-'*(10*len(codes)+10)}")

    for idx in codes:
        row = f"{idx:>10}"
        for col in codes:
            val = corr_matrix.loc[idx, col]
            if val >= 0.7:
                row += f"  🔴{val:>5.3f}"
            elif val >= 0.4:
                row += f"  🟡{val:>5.3f}"
            else:
                row += f"  🟢{val:>5.3f}"
        print(row)

    # 高相关性警告
    print(f"\n💡 分析:")
    high_corr = []
    for i, c1 in enumerate(codes):
        for j, c2 in enumerate(codes):
            if i < j and corr_matrix.loc[c1, c2] >= 0.7:
                high_corr.append((c1, c2, corr_matrix.loc[c1, c2]))

    if high_corr:
        print("   ⚠️ 以下持仓高度相关，分散效果不佳:")
        for c1, c2, val in high_corr:
            print(f"     {c1}({name_map[c1]}) ↔ {c2}({name_map[c2]}): {val:.3f}")
    else:
        print("   ✅ 持仓间相关性适中，分散化较好")

    print(f"{'='*60}")


def analyze_health():
    """健康度评分"""
    data = load_holdings_with_prices(calc_profit=False)
    if not data:
        print("📭 无持仓数据")
        return

    print(f"\n{'='*60}")
    print("🏥 持仓健康度评分")
    print(f"{'='*60}")

    scores = {
        "分散性": 0,
        "收益质量": 0,
        "风险控制": 0,
        "配置均衡": 0,
    }

    total_value = sum(info["shares"] * info["current_nav"] for info in data.values())

    # 1. 分散性评分 (25分)
    n_funds = len(data)
    type_set = set(info["fund_type"] for info in data.values() if info["fund_type"])

    if n_funds >= 5 and len(type_set) >= 3:
        scores["分散性"] = 25
    elif n_funds >= 3 and len(type_set) >= 2:
        scores["分散性"] = 20
    elif n_funds >= 2:
        scores["分散性"] = 15
    else:
        scores["分散性"] = 5

    # 2. 收益质量评分 (25分)
    sharpe_scores = []
    for code, info in data.items():
        sharpe = calc_sharpe_ratio(info["prices"])
        sharpe_scores.append(sharpe)

    avg_sharpe = np.mean(sharpe_scores) if sharpe_scores else 0
    if avg_sharpe >= 1.5:
        scores["收益质量"] = 25
    elif avg_sharpe >= 1.0:
        scores["收益质量"] = 20
    elif avg_sharpe >= 0.5:
        scores["收益质量"] = 15
    elif avg_sharpe >= 0:
        scores["收益质量"] = 10
    else:
        scores["收益质量"] = 5

    # 3. 风险控制评分 (25分)
    max_dds = []
    for code, info in data.items():
        dd = abs(calc_max_drawdown(info["prices"]))
        max_dds.append(dd)

    avg_dd = np.mean(max_dds) if max_dds else 0
    if avg_dd <= 10:
        scores["风险控制"] = 25
    elif avg_dd <= 20:
        scores["风险控制"] = 20
    elif avg_dd <= 30:
        scores["风险控制"] = 15
    elif avg_dd <= 40:
        scores["风险控制"] = 10
    else:
        scores["风险控制"] = 5

    # 4. 配置均衡评分 (25分)
    weights = [(info["shares"] * info["current_nav"]) / total_value for info in data.values()
               if total_value > 0]
    if weights:
        # 集中度：最大权重占比
        max_weight = max(weights)
        if max_weight <= 0.3:
            scores["配置均衡"] = 25
        elif max_weight <= 0.5:
            scores["配置均衡"] = 20
        elif max_weight <= 0.7:
            scores["配置均衡"] = 15
        else:
            scores["配置均衡"] = 10

    total_score = sum(scores.values())

    # 输出
    print(f"\n{'维度':<12} {'得分':>6} {'满分':>6}")
    print(f"{'-'*30}")
    for dim, score in scores.items():
        bar = "█" * (score // 5) + "░" * ((25 - score) // 5)
        print(f"{dim:<12} {score:>6} {'/25':>6}  {bar}")
    print(f"{'-'*30}")

    grade = "🏆 优秀" if total_score >= 80 else "👍 良好" if total_score >= 60 else "⚠️ 一般" if total_score >= 40 else "❌ 较差"
    print(f"{'总分':<12} {total_score:>6} {'/100':>6}  {grade}")

    # 建议
    print(f"\n💡 改进建议:")
    if scores["分散性"] < 20:
        print("   • 建议增加持仓数量和类型，提升分散化程度")
    if scores["收益质量"] < 15:
        print("   • 部分基金风险收益比不佳，建议考虑替换")
    if scores["风险控制"] < 15:
        print("   • 整体回撤较大，建议增配债券型/货币型基金降低风险")
    if scores["配置均衡"] < 15:
        print("   • 持仓集中度过高，建议适当分散单只基金权重")
    if total_score >= 80:
        print("   • 整体配置良好，继续保持！")

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="持仓分析与诊断")
    subparsers = parser.add_subparsers(dest="command", help="分析类型")

    subparsers.add_parser("overview", help="持仓概览")
    subparsers.add_parser("risk", help="风险评估")
    subparsers.add_parser("correlation", help="相关性分析")
    subparsers.add_parser("health", help="健康度评分")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "overview": analyze_overview,
        "risk": analyze_risk,
        "correlation": analyze_correlation,
        "health": analyze_health,
    }

    func = cmd_map.get(args.command)
    if func:
        func()


if __name__ == "__main__":
    main()
