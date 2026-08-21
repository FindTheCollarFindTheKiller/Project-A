from dataclasses import dataclass
from .enums import TechTier


_TIER_NAMES = {
    TechTier.PREINDUSTRIAL: "Pre-Industrial",
    TechTier.AGRICULTURAL: "Agricultural",
    TechTier.EARLY_INDUSTRIAL: "Early Industrial",
    TechTier.INDUSTRIAL: "Industrial",
    TechTier.DIGITAL: "Digital Age",
    TechTier.ADVANCED: "Advanced / Post-Industrial",
}

_TIER_GDP_MULTIPLIER = {
    TechTier.PREINDUSTRIAL: 0.2,
    TechTier.AGRICULTURAL: 0.4,
    TechTier.EARLY_INDUSTRIAL: 0.6,
    TechTier.INDUSTRIAL: 1.0,
    TechTier.DIGITAL: 1.5,
    TechTier.ADVANCED: 2.2,
}


@dataclass
class Technology:
    tier: TechTier = TechTier.INDUSTRIAL
    rd_spending_gdp: float = 0.02          # fraction of GDP on R&D
    innovation_index: float = 0.40        # 0-1 output of new innovations
    tech_adoption_rate: float = 0.50      # 0-1 speed of adopting external tech
    digital_penetration: float = 0.45     # internet/mobile access fraction
    education_quality: float = 0.55       # quality of tertiary education
    brain_drain: float = 0.0             # -1=severe drain, 0=neutral, 1=strong gain
    patent_output: float = 0.20          # normalized patents per capita

    @property
    def tier_name(self) -> str:
        return _TIER_NAMES.get(self.tier, "Unknown")

    @property
    def gdp_multiplier(self) -> float:
        return _TIER_GDP_MULTIPLIER.get(self.tier, 1.0)

    @property
    def innovation_output(self) -> float:
        """Effective innovation: R&D spend * quality * education."""
        rd_score = min(1.0, self.rd_spending_gdp * 20)
        return (rd_score * 0.4 + self.innovation_index * 0.35 + self.education_quality * 0.25)

    @property
    def tech_advance_rate(self) -> float:
        """Probability of advancing a tech tier this decade."""
        return min(0.3, self.innovation_output * 0.2 + self.tech_adoption_rate * 0.1)

    @property
    def military_tech_bonus(self) -> float:
        """Technology bonus applied to military equipment quality."""
        return self.tier.value / 5.0 * 0.4

    @property
    def economic_productivity_bonus(self) -> float:
        """Tech multiplier on economic output."""
        return (self.gdp_multiplier - 1.0) * 0.5 + self.innovation_output * 0.1
