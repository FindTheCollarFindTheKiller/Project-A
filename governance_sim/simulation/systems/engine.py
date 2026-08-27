"""
Main simulation engine: orchestrates one turn per country.
"""
from __future__ import annotations
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.country import Country

from ..models.enums import GovernmentType, TechTier
from .feedback import apply_all_feedback
from .events import EventSystem, GameEvent
from .world import World


class TurnResult:
    def __init__(self) -> None:
        self.triggered_events: List[GameEvent] = []
        self.random_events: List[GameEvent] = []
        self.pending_choices: List[Tuple[GameEvent, "Country"]] = []
        self.log: List[str] = []

    @property
    def all_events(self) -> List[GameEvent]:
        return self.triggered_events + self.random_events

    def add_log(self, msg: str) -> None:
        self.log.append(msg)


class SimulationEngine:
    def __init__(self, world: World, rng: Optional[random.Random] = None) -> None:
        self.world = world
        self.rng = rng or random.Random()
        self.event_system = EventSystem(self.rng)

    # ── Public API ──────────────────────────────────────────────────────────

    def advance_turn(self, country: "Country", auto_resolve_events: bool = False) -> TurnResult:
        """Process one year for a single country. Returns events that need resolution."""
        result = TurnResult()

        # 0. Snapshot stats before feedback for delta tracking
        country.snapshot_stats()

        # 1. Apply cross-system feedback (drift, growth, stability updates)
        apply_all_feedback(country)

        # 2. Check for triggered events
        triggered = self.event_system.check_triggered_events(country)
        result.triggered_events = triggered

        # 3. Roll for random events
        random_events = self.event_system.roll_random_events(country, max_events=2)
        result.random_events = random_events

        # 4. Separate player-choice events from auto-resolved events
        for event in result.all_events:
            if event.is_player_choice() and not auto_resolve_events:
                result.pending_choices.append((event, country))
            else:
                # Auto-apply base effects only
                self.event_system.apply_event(event, country, choice_index=None)
                result.add_log(f"[Event] {event.name}: {event.description}")

        # 5. Technology tier advancement check
        self._check_tech_advancement(country, result)

        # 6. Revolution / Coup / Collapse checks
        self._check_political_upheaval(country, result)

        # 7. Advance year
        country.current_year += 1

        return result

    def advance_world_turn(self, auto_resolve_events: bool = True) -> dict:
        """Advance all non-player countries by one year (AI-controlled)."""
        results = {}
        for cid, country in self.world.countries.items():
            if cid == self.world.player_id:
                continue
            result = self.advance_turn(country, auto_resolve_events=True)
            results[cid] = result
        return results

    def resolve_event(self, event: GameEvent, country: "Country", choice_index: int) -> None:
        """Apply a player's choice to an event."""
        self.event_system.apply_event(event, country, choice_index)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _check_tech_advancement(self, country: "Country", result: TurnResult) -> None:
        from ..systems.feedback import compute_tech_progress
        progress = compute_tech_progress(country)
        if country.technology.tier.value < TechTier.ADVANCED.value:
            if self.rng.random() < progress:
                old_tier = country.technology.tier
                country.technology.tier = TechTier(country.technology.tier.value + 1)
                msg = (f"[Tech] {country.name} advances to {country.technology.tier_name}! "
                       f"(from {old_tier.name})")
                result.add_log(msg)
                country.add_history("Technology Leap", msg)
                country.economy.gdp_growth += 0.01

    def _check_political_upheaval(self, country: "Country", result: TurnResult) -> None:
        """Check for and apply revolution / coup / separatism events."""
        risk_modifiers = {
            "Easy": 0.5,
            "Normal": 1.0,
            "Hard": 1.3,
        }
        risk_modifier = risk_modifiers.get(getattr(self.world, "difficulty", "Normal"), 1.0)
        # Revolution
        if self.rng.random() < min(1.0, country.stability.revolution_risk * risk_modifier):
            self._apply_revolution(country, result)
        # Coup
        elif self.rng.random() < min(1.0, country.stability.coup_risk * risk_modifier):
            self._apply_coup(country, result)
        # Separatism
        elif self.rng.random() < country.stability.separatism_risk * 0.3:
            self._apply_separatism(country, result)

    def _apply_revolution(self, country: "Country", result: TurnResult) -> None:
        msg = f"[REVOLUTION] Popular uprising overthrows the government in {country.name}!"
        result.add_log(msg)
        country.add_history("Revolution", msg)
        # Transition toward democracy (simplified)
        if country.government.is_authoritarian:
            country.government.type = GovernmentType.REPUBLIC
        country.government.legitimacy = 0.4
        country.government.years_in_power = 0
        country.government.corruption = max(0.1, country.government.corruption - 0.2)
        country.government.civil_liberties = min(1.0, country.government.civil_liberties + 0.2)
        country.stability.overall = max(0.15, country.stability.overall - 0.25)
        country.economy.gdp_growth -= 0.05
        country.demographics.happiness += 0.1  # initial euphoria

    def _apply_coup(self, country: "Country", result: TurnResult) -> None:
        msg = f"[COUP] Military seizes power in {country.name}!"
        result.add_log(msg)
        country.add_history("Military Coup", msg)
        country.government.type = GovernmentType.AUTOCRACY
        country.government.military_loyalty = 0.85
        country.government.legitimacy = 0.30
        country.government.years_in_power = 0
        country.government.civil_liberties = max(0.1, country.government.civil_liberties - 0.25)
        country.government.press_freedom = max(0.1, country.government.press_freedom - 0.3)
        country.stability.overall = max(0.2, country.stability.overall - 0.15)
        country.government.budget_allocation["military"] = min(0.40,
            country.government.budget_allocation.get("military", 0.15) + 0.08)
        country.government.validate_budget()

    def _apply_separatism(self, country: "Country", result: TurnResult) -> None:
        msg = f"[SEPARATISM] A separatist movement gains significant ground in {country.name}."
        result.add_log(msg)
        country.add_history("Separatist Crisis", msg)
        country.stability.separatism_risk = max(0.0, country.stability.separatism_risk - 0.15)
        country.stability.political = max(0.1, country.stability.political - 0.1)
        country.government.legitimacy = max(0.1, country.government.legitimacy - 0.08)

    # ── Policy application ──────────────────────────────────────────────────

    @staticmethod
    def apply_policy(country: "Country", domain: str, **kwargs) -> List[str]:
        """
        Apply a policy change to the country. Returns a list of log messages.
        domain: 'budget', 'tax', 'social', 'military', 'trade'
        kwargs: specific policy parameters
        """
        logs = []
        gov = country.government

        if domain == "budget":
            for key, value in kwargs.items():
                if key in gov.budget_allocation:
                    old = gov.budget_allocation[key]
                    gov.budget_allocation[key] = max(0.0, min(0.5, float(value)))
                    logs.append(f"Budget: {key} changed from {old:.1%} to {gov.budget_allocation[key]:.1%}")
            gov.validate_budget()

        elif domain == "tax":
            old = gov.tax_rate
            gov.tax_rate = max(0.05, min(0.65, float(kwargs.get("rate", gov.tax_rate))))
            delta = gov.tax_rate - old
            country.economy.gdp_growth -= delta * 0.1  # tax drag
            country.demographics.happiness -= delta * 0.3
            logs.append(f"Tax rate: {old:.1%} → {gov.tax_rate:.1%}")

        elif domain == "military":
            action = kwargs.get("action")
            if action == "increase_size":
                factor = float(kwargs.get("factor", 1.1))
                old_size = country.military.size
                country.military.size = int(old_size * factor)
                cost_gdp = (country.military.size - old_size) * 50_000 / (country.economy.gdp_total * 1e9)
                country.government.budget_allocation["military"] = min(0.45,
                    country.government.budget_allocation.get("military", 0.15) + cost_gdp)
                gov.validate_budget()
                logs.append(f"Military expanded from {old_size:,} to {country.military.size:,}")
            elif action == "nuclear_program":
                country.government.budget_allocation["military"] = min(0.45,
                    country.government.budget_allocation.get("military", 0.15) + 0.05)
                gov.validate_budget()
                logs.append("Nuclear weapons program initiated (takes ~10 years)")

        elif domain == "social":
            target = kwargs.get("target")
            if target == "gender_equality":
                country.culture.gender_equality = min(1.0, country.culture.gender_equality + 0.05)
                country.demographics.education_index = min(1.0, country.demographics.education_index + 0.02)
                logs.append("Gender equality legislation passed")
            elif target == "ethnic_reconciliation":
                country.culture.ethnic_tension = max(0.0, country.culture.ethnic_tension - 0.08)
                country.government.legitimacy = min(1.0, country.government.legitimacy + 0.04)
                logs.append("Ethnic reconciliation program launched")
            elif target == "press_freedom":
                country.government.press_freedom = min(1.0, country.government.press_freedom + 0.08)
                country.government.corruption = max(0.0, country.government.corruption - 0.03)
                logs.append("Press freedom protections strengthened")
            elif target == "restrict_press":
                country.government.press_freedom = max(0.05, country.government.press_freedom - 0.1)
                country.government.civil_liberties = max(0.05, country.government.civil_liberties - 0.05)
                logs.append("Media restrictions imposed")

        elif domain == "trade":
            action = kwargs.get("action")
            if action == "open":
                country.economy.trade_agreements += 1
                country.economy.sanctions_level = max(0.0, country.economy.sanctions_level - 0.05)
                logs.append("New trade agreement signed")
            elif action == "protectionist":
                country.economy.trade_agreements = max(0, country.economy.trade_agreements - 1)
                country.economy.gdp_growth -= 0.005
                logs.append("Protectionist tariffs implemented")

        elif domain == "research":
            max_rd = 0.08
            current = country.technology.rd_spending_gdp
            if current >= max_rd:
                logs.append(f"R&D already at maximum effective level ({current:.1%} of GDP).")
            else:
                boost = float(kwargs.get("boost", 0.005))
                new_val = min(max_rd, current + boost)
                country.technology.rd_spending_gdp = new_val
                country.government.budget_allocation["research"] = min(0.15,
                    country.government.budget_allocation.get("research", 0.04) + boost)
                gov.validate_budget()
                logs.append(f"R&D spending increased: {current:.1%} → {new_val:.1%} of GDP")

        elif domain == "civil_rights":
            if country.government.is_authoritarian:
                logs.append("Authoritarian governments cannot pass Civil Rights Acts.")
            else:
                country.government.civil_liberties = min(1.0, country.government.civil_liberties + 0.10)
                country.demographics.happiness = min(1.0, country.demographics.happiness + 0.05)
                country.government.legitimacy = min(0.98, country.government.legitimacy + 0.08)
                logs.append("Civil Rights Act passed — civil liberties strengthened.")

        elif domain == "anti_corruption":
            if country.government.corruption < 0.15:
                logs.append("Corruption is already very low — further drives have diminishing returns.")
            else:
                country.government.corruption = max(0.05, country.government.corruption - 0.12)
                country.government.press_freedom = min(1.0, country.government.press_freedom + 0.05)
                country.government.legitimacy = max(0.05, country.government.legitimacy - 0.05)
                logs.append("Anti-Corruption Drive launched — short-term political resistance expected.")

        elif domain == "language":
            action = kwargs.get("action", "bilingual")
            from ..models.enums import LanguagePolicy
            if action == "bilingual":
                country.language.policy = LanguagePolicy.BILINGUAL
                country.language.literacy_rate = min(0.99, country.language.literacy_rate + 0.03)
                country.government.budget_allocation["education"] = min(0.25,
                    country.government.budget_allocation.get("education", 0.12) + 0.02)
                gov.validate_budget()
                logs.append("Bilingual education policy enacted — literacy rates will rise.")
            elif action == "promote":
                country.language.policy = LanguagePolicy.PROMOTE
                country.culture.national_identity = min(1.0, country.culture.national_identity + 0.04)
                logs.append("National language promotion campaign launched.")
            elif action == "suppress":
                country.language.policy = LanguagePolicy.SUPPRESS
                country.culture.ethnic_tension = min(1.0, country.culture.ethnic_tension + 0.06)
                country.government.civil_liberties = max(0.05, country.government.civil_liberties - 0.04)
                logs.append("Minority language suppression policy enacted — expect ethnic backlash.")

        elif domain == "immigration":
            action = kwargs.get("action", "open")
            if action == "open":
                country.demographics.immigration_rate = min(20.0, country.demographics.immigration_rate + 3.0)
                country.demographics.population += int(country.demographics.population * 0.01)
                country.culture.ethnic_diversity = min(1.0, country.culture.ethnic_diversity + 0.02)
                country.economy.gdp_growth += 0.005
                logs.append("Open immigration policy — population and economic growth expected.")
            elif action == "restrict":
                country.demographics.immigration_rate = max(0.0, country.demographics.immigration_rate - 2.0)
                country.culture.national_identity = min(1.0, country.culture.national_identity + 0.04)
                country.economy.gdp_growth -= 0.003
                logs.append("Immigration restrictions tightened — labour market effects will follow.")

        return logs
