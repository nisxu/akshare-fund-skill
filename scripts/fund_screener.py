#!/usr/bin/env python3
"""
基金筛选引擎
支持多维度条件筛选、智能排序，输出 Top N 基金列表。
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.akshare_client import get_open_fund_ranking
import pandas as pd


# 基金类型映射
FUND_TYPE_MAP = {
    "全部": "全部",
    "股票型": "股票型",
    "混合型": "混合型",
    "债券型": "债券型",
    "指数型": "指数型",
    "QDII": "QDII",
    "FOF": "FOF",
    "ETF": "ETF",
}

# 排序字段映射（中文列名 -> 排序 key）
SORT_FIELD_MAP = {
    "return_1m": "近1月",
    "return_3m": "近3月",
    "return_6m": "近6月",
    "return_1y": "近1年",
    "return_2y": "近2年",
    "return_3y": "近3年",
    "nav": "单位净值",
}


def screen_funds(fund_type: str = "全部", keyword: str = "",
                 min_return_1y: float = None, max_return_1y: float = None,
                 min_return_6m: float = None, max_return_6m: float = None,
                 min_return_3m: float = None, max_return_3m: float = None,
                 min_return_1m: float = None, max_return_1m: float = None,
                 min_scale: float = None,
                 sort_by: str = "return_1y", ascending: bool = False,
                 top: int = 20) -> list[dict]:
    """
    基金筛选主函数

    Args:
        fund_type: 基金类型
        keyword: 关键字搜索（基金名称/代码）
        min_return_*: 最低收益率(%)
        max_return_*: 最高收益率(%)
        min_scale: 最低规模(亿)
        sort_by: 排序字段
        ascending: 是否升序
        top: 返回数量

    Returns:
        筛选后的基金列表
    """
    # 获取数据
    mapped_type = FUND_TYPE_MAP.get(fund_type, "全部")

    if mapped_type == "ETF":
        # ETF 使用专门的接口
        from utils.akshare_client import get_etf_spot
        df = get_etf_spot()
        if df.empty:
            print("未获取到 ETF 数据")
            return []
        # ETF 数据列名不同，做简单格式化
        result = _process_etf_data(df, keyword, sort_by, ascending, top)
        return result

    df = get_open_fund_ranking(fund_type=mapped_type)
    if df.empty:
        print(f"未获取到 {fund_type} 基金数据")
        return []

    # 防止修改缓存中的原始数据
    df = df.copy()

    # 关键字筛选（regex=False 防止用户输入特殊字符导致正则解析错误）
    if keyword:
        mask = (df.iloc[:, 1].astype(str).str.contains(keyword, na=False, regex=False) |
                df.iloc[:, 0].astype(str).str.contains(keyword, na=False, regex=False))
        df = df[mask]

    # 标准化列名处理
    columns = df.columns.tolist()

    # 转换数值列
    numeric_cols = []
    for col in columns:
        if any(kw in str(col) for kw in ["净值", "收益", "近", "手续费"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
            numeric_cols.append(col)

    # 收益率筛选
    df = _apply_return_filter(df, columns, "近1月", min_return_1m, max_return_1m)
    df = _apply_return_filter(df, columns, "近3月", min_return_3m, max_return_3m)
    df = _apply_return_filter(df, columns, "近6月", min_return_6m, max_return_6m)
    df = _apply_return_filter(df, columns, "近1年", min_return_1y, max_return_1y)

    # 规模筛选
    if min_scale is not None:
        scale_cols = [c for c in columns if "规模" in str(c)]
        if scale_cols:
            df[scale_cols[0]] = pd.to_numeric(df[scale_cols[0]], errors="coerce")
            df = df[df[scale_cols[0]] >= min_scale]

    # 排序
    sort_col = SORT_FIELD_MAP.get(sort_by, "近1年")
    matched_cols = [c for c in columns if sort_col in str(c)]
    if matched_cols:
        df = df.sort_values(by=matched_cols[0], ascending=ascending, na_position="last")

    # 取 Top N
    df = df.head(top)

    # 格式化输出
    results = []
    for _, row in df.iterrows():
        fund = {
            "代码": str(row.iloc[0]) if len(columns) > 0 else "",
            "名称": str(row.iloc[1]) if len(columns) > 1 else "",
        }
        for col in columns[2:]:
            fund[str(col)] = _format_value(row[col])
        results.append(fund)

    return results


def _apply_return_filter(df: pd.DataFrame, columns: list, keyword: str,
                         min_val: float = None, max_val: float = None) -> pd.DataFrame:
    """应用收益率筛选条件，返回筛选后的 DataFrame"""
    matched = [c for c in columns if keyword in str(c)]
    if not matched:
        return df
    col = matched[0]
    if min_val is not None:
        df = df[df[col] >= min_val]
    if max_val is not None:
        df = df[df[col] <= max_val]
    return df


def _process_etf_data(df: pd.DataFrame, keyword: str, sort_by: str,
                      ascending: bool, top: int) -> list[dict]:
    """处理 ETF 数据"""
    if keyword:
        # 用列级搜索替代逐行 apply，性能更优
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.contains(keyword, na=False)
        df = df[mask]

    # 转换数值列
    for col in df.columns:
        if any(kw in str(col) for kw in ["价", "额", "量", "幅", "率"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 排序
    sort_map = {"return_1y": "涨跌幅", "return_6m": "涨跌幅", "return_3m": "涨跌幅",
                "return_1m": "涨跌幅", "nav": "最新价"}
    sort_kw = sort_map.get(sort_by, "涨跌幅")
    matched = [c for c in df.columns if sort_kw in str(c)]
    if matched:
        df = df.sort_values(by=matched[0], ascending=ascending, na_position="last")

    df = df.head(top)

    results = []
    for _, row in df.iterrows():
        fund = {}
        for col in df.columns:
            fund[str(col)] = _format_value(row[col])
        results.append(fund)
    return results


def _format_value(val) -> str:
    """格式化输出值"""
    if pd.isna(val):
        return "-"
    if isinstance(val, float):
        return f"{val:.4f}" if abs(val) < 1 else f"{val:.2f}"
    return str(val)


def main():
    parser = argparse.ArgumentParser(description="基金筛选引擎")
    parser.add_argument("--type", default="全部", help="基金类型: 股票型/混合型/债券型/指数型/QDII/FOF/ETF")
    parser.add_argument("--keyword", default="", help="关键字搜索(名称/代码)")
    parser.add_argument("--min-return-1y", type=float, default=None, help="最低近1年收益率(%)")
    parser.add_argument("--max-return-1y", type=float, default=None, help="最高近1年收益率(%)")
    parser.add_argument("--min-return-6m", type=float, default=None, help="最低近6月收益率(%)")
    parser.add_argument("--max-return-6m", type=float, default=None, help="最高近6月收益率(%)")
    parser.add_argument("--min-return-3m", type=float, default=None, help="最低近3月收益率(%)")
    parser.add_argument("--min-return-1m", type=float, default=None, help="最低近1月收益率(%)")
    parser.add_argument("--min-scale", type=float, default=None, help="最低基金规模(亿)")
    parser.add_argument("--sort", default="return_1y", help="排序字段: return_1m/3m/6m/1y/2y/3y/nav")
    parser.add_argument("--asc", action="store_true", help="升序排列")
    parser.add_argument("--top", type=int, default=20, help="返回数量")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    results = screen_funds(
        fund_type=args.type,
        keyword=args.keyword,
        min_return_1y=args.min_return_1y,
        max_return_1y=args.max_return_1y,
        min_return_6m=args.min_return_6m,
        max_return_6m=args.max_return_6m,
        min_return_3m=args.min_return_3m,
        min_return_1m=args.min_return_1m,
        min_scale=args.min_scale,
        sort_by=args.sort,
        ascending=args.asc,
        top=args.top,
    )

    if not results:
        print("未找到符合条件的基金")
        return

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # 表格输出
        print(f"\n{'='*80}")
        print(f"基金筛选结果 (共 {len(results)} 只)")
        print(f"{'='*80}")
        for i, fund in enumerate(results, 1):
            code = fund.get("代码", "")
            name = fund.get("名称", "")
            print(f"\n{i:>3}. [{code}] {name}")
            for k, v in fund.items():
                if k not in ("代码", "名称"):
                    print(f"     {k}: {v}")
        print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
