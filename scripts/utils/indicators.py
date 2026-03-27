"""
指标计算模块
提供收益率、风险指标、夏普比率等金融指标的计算函数。
"""

import numpy as np
import pandas as pd
from typing import Optional


def calc_return(prices: pd.Series, periods: int = None) -> float:
    """
    计算区间收益率
    prices: 净值序列（按时间正序）
    periods: 区间天数，None 表示全区间
    """
    if prices.empty or len(prices) < 2:
        return 0.0
    if periods and len(prices) > periods:
        start = prices.iloc[-periods]
    else:
        start = prices.iloc[0]
    end = prices.iloc[-1]
    if abs(start) < 1e-10:
        return 0.0
    return ((end - start) / start) * 100


def calc_annualized_return(prices: pd.Series, trading_days: int = 252) -> float:
    """计算年化收益率"""
    if prices.empty or len(prices) < 2:
        return 0.0
    if abs(prices.iloc[0]) < 1e-10:
        return 0.0
    total_days = len(prices)
    total_return = prices.iloc[-1] / prices.iloc[0]
    if total_return <= 0:
        return 0.0
    years = total_days / trading_days
    if years <= 0:
        return 0.0
    annualized = (total_return ** (1 / years) - 1) * 100
    return round(annualized, 2)


def calc_volatility(prices: pd.Series, trading_days: int = 252) -> float:
    """
    计算年化波动率
    """
    if prices.empty or len(prices) < 3:
        return 0.0
    returns = prices.pct_change().dropna()
    if returns.empty:
        return 0.0
    vol = returns.std() * np.sqrt(trading_days) * 100
    return round(vol, 2)


def calc_max_drawdown(prices: pd.Series) -> float:
    """
    计算最大回撤(%)
    """
    if prices.empty or len(prices) < 2:
        return 0.0
    cummax = prices.cummax()
    # 保护除零：将 cummax 中的零值替换为 NaN
    cummax = cummax.replace(0, np.nan)
    drawdown = (prices - cummax) / cummax
    drawdown = drawdown.dropna()
    if drawdown.empty:
        return 0.0
    max_dd = drawdown.min() * 100
    return round(max_dd, 2)


def calc_sharpe_ratio(prices: pd.Series, risk_free_rate: float = 0.015,
                      trading_days: int = 252) -> float:
    """
    计算夏普比率
    risk_free_rate: 无风险利率（年化，默认 1.5%）
    """
    if prices.empty or len(prices) < 3:
        return 0.0
    returns = prices.pct_change().dropna()
    if returns.empty or returns.std() < 1e-10:
        return 0.0
    excess_return = returns.mean() * trading_days - risk_free_rate
    vol = returns.std() * np.sqrt(trading_days)
    sharpe = excess_return / vol
    return round(sharpe, 2)


def calc_sortino_ratio(prices: pd.Series, risk_free_rate: float = 0.015,
                       trading_days: int = 252) -> float:
    """计算索提诺比率（仅考虑下行波动）"""
    if prices.empty or len(prices) < 3:
        return 0.0
    returns = prices.pct_change().dropna()
    if returns.empty:
        return 0.0
    downside = returns[returns < 0]
    if downside.empty or downside.std() < 1e-10:
        return 0.0
    excess_return = returns.mean() * trading_days - risk_free_rate
    downside_vol = downside.std() * np.sqrt(trading_days)
    return round(excess_return / downside_vol, 2)


def calc_calmar_ratio(prices: pd.Series, trading_days: int = 252) -> float:
    """计算卡玛比率（年化收益 / 最大回撤）"""
    ann_ret = calc_annualized_return(prices, trading_days)
    max_dd = abs(calc_max_drawdown(prices))
    if max_dd < 1e-10:
        return 0.0
    return round(ann_ret / max_dd, 2)


def calc_correlation_matrix(price_dict: dict[str, pd.Series]) -> pd.DataFrame:
    """
    计算多只基金的收益率相关性矩阵
    price_dict: {基金代码: 净值序列}
    """
    returns_dict = {}
    for code, prices in price_dict.items():
        if not prices.empty and len(prices) > 1:
            returns_dict[code] = prices.pct_change().dropna()

    if len(returns_dict) < 2:
        return pd.DataFrame()

    returns_df = pd.DataFrame(returns_dict)
    return returns_df.corr().round(3)


def calc_var(prices: pd.Series, confidence: float = 0.95,
             holding_period: int = 1) -> float:
    """
    计算 VaR（历史模拟法）
    confidence: 置信水平
    holding_period: 持有期（天）
    返回百分比损失
    """
    if prices.empty or len(prices) < 30:
        return 0.0
    returns = prices.pct_change().dropna()
    if returns.empty:
        return 0.0
    if holding_period > 1:
        returns = returns.rolling(holding_period).sum().dropna()
    var_value = np.percentile(returns, (1 - confidence) * 100)
    return round(var_value * 100, 2)


def classify_trend(prices: pd.Series, short_window: int = 5,
                   long_window: int = 20) -> str:
    """
    基于均线判断趋势
    返回: 上涨 / 下跌 / 震荡
    """
    if prices.empty or len(prices) < long_window:
        return "数据不足"
    ma_short = prices.rolling(short_window).mean().iloc[-1]
    ma_long = prices.rolling(long_window).mean().iloc[-1]
    current = prices.iloc[-1]

    if current > ma_short > ma_long:
        return "上涨"
    elif current < ma_short < ma_long:
        return "下跌"
    else:
        return "震荡"


def calc_pe_percentile(pe_series: pd.Series, current_pe: float) -> float:
    """计算 PE 在历史中的百分位"""
    if pe_series.empty:
        return 0.0
    percentile = (pe_series < current_pe).sum() / len(pe_series) * 100
    return round(percentile, 2)
