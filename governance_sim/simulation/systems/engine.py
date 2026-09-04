"""
Main simulation engine: orchestrates one turn per country.
"""
from __future__ import annotations
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.country import Country

from ..models.enums import GovernmentType, TechTier, ElectionSystem, SuccessionType
from .feedback import apply_all_feedback
from .events import EventSystem, GameEvent
from .world import World
from .ai import OpponentAI


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
        self.opponent_ai = OpponentAI(self.rng)

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
                choice_index = self._choose_ai_event_response(event, country) if auto_resolve_events else None
                self.event_system.apply_event(event, country, choice_index=choice_index)
                result.add_log(f"[Event] {event.name}: {event.description}")

        # 5. Technology tier advancement check
        self._check_tech_advancement(country, result)

        # 6. Revolution / Coup / Collapse checks
        self._check_political_upheaval(country, result)

        # 6b. Democratic elections on a fixed term cycle
        self._check_elections(country, result)

        # 6c. Hereditary succession for monarchies
        self._check_succession(country, result)

        # 7. Advance year
        country.current_year += 1

        return result

    def advance_world_turn(self, auto_resolve_events: bool = True) -> dict:
        """Advance all non-player countries by one year (AI-controlled)."""
        results = {}
        for cid, country in self.world.countries.items():
            if cid == self.world.player_id:
                continue
            ai_logs = self.opponent_ai.take_turn(country, self.world, self.apply_policy)
            result = self.advance_turn(country, auto_resolve_events=True)
            result.log[0:0] = ai_logs
            results[cid] = result
        return results

    def _choose_ai_event_response(self, event: GameEvent, country: "Country") -> Optional[int]:
        if not event.choices:
            return None

        def score(choice: object) -> float:
            effects = getattr(choice, "effects", {})
            value = 0.0
            for path, delta in effects.items():
                if not isinstance(delta, (int, float)):
                    continue
                if "stability" in path or "legitimacy" in path or "happiness" in path:
                    value += delta * (2.0 if country.stability.overall < 0.45 else 1.0)
                elif "gdp" in path or "unemployment" in path:
                    value += delta * (1.5 if country.economy.gdp_growth < 0 else 0.8)
                elif "tension" in path or "corruption" in path:
                    value += delta * 1.2
                elif "civil_liberties" in path and country.government.is_democratic:
                    value += delta
            return value

        scores = [score(choice) for choice in event.choices]
        best = max(scores)
        # Near ties remain uncertain, which makes event handling less robotic.
        contenders = [i for i, value in enumerate(scores) if value >= best - 0.08]
        return self.rng.choice(contenders)

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

    def _check_elections(self, country: "Country", result: TurnResult) -> None:
        """Democracies hold elections on a fixed 4-year term; performance decides the outcome."""
        gov = country.government
        term_length = 4
        if not gov.is_democratic or gov.election_system == ElectionSystem.NONE:
            return
        if gov.years_in_power <= 0 or gov.years_in_power % term_length != 0:
            return

        approval = (
            country.demographics.happiness * 0.35
            + country.stability.overall * 0.30
            + max(0.0, min(1.0, country.economy.gdp_growth * 10)) * 0.20
            + (1.0 - gov.corruption) * 0.15
        )
        incumbent_wins = self.rng.random() < min(0.95, max(0.05, approval))
        if incumbent_wins:
            gov.legitimacy = min(0.98, gov.legitimacy + 0.05)
            msg = f"[Election] {country.name}: incumbent government re-elected (approval {approval:.0%})."
            country.add_history("Election", msg)
        else:
            gov.years_in_power = 0
            gov.legitimacy = min(0.98, max(gov.legitimacy, 0.55))
            gov.corruption = max(0.05, gov.corruption - 0.05)
            country.demographics.happiness = min(1.0, country.demographics.happiness + 0.05)
            msg = f"[Election] {country.name}: opposition wins, power transfers peacefully (approval {approval:.0%})."
            country.add_history("Change of Government", msg)
        result.add_log(msg)

    def _check_succession(self, country: "Country", result: TurnResult) -> None:
        """Hereditary monarchs eventually die; the heir's quality is a gamble."""
        gov = country.government
        if gov.succession_type != SuccessionType.HEREDITARY:
            return
        if self.rng.random() >= 0.03:
            return

        quality = self.rng.uniform(0.2, 1.0)
        gov.years_in_power = 0
        gov.legitimacy = max(0.05, min(0.98, gov.legitimacy + (quality - 0.55) * 0.25))
        if quality >= 0.75:
            descriptor = "a capable and popular heir"
            gov.corruption = max(0.05, gov.corruption - 0.04)
            country.demographics.happiness = min(1.0, country.demographics.happiness + 0.03)
        elif quality <= 0.4:
            descriptor = "a weak and contested heir"
            gov.corruption = min(0.95, gov.corruption + 0.05)
            country.stability.political = max(0.05, country.stability.political - 0.08)
            if quality <= 0.28:
                country.stability.separatism_risk = min(0.80, country.stability.separatism_risk + 0.05)
        else:
            descriptor = "an untested heir"
        msg = f"[Succession] {country.name}: the monarch has died; the throne passes to {descriptor}."
        result.add_log(msg)
        country.add_history("Royal Succession", msg)

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
