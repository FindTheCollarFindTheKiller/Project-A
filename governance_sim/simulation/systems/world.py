"""
World: manages a collection of countries, bilateral relations, and world-level state.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models.country import Country
from ..models.enums import DiplomaticStance, GovernmentType, MilitaryDoctrine


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

    def declare_war(self, aggressor_id: str, target_id: str, _drag_allies: bool = True) -> List[str]:
        """Declare war and return log lines for any defense-pact allies dragged in."""
        rel = self.get_relation(aggressor_id, target_id)
        if rel.at_war:
            return []
        rel.at_war = True
        rel.score = -1.0
        if _drag_allies:
            return self._drag_in_allies(aggressor_id, target_id)
        return []

    def _drag_in_allies(self, aggressor_id: str, target_id: str) -> List[str]:
        """Defense-pact partners of the defender may honor their treaty and join the war."""
        aggressor = self.countries.get(aggressor_id)
        target = self.countries.get(target_id)
        if not aggressor or not target:
            return []
        logs: List[str] = []
        for other_id, other in list(self.countries.items()):
            if other_id in (aggressor_id, target_id):
                continue
            # Look up any existing pact without materializing new relation
            # records for pairs that have never actually interacted.
            pact = self._relations.get(self._rel_key(target_id, other_id))
            existing_war = self._relations.get(self._rel_key(aggressor_id, other_id))
            if pact and pact.treaty_defense and not (existing_war and existing_war.at_war):
                if self.rng.random() < 0.75:
                    self.declare_war(other_id, aggressor_id, _drag_allies=False)
                    logs.append(f"[WAR] {other.name} honors its defense pact and joins the war against {aggressor.name}!")
        return logs

    def end_war(self, a_id: str, b_id: str) -> None:
        rel = self.get_relation(a_id, b_id)
        rel.at_war = False
        rel.score = -0.6

    def sue_for_peace(self, initiator_id: str, target_id: str) -> bool:
        """Unilateral peace offer. Always succeeds but costs the initiator prestige."""
        rel = self.get_relation(initiator_id, target_id)
        if not rel.at_war:
            return False
        rel.at_war = False
        rel.score = max(rel.score, -0.4)
        initiator = self.countries.get(initiator_id)
        target = self.countries.get(target_id)
        if initiator:
            initiator.government.legitimacy = max(0.05, initiator.government.legitimacy - 0.03)
            initiator.military.war_exhaustion = max(0.0, initiator.military.war_exhaustion - 0.3)
        if target:
            target.military.war_exhaustion = max(0.0, target.military.war_exhaustion - 0.3)
        return True

    # ── Espionage ────────────────────────────────────────────────────────────

    _ESPIONAGE_OPS = ("steal_tech", "sabotage_economy", "incite_unrest")

    def attempt_espionage(self, actor_id: str, target_id: str, operation: str) -> str:
        """Covert operation against a rival. Returns a tagged log line describing the outcome."""
        actor = self.countries.get(actor_id)
        target = self.countries.get(target_id)
        if not actor or not target or operation not in self._ESPIONAGE_OPS:
            return ""

        success_chance = max(0.15, min(0.85, 0.5
            + (actor.technology.tier.value - target.technology.tier.value) * 0.05
            + (actor.culture.soft_power - target.culture.soft_power) * 0.10))
        caught_chance = max(0.10, min(0.75, 0.30 + target.government.press_freedom * 0.20
            - actor.culture.soft_power * 0.10))

        success = self.rng.random() < success_chance
        caught = self.rng.random() < caught_chance

        if operation == "steal_tech":
            if success:
                actor.technology.innovation_index = min(1.0, actor.technology.innovation_index + 0.05)
                outcome = f"{actor.name} successfully stole technological secrets from {target.name}."
            else:
                outcome = f"{actor.name}'s attempt to steal technology from {target.name} failed."
        elif operation == "sabotage_economy":
            if success:
                target.economy.gdp_growth -= 0.02
                outcome = f"{actor.name} sabotaged {target.name}'s economy."
            else:
                outcome = f"{actor.name}'s sabotage operation against {target.name} failed."
        else:  # incite_unrest
            if success:
                target.stability.protest_level = min(1.0, target.stability.protest_level + 0.15)
                target.government.legitimacy = max(0.05, target.government.legitimacy - 0.05)
                outcome = f"{actor.name} incited unrest within {target.name}."
            else:
                outcome = f"{actor.name}'s attempt to incite unrest in {target.name} failed."

        if caught:
            rel = self.get_relation(actor_id, target_id)
            rel.score = max(-1.0, rel.score - 0.35)
            outcome += f" {target.name} uncovered the operation, souring relations."
        return f"[ESPIONAGE] {outcome}"

    def _combat_power(self, c: Country) -> float:
        base = c.military.conventional_strength
        doctrine_bonus = 1.15 if c.military.doctrine == MilitaryDoctrine.EXPEDITIONARY else 1.0
        exhaustion_penalty = 1.0 - c.military.war_exhaustion * 0.4
        return max(0.01, base * doctrine_bonus * exhaustion_penalty) * self.rng.uniform(0.85, 1.15)

    def _force_peace(self, a_id: str, b_id: str, loser_id: str, winner_id: str) -> None:
        rel = self.get_relation(a_id, b_id)
        rel.at_war = False
        rel.score = -0.5
        loser = self.countries.get(loser_id)
        winner = self.countries.get(winner_id)
        if loser:
            loser.government.legitimacy = max(0.05, loser.government.legitimacy - 0.10)
            loser.military.war_exhaustion = 0.5
        if winner:
            winner.government.legitimacy = min(0.98, winner.government.legitimacy + 0.05)
            winner.military.war_exhaustion = 0.4

    def _resolve_war(self, a_id: str, b_id: str, rel: "BilateralRelation") -> Optional[str]:
        """Resolve one year of active combat between two countries. Returns a log line."""
        a = self.countries.get(a_id)
        b = self.countries.get(b_id)
        if not a or not b:
            rel.at_war = False
            return None

        power_a = self._combat_power(a)
        power_b = self._combat_power(b)
        swing = (power_a - power_b) / (power_a + power_b)  # -1 favors b, +1 favors a
        loser_a_share = max(0.0, -swing)
        loser_b_share = max(0.0, swing)

        cas_a = int(a.military.size * (0.004 + loser_a_share * 0.012) * self.rng.uniform(0.8, 1.2))
        cas_b = int(b.military.size * (0.004 + loser_b_share * 0.012) * self.rng.uniform(0.8, 1.2))
        a.military.size = max(5_000, a.military.size - cas_a)
        b.military.size = max(5_000, b.military.size - cas_b)

        a.economy.gdp_growth -= 0.015 + loser_a_share * 0.01
        b.economy.gdp_growth -= 0.015 + loser_b_share * 0.01
        a.demographics.happiness = max(0.02, a.demographics.happiness - 0.01 - loser_a_share * 0.02)
        b.demographics.happiness = max(0.02, b.demographics.happiness - 0.01 - loser_b_share * 0.02)
        a.military.war_exhaustion = min(1.0, a.military.war_exhaustion + 0.06 + loser_a_share * 0.05)
        b.military.war_exhaustion = min(1.0, b.military.war_exhaustion + 0.06 + loser_b_share * 0.05)

        if swing > 0.15:
            verdict = f"{a.name} advances"
        elif swing < -0.15:
            verdict = f"{b.name} advances"
        else:
            verdict = "stalemate"
        log = f"[WAR] {a.name} vs {b.name}: {verdict} ({cas_a:,} vs {cas_b:,} casualties)"

        exhausted_loser = None
        if a.military.war_exhaustion >= 0.9 and a.military.war_exhaustion >= b.military.war_exhaustion:
            exhausted_loser = a_id
        elif b.military.war_exhaustion >= 0.9 and b.military.war_exhaustion > a.military.war_exhaustion:
            exhausted_loser = b_id
        if exhausted_loser:
            winner_id = b_id if exhausted_loser == a_id else a_id
            self._force_peace(a_id, b_id, exhausted_loser, winner_id)
            log += f" — {self.countries[exhausted_loser].name} capitulates, war ends."
        return log

    # ── World turn ──────────────────────────────────────────────────────────

    def advance_world_year(self) -> List[str]:
        """Resolve active wars, apply slow relation drift, and decay war exhaustion at peace."""
        self.year += 1
        war_logs: List[str] = []
        combatant_ids = set()
        for (a_id, b_id), rel in self._relations.items():
            if rel.at_war:
                combatant_ids.add(a_id)
                combatant_ids.add(b_id)
                log = self._resolve_war(a_id, b_id, rel)
                if log:
                    war_logs.append(log)

        for cid, country in self.countries.items():
            if cid not in combatant_ids:
                country.military.war_exhaustion = max(0.0, country.military.war_exhaustion - 0.08)

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
        return war_logs

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
