from dataclasses import dataclass, field
from typing import Dict, List
from .enums import TerrainType, ClimateZone, ResourceType, DisasterType


@dataclass
class Geography:
    terrain_types: List[TerrainType] = field(default_factory=list)
    climate_zone: ClimateZone = ClimateZone.TEMPERATE
    area_km2: float = 500_000.0
    coastline_km: float = 0.0
    is_landlocked: bool = False
    river_count: int = 3
    natural_resources: Dict[ResourceType, float] = field(default_factory=dict)
    neighbor_count: int = 3
    border_defensibility: float = 0.5      # 0=open plains, 1=mountain fortress
    natural_disaster_risk: Dict[DisasterType, float] = field(default_factory=dict)
    elevation_mean_m: float = 500.0
    arable_fraction: float = 0.3           # fraction of land suitable for farming

    @property
    def trade_access(self) -> float:
        """0-1 composite: coastline, rivers, neighbors."""
        coast = min(1.0, self.coastline_km / 5000.0) * 0.5
        river = min(1.0, self.river_count / 8.0) * 0.2
        neighbor = min(1.0, self.neighbor_count / 8.0) * 0.3
        landlocked_penalty = -0.2 if self.is_landlocked else 0.0
        return max(0.0, min(1.0, coast + river + neighbor + landlocked_penalty))

    @property
    def resource_wealth(self) -> float:
        """Average resource abundance across all present resources."""
        if not self.natural_resources:
            return 0.0
        return sum(self.natural_resources.values()) / max(len(self.natural_resources), 1)

    @property
    def agricultural_potential(self) -> float:
        """Based on arable fraction, climate, and water access."""
        climate_mod = {
            ClimateZone.TROPICAL: 0.9,
            ClimateZone.TEMPERATE: 1.0,
            ClimateZone.MEDITERRANEAN: 0.85,
            ClimateZone.MONSOON: 0.95,
            ClimateZone.CONTINENTAL: 0.7,
            ClimateZone.SEMI_ARID: 0.4,
            ClimateZone.ARID: 0.1,
            ClimateZone.POLAR: 0.05,
        }.get(self.climate_zone, 0.6)
        river_bonus = min(0.2, self.river_count * 0.03)
        return min(1.0, self.arable_fraction * climate_mod + river_bonus)

    @property
    def strategic_value(self) -> float:
        """Composite geographic strategic importance."""
        return min(1.0, (
            self.border_defensibility * 0.3
            + self.trade_access * 0.4
            + self.resource_wealth * 0.3
        ))

    @property
    def disaster_frequency(self) -> float:
        """Expected disaster events per decade."""
        return sum(self.natural_disaster_risk.values())
