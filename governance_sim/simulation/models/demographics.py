from dataclasses import dataclass


@dataclass
class Demographics:
    population: int = 10_000_000
    growth_rate: float = 0.01             # annual fraction
    median_age: float = 30.0
    urbanization: float = 0.55            # fraction in cities
    education_index: float = 0.60         # composite 0-1
    healthcare_index: float = 0.60        # composite 0-1
    happiness: float = 0.55              # subjective wellbeing 0-1
    immigration_rate: float = 2.0         # per 1000 per year
    emigration_rate: float = 2.0          # per 1000 per year
    youth_bulge: float = 0.0             # excess youth ratio (-1 to 1; 0=balanced)
    social_mobility: float = 0.5         # 0=rigid, 1=fluid

    @property
    def hdi(self) -> float:
        """Human Development Index composite."""
        return (self.education_index + self.healthcare_index + self.social_mobility) / 3.0

    @property
    def net_migration_rate(self) -> float:
        """Positive = net inflow of migrants."""
        return self.immigration_rate - self.emigration_rate

    @property
    def dependency_ratio(self) -> float:
        """Young + old vs working-age. Higher = more economic burden."""
        age_factor = abs(self.median_age - 35.0) / 35.0
        youth_factor = max(0.0, self.youth_bulge) * 0.3
        return min(1.0, age_factor + youth_factor)

    @property
    def labor_force_quality(self) -> float:
        """Education and health composite for workforce quality."""
        return (self.education_index * 0.6 + self.healthcare_index * 0.4)

    @property
    def political_pressure(self) -> float:
        """Demographic pressure to change government (youth + unhappiness)."""
        youth_pressure = max(0.0, self.youth_bulge) * 0.4
        unhappiness = (1.0 - self.happiness) * 0.6
        return min(1.0, youth_pressure + unhappiness)

    @property
    def urbanization_bonus(self) -> float:
        """Economic productivity bonus from urbanization (diminishing returns)."""
        return min(0.3, self.urbanization * 0.4 - 0.08)
