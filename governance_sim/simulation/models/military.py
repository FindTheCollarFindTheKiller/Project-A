from dataclasses import dataclass
from .enums import MilitaryDoctrine, TechTier


@dataclass
class Military:
    size: int = 100_000                   # active personnel
    reserve_size: int = 200_000
    tech_tier: TechTier = TechTier.INDUSTRIAL
    defense_spending_gdp: float = 0.02    # fraction of GDP
    doctrine: MilitaryDoctrine = MilitaryDoctrine.CONVENTIONAL
    has_nuclear: bool = False
    morale: float = 0.65                  # 0-1
    training_quality: float = 0.60        # 0-1
    equipment_quality: float = 0.55       # 0-1
    veteran_ratio: float = 0.15           # fraction of forces with combat experience
    paramilitary_strength: float = 0.3    # internal security forces 0-1

    @property
    def conventional_strength(self) -> float:
        """Composite conventional military power (0-1 relative scale)."""
        tech_score = self.tech_tier.value / 5.0
        personnel_score = min(1.0, self.size / 1_000_000)
        quality_score = (self.morale + self.training_quality + self.equipment_quality) / 3.0
        return (tech_score * 0.35 + personnel_score * 0.25 + quality_score * 0.40)

    @property
    def deterrence_score(self) -> float:
        """How effectively this military deters aggression."""
        nuclear_bonus = 0.4 if self.has_nuclear else 0.0
        return min(1.0, self.conventional_strength * 0.6 + nuclear_bonus)

    @property
    def power_projection(self) -> float:
        """Ability to project force beyond borders."""
        if self.doctrine == MilitaryDoctrine.DEFENSIVE:
            return self.conventional_strength * 0.3
        if self.doctrine == MilitaryDoctrine.EXPEDITIONARY:
            return self.conventional_strength * 0.9
        return self.conventional_strength * 0.6

    @property
    def internal_control(self) -> float:
        """Ability to suppress internal unrest."""
        return (self.paramilitary_strength * 0.5 + self.morale * 0.3 + self.training_quality * 0.2)

    @property
    def gdp_drain(self) -> float:
        """Economic opportunity cost of military spending."""
        return self.defense_spending_gdp
