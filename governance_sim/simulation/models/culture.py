from dataclasses import dataclass, field
from typing import List
from .enums import Religion


@dataclass
class Culture:
    # Hofstede-inspired axes (0.0–1.0)
    individualism: float = 0.5             # 0=collectivist, 1=individualist
    power_distance: float = 0.5            # 0=egalitarian, 1=hierarchy accepted
    uncertainty_avoidance: float = 0.5     # 0=ambiguity ok, 1=rules-driven
    long_term_orientation: float = 0.5     # 0=short-term/tradition, 1=future-focused
    indulgence: float = 0.5               # 0=restrained, 1=expressive
    competition: float = 0.5              # 0=cooperative, 1=competitive

    # Religion
    dominant_religion: Religion = Religion.SECULAR
    minority_religions: List[Religion] = field(default_factory=list)
    religious_influence: float = 0.3      # influence on politics and law
    secularism: float = 0.7               # separation of religion from state

    # Social composition
    ethnic_diversity: float = 0.3         # fractionalization 0=homogeneous, 1=highly diverse
    ethnic_tension: float = 0.2           # 0=harmonious, 1=severe tension
    national_identity: float = 0.6        # strength of shared national identity
    class_rigidity: float = 0.4           # 0=fluid meritocracy, 1=rigid caste/class
    gender_equality: float = 0.5          # 0=highly unequal, 1=full equality

    # Soft power
    cultural_output: float = 0.3          # arts, media, cuisine — global influence
    diaspora_influence: float = 0.2       # influence through overseas population
    soft_power_bonus: float = 0.0         # accumulated modifier from events

    @property
    def social_cohesion(self) -> float:
        """Composite cohesion: identity, low tension, low rigidity."""
        return min(1.0, max(0.0,
            self.national_identity * 0.5
            - self.ethnic_tension * 0.4
            - self.class_rigidity * 0.1
            + (1.0 - self.ethnic_diversity) * 0.15
        ))

    @property
    def innovation_culture(self) -> float:
        """Cultural propensity for innovation (individualism + long-term + low avoidance)."""
        return (self.individualism + self.long_term_orientation + (1.0 - self.uncertainty_avoidance)) / 3.0

    @property
    def soft_power(self) -> float:
        """Composite soft power from culture and diaspora."""
        return max(0.0, min(1.0, self.cultural_output * 0.7 + self.diaspora_influence * 0.3 + self.soft_power_bonus))

    @property
    def protest_propensity(self) -> float:
        """Cultural willingness to protest (individualism + low power distance)."""
        return (self.individualism + (1.0 - self.power_distance)) / 2.0

    @property
    def religious_tension(self) -> float:
        """Tension from religious diversity and influence."""
        religious_diversity = min(1.0, len(self.minority_religions) * 0.15)
        return min(1.0, religious_diversity * self.religious_influence * 0.5)
