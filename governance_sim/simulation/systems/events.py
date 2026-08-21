"""
Event definitions and the EventSystem that generates, checks, and resolves them.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.country import Country

from ..models.enums import EventType, DisasterType


@dataclass
class Choice:
    label: str
    description: str
    effects: Dict[str, Any]      # attribute-path -> delta or override
    probability_modifier: float = 0.0  # modifies outcome probabilities


@dataclass
class GameEvent:
    id: str
    name: str
    description: str
    type: EventType
    choices: List[Choice] = field(default_factory=list)
    severity: float = 0.5             # 0=minor, 1=catastrophic
    base_effects: Dict[str, Any] = field(default_factory=dict)

    def is_player_choice(self) -> bool:
        return len(self.choices) > 0


def _apply_delta(obj: Any, path: str, delta: Any) -> None:
    """Apply a delta to a nested attribute via dot-path (e.g. 'economy.gdp_growth')."""
    parts = path.split(".")
    for part in parts[:-1]:
        obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
    attr = parts[-1]
    if isinstance(obj, dict):
        current = obj.get(attr, 0)
        if isinstance(current, (int, float)) and isinstance(delta, (int, float)):
            obj[attr] = type(current)(current + delta)
        else:
            obj[attr] = delta
    else:
        current = getattr(obj, attr, None)
        if isinstance(current, (int, float)) and isinstance(delta, (int, float)):
            setattr(obj, attr, type(current)(current + delta))
        else:
            setattr(obj, attr, delta)


def apply_event_effects(country: Country, effects: Dict[str, Any]) -> None:
    for path, delta in effects.items():
        try:
            _apply_delta(country, path, delta)
        except AttributeError as e:
            import sys
            print(f"[event-warning] Bad effect path '{path}': {e}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Event catalogue
# ──────────────────────────────────────────────────────────────────────────────

def _build_event_catalogue() -> List[GameEvent]:
    return [

        # ── ECONOMIC ────────────────────────────────────────────────────────
        GameEvent(
            id="economic_boom",
            name="Economic Boom",
            description="Strong global demand and investor confidence drive exceptional growth.",
            type=EventType.ECONOMIC,
            severity=0.1,
            base_effects={"economy.gdp_growth": 0.02, "demographics.happiness": 0.05},
        ),
        GameEvent(
            id="recession",
            name="Economic Recession",
            description="Output contracts and unemployment rises sharply.",
            type=EventType.ECONOMIC,
            severity=0.6,
            base_effects={"economy.gdp_growth": -0.04, "economy.unemployment": 0.04,
                          "demographics.happiness": -0.08, "stability.economic": -0.1},
            choices=[
                Choice("Austerity Measures", "Cut spending to stabilise debt.",
                       {"government.budget_allocation.social_welfare": -0.03,
                        "economy.foreign_debt_gdp": -0.05, "demographics.happiness": -0.05}),
                Choice("Stimulus Package", "Borrow to fund economic stimulus.",
                       {"economy.gdp_growth": 0.02, "economy.foreign_debt_gdp": 0.08,
                        "demographics.happiness": 0.03}),
                Choice("Do Nothing", "Let the market self-correct.",
                       {}),
            ],
        ),
        GameEvent(
            id="oil_discovery",
            name="Major Resource Discovery",
            description="Significant reserves of oil and natural gas discovered offshore.",
            type=EventType.ECONOMIC,
            severity=0.1,
            base_effects={"economy.resource_income_fraction": 0.08, "economy.gdp_total": 0.0},
        ),
        GameEvent(
            id="trade_partner_crisis",
            name="Trade Partner Crisis",
            description="A major trading partner enters political turmoil, disrupting exports.",
            type=EventType.ECONOMIC,
            severity=0.4,
            base_effects={"economy.trade_balance": -5.0, "economy.gdp_growth": -0.01},
        ),
        GameEvent(
            id="debt_crisis",
            name="Debt Crisis",
            description="Creditors lose confidence and demand immediate repayment.",
            type=EventType.ECONOMIC,
            severity=0.8,
            base_effects={"economy.gdp_growth": -0.05, "economy.inflation": 0.08,
                          "stability.economic": -0.2, "government.legitimacy": -0.1},
            choices=[
                Choice("IMF Bailout", "Accept conditional foreign financial assistance.",
                       {"economy.foreign_debt_gdp": -0.2, "government.civil_liberties": -0.05,
                        "government.budget_allocation.social_welfare": -0.04}),
                Choice("Default", "Refuse to pay and restructure debt unilaterally.",
                       {"economy.foreign_debt_gdp": -0.3, "economy.sanctions_level": 0.2,
                        "economy.trade_agreements": -2}),
            ],
        ),

        # ── POLITICAL ────────────────────────────────────────────────────────
        GameEvent(
            id="election_scandal",
            name="Election Scandal",
            description="Evidence of electoral fraud surfaces, shaking public confidence.",
            type=EventType.TRIGGERED,
            severity=0.6,
            base_effects={"government.legitimacy": -0.15, "stability.political": -0.1,
                          "demographics.happiness": -0.05},
        ),
        GameEvent(
            id="constitutional_reform",
            name="Constitutional Reform Movement",
            description="Civil society demands significant constitutional changes.",
            type=EventType.TRIGGERED,
            severity=0.4,
            base_effects={},
            choices=[
                Choice("Grant Reforms", "Expand civil liberties and democratic oversight.",
                       {"government.civil_liberties": 0.1, "government.legitimacy": 0.1,
                        "government.executive_strength": -0.05}),
                Choice("Limited Concessions", "Offer symbolic reforms.",
                       {"government.legitimacy": 0.03, "stability.protest_level": -0.1}),
                Choice("Suppress Movement", "Use security forces to end protests.",
                       {"stability.protest_level": -0.2, "government.civil_liberties": -0.05,
                        "government.legitimacy": -0.1, "culture.ethnic_tension": 0.05}),
            ],
        ),
        GameEvent(
            id="corruption_scandal",
            name="Corruption Scandal",
            description="A major corruption scandal implicates senior officials.",
            type=EventType.TRIGGERED,
            severity=0.5,
            base_effects={"government.legitimacy": -0.12, "government.corruption": 0.05},
            choices=[
                Choice("Prosecute Officials", "Hold corrupt officials accountable.",
                       {"government.corruption": -0.08, "government.legitimacy": 0.08,
                        "government.press_freedom": 0.03}),
                Choice("Cover It Up", "Suppress the story.",
                       {"government.press_freedom": -0.08, "government.corruption": 0.03,
                        "government.legitimacy": -0.05}),
            ],
        ),
        GameEvent(
            id="populist_movement",
            name="Populist Movement Rises",
            description="A populist political movement challenges the establishment.",
            type=EventType.TRIGGERED,
            severity=0.5,
            base_effects={"stability.political": -0.1},
            choices=[
                Choice("Engage and Co-opt", "Adopt some populist policies to defuse the movement.",
                       {"government.legitimacy": 0.05, "economy.gini_coefficient": -0.03}),
                Choice("Dismiss and Oppose", "Publicly fight the movement.",
                       {"stability.political": -0.05, "stability.protest_level": 0.1}),
            ],
        ),

        # ── SOCIAL / CULTURAL ─────────────────────────────────────────────
        GameEvent(
            id="social_movement",
            name="Major Social Movement",
            description="A broad social movement demands equality and justice.",
            type=EventType.TRIGGERED,
            severity=0.4,
            base_effects={},
            choices=[
                Choice("Support Reforms", "Pass meaningful social reform legislation.",
                       {"culture.gender_equality": 0.08, "government.civil_liberties": 0.06,
                        "demographics.happiness": 0.05, "government.legitimacy": 0.06}),
                Choice("Partial Reforms", "Acknowledge concerns but move slowly.",
                       {"culture.gender_equality": 0.03, "demographics.happiness": 0.02}),
                Choice("Reject Demands", "Maintain the status quo.",
                       {"stability.protest_level": 0.15, "culture.ethnic_tension": 0.05}),
            ],
        ),
        GameEvent(
            id="cultural_renaissance",
            name="Cultural Renaissance",
            description="A flourishing of arts, literature, and national pride.",
            type=EventType.RANDOM,
            severity=0.1,
            base_effects={"culture.cultural_output": 0.08, "culture.national_identity": 0.05,
                          "demographics.happiness": 0.03},
        ),
        GameEvent(
            id="ethnic_conflict",
            name="Ethnic Conflict Erupts",
            description="Long-standing ethnic tensions turn violent in several cities.",
            type=EventType.TRIGGERED,
            severity=0.8,
            base_effects={"culture.ethnic_tension": 0.15, "stability.social": -0.2,
                          "economy.gdp_growth": -0.02, "demographics.happiness": -0.1},
            choices=[
                Choice("Deploy Security Forces", "Restore order by force.",
                       {"stability.social": 0.05, "government.civil_liberties": -0.08}),
                Choice("Open Dialogue Process", "Convene a national reconciliation council.",
                       {"culture.ethnic_tension": -0.08, "stability.social": 0.1,
                        "government.legitimacy": 0.05}),
                Choice("Offer Regional Autonomy", "Grant affected minorities greater self-governance.",
                       {"culture.ethnic_tension": -0.15, "stability.separatism_risk": 0.1}),
            ],
        ),
        GameEvent(
            id="pandemic",
            name="Epidemic Outbreak",
            description="A dangerous disease spreads through the population.",
            type=EventType.RANDOM,
            severity=0.75,
            base_effects={"demographics.healthcare_index": -0.1, "economy.gdp_growth": -0.03,
                          "stability.social": -0.15, "demographics.happiness": -0.1},
            choices=[
                Choice("Aggressive Containment", "Implement strict quarantine and contact tracing.",
                       {"demographics.healthcare_index": 0.05, "economy.gdp_growth": -0.02,
                        "government.legitimacy": 0.05}),
                Choice("Minimal Restrictions", "Prioritise economic continuity.",
                       {"economy.gdp_growth": 0.01, "demographics.healthcare_index": -0.05,
                        "government.legitimacy": -0.05}),
            ],
        ),

        # ── MILITARY / SECURITY ──────────────────────────────────────────
        GameEvent(
            id="military_coup_attempt",
            name="Military Coup Attempt",
            description="Disloyal military factions attempt to seize the government.",
            type=EventType.TRIGGERED,
            severity=0.95,
            base_effects={"stability.political": -0.3, "government.legitimacy": -0.2},
            choices=[
                Choice("Defeat the Coup", "Rally loyal forces; the coup collapses.",
                       {"government.military_loyalty": 0.1, "government.legitimacy": 0.1,
                        "stability.political": 0.05}),
                Choice("Negotiate", "Offer coup leaders concessions to stand down.",
                       {"government.executive_strength": -0.1, "government.military_loyalty": 0.05}),
            ],
        ),
        GameEvent(
            id="terrorist_attack",
            name="Major Terrorist Attack",
            description="A devastating attack kills hundreds and shocks the nation.",
            type=EventType.RANDOM,
            severity=0.7,
            base_effects={"stability.social": -0.15, "demographics.happiness": -0.08,
                          "government.legitimacy": -0.05},
            choices=[
                Choice("Increase Security Spending", "Invest heavily in intelligence and policing.",
                       {"government.budget_allocation.military": 0.03,
                        "government.civil_liberties": -0.05}),
                Choice("Address Root Causes", "Invest in at-risk communities.",
                       {"economy.gini_coefficient": -0.02, "culture.ethnic_tension": -0.05,
                        "economy.gdp_growth": -0.005}),
            ],
        ),
        GameEvent(
            id="border_tension",
            name="Border Skirmish",
            description="Armed clashes with a neighboring country raise war fears.",
            type=EventType.TRIGGERED,
            severity=0.6,
            base_effects={"stability.political": -0.08, "government.budget_allocation.military": 0.02},
            choices=[
                Choice("Military Buildup", "Reinforce the border and signal resolve.",
                       {"military.morale": 0.05, "economy.gdp_growth": -0.01,
                        "government.legitimacy": 0.04}),
                Choice("Diplomatic Dialogue", "Seek international mediation.",
                       {"government.legitimacy": 0.03, "culture.soft_power_bonus": 0.03}),
                Choice("Escalate", "Launch limited military action.",
                       {"military.morale": 0.1, "government.legitimacy": 0.05,
                        "stability.political": -0.1, "economy.gdp_growth": -0.02}),
            ],
        ),

        # ── TECHNOLOGY / ENVIRONMENT ─────────────────────────────────────
        GameEvent(
            id="tech_breakthrough",
            name="Technological Breakthrough",
            description="Researchers make a paradigm-shifting scientific discovery.",
            type=EventType.RANDOM,
            severity=0.1,
            base_effects={"technology.innovation_index": 0.1, "economy.gdp_growth": 0.01,
                          "demographics.happiness": 0.03},
        ),
        GameEvent(
            id="natural_disaster",
            name="Natural Disaster",
            description="A severe natural disaster devastates part of the country.",
            type=EventType.RANDOM,
            severity=0.7,
            base_effects={"economy.gdp_growth": -0.025, "stability.social": -0.1,
                          "demographics.happiness": -0.08, "government.legitimacy": -0.05},
            choices=[
                Choice("Emergency Response", "Deploy full national resources for relief.",
                       {"government.budget_allocation.infrastructure": 0.04,
                        "government.legitimacy": 0.08, "economy.foreign_debt_gdp": 0.03}),
                Choice("International Aid", "Request foreign assistance.",
                       {"government.legitimacy": 0.03, "culture.soft_power_bonus": 0.02}),
            ],
        ),
        GameEvent(
            id="environmental_crisis",
            name="Environmental Crisis",
            description="Severe pollution or ecosystem collapse threatens public health.",
            type=EventType.TRIGGERED,
            severity=0.65,
            base_effects={"demographics.healthcare_index": -0.08, "demographics.happiness": -0.06,
                          "economy.gdp_growth": -0.01},
            choices=[
                Choice("Green Investment", "Redirect funds to environmental protection.",
                       {"government.budget_allocation.research": 0.02,
                        "economy.gdp_growth": -0.005, "culture.soft_power_bonus": 0.05}),
                Choice("Ignore Reports", "Deny the crisis to protect industry.",
                       {"government.press_freedom": -0.05, "demographics.healthcare_index": -0.03}),
            ],
        ),

        # ── DIPLOMATIC ────────────────────────────────────────────────────
        GameEvent(
            id="foreign_sanctions",
            name="International Sanctions Imposed",
            description="A coalition of nations imposes economic sanctions.",
            type=EventType.DIPLOMATIC,
            severity=0.7,
            base_effects={"economy.sanctions_level": 0.2, "economy.trade_agreements": -1,
                          "economy.gdp_growth": -0.025, "government.legitimacy": -0.05},
        ),
        GameEvent(
            id="trade_agreement",
            name="Major Trade Agreement Signed",
            description="A landmark free trade agreement opens new markets.",
            type=EventType.DIPLOMATIC,
            severity=0.1,
            base_effects={"economy.trade_agreements": 2, "economy.gdp_growth": 0.01,
                          "demographics.happiness": 0.02},
        ),
        GameEvent(
            id="refugee_crisis",
            name="Refugee Crisis",
            description="A wave of refugees from a neighboring conflict arrives.",
            type=EventType.DIPLOMATIC,
            severity=0.5,
            base_effects={"demographics.immigration_rate": 5.0},
            choices=[
                Choice("Open Borders", "Accept refugees with full integration support.",
                       {"culture.ethnic_diversity": 0.04, "demographics.population": 50_000,
                        "government.legitimacy": 0.03, "economy.gdp_growth": 0.005}),
                Choice("Controlled Admission", "Accept limited numbers through processing.",
                       {"demographics.population": 10_000, "government.legitimacy": 0.0}),
                Choice("Close Borders", "Refuse entry; return refugees.",
                       {"culture.ethnic_tension": 0.05, "culture.soft_power_bonus": -0.05,
                        "government.legitimacy": -0.05}),
            ],
        ),

        # ── NEW EVENTS ────────────────────────────────────────────────────
        GameEvent(
            id="alliance_offer",
            name="Alliance Offer",
            description="A neighboring state extends a formal proposal for military alliance.",
            type=EventType.DIPLOMATIC,
            severity=0.2,
            base_effects={},
            choices=[
                Choice("Accept Alliance", "Form a mutual defense pact.",
                       {"government.legitimacy": 0.04, "military.morale": 0.05,
                        "culture.soft_power_bonus": 0.04}),
                Choice("Decline Politely", "Remain independent but friendly.",
                       {"culture.soft_power_bonus": 0.01}),
                Choice("Refuse Sharply", "Send a strong message of independence.",
                       {"culture.national_identity": 0.05, "government.legitimacy": 0.02}),
            ],
        ),
        GameEvent(
            id="brain_drain_crisis",
            name="Brain Drain Crisis",
            description="Record numbers of educated professionals are emigrating, "
                         "hollowing out key industries.",
            type=EventType.TRIGGERED,
            severity=0.6,
            base_effects={"technology.innovation_index": -0.08, "demographics.education_index": -0.04,
                          "economy.gdp_growth": -0.01},
            choices=[
                Choice("Incentive Packages", "Offer tax breaks and grants to retain talent.",
                       {"technology.brain_drain": 0.15, "economy.foreign_debt_gdp": 0.03}),
                Choice("Expand Universities", "Invest in education to build new talent pools.",
                       {"government.budget_allocation.education": 0.03,
                        "demographics.education_index": 0.03}),
                Choice("Accept the Trend", "No intervention.",
                       {}),
            ],
        ),
        GameEvent(
            id="trade_boom",
            name="Global Trade Boom",
            description="A surge in global commodity prices dramatically boosts export revenue.",
            type=EventType.RANDOM,
            severity=0.1,
            base_effects={"economy.gdp_growth": 0.025, "economy.trade_balance": 8.0,
                          "demographics.happiness": 0.04, "government.legitimacy": 0.03},
        ),
        GameEvent(
            id="religious_revival",
            name="Religious Revival",
            description="A sweeping religious revival movement reshapes social values "
                         "and puts pressure on secular institutions.",
            type=EventType.TRIGGERED,
            severity=0.45,
            base_effects={"culture.religious_influence": 0.08},
            choices=[
                Choice("Embrace the Revival", "Align government policy with religious values.",
                       {"government.legitimacy": 0.08, "culture.secularism": -0.08,
                        "government.civil_liberties": -0.04}),
                Choice("Maintain Secularism", "Reaffirm separation of church and state.",
                       {"government.civil_liberties": 0.05, "government.legitimacy": -0.04,
                        "culture.religious_influence": -0.04}),
                Choice("Commission Dialogue", "Facilitate national debate on values.",
                       {"culture.national_identity": 0.04, "demographics.happiness": 0.02}),
            ],
        ),
        GameEvent(
            id="foreign_interference",
            name="Foreign Interference Scandal",
            description="Evidence surfaces that a foreign power covertly funded opposition "
                         "groups and spread disinformation.",
            type=EventType.RANDOM,
            severity=0.55,
            base_effects={"stability.political": -0.1, "government.legitimacy": -0.07,
                          "culture.national_identity": 0.05},
            choices=[
                Choice("Expel Diplomats", "Declare persona non grata and retaliate diplomatically.",
                       {"culture.soft_power_bonus": -0.03, "government.legitimacy": 0.06}),
                Choice("Launch Investigation", "Form an independent inquiry.",
                       {"government.press_freedom": 0.04, "government.legitimacy": 0.04}),
                Choice("Downplay", "Avoid escalation and keep quiet.",
                       {"government.press_freedom": -0.03}),
            ],
        ),
        GameEvent(
            id="scientific_expedition",
            name="Scientific Expedition Returns",
            description="A government-funded research expedition returns with "
                         "groundbreaking discoveries.",
            type=EventType.RANDOM,
            severity=0.1,
            base_effects={"technology.innovation_index": 0.07, "technology.rd_spending_gdp": 0.003,
                          "demographics.happiness": 0.03, "culture.soft_power_bonus": 0.04},
        ),
        GameEvent(
            id="famine",
            name="Food Crisis",
            description="Crop failures and supply chain disruptions push millions "
                         "to the edge of hunger.",
            type=EventType.TRIGGERED,
            severity=0.80,
            base_effects={"demographics.healthcare_index": -0.10, "demographics.happiness": -0.12,
                          "stability.social": -0.15, "government.legitimacy": -0.08},
            choices=[
                Choice("Emergency Food Program", "Divert budget to subsidise food.",
                       {"demographics.happiness": 0.08, "economy.foreign_debt_gdp": 0.05,
                        "government.legitimacy": 0.06}),
                Choice("International Appeal", "Request food aid from allies and the UN.",
                       {"government.legitimacy": 0.03, "culture.soft_power_bonus": -0.03,
                        "demographics.happiness": 0.04}),
                Choice("Price Controls", "Cap food prices by law.",
                       {"demographics.happiness": 0.05, "economy.gdp_growth": -0.01}),
            ],
        ),
        GameEvent(
            id="diplomatic_summit",
            name="International Summit",
            description="Your nation is invited to host a major multilateral summit, "
                         "putting you at the centre of world diplomacy.",
            type=EventType.DIPLOMATIC,
            severity=0.1,
            base_effects={"culture.soft_power_bonus": 0.06, "economy.gdp_growth": 0.005},
            choices=[
                Choice("Host Grand Summit", "Pull out all stops for a prestige event.",
                       {"culture.soft_power_bonus": 0.08, "government.legitimacy": 0.05,
                        "economy.foreign_debt_gdp": 0.02}),
                Choice("Quiet Working Summit", "Host efficiently without fanfare.",
                       {"culture.soft_power_bonus": 0.04, "economy.trade_agreements": 1}),
            ],
        ),
        GameEvent(
            id="industrial_accident",
            name="Major Industrial Accident",
            description="A catastrophic factory or energy plant accident kills workers "
                         "and pollutes a major region.",
            type=EventType.RANDOM,
            severity=0.65,
            base_effects={"demographics.healthcare_index": -0.05, "demographics.happiness": -0.07,
                          "government.legitimacy": -0.06, "culture.soft_power_bonus": -0.03},
            choices=[
                Choice("Full Accountability", "Prosecute negligent firms and compensate victims.",
                       {"government.legitimacy": 0.06, "government.press_freedom": 0.03}),
                Choice("Cover It Up", "Suppress media coverage to protect industry.",
                       {"government.press_freedom": -0.08, "government.corruption": 0.04}),
            ],
        ),
        GameEvent(
            id="protest_crackdown",
            name="Protest Crackdown",
            description="Security forces clash violently with protesters, drawing "
                         "international condemnation.",
            type=EventType.TRIGGERED,
            severity=0.70,
            base_effects={"stability.protest_level": -0.2, "government.civil_liberties": -0.06,
                          "culture.soft_power_bonus": -0.05},
            choices=[
                Choice("Double Down", "Authorise further security measures.",
                       {"stability.protest_level": -0.15, "government.civil_liberties": -0.08,
                        "government.legitimacy": -0.05}),
                Choice("Open Talks", "Invite protest leaders to negotiate.",
                       {"government.legitimacy": 0.06, "government.civil_liberties": 0.04,
                        "stability.protest_level": -0.1}),
            ],
        ),
    ]


EVENT_CATALOGUE: List[GameEvent] = _build_event_catalogue()
_EVENT_MAP: Dict[str, GameEvent] = {e.id: e for e in EVENT_CATALOGUE}

# Per-event cooldown in years (0 = no cooldown)
EVENT_COOLDOWNS: Dict[str, int] = {
    "border_tension": 3,
    "military_coup_attempt": 5,
    "pandemic": 8,
    "debt_crisis": 4,
    "election_scandal": 3,
    "ethnic_conflict": 4,
    "famine": 4,
    "foreign_interference": 3,
    "industrial_accident": 3,
    "protest_crackdown": 2,
    "refugee_crisis": 3,
    "religious_revival": 5,
    "brain_drain_crisis": 4,
    "diplomatic_summit": 3,
    "alliance_offer": 4,
    "environmental_crisis": 5,
}


class EventSystem:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def _on_cooldown(self, event_id: str, country: Country) -> bool:
        return country.event_cooldowns.get(event_id, 0) > 0

    def _passes_trigger(self, event_id: str, country: Country) -> bool:
        """Check if a triggered event's conditions are met."""
        c = country
        triggers = {
            "recession": c.economy.gdp_growth < -0.01,
            "debt_crisis": c.economy.foreign_debt_gdp > 1.2,
            "election_scandal": c.government.corruption > 0.6 and c.government.is_democratic,
            "constitutional_reform": c.stability.protest_level > 0.5,
            "corruption_scandal": c.government.corruption > 0.55,
            "populist_movement": c.economy.gini_coefficient > 0.50 and c.stability.protest_level > 0.35,
            "social_movement": c.culture.gender_equality < 0.35 or c.government.civil_liberties < 0.35,
            "ethnic_conflict": c.culture.ethnic_tension > 0.65,
            "military_coup_attempt": c.stability.coup_risk > 0.45,
            "border_tension": len(c.neighbor_ids) > 0 and c.stability.political < 0.45,
            "environmental_crisis": c.economy.gdp_total > 200 and c.technology.rd_spending_gdp < 0.01,
            "brain_drain_crisis": c.technology.brain_drain < -0.45,
            "religious_revival": c.culture.religious_influence > 0.70 and c.culture.secularism < 0.30,
            "famine": c.geography.agricultural_potential < 0.25 and c.demographics.healthcare_index < 0.45,
            "protest_crackdown": c.stability.protest_level > 0.60 and not c.government.is_democratic,
        }
        return triggers.get(event_id, False)

    def check_triggered_events(self, country: Country) -> List[GameEvent]:
        """Return all triggered events whose conditions are currently met and not on cooldown."""
        triggered = []
        for event in EVENT_CATALOGUE:
            if (event.type == EventType.TRIGGERED
                    and not self._on_cooldown(event.id, country)
                    and self._passes_trigger(event.id, country)):
                triggered.append(event)
        return triggered

    def roll_random_events(self, country: Country, max_events: int = 2) -> List[GameEvent]:
        """Draw random events weighted by disaster geography and luck, skipping cooldowns."""
        random_pool = [
            e for e in EVENT_CATALOGUE
            if e.type == EventType.RANDOM and not self._on_cooldown(e.id, country)
        ]
        # Weight events by contextual factors
        weights = []
        for event in random_pool:
            if event.id == "natural_disaster":
                w = max(0.1, country.geography.disaster_frequency * 3)
            elif event.id == "pandemic":
                w = 0.3 + (1.0 - country.demographics.healthcare_index) * 0.5
            elif event.id == "tech_breakthrough":
                w = country.technology.innovation_output * 0.5
            elif event.id == "economic_boom":
                w = 0.3 + country.stability.economic * 0.4
            elif event.id == "cultural_renaissance":
                w = country.culture.cultural_output * 0.5
            elif event.id == "trade_boom":
                w = 0.3 + country.economy.trade_openness * 0.4
            elif event.id == "scientific_expedition":
                w = 0.2 + country.technology.rd_spending_gdp * 10
            elif event.id == "industrial_accident":
                w = 0.2 + country.economy.sector_weights.get("Manufacturing", 0.25) * 0.5
            elif event.id == "terrorist_attack":
                w = 0.15 + country.culture.ethnic_tension * 0.3
            else:
                w = 0.4
            weights.append(w)

        n = self.rng.randint(0, max_events)
        if n == 0 or not random_pool:
            return []
        total = sum(weights)
        norm = [w / total for w in weights]
        chosen_indices = self.rng.choices(range(len(random_pool)), weights=norm, k=n)
        seen = set()
        result = []
        for i in chosen_indices:
            if i not in seen:
                seen.add(i)
                result.append(random_pool[i])
        return result

    def apply_event(self, event: GameEvent, country: Country,
                    choice_index: Optional[int] = None) -> None:
        """Apply base effects and optional choice effects; set cooldown."""
        apply_event_effects(country, event.base_effects)
        if choice_index is not None and event.choices:
            idx = max(0, min(len(event.choices) - 1, choice_index))
            apply_event_effects(country, event.choices[idx].effects)
        country.add_history(event.name, event.description)
        # Set cooldown so this event cannot fire again immediately
        cooldown = EVENT_COOLDOWNS.get(event.id, 0)
        if cooldown > 0:
            country.event_cooldowns[event.id] = cooldown

    def get_event(self, event_id: str) -> Optional[GameEvent]:
        return _EVENT_MAP.get(event_id)
