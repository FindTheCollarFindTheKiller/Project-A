from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .geography import Geography
from .government import Government
from .culture import Culture
from .language import Language
from .economy import Economy
from .demographics import Demographics
from .military import Military
from .technology import Technology
from .stability import Stability


@dataclass
class HistoricalEvent:
    year: int
    title: str
    description: str
    effects: Dict[str, float] = field(default_factory=dict)


@dataclass
class Country:
    id: str
    name: str
    adjective: str                        # e.g. "French" for "France"
    capital: str
    founding_year: int
    current_year: int
    geography: Geography = field(default_factory=Geography)
    government: Government = field(default_factory=Government)
    culture: Culture = field(default_factory=Culture)
    language: Language = field(default_factory=Language)
    economy: Economy = field(default_factory=Economy)
    demographics: Demographics = field(default_factory=Demographics)
    military: Military = field(default_factory=Military)
    technology: Technology = field(default_factory=Technology)
    stability: Stability = field(default_factory=Stability)
    history: List[HistoricalEvent] = field(default_factory=list)
    neighbor_ids: List[str] = field(default_factory=list)
    pending_events: List[dict] = field(default_factory=list)
    previous_stats: dict = field(default_factory=dict)   # snapshot before each turn
    metric_history: List[Tuple[int, dict]] = field(default_factory=list)  # (year, stats) time series
    event_cooldowns: dict = field(default_factory=dict)  # {event_id: years_remaining}

    @property
    def age(self) -> int:
        return self.current_year - self.founding_year

    @property
    def global_power_score(self) -> float:
        """Composite great-power index (0-1)."""
        gdp_score = min(1.0, self.economy.gdp_total / 20_000)      # 20T = max
        mil_score = self.military.conventional_strength
        pop_score = min(1.0, self.demographics.population / 1_400_000_000)
        tech_score = self.technology.tier.value / 5.0
        soft_score = self.culture.soft_power
        return (gdp_score * 0.35 + mil_score * 0.25 + pop_score * 0.15
                + tech_score * 0.15 + soft_score * 0.10)

    @property
    def regional_influence(self) -> float:
        """Power projection in immediate region."""
        return (self.military.power_projection * 0.4
                + self.economy.development_level * 0.35
                + self.culture.soft_power * 0.25)

    @property
    def human_development(self) -> float:
        """Human development composite."""
        return self.demographics.hdi

    @property
    def population_str(self) -> str:
        p = self.demographics.population
        if p >= 1_000_000_000:
            return f"{p / 1_000_000_000:.1f}B"
        if p >= 1_000_000:
            return f"{p / 1_000_000:.1f}M"
        return f"{p / 1_000:.0f}K"

    @property
    def gdp_str(self) -> str:
        g = self.economy.gdp_total
        if g >= 1_000:
            return f"${g / 1_000:.1f}T"
        return f"${g:.0f}B"

    def add_history(self, title: str, description: str, effects: Optional[Dict] = None) -> None:
        self.history.append(HistoricalEvent(
            year=self.current_year,
            title=title,
            description=description,
            effects=effects or {},
        ))

    def snapshot_stats(self) -> None:
        """Store current key metrics in previous_stats before a turn's feedback runs."""
        self.previous_stats = {
            "gdp_per_capita": self.economy.gdp_per_capita,
            "gdp_growth": self.economy.gdp_growth,
            "gdp_total": self.economy.gdp_total,
            "stability": self.stability.overall,
            "happiness": self.demographics.happiness,
            "legitimacy": self.government.legitimacy,
            "corruption": self.government.corruption,
            "education": self.demographics.education_index,
            "healthcare": self.demographics.healthcare_index,
            "military_strength": self.military.conventional_strength,
            "unemployment": self.economy.unemployment,
            "gini": self.economy.gini_coefficient,
            "inflation": self.economy.inflation,
            "civil_liberties": self.government.civil_liberties,
            "press_freedom": self.government.press_freedom,
            "soft_power": self.culture.soft_power,
            "population": self.demographics.population,
        }
        self.metric_history.append((self.current_year, dict(self.previous_stats)))
        if len(self.metric_history) > 400:
            self.metric_history.pop(0)

    def summary_dict(self) -> dict:
        return {
            "name": self.name,
            "year": self.current_year,
            "government": self.government.type.value,
            "population": self.demographics.population,
            "gdp_per_capita": self.economy.gdp_per_capita,
            "gdp_total": self.economy.gdp_total,
            "stability": self.stability.overall,
            "happiness": self.demographics.happiness,
            "tech_tier": self.technology.tier_name,
            "military_strength": self.military.conventional_strength,
            "power_score": self.global_power_score,
        }
