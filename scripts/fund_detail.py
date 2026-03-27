#!/usr/bin/env python3
"""
基金详情深度分析
查询单只基金的全方位信息：净值走势、持仓明细、基金经理、风险指标等。
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.akshare_client import (
    get_fund_info, get_fund_list, get_fund_portfolio, get_fund_rating
)
from utils.indicators import (
    calc_return, calc_annualized_return, calc_volatility,
    calc_max_drawdown, calc_sharpe_ratio, calc_sortino_ratio,
    calc_calmar_ratio, classify_trend
)
import pandas as pd
from datetime import datetime, timedelta


def get_fund_detail(fund_code: str, days: int = 365) -> dict:
    """
    获取基金详情

    Args:
        fund_code: 基金代码
        days: 历史天数

    Returns:
        包含基金完整信息的字典
    """
    result = {
        "code": fund_code,
        "basic_info": {},
        "nav_info": {},
        "risk_metrics": {},
        "holdings": [],
        "rating": {},
    }

    # 1. 基本信息 - 从基金列表中查找
    fund_list = get_fund_list()
    if not fund_list.empty:
        matched = fund_list[fund_list.iloc[:, 0].astype(str) == str(fund_code)]
        if not matched.empty:
            row = matched.iloc[0]
            result["basic_info"] = {
                "代码": str(row.iloc[0]),
                "名称": str(row.iloc[1]) if len(matched.columns) > 1 else "",
                "类型": str(row.iloc[2]) if len(matched.columns) > 2 else "",
            }

    # 2. 净值走势
    nav_df = get_fund_info(fund_code, indicator="累计净值走势")
    if not nav_df.empty:
        # 取最近 N 天
        nav_df = nav_df.tail(days)
        prices = pd.to_numeric(nav_df.iloc[:, 1], errors="coerce").dropna()

        if not prices.empty:
            result["nav_info"] = {
                "最新净值": round(float(prices.iloc[-1]), 4),
                "净值日期": str(nav_df.iloc[-1, 0]),
                "数据天数": len(prices),
            }

            # 3. 收益率计算
            result["nav_info"]["近1月收益率"] = f"{calc_return(prices, 22):.2f}%"
            result["nav_info"]["近3月收益率"] = f"{calc_return(prices, 66):.2f}%"
            result["nav_info"]["近6月收益率"] = f"{calc_return(prices, 132):.2f}%"
            result["nav_info"]["近1年收益率"] = f"{calc_return(prices, 252):.2f}%"
            result["nav_info"]["年化收益率"] = f"{calc_annualized_return(prices):.2f}%"

            # 4. 风险指标
            result["risk_metrics"] = {
                "年化波动率": f"{calc_volatility(prices):.2f}%",
                "最大回撤": f"{calc_max_drawdown(prices):.2f}%",
                "夏普比率": calc_sharpe_ratio(prices),
                "索提诺比率": calc_sortino_ratio(prices),
                "卡玛比率": calc_calmar_ratio(prices),
                "趋势判断": classify_trend(prices),
            }

    # 5. 持仓明细
    current_year = str(datetime.now().year)
    portfolio_df = get_fund_portfolio(fund_code, year=current_year)
    if portfolio_df.empty:
        # 如果当年没数据，尝试上一年
        portfolio_df = get_fund_portfolio(fund_code, year=str(int(current_year) - 1))

    if not portfolio_df.empty:
        holdings = []
        for _, row in portfolio_df.head(10).iterrows():
            holding = {}
            for col in portfolio_df.columns:
                holding[str(col)] = str(row[col]) if pd.notna(row[col]) else "-"
            holdings.append(holding)
        result["holdings"] = holdings

    # 6. 基金评级
    rating_df = get_fund_rating(fund_code)
    if not rating_df.empty:
        row = rating_df.iloc[0]
        result["rating"] = {str(col): str(row[col]) for col in rating_df.columns}

    return result


def format_detail(detail: dict) -> str:
    """格式化基金详情输出"""
    lines = []
    lines.append(f"\n{'='*60}")

    # 基本信息
    basic = detail.get("basic_info", {})
    lines.append(f"📊 基金详情: [{basic.get('代码', detail['code'])}] {basic.get('名称', '')}")
    lines.append(f"   类型: {basic.get('类型', '-')}")
    lines.append(f"{'='*60}")

    # 净值信息
    nav = detail.get("nav_info", {})
    if nav:
        lines.append(f"\n📈 净值与收益:")
        for k, v in nav.items():
            lines.append(f"   {k}: {v}")

    # 风险指标
    risk = detail.get("risk_metrics", {})
    if risk:
        lines.append(f"\n⚠️  风险指标:")
        for k, v in risk.items():
            lines.append(f"   {k}: {v}")

    # 持仓明细
    holdings = detail.get("holdings", [])
    if holdings:
        lines.append(f"\n🏢 前十大持仓:")
        for i, h in enumerate(holdings, 1):
            stock_name = h.get("股票名称", h.get("名称", "-"))
            weight = h.get("占净值比例", h.get("比例", "-"))
            lines.append(f"   {i:>2}. {stock_name} (占比: {weight})")

    # 评级
    rating = detail.get("rating", {})
    if rating:
        lines.append(f"\n⭐ 基金评级:")
        for k, v in rating.items():
            lines.append(f"   {k}: {v}")

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="基金详情分析")
    parser.add_argument("--code", required=True, help="基金代码")
    parser.add_argument("--days", type=int, default=365, help="历史天数(默认365)")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    detail = get_fund_detail(args.code, days=args.days)

    if args.json:
        print(json.dumps(detail, ensure_ascii=False, indent=2))
    else:
        print(format_detail(detail))


if __name__ == "__main__":
    main()
