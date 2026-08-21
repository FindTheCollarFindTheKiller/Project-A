"""
Cross-system feedback loop calculations.
Each function takes a Country and returns computed values without mutating state.
The engine calls these to update the country each turn.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Tuple
import math

if TYPE_CHECKING:
    from ..models.country import Country
from ..models.enums import GovernmentType, EconomicSystem, TechTier


def compute_gdp_growth(c: Country) -> float:
    """Annual GDP growth rate incorporating all system interactions."""
    base = c.economy.base_growth_rate

    # Government efficiency
    corruption_penalty = c.government.corruption * 0.03
    stability_mod = (c.stability.economic - 0.5) * 0.02

    # Geography / resources
    resource_mod = c.geography.resource_wealth * 0.015
    trade_mod = c.geography.trade_access * c.economy.trade_openness * 0.02
    dutch_disease = c.economy.resource_dependency * 0.01  # penalty

    # Human capital
    education_mod = c.demographics.education_index * 0.02
    tech_mod = c.technology.economic_productivity_bonus * 0.015
    literacy_mod = (c.language.literacy_rate - 0.5) * 0.01

    # Demographic
    urbanization_mod = c.demographics.urbanization_bonus * 0.1
    population_scale = math.log10(max(1, c.demographics.population)) / 10.0 * 0.005

    # Sanctions and isolation
    sanctions_penalty = c.economy.sanctions_level * 0.04

    growth = (
        base
        + stability_mod
        + resource_mod
        + trade_mod
        + education_mod
        + tech_mod
        + literacy_mod
        + urbanization_mod
        + population_scale
        - corruption_penalty
        - dutch_disease
        - sanctions_penalty
    )
    return max(-0.15, min(0.20, growth))


def compute_stability(c: Country) -> Tuple[float, float, float, float]:
    """Returns (overall, political, social, economic) stability 0-1."""
    # --- Political stability ---
    # Recalibrated so a healthy democracy reaches 0.60-0.75, not 0.46
    legitimacy_score = c.government.legitimacy * 0.45
    civil_lib_score = c.government.civil_liberties * 0.25
    corruption_penalty = c.government.corruption * 0.15
    press_score = c.government.press_freedom * 0.15
    political = max(0.0, min(1.0,
        legitimacy_score + civil_lib_score + press_score - corruption_penalty
    ))

    # --- Social stability ---
    cohesion_score = c.culture.social_cohesion * 0.4
    happiness_score = c.demographics.happiness * 0.35
    ethnic_penalty = c.culture.ethnic_tension * 0.15
    inequality_penalty = c.economy.gini_coefficient * 0.1
    social = max(0.0, min(1.0,
        cohesion_score + happiness_score - ethnic_penalty - inequality_penalty
    ))

    # --- Economic stability ---
    econ_stability = c.economy.economic_stability
    unemployment_penalty = c.economy.unemployment * 0.3
    growth_bonus = max(0.0, c.economy.gdp_growth) * 2
    economic = max(0.0, min(1.0,
        econ_stability * 0.6 + growth_bonus - unemployment_penalty * 0.4
    ))

    overall = political * 0.35 + social * 0.35 + economic * 0.30
    return overall, political, social, economic


def compute_legitimacy(c: Country) -> float:
    """Government legitimacy from multiple sources."""
    base = c.government.legitimacy

    # Democratic legitimacy decays without elections, grows with civil liberties
    if c.government.is_democratic:
        civil_bonus = (c.government.civil_liberties - 0.5) * 0.1
        press_bonus = (c.government.press_freedom - 0.5) * 0.05
    else:
        civil_bonus = 0.0
        press_bonus = 0.0

    # Result-based legitimacy (autocracies need economic results)
    economic_results = (c.economy.gdp_growth - 0.01) * 0.5
    happiness_mod = (c.demographics.happiness - 0.5) * 0.1

    # Religious legitimacy for theocracies
    if c.government.type == GovernmentType.THEOCRACY:
        religious_bonus = c.culture.religious_influence * 0.15
    else:
        religious_bonus = 0.0

    # Long time in power corrodes democratic legitimacy
    tenure_penalty = min(0.1, c.government.years_in_power * 0.002)

    new_legitimacy = base + civil_bonus + press_bonus + economic_results + happiness_mod + religious_bonus - tenure_penalty
    return max(0.05, min(0.98, new_legitimacy))


def compute_revolution_risk(c: Country) -> float:
    """Probability of popular revolution this turn."""
    instability = (1.0 - c.stability.overall) * 0.40   # reduced from 0.50
    illegitimacy = (1.0 - c.government.legitimacy) * 0.3
    inequality_factor = c.economy.gini_coefficient * 0.1
    protest_factor = c.stability.protest_level * 0.1
    youth_factor = max(0.0, c.demographics.youth_bulge) * 0.08
    culture_factor = c.culture.protest_propensity * 0.05

    base_risk = instability + illegitimacy + inequality_factor + protest_factor + youth_factor + culture_factor

    # Military suppresses revolution
    suppression = c.military.internal_control * 0.4

    # Grace period: new governments are more resilient for their first 6 years
    grace = min(1.0, c.government.years_in_power / 6.0)

    return max(0.0, min(0.95, (base_risk - suppression) * grace))


def compute_coup_risk(c: Country) -> float:
    """Probability of military coup this turn."""
    if c.government.military_loyalty > 0.75:   # lowered from 0.80
        return 0.02
    vulnerability = c.government.coup_vulnerability * 0.45   # reduced from 0.60
    instability = (1.0 - c.stability.political) * 0.3
    economic_crisis = max(0.0, -c.economy.gdp_growth) * 0.5

    # Grace period: newly formed governments earn loyalty over time
    grace = min(1.0, c.government.years_in_power / 6.0)

    return max(0.0, min(0.90, (vulnerability + instability + economic_crisis) * grace))


def compute_happiness(c: Country) -> float:
    """Population happiness / life satisfaction."""
    gdp_score = c.economy.development_level * 0.25
    hdi_score = c.demographics.hdi * 0.25
    freedom_score = c.government.civil_liberties * 0.20
    stability_score = c.stability.social * 0.15
    inequality_penalty = c.economy.gini_coefficient * 0.15
    return max(0.05, min(0.98, gdp_score + hdi_score + freedom_score + stability_score - inequality_penalty))


def compute_brain_drain(c: Country) -> float:
    """Brain drain: -1 = severe drain, 0 = balanced, +1 = strong gain."""
    # Push factors (drive talent away)
    freedom_push = (0.5 - c.government.civil_liberties) * 0.4
    opportunity_push = (0.4 - c.economy.development_level) * 0.3
    stability_push = (0.5 - c.stability.overall) * 0.2

    # Pull factors (attract talent)
    salary_pull = c.economy.development_level * 0.3

    raw = salary_pull - freedom_push - opportunity_push - stability_push
    return max(-1.0, min(1.0, raw))


def compute_population_growth(c: Country) -> float:
    """Annual net population growth fraction."""
    base_growth = c.demographics.growth_rate
    healthcare_mod = (c.demographics.healthcare_index - 0.5) * 0.005
    development_mod = -(c.economy.development_level - 0.3) * 0.008  # richer = lower fertility
    conflict_penalty = -c.stability.civil_war_risk * 0.02
    net_migration = (c.demographics.immigration_rate - c.demographics.emigration_rate) / 1000.0
    return max(-0.05, min(0.06, base_growth + healthcare_mod + development_mod + conflict_penalty + net_migration))


def compute_tech_progress(c: Country) -> float:
    """Progress toward next technology tier (0-1 per decade)."""
    rd_score = min(1.0, c.technology.rd_spending_gdp * 25)
    education_score = c.demographics.education_index
    brain_score = max(0.0, c.technology.brain_drain) * 0.2
    adoption_score = c.technology.tech_adoption_rate * 0.3
    base = (rd_score * 0.4 + education_score * 0.3 + adoption_score * 0.2 + brain_score * 0.1)
    return base / 10.0  # per year


def compute_corruption_drift(c: Country) -> float:
    """Direction and magnitude of corruption change per year."""
    press_freedom = c.government.press_freedom
    civil_liberties = c.government.civil_liberties
    institutional_strength = c.government.judicial_independence

    cleansing = (press_freedom + civil_liberties + institutional_strength) / 3.0
    tendency = 0.3 - cleansing * 0.4  # clean institutions push corruption down

    # Authoritarian states have higher corruption drift up
    if c.government.is_authoritarian:
        tendency += 0.05
    return max(-0.05, min(0.05, tendency * 0.02))


def compute_military_loyalty(c: Country) -> float:
    """How loyal military is to current government."""
    base = c.government.military_loyalty
    pay_factor = c.government.effective_spending.get("military", 0.15) / 0.15 - 1.0
    legitimacy_factor = (c.government.legitimacy - 0.5) * 0.1
    return max(0.1, min(0.99, base + pay_factor * 0.05 + legitimacy_factor))


def compute_separatism_risk(c: Country) -> float:
    """Risk of regional separatist movements."""
    ethnic_factor = c.culture.ethnic_diversity * c.culture.ethnic_tension * 0.5
    linguistic_factor = c.language.linguistic_diversity * 0.2
    instability_factor = (1.0 - c.stability.political) * 0.2
    autonomy_factor = (1.0 - c.government.civil_liberties) * 0.1
    return max(0.0, min(0.80, ethnic_factor + linguistic_factor + instability_factor + autonomy_factor))


def compute_soft_power(c: Country) -> float:
    """International cultural influence."""
    cultural = c.culture.cultural_output * 0.4
    language_reach = c.language.diaspora_language_reach * 0.2
    development = c.economy.development_level * 0.2
    democracy_bonus = 0.1 if c.government.is_democratic else 0.0
    tech_bonus = c.technology.tier.value / 5.0 * 0.1
    return min(1.0, cultural + language_reach + development + democracy_bonus + tech_bonus)


def compute_trade_balance(c: Country) -> float:
    """Simplified trade balance in billions USD."""
    exports = (
        c.economy.gdp_total * c.geography.resource_wealth * 0.15
        + c.economy.gdp_total * c.economy.trade_openness * 0.08
        + c.economy.gdp_total * c.technology.tier.value / 5.0 * 0.05
    )
    imports = c.economy.gdp_total * c.economy.trade_openness * 0.10
    return exports - imports


def apply_all_feedback(c: Country) -> None:
    """
    Compute and apply one turn's worth of feedback to the country in-place.
    Call this after policy effects have been set.
    """
    # --- Economy ---
    growth = compute_gdp_growth(c)
    c.economy.gdp_growth = growth
    c.economy.gdp_total *= (1.0 + growth)
    c.economy.gdp_per_capita = (c.economy.gdp_total * 1e9) / max(1, c.demographics.population)
    c.economy.trade_balance = compute_trade_balance(c)

    # Unemployment drifts toward equilibrium based on growth
    unemployment_pressure = -growth * 2.0  # growth reduces unemployment
    c.economy.unemployment = max(0.01, min(0.50, c.economy.unemployment + unemployment_pressure * 0.1))

    # Inflation (simplistic monetary model)
    deficit_pressure = max(0.0, c.government.tax_rate - 0.15) * 0.01
    c.economy.inflation = max(0.0, min(0.30, c.economy.inflation + deficit_pressure - growth * 0.1))

    # Foreign debt grows with deficit spending
    if c.economy.gdp_growth < 0.02:
        c.economy.foreign_debt_gdp = min(2.0, c.economy.foreign_debt_gdp + 0.02)

    # --- Demographics ---
    pop_growth = compute_population_growth(c)
    c.demographics.population = int(c.demographics.population * (1.0 + pop_growth))
    c.demographics.growth_rate = pop_growth

    # Education drifts based on spending
    edu_spending = c.government.effective_spending.get("education", 0.12)
    edu_target = min(c.language.education_ceiling, edu_spending * 5)
    c.demographics.education_index += (edu_target - c.demographics.education_index) * 0.05

    # Healthcare drifts based on spending and development
    health_spending = c.government.effective_spending.get("healthcare", 0.10)
    health_target = min(0.98, health_spending * 6 + c.economy.development_level * 0.2)
    c.demographics.healthcare_index += (health_target - c.demographics.healthcare_index) * 0.05

    # Happiness
    c.demographics.happiness = compute_happiness(c)

    # --- Technology ---
    tech_progress = compute_tech_progress(c)
    c.technology.innovation_index = min(1.0, c.technology.innovation_index + tech_progress * 0.3)
    c.technology.brain_drain = compute_brain_drain(c)

    # Literacy drifts with education
    c.language.literacy_rate = min(0.99, c.language.literacy_rate + (c.demographics.education_index - c.language.literacy_rate) * 0.03)

    # --- Government ---
    c.government.legitimacy = compute_legitimacy(c)
    c.government.military_loyalty = compute_military_loyalty(c)
    corruption_drift = compute_corruption_drift(c)
    c.government.corruption = max(0.01, min(0.99, c.government.corruption + corruption_drift))
    c.government.years_in_power += 1

    # --- Culture ---
    # Slow cultural drift toward education-linked individualism
    edu_pull = (c.demographics.education_index - 0.5) * 0.02
    c.culture.individualism = max(0.0, min(1.0, c.culture.individualism + edu_pull * 0.01))
    c.culture.gender_equality = min(1.0, c.culture.gender_equality + c.demographics.education_index * 0.002)

    # Ethnic tension drifts down with prosperity
    prosperity_mod = -(c.demographics.happiness - 0.5) * 0.02
    c.culture.ethnic_tension = max(0.0, min(1.0, c.culture.ethnic_tension + prosperity_mod))

    # --- Military ---
    mil_spending = c.government.effective_spending.get("military", 0.15)
    mil_target = min(0.99, mil_spending * 10)
    c.military.equipment_quality += (mil_target - c.military.equipment_quality) * 0.05
    c.military.morale = max(0.1, min(0.99, c.military.morale + (0.6 - c.military.morale) * 0.03))

    # --- Stability ---
    overall, political, social, economic = compute_stability(c)
    c.stability.overall = overall
    c.stability.political = political
    c.stability.social = social
    c.stability.economic = economic
    c.stability.revolution_risk = compute_revolution_risk(c)
    c.stability.coup_risk = compute_coup_risk(c)
    c.stability.separatism_risk = compute_separatism_risk(c)
    c.stability.protest_level = max(0.0, min(1.0,
        (1.0 - c.stability.social) * 0.5
        + c.culture.protest_propensity * (1.0 - c.stability.political) * 0.4
    ))
    c.stability.civil_war_risk = max(0.0,
        c.stability.separatism_risk * 0.3
        + (c.stability.revolution_risk - 0.4) * 0.5
        if c.stability.revolution_risk > 0.4 else c.stability.separatism_risk * 0.1
    )

    # Decrement event cooldowns each turn and remove expired ones
    c.event_cooldowns = {
        eid: years - 1
        for eid, years in c.event_cooldowns.items()
        if years > 1
    }
