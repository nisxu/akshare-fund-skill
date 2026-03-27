"""
AKShare 客户端封装模块
提供带缓存的 AKShare 数据获取功能，减少重复请求。
"""

import time
import functools
from typing import Optional
from datetime import datetime

import akshare as ak
import pandas as pd


# 内存缓存，key -> (timestamp, data)
_cache: dict[str, tuple[float, object]] = {}
_MAX_CACHE_SIZE = 256  # 最大缓存条目数
DEFAULT_TTL = 300  # 默认缓存 5 分钟


def _evict_expired():
    """清理过期缓存条目"""
    now = time.time()
    expired_keys = [k for k, (ts, _) in _cache.items() if now - ts > 86400]
    for k in expired_keys:
        del _cache[k]


def cached(ttl: int = DEFAULT_TTL):
    """带 TTL 的缓存装饰器，返回 DataFrame 的深拷贝以防止缓存被外部修改"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            if cache_key in _cache:
                ts, data = _cache[cache_key]
                if now - ts < ttl:
                    return data.copy() if isinstance(data, pd.DataFrame) else data
            result = func(*args, **kwargs)
            # 缓存满时先清理过期条目，仍满则淘汰最旧条目
            if len(_cache) >= _MAX_CACHE_SIZE:
                _evict_expired()
            if len(_cache) >= _MAX_CACHE_SIZE:
                oldest_key = min(_cache, key=lambda k: _cache[k][0])
                del _cache[oldest_key]
            _cache[cache_key] = (now, result)
            return result.copy() if isinstance(result, pd.DataFrame) else result
        return wrapper
    return decorator


def clear_cache():
    """清除所有缓存"""
    _cache.clear()


@cached(ttl=3600)
def get_fund_list() -> pd.DataFrame:
    """获取全市场基金名称列表"""
    try:
        df = ak.fund_name_em()
        return df
    except Exception as e:
        print(f"[错误] 获取基金列表失败: {e}")
        return pd.DataFrame()


@cached(ttl=300)
def get_open_fund_daily() -> pd.DataFrame:
    """获取开放式基金每日净值数据"""
    try:
        df = ak.fund_open_fund_daily_em()
        return df
    except Exception as e:
        print(f"[错误] 获取开放式基金每日数据失败: {e}")
        return pd.DataFrame()


@cached(ttl=300)
def get_fund_info(fund_code: str, indicator: str = "单位净值走势", period: str = "6月") -> pd.DataFrame:
    """
    获取单只基金历史净值信息
    indicator: 累计净值走势 / 单位净值走势 / 累计收益率走势 / 同类排名走势 /
               同类排名百分比 / 分红送配详情 / 拆分详情
    period: "1月" / "3月" / "6月" / "1年" / "3年" / "5年" / "今年来" / "成立来"
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator=indicator, period=period)
        return df
    except Exception as e:
        print(f"[错误] 获取基金 {fund_code} 信息失败: {e}")
        return pd.DataFrame()


@cached(ttl=300)
def get_etf_spot() -> pd.DataFrame:
    """获取 ETF 实时行情"""
    try:
        df = ak.fund_etf_spot_em()
        return df
    except Exception as e:
        print(f"[错误] 获取 ETF 行情失败: {e}")
        return pd.DataFrame()


@cached(ttl=3600)
def get_fund_portfolio(fund_code: str, year: str = "") -> pd.DataFrame:
    """获取基金持仓明细"""
    try:
        if not year:
            year = str(datetime.now().year)
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
        return df
    except Exception as e:
        print(f"[错误] 获取基金 {fund_code} 持仓失败: {e}")
        return pd.DataFrame()


@cached(ttl=86400)
def get_fund_manager() -> pd.DataFrame:
    """获取基金经理信息"""
    try:
        df = ak.fund_manager_em()
        return df
    except Exception as e:
        print(f"[错误] 获取基金经理信息失败: {e}")
        return pd.DataFrame()


def _format_index_symbol(symbol: str) -> str:
    """将指数代码转换为 akshare 所需的市场前缀格式"""
    # 如果已经是完整格式（如 sh000300），直接返回
    if symbol.startswith(("sh", "sz", "csi")):
        return symbol
    # 创业板指数以 399 开头 → 深交所
    if symbol.startswith("399"):
        return f"sz{symbol}"
    # 其他以 0/1/2/3 开头 → 上交所
    return f"sh{symbol}"


@cached(ttl=300)
def get_index_daily(symbol: str = "000300",
                    start_date: str = "20200101", end_date: str = "") -> pd.DataFrame:
    """获取大盘指数日线数据"""
    try:
        if not end_date:
            end_date = time.strftime("%Y%m%d")
        formatted_symbol = _format_index_symbol(symbol)
        df = ak.stock_zh_index_daily_em(
            symbol=formatted_symbol,
            start_date=start_date, end_date=end_date
        )
        return df
    except Exception as e:
        print(f"[错误] 获取指数 {symbol} 数据失败: {e}")
        return pd.DataFrame()


@cached(ttl=300)
def get_fund_etf_fund_daily_em() -> pd.DataFrame:
    """获取 ETF 基金每日数据"""
    try:
        df = ak.fund_etf_fund_daily_em()
        return df
    except Exception as e:
        print(f"[错误] 获取 ETF 基金每日数据失败: {e}")
        return pd.DataFrame()


@cached(ttl=600)
def _get_fund_rating_all() -> pd.DataFrame:
    """获取全市场基金评级（内部缓存，全量数据只拉一次）"""
    try:
        return ak.fund_rating_all()
    except Exception as e:
        print(f"[错误] 获取基金评级失败: {e}")
        return pd.DataFrame()


def get_fund_rating(fund_code: str) -> pd.DataFrame:
    """获取指定基金的评级"""
    df = _get_fund_rating_all()
    if not df.empty and fund_code:
        # 尝试找到基金代码列（列名可能是"代码"、"基金代码"等）
        code_col = None
        for col in df.columns:
            if "代码" in col or col in ("代码", "基金代码"):
                code_col = col
                break
        if code_col:
            df = df[df[code_col].astype(str) == str(fund_code)]
    return df


@cached(ttl=300)
def get_open_fund_ranking(fund_type: str = "全部") -> pd.DataFrame:
    """
    获取开放式基金排行
    fund_type: 全部 / 股票型 / 混合型 / 债券型 / 指数型 / QDII / FOF
    """
    try:
        df = ak.fund_open_fund_rank_em(symbol=fund_type)
        return df
    except Exception as e:
        print(f"[错误] 获取基金排行失败: {e}")
        return pd.DataFrame()
