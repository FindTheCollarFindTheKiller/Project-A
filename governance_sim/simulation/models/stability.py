from dataclasses import dataclass


@dataclass
class Stability:
    overall: float = 0.60                 # composite stability 0-1
    political: float = 0.65
    social: float = 0.60
    economic: float = 0.65
    revolution_risk: float = 0.10         # probability of revolution this turn
    coup_risk: float = 0.05              # probability of military coup this turn
    separatism_risk: float = 0.08        # risk of regional secession
    protest_level: float = 0.20          # active protest intensity 0-1
    civil_war_risk: float = 0.03

    @property
    def composite(self) -> float:
        return (self.political * 0.35 + self.social * 0.35 + self.economic * 0.30)

    @property
    def crisis_level(self) -> str:
        s = self.overall
        if s >= 0.75:
            return "Stable"
        if s >= 0.55:
            return "Moderate"
        if s >= 0.35:
            return "Unstable"
        if s >= 0.20:
            return "Crisis"
        return "Collapse"

    @property
    def imminent_event_risk(self) -> float:
        """Combined probability of a major destabilizing event this turn."""
        return min(0.95, self.revolution_risk + self.coup_risk + self.civil_war_risk)
