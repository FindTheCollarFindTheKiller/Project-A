"""
World: manages a collection of countries, bilateral relations, and world-level state.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models.country import Country
from ..models.enums import DiplomaticStance, GovernmentType


@dataclass
class BilateralRelation:
    score: float = 0.0         # -1.0 (war) to +1.0 (alliance)
    at_war: bool = False
    treaty_trade: bool = False
    treaty_defense: bool = False
    sanction_sender: bool = False  # this country is imposing sanctions on the other

    @property
    def stance(self) -> DiplomaticStance:
        if self.at_war:
            return DiplomaticStance.AT_WAR
        if self.score >= 0.6:
            return DiplomaticStance.ALLIED
        if self.score >= 0.25:
            return DiplomaticStance.FRIENDLY
        if self.score >= -0.25:
            return DiplomaticStance.NEUTRAL
        if self.score >= -0.6:
            return DiplomaticStance.TENSE
        return DiplomaticStance.HOSTILE


class World:
    def __init__(self, year: int = 1900) -> None:
        self.year = year
        self.countries: Dict[str, Country] = {}
        self._relations: Dict[Tuple[str, str], BilateralRelation] = {}
        self.player_id: Optional[str] = None
        self.world_events: List[dict] = []
        self.rng = random.Random()

    # ── Country management ──────────────────────────────────────────────────

    def add_country(self, country: Country) -> None:
        self.countries[country.id] = country

    def remove_country(self, country_id: str) -> Optional[Country]:
        return self.countries.pop(country_id, None)

    @property
    def player_country(self) -> Optional[Country]:
        if self.player_id:
            return self.countries.get(self.player_id)
        return None

    # ── Relations ───────────────────────────────────────────────────────────

    def _rel_key(self, a: str, b: str) -> Tuple[str, str]:
        return (min(a, b), max(a, b))

    def get_relation(self, a_id: str, b_id: str) -> BilateralRelation:
        key = self._rel_key(a_id, b_id)
        if key not in self._relations:
            self._relations[key] = BilateralRelation(score=self._initial_relation_score(a_id, b_id))
        return self._relations[key]

    def set_relation_score(self, a_id: str, b_id: str, score: float) -> None:
        rel = self.get_relation(a_id, b_id)
        rel.score = max(-1.0, min(1.0, score))

    def adjust_relation(self, a_id: str, b_id: str, delta: float) -> None:
        rel = self.get_relation(a_id, b_id)
        rel.score = max(-1.0, min(1.0, rel.score + delta))

    def _initial_relation_score(self, a_id: str, b_id: str) -> float:
        """Seed initial bilateral score from shared traits."""
        a = self.countries.get(a_id)
        b = self.countries.get(b_id)
        if not a or not b:
            return 0.0
        score = 0.0
        # Shared government type
        if a.government.type == b.government.type:
            score += 0.15
        # Both democratic
        if a.government.is_democratic and b.government.is_democratic:
            score += 0.10
        # Ideological opposition
        if a.government.is_democratic and b.government.is_authoritarian:
            score -= 0.15
        # Shared language family
        if a.language.dominant_family == b.language.dominant_family:
            score += 0.10
        # Shared religion
        if a.culture.dominant_religion == b.culture.dominant_religion:
            score += 0.08
        # Development gap creates friction
        dev_gap = abs(a.economy.development_level - b.economy.development_level)
        score -= dev_gap * 0.1
        # Random noise
        score += self.rng.uniform(-0.15, 0.15)
        return max(-0.85, min(0.85, score))

    def get_neighbors(self, country_id: str) -> List[Country]:
        c = self.countries.get(country_id)
        if not c:
            return []
        return [self.countries[nid] for nid in c.neighbor_ids if nid in self.countries]

    # ── Rankings ────────────────────────────────────────────────────────────

    def power_ranking(self) -> List[Country]:
        return sorted(self.countries.values(), key=lambda c: c.global_power_score, reverse=True)

    def gdp_ranking(self) -> List[Country]:
        return sorted(self.countries.values(), key=lambda c: c.economy.gdp_total, reverse=True)

    def hdi_ranking(self) -> List[Country]:
        return sorted(self.countries.values(), key=lambda c: c.demographics.hdi, reverse=True)

    # ── Diplomacy actions ───────────────────────────────────────────────────

    def impose_sanctions(self, sender_id: str, target_id: str) -> None:
        rel = self.get_relation(sender_id, target_id)
        rel.sanction_sender = True
        rel.score = max(-1.0, rel.score - 0.2)
        target = self.countries.get(target_id)
        if target:
            target.economy.sanctions_level = min(1.0, target.economy.sanctions_level + 0.15)

    def lift_sanctions(self, sender_id: str, target_id: str) -> None:
        rel = self.get_relation(sender_id, target_id)
        rel.sanction_sender = False
        target = self.countries.get(target_id)
        if target:
            target.economy.sanctions_level = max(0.0, target.economy.sanctions_level - 0.15)

    def sign_trade_agreement(self, a_id: str, b_id: str) -> None:
        rel = self.get_relation(a_id, b_id)
        if not rel.treaty_trade:
            rel.treaty_trade = True
            rel.score = min(1.0, rel.score + 0.15)
            for cid in (a_id, b_id):
                c = self.countries.get(cid)
                if c:
                    c.economy.trade_agreements += 1

    def sign_defense_pact(self, a_id: str, b_id: str) -> None:
        rel = self.get_relation(a_id, b_id)
        if not rel.treaty_defense:
            rel.treaty_defense = True
            rel.score = min(1.0, rel.score + 0.20)

    def declare_war(self, aggressor_id: str, target_id: str) -> None:
        rel = self.get_relation(aggressor_id, target_id)
        rel.at_war = True
        rel.score = -1.0

    def end_war(self, a_id: str, b_id: str) -> None:
        rel = self.get_relation(a_id, b_id)
        rel.at_war = False
        rel.score = -0.6

    # ── World turn ──────────────────────────────────────────────────────────

    def advance_world_year(self) -> None:
        """Apply slow natural drift to all bilateral relations."""
        self.year += 1
        for (a_id, b_id), rel in self._relations.items():
            if rel.at_war:
                continue
            # Slow drift back toward zero unless treaties exist
            drift = -rel.score * 0.02
            if rel.treaty_trade:
                drift += 0.01
            if rel.treaty_defense:
                drift += 0.005
            rel.score = max(-1.0, min(1.0, rel.score + drift + self.rng.uniform(-0.02, 0.02)))

    def relations_for(self, country_id: str) -> List[Tuple[Country, BilateralRelation]]:
        """Return all bilateral relations for a given country, sorted by score."""
        result = []
        for (a, b), rel in self._relations.items():
            other_id = b if a == country_id else (a if b == country_id else None)
            if other_id and other_id in self.countries:
                result.append((self.countries[other_id], rel))
        result.sort(key=lambda x: x[1].score, reverse=True)
        return result

    def summary(self) -> dict:
        return {
            "year": self.year,
            "num_countries": len(self.countries),
            "power_ranking": [c.name for c in self.power_ranking()],
        }
