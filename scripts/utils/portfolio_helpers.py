"""
持仓数据加载辅助模块
提供统一的持仓数据加载与盈亏计算，消除各模块的重复代码。
"""

import pandas as pd

from utils.storage import get_all_holdings
from utils.akshare_client import get_fund_info, get_fund_list


def load_holdings_with_prices(days: int = 252, calc_profit: bool = True) -> dict:
    """
    加载持仓并附带净值序列和可选的盈亏计算。

    Args:
        days: 历史净值天数
        calc_profit: 是否计算盈亏信息（invested, current_value, profit_rate）

    Returns:
        {基金代码: {name, shares, cost_price, current_nav, prices, fund_type, target_weight,
                    [invested, current_value, profit_rate]}}
    """
    holdings = get_all_holdings()
    if not holdings:
        return {}

    result = {}
    fund_list = get_fund_list()

    for code, h in holdings.items():
        nav_df = get_fund_info(code, indicator="累计净值走势")
        if nav_df.empty:
            continue

        prices = pd.to_numeric(nav_df.iloc[:, 1], errors="coerce").dropna()
        if prices.empty:
            continue

        prices = prices.tail(days)

        # 获取基金类型
        fund_type = ""
        if not fund_list.empty:
            matched = fund_list[fund_list.iloc[:, 0].astype(str) == str(code)]
            if not matched.empty and len(matched.columns) > 2:
                fund_type = str(matched.iloc[0, 2])

        current_nav = float(prices.iloc[-1])
        shares = h.get("shares", 0)
        cost_price = h.get("cost_price", 0)

        info = {
            "name": h.get("name", ""),
            "shares": shares,
            "cost_price": cost_price,
            "current_nav": current_nav,
            "prices": prices,
            "fund_type": fund_type,
            "target_weight": h.get("target_weight", 0),
        }

        if calc_profit:
            invested = shares * cost_price
            current_value = shares * current_nav
            profit_rate = ((current_nav - cost_price) / cost_price * 100) if cost_price > 0 else 0
            info["invested"] = invested
            info["current_value"] = current_value
            info["profit_rate"] = profit_rate

        result[code] = info

    return result
