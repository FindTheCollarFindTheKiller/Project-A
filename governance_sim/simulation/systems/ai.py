"""Decision making for computer-controlled countries."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from ..models.country import Country
    from .world import World


class OpponentAI:
    """Small utility AI: prioritize threats, retain personality, add variation."""

    _PERSONALITY_BONUS = {
        "democratic": {"social": 1.15, "research": 1.10, "trade": 1.05},
        "authoritarian": {"military": 1.20, "budget": 1.10, "social": 0.85},
        "default": {"trade": 1.10, "military": 1.05, "research": 1.05},
    }

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def take_turn(self, country: "Country", world: "World", apply_policy) -> List[str]:
        """Apply one best-fit domestic move and, sometimes, a diplomatic move."""
        candidates = self._policy_candidates(country, world)
        personality = ("democratic" if country.government.is_democratic
                       else "authoritarian" if country.government.is_authoritarian
                       else "default")
        bonuses = self._PERSONALITY_BONUS[personality]
        weighted = [(score * bonuses.get(domain, 1.0), domain, kwargs, label)
                    for score, domain, kwargs, label in candidates]
        weighted.sort(reverse=True, key=lambda item: item[0])

        # Usually choose among the strongest options; occasionally take a
        # weaker move so opponents do not become perfectly predictable.
        pool = weighted[:min(3, len(weighted))]
        if not pool:
            return []
        if self.rng.random() < 0.18 and len(weighted) > 3:
            pool = weighted[:min(5, len(weighted))]
        choice = self.rng.choices(pool, weights=[max(0.05, item[0]) for item in pool], k=1)[0]
        _, domain, kwargs, label = choice
        logs = apply_policy(country, domain, **kwargs)
        actions = [f"[AI] {country.name}: {label}"] if logs else []

        diplomacy = self._diplomatic_move(country, world)
        if diplomacy:
            actions.append(f"[AI] {country.name}: {diplomacy}")
        return actions

    def _policy_candidates(self, c: "Country", world: "World") -> List[Tuple[float, str, dict, str]]:
        g = c.government
        e = c.economy
        s = c.stability
        candidates = [
            (max(0.0, 0.55 - s.overall) * 3.0, "budget",
             {"social_welfare": min(0.30, g.budget_allocation.get("social_welfare", 0.12) + 0.04)},
             "increased social welfare spending"),
            (max(0.0, g.corruption - 0.25) * 2.5, "anti_corruption", {}, "launched an anti-corruption drive"),
            (max(0.0, c.culture.ethnic_tension - 0.25) * 2.2, "social",
             {"target": "ethnic_reconciliation"}, "opened ethnic reconciliation talks"),
            (max(0.0, 0.48 - c.demographics.education_index) * 1.7, "research",
             {"boost": 0.005}, "increased research funding"),
            (max(0.0, 0.40 - c.technology.rd_spending_gdp) * 1.2, "research",
             {"boost": 0.005}, "invested in research"),
            (max(0.0, e.unemployment - 0.10) * 1.8, "trade", {"action": "open"}, "opened trade policy"),
            (max(0.0, 0.18 - c.military.conventional_strength) * 1.6, "military",
             {"action": "increase_size", "factor": 1.1}, "expanded the military"),
            (max(0.0, e.inflation - 0.12) * 1.8, "budget",
             {"social_welfare": max(0.04, g.budget_allocation.get("social_welfare", 0.12) - 0.02)},
             "tightened fiscal spending"),
        ]
        return [(score, domain, kwargs, label) for score, domain, kwargs, label in candidates if score > 0.03]

    def _diplomatic_move(self, c: "Country", world: "World") -> str:
        if self.rng.random() > 0.28:
            return ""
        options = []
        for other, relation in world.relations_for(c.id):
            if relation.at_war:
                continue
            power_gap = c.global_power_score - other.global_power_score
            if relation.score > 0.15 and not relation.treaty_trade:
                options.append((relation.score + 0.25, "trade", other))
            if relation.score > 0.35 and not relation.treaty_defense and c.military.conventional_strength < 0.55:
                options.append((relation.score + 0.15, "defense", other))
            if relation.score < -0.45 and power_gap > 0.12 and self.rng.random() < 0.20:
                options.append((0.25 + power_gap, "war", other))
        if not options:
            return ""
        _, action, target = self.rng.choice(sorted(options, reverse=True, key=lambda item: item[0])[:3])
        if action == "trade":
            world.sign_trade_agreement(c.id, target.id)
            return f"signed a trade agreement with {target.name}"
        if action == "defense":
            world.sign_defense_pact(c.id, target.id)
            return f"signed a defense pact with {target.name}"
        world.declare_war(c.id, target.id)
        return f"declared war on {target.name}"