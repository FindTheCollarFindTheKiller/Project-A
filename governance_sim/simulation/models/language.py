from dataclasses import dataclass, field
from typing import List, Optional
from .enums import LanguageFamily, ScriptSystem, LanguagePolicy


@dataclass
class Language:
    official_languages: List[str] = field(default_factory=lambda: ["National Language"])
    dominant_family: LanguageFamily = LanguageFamily.INDO_EUROPEAN
    script_system: ScriptSystem = ScriptSystem.LATIN
    linguistic_diversity: float = 0.2     # 0=monolingual, 1=highly fragmented
    literacy_rate: float = 0.75           # fraction of population that can read/write
    lingua_franca: Optional[str] = None   # trade/diplomatic common language
    policy: LanguagePolicy = LanguagePolicy.PROMOTE
    diaspora_language_reach: float = 0.1  # 0-1 how widely spoken abroad

    @property
    def official_language_count(self) -> int:
        return len(self.official_languages)

    @property
    def governance_cost_modifier(self) -> float:
        """Higher diversity = higher cost of multilingual governance."""
        return 1.0 + self.linguistic_diversity * 0.25

    @property
    def cultural_affinity_bonus(self) -> float:
        """Bonus to relations with countries sharing the same language family."""
        return 0.1 + self.diaspora_language_reach * 0.1

    @property
    def education_ceiling(self) -> float:
        """Max achievable education index given literacy constraints."""
        return min(1.0, self.literacy_rate * 1.1)

    @property
    def economic_productivity_modifier(self) -> float:
        """Literacy and single-language countries coordinate more efficiently."""
        fragmentation_penalty = self.linguistic_diversity * 0.15
        literacy_bonus = self.literacy_rate * 0.2
        return max(0.7, 1.0 + literacy_bonus - fragmentation_penalty)
