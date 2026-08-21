from dataclasses import dataclass, field
from typing import Dict, Optional
from .enums import GovernmentType, ElectionSystem, SuccessionType


_DEFAULT_BUDGET = {
    "military": 0.15,
    "education": 0.15,
    "healthcare": 0.12,
    "infrastructure": 0.12,
    "social_welfare": 0.10,
    "administration": 0.08,
    "research": 0.05,
    "other": 0.23,
}

_GOV_CIVIL_LIBERTIES = {
    GovernmentType.DEMOCRACY: 0.85,
    GovernmentType.REPUBLIC: 0.75,
    GovernmentType.CONSTITUTIONAL_MONARCHY: 0.70,
    GovernmentType.ABSOLUTE_MONARCHY: 0.30,
    GovernmentType.THEOCRACY: 0.25,
    GovernmentType.OLIGARCHY: 0.40,
    GovernmentType.AUTOCRACY: 0.20,
    GovernmentType.COMMUNISM: 0.25,
    GovernmentType.ANARCHY: 0.60,
}

_GOV_CORRUPTION_BASE = {
    GovernmentType.DEMOCRACY: 0.25,
    GovernmentType.REPUBLIC: 0.30,
    GovernmentType.CONSTITUTIONAL_MONARCHY: 0.30,
    GovernmentType.ABSOLUTE_MONARCHY: 0.55,
    GovernmentType.THEOCRACY: 0.45,
    GovernmentType.OLIGARCHY: 0.65,
    GovernmentType.AUTOCRACY: 0.60,
    GovernmentType.COMMUNISM: 0.50,
    GovernmentType.ANARCHY: 0.70,
}


@dataclass
class Government:
    type: GovernmentType = GovernmentType.REPUBLIC
    election_system: ElectionSystem = ElectionSystem.PROPORTIONAL
    succession_type: SuccessionType = SuccessionType.ELECTION
    executive_strength: float = 0.5        # 0=weak executive, 1=near-absolute
    legislative_strength: float = 0.5
    judicial_independence: float = 0.5
    corruption: float = 0.3                # 0=clean, 1=fully corrupt
    civil_liberties: float = 0.7
    press_freedom: float = 0.7
    military_loyalty: float = 0.7          # loyalty of military to current government
    legitimacy: float = 0.65              # 0-1 popular + institutional legitimacy
    years_in_power: int = 0
    tax_rate: float = 0.25                 # fraction of GDP collected as tax
    budget_allocation: Dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_BUDGET))
    policy_reform_speed: float = 0.5       # how quickly policies take effect (0=slow, 1=fast)

    def __post_init__(self) -> None:
        if self.civil_liberties == 0.7:
            self.civil_liberties = _GOV_CIVIL_LIBERTIES.get(self.type, 0.5)
        if self.corruption == 0.3:
            self.corruption = _GOV_CORRUPTION_BASE.get(self.type, 0.4)

    @property
    def effective_spending(self) -> Dict[str, float]:
        """Budget reduced by corruption drain."""
        efficiency = 1.0 - self.corruption * 0.6
        return {k: v * efficiency for k, v in self.budget_allocation.items()}

    @property
    def separation_of_powers(self) -> float:
        """How well power is distributed across branches."""
        return (self.executive_strength + self.legislative_strength + self.judicial_independence) / 3.0

    @property
    def is_democratic(self) -> bool:
        return self.type in (GovernmentType.DEMOCRACY, GovernmentType.REPUBLIC)

    @property
    def is_authoritarian(self) -> bool:
        return self.type in (
            GovernmentType.AUTOCRACY,
            GovernmentType.COMMUNISM,
            GovernmentType.ABSOLUTE_MONARCHY,
        )

    @property
    def coup_vulnerability(self) -> float:
        """Risk that military seizes power (0=none, 1=imminent)."""
        base = (1.0 - self.military_loyalty) * 0.6
        legitimacy_factor = (1.0 - self.legitimacy) * 0.4
        return min(1.0, base + legitimacy_factor)

    def validate_budget(self) -> None:
        """Normalize budget to sum to 1.0."""
        total = sum(self.budget_allocation.values())
        if total > 0:
            self.budget_allocation = {k: v / total for k, v in self.budget_allocation.items()}
