#!/usr/bin/env python3
"""
市场行情研判
提供大盘行情、估值分位、市场情绪等分析。
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.akshare_client import get_index_daily
from utils.indicators import (
    calc_return, calc_volatility, calc_max_drawdown, classify_trend,
    calc_pe_percentile
)
from utils.constants import MAJOR_INDICES
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def market_overview():
    """市场概览"""
    print(f"\n{'='*70}")
    print(f"📊 市场行情概览 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'='*70}")

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    print(f"\n{'指数':>12} {'最新':>10} {'涨跌幅':>8} {'近1月':>8} {'近3月':>8} {'近6月':>8} {'趋势':>6}")
    print(f"   {'-'*68}")

    for code, name in MAJOR_INDICES.items():
        df = get_index_daily(symbol=code, start_date=start_date, end_date=end_date)
        if df.empty:
            print(f"   {name:>12} {'数据获取失败'}")
            continue

        prices = pd.to_numeric(df["close"] if "close" in df.columns else df.iloc[:, -2],
                               errors="coerce").dropna()
        if prices.empty:
            continue

        current = float(prices.iloc[-1])
        prev = float(prices.iloc[-2]) if len(prices) > 1 else current
        daily_chg = ((current - prev) / prev) * 100

        ret_1m = calc_return(prices, 22)
        ret_3m = calc_return(prices, 66)
        ret_6m = calc_return(prices, 132)
        trend = classify_trend(prices)

        daily_emoji = "🟢" if daily_chg >= 0 else "🔴"
        print(f"   {name:>10} {current:>10.2f} {daily_emoji}{daily_chg:>+6.2f}% {ret_1m:>+7.2f}% {ret_3m:>+7.2f}% {ret_6m:>+7.2f}% {trend:>4}")

    print(f"{'='*70}")


def valuation_analysis():
    """估值分位分析"""
    print(f"\n{'='*60}")
    print("📏 主要指数估值分位")
    print(f"{'='*60}")

    # 用近5年数据计算估值分位
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y%m%d")

    key_indices = {
        "000300": "沪深300",
        "000905": "中证500",
        "399006": "创业板指",
        "000852": "中证1000",
    }

    print(f"\n{'指数':>12} {'当前点位':>10} {'5年最低':>10} {'5年最高':>10} {'分位':>8} {'评估':>6}")
    print(f"   {'-'*58}")

    for code, name in key_indices.items():
        df = get_index_daily(symbol=code, start_date=start_date, end_date=end_date)
        if df.empty:
            continue

        prices = pd.to_numeric(df["close"] if "close" in df.columns else df.iloc[:, -2],
                               errors="coerce").dropna()
        if prices.empty or len(prices) < 100:
            continue

        current = float(prices.iloc[-1])
        low_5y = float(prices.min())
        high_5y = float(prices.max())

        # 简化的分位计算（基于价格分位近似估值分位）
        percentile = (prices < current).sum() / len(prices) * 100

        if percentile <= 20:
            assessment = "🟢低估"
        elif percentile <= 40:
            assessment = "🔵偏低"
        elif percentile <= 60:
            assessment = "🟡适中"
        elif percentile <= 80:
            assessment = "🟠偏高"
        else:
            assessment = "🔴高估"

        print(f"   {name:>10} {current:>10.2f} {low_5y:>10.2f} {high_5y:>10.2f} {percentile:>6.1f}% {assessment}")

    print(f"\n💡 说明: 分位越低表示越接近历史低点，可能是较好的建仓时机")
    print(f"   20%以下=低估区域 | 20-40%=偏低 | 40-60%=适中 | 60-80%=偏高 | 80%以上=高估区域")
    print(f"{'='*60}")


def sentiment_analysis():
    """市场情绪综合分析"""
    print(f"\n{'='*60}")
    print("🎭 市场情绪综合分析")
    print(f"{'='*60}")

    end_date = datetime.now().strftime("%Y%m%d")
    start_date_long = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    # 以沪深300为代表分析
    df = get_index_daily(symbol="000300", start_date=start_date_long, end_date=end_date)
    if df.empty:
        print("数据获取失败")
        return

    prices = pd.to_numeric(df["close"] if "close" in df.columns else df.iloc[:, -2],
                           errors="coerce").dropna()
    if prices.empty:
        print("数据不足")
        return

    # 指标计算
    current = float(prices.iloc[-1])
    ma5 = float(prices.tail(5).mean())
    ma20 = float(prices.tail(20).mean())
    ma60 = float(prices.tail(60).mean())
    ma120 = float(prices.tail(120).mean()) if len(prices) >= 120 else ma60

    vol_recent = calc_volatility(prices.tail(20))
    vol_long = calc_volatility(prices.tail(120))
    dd_recent = calc_max_drawdown(prices.tail(60))
    ret_1m = calc_return(prices, 22)
    ret_3m = calc_return(prices, 66)
    trend = classify_trend(prices)

    # 多空信号计分
    score = 50  # 中性起点

    # 均线系统
    if current > ma5 > ma20 > ma60:
        score += 15
        ma_signal = "多头排列"
    elif current < ma5 < ma20 < ma60:
        score -= 15
        ma_signal = "空头排列"
    elif current > ma20:
        score += 5
        ma_signal = "站上20日线"
    else:
        score -= 5
        ma_signal = "跌破20日线"

    # 动量
    if ret_1m > 5:
        score += 10
    elif ret_1m > 0:
        score += 5
    elif ret_1m > -5:
        score -= 5
    else:
        score -= 10

    # 波动率
    if vol_recent > vol_long * 1.5:
        score -= 10
        vol_signal = "波动放大"
    elif vol_recent < vol_long * 0.7:
        score += 5
        vol_signal = "波动收敛"
    else:
        vol_signal = "波动正常"

    # 回撤
    if dd_recent < -15:
        score -= 10
    elif dd_recent < -10:
        score -= 5

    # 限制范围
    score = max(0, min(100, score))

    # 情绪判断
    if score >= 75:
        sentiment = "🟢 极度贪婪"
        advice = "市场情绪过热，注意风险，不宜追高"
    elif score >= 60:
        sentiment = "🟢 乐观"
        advice = "市场情绪偏多，可适当持有"
    elif score >= 40:
        sentiment = "🟡 中性"
        advice = "市场方向不明，建议观望或小仓位操作"
    elif score >= 25:
        sentiment = "🔴 悲观"
        advice = "市场情绪偏空，但可关注逢低布局机会"
    else:
        sentiment = "🔴 极度恐惧"
        advice = "市场情绪极度恐慌，长期投资者可考虑分批建仓"

    # 输出
    print(f"\n🎯 沪深300 情绪指标:")
    print(f"   当前点位: {current:.2f}")
    print(f"   趋势判断: {trend}")
    print(f"   均线信号: {ma_signal}")
    print(f"   波动状态: {vol_signal}")
    print(f"   近1月涨幅: {ret_1m:+.2f}%")
    print(f"   近3月涨幅: {ret_3m:+.2f}%")
    print(f"   近60日最大回撤: {dd_recent:.2f}%")

    # 情绪仪表盘
    print(f"\n🌡️  情绪温度计: {score}/100")
    bar_full = int(score / 5)
    bar_empty = 20 - bar_full
    if score >= 60:
        bar_char = "🟢"
    elif score >= 40:
        bar_char = "🟡"
    else:
        bar_char = "🔴"
    bar = bar_char * bar_full + "⬜" * bar_empty
    print(f"   {bar}")
    print(f"   情绪: {sentiment}")

    print(f"\n💡 操作建议: {advice}")

    print(f"\n📋 综合建议:")
    if score >= 70:
        print("   • 权益仓位可适当降低，锁定部分利润")
        print("   • 增加债券型/货币型基金配置")
        print("   • 避免追高热门主题基金")
    elif score >= 40:
        print("   • 维持当前配置，按既定计划操作")
        print("   • 关注结构性机会（低估值板块）")
        print("   • 适合定投策略持续执行")
    else:
        print("   • 可逢低分批加仓优质基金")
        print("   • 关注低估值宽基指数基金")
        print("   • 控制单次加仓比例，分批建仓")

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="市场行情研判")
    subparsers = parser.add_subparsers(dest="command", help="分析类型")

    subparsers.add_parser("overview", help="市场概览")
    subparsers.add_parser("valuation", help="估值分位")
    subparsers.add_parser("sentiment", help="情绪分析")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "overview": market_overview,
        "valuation": valuation_analysis,
        "sentiment": sentiment_analysis,
    }

    func = cmd_map.get(args.command)
    if func:
        func()


if __name__ == "__main__":
    main()
