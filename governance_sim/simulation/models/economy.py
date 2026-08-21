from dataclasses import dataclass, field
from typing import Dict
from .enums import EconomicSystem, EconomicSector


_DEFAULT_SECTORS: Dict[str, float] = {
    EconomicSector.AGRICULTURE.value: 0.15,
    EconomicSector.MANUFACTURING.value: 0.25,
    EconomicSector.SERVICES.value: 0.40,
    EconomicSector.TECHNOLOGY.value: 0.10,
    EconomicSector.EXTRACTION.value: 0.10,
}

_SYSTEM_GROWTH_BASE = {
    EconomicSystem.FREE_MARKET: 0.04,
    EconomicSystem.MIXED: 0.035,
    EconomicSystem.WELFARE_STATE: 0.03,
    EconomicSystem.COMMAND: 0.02,
    EconomicSystem.SUBSISTENCE: 0.01,
}

_SYSTEM_INEQUALITY_BASE = {
    EconomicSystem.FREE_MARKET: 0.45,
    EconomicSystem.MIXED: 0.35,
    EconomicSystem.WELFARE_STATE: 0.28,
    EconomicSystem.COMMAND: 0.30,
    EconomicSystem.SUBSISTENCE: 0.50,
}


@dataclass
class Economy:
    system: EconomicSystem = EconomicSystem.MIXED
    gdp_total: float = 500.0              # billions USD
    gdp_per_capita: float = 10_000.0      # USD
    gdp_growth: float = 0.025             # annual fraction (2.5%)
    gini_coefficient: float = 0.35        # 0=perfect equality, 1=perfect inequality
    inflation: float = 0.03               # annual fraction
    unemployment: float = 0.07           # fraction of workforce
    trade_balance: float = 0.0           # billions USD (positive = surplus)
    foreign_debt_gdp: float = 0.40       # fraction of GDP
    trade_agreements: int = 3
    sector_weights: Dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_SECTORS))
    resource_income_fraction: float = 0.10  # fraction of GDP from resource exports
    sanctions_level: float = 0.0          # 0=none, 1=severe isolation

    def __post_init__(self) -> None:
        if self.gini_coefficient == 0.35:
            self.gini_coefficient = _SYSTEM_INEQUALITY_BASE.get(self.system, 0.35)

    @property
    def base_growth_rate(self) -> float:
        return _SYSTEM_GROWTH_BASE.get(self.system, 0.025)

    @property
    def trade_openness(self) -> float:
        """How open the economy is to trade (0=closed, 1=fully open)."""
        agreement_bonus = min(0.5, self.trade_agreements * 0.05)
        system_openness = {
            EconomicSystem.FREE_MARKET: 0.8,
            EconomicSystem.MIXED: 0.6,
            EconomicSystem.WELFARE_STATE: 0.6,
            EconomicSystem.COMMAND: 0.2,
            EconomicSystem.SUBSISTENCE: 0.1,
        }.get(self.system, 0.5)
        sanctions_penalty = self.sanctions_level * 0.5
        return max(0.0, min(1.0, system_openness + agreement_bonus - sanctions_penalty))

    @property
    def development_level(self) -> float:
        """Normalized development based on GDP/capita (log scale, cap ~$80k)."""
        import math
        return min(1.0, max(0.0, math.log10(max(1, self.gdp_per_capita)) / math.log10(80_000)))

    @property
    def economic_stability(self) -> float:
        """Composite stability: low inflation, low unemployment, manageable debt."""
        inflation_score = max(0.0, 1.0 - self.inflation * 10)
        unemployment_score = max(0.0, 1.0 - self.unemployment * 5)
        debt_score = max(0.0, 1.0 - self.foreign_debt_gdp)
        return (inflation_score + unemployment_score + debt_score) / 3.0

    @property
    def resource_dependency(self) -> float:
        """Risk of Dutch disease (high when resource income fraction is high)."""
        return min(1.0, self.resource_income_fraction * 2.0)

    def validate_sectors(self) -> None:
        total = sum(self.sector_weights.values())
        if total > 0:
            self.sector_weights = {k: v / total for k, v in self.sector_weights.items()}
