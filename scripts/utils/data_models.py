"""
数据模型定义
定义基金信息、持仓记录等核心数据结构。
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class HoldingRecord:
    """用户持仓记录"""
    code: str                  # 基金代码
    name: str = ""             # 基金名称
    shares: float = 0.0        # 持有份额
    cost_price: float = 0.0    # 买入成本价(每份)
    total_cost: float = 0.0    # 总投入金额
    current_nav: float = 0.0   # 当前净值
    current_value: float = 0.0 # 当前市值
    profit: float = 0.0        # 盈亏金额
    profit_rate: float = 0.0   # 盈亏比率(%)
    buy_date: str = ""         # 买入日期
    target_weight: float = 0.0 # 目标配置比例(%)
    notes: str = ""            # 备注

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HoldingRecord":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def update_profit(self):
        """更新盈亏计算"""
        self.current_value = self.shares * self.current_nav
        self.total_cost = self.shares * self.cost_price
        self.profit = self.current_value - self.total_cost
        if self.total_cost > 0:
            self.profit_rate = (self.profit / self.total_cost) * 100


@dataclass
class PortfolioSummary:
    """持仓汇总"""
    total_cost: float = 0.0        # 总投入
    total_value: float = 0.0       # 总市值
    total_profit: float = 0.0      # 总盈亏
    total_profit_rate: float = 0.0 # 总收益率(%)
    holding_count: int = 0         # 持仓数量
    holdings: list[HoldingRecord] = field(default_factory=list)
    update_time: str = ""          # 更新时间

    def to_dict(self) -> dict:
        return asdict(self)
