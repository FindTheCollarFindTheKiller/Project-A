"""
AI Advisor system — analyses country state and returns prioritised warnings and opportunities.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.country import Country


@dataclass
class Warning:
    severity: str          # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    category: str          # "political", "economic", "social", "military"
    message: str
    recommendation: str
    value: float = 0.0     # the metric value that triggered this warning


@dataclass
class Opportunity:
    category: str
    message: str
    action_hint: str       # which menu/policy to use


_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class Advisor:
    """Stateless advisor — all methods are static."""

    @staticmethod
    def get_warnings(country: Country) -> List[Warning]:
        c = country
        warnings: List[Warning] = []

        # ── CRITICAL ───────────────────────────────────────────────────────
        if c.stability.revolution_risk > 0.40:
            warnings.append(Warning(
                severity="CRITICAL", category="political",
                message=f"Revolution risk is {c.stability.revolution_risk:.0%}.",
                recommendation="Boost legitimacy: increase social spending or pass civil rights reforms.",
                value=c.stability.revolution_risk,
            ))
        if c.stability.coup_risk > 0.35:
            warnings.append(Warning(
                severity="CRITICAL", category="military",
                message=f"Coup risk is {c.stability.coup_risk:.0%}. Military loyalty at {c.government.military_loyalty:.0%}.",
                recommendation="Increase military budget allocation or improve legitimacy.",
                value=c.stability.coup_risk,
            ))
        if c.economy.gdp_growth < -0.03:
            warnings.append(Warning(
                severity="CRITICAL", category="economic",
                message=f"Economy contracting at {c.economy.gdp_growth:.1%} per year.",
                recommendation="Consider a stimulus package or open trade agreements.",
                value=c.economy.gdp_growth,
            ))
        if c.stability.overall < 0.20:
            warnings.append(Warning(
                severity="CRITICAL", category="political",
                message=f"National stability is dangerously low ({c.stability.overall:.0%}).",
                recommendation="Prioritise order — increase security spending and address underlying grievances.",
                value=c.stability.overall,
            ))
        if c.economy.inflation > 0.20:
            warnings.append(Warning(
                severity="CRITICAL", category="economic",
                message=f"Hyperinflation at {c.economy.inflation:.1%} is destroying savings.",
                recommendation="Reduce spending or raise interest rates (cut budget allocations).",
                value=c.economy.inflation,
            ))

        # ── HIGH ───────────────────────────────────────────────────────────
        if c.government.corruption > 0.70:
            drain = c.government.corruption * 0.6
            warnings.append(Warning(
                severity="HIGH", category="political",
                message=f"Corruption ({c.government.corruption:.0%}) is consuming {drain:.0%} of all spending.",
                recommendation="Launch an Anti-Corruption Drive (Policy → Anti-Corruption).",
                value=c.government.corruption,
            ))
        if c.economy.foreign_debt_gdp > 1.0:
            warnings.append(Warning(
                severity="HIGH", category="economic",
                message=f"Foreign debt is {c.economy.foreign_debt_gdp:.0%} of GDP — default risk rising.",
                recommendation="Run a surplus: raise taxes or cut spending.",
                value=c.economy.foreign_debt_gdp,
            ))
        if c.culture.ethnic_tension > 0.65:
            warnings.append(Warning(
                severity="HIGH", category="social",
                message=f"Ethnic tension ({c.culture.ethnic_tension:.0%}) approaching flashpoint.",
                recommendation="Launch ethnic reconciliation programs (Policy → Social).",
                value=c.culture.ethnic_tension,
            ))
        if c.economy.unemployment > 0.20:
            warnings.append(Warning(
                severity="HIGH", category="economic",
                message=f"Unemployment at {c.economy.unemployment:.0%} fuelling social unrest.",
                recommendation="Invest in infrastructure and education to stimulate job creation.",
                value=c.economy.unemployment,
            ))
        if c.stability.separatism_risk > 0.50:
            warnings.append(Warning(
                severity="HIGH", category="political",
                message=f"Separatism risk is {c.stability.separatism_risk:.0%}.",
                recommendation="Offer regional autonomy or launch dialogue — suppression may backfire.",
                value=c.stability.separatism_risk,
            ))
        if c.stability.civil_war_risk > 0.20:
            warnings.append(Warning(
                severity="HIGH", category="military",
                message=f"Civil war risk is {c.stability.civil_war_risk:.0%}.",
                recommendation="Immediately address stability drivers: inequality, ethnic tension, legitimacy.",
                value=c.stability.civil_war_risk,
            ))

        # ── MEDIUM ─────────────────────────────────────────────────────────
        if c.demographics.happiness < 0.35:
            warnings.append(Warning(
                severity="MEDIUM", category="social",
                message=f"Population happiness is low ({c.demographics.happiness:.0%}).",
                recommendation="Increase healthcare and social welfare spending.",
                value=c.demographics.happiness,
            ))
        if c.government.press_freedom < 0.25 and c.government.corruption > 0.40:
            warnings.append(Warning(
                severity="MEDIUM", category="political",
                message=f"Restricted press ({c.government.press_freedom:.0%}) is accelerating corruption.",
                recommendation="Strengthen press freedom to slow corruption drift.",
                value=c.government.press_freedom,
            ))
        if c.technology.brain_drain < -0.40:
            warnings.append(Warning(
                severity="MEDIUM", category="social",
                message="Significant brain drain — skilled workers are emigrating.",
                recommendation="Improve civil liberties and economic opportunity to retain talent.",
                value=c.technology.brain_drain,
            ))
        if c.economy.gini_coefficient > 0.55:
            warnings.append(Warning(
                severity="MEDIUM", category="economic",
                message=f"High inequality (Gini {c.economy.gini_coefficient:.2f}) fuelling resentment.",
                recommendation="Increase social welfare spending or raise progressive taxes.",
                value=c.economy.gini_coefficient,
            ))
        if c.economy.sanctions_level > 0.30:
            warnings.append(Warning(
                severity="MEDIUM", category="economic",
                message=f"International sanctions ({c.economy.sanctions_level:.0%}) are hurting growth.",
                recommendation="Open diplomatic dialogue to have sanctions lifted.",
                value=c.economy.sanctions_level,
            ))

        # ── LOW ────────────────────────────────────────────────────────────
        if c.demographics.education_index < 0.40:
            warnings.append(Warning(
                severity="LOW", category="social",
                message=f"Low education ({c.demographics.education_index:.0%}) is capping tech adoption.",
                recommendation="Increase education budget allocation.",
                value=c.demographics.education_index,
            ))
        if c.demographics.healthcare_index < 0.35:
            warnings.append(Warning(
                severity="LOW", category="social",
                message=f"Poor healthcare ({c.demographics.healthcare_index:.0%}) reduces workforce productivity.",
                recommendation="Increase healthcare spending.",
                value=c.demographics.healthcare_index,
            ))
        if c.economy.gdp_growth < 0.01 and c.economy.foreign_debt_gdp > 0.60:
            warnings.append(Warning(
                severity="LOW", category="economic",
                message="Stagnant growth with rising debt — fiscal space is shrinking.",
                recommendation="Prioritise growth-oriented investments: education, R&D, infrastructure.",
                value=c.economy.gdp_growth,
            ))

        # Sort by severity, then by value (most severe first within each tier)
        warnings.sort(key=lambda w: (_SEVERITY_ORDER.get(w.severity, 99), -w.value))
        return warnings

    @staticmethod
    def get_opportunities(country: Country) -> List[Opportunity]:
        c = country
        opps: List[Opportunity] = []
        from ..systems.feedback import compute_tech_progress

        tech_p = compute_tech_progress(c)
        if tech_p > 0.08 and c.technology.tier.value < 5:
            opps.append(Opportunity(
                category="technology",
                message=f"Tech advancement within reach (progress rate {tech_p:.0%}/yr).",
                action_hint="Policy → Research Funding",
            ))

        if c.economy.trade_openness > 0.55 and c.economy.trade_agreements < 4:
            opps.append(Opportunity(
                category="economic",
                message="High trade openness — new trade agreements could boost growth.",
                action_hint="Foreign Affairs → Sign Trade Agreement",
            ))

        if c.stability.overall > 0.72 and c.culture.soft_power < 0.50:
            opps.append(Opportunity(
                category="diplomatic",
                message="Stable conditions — invest in cultural output to build soft power.",
                action_hint="Policy → Budget (increase research/culture)",
            ))

        if c.government.corruption > 0.50 and c.government.press_freedom > 0.50:
            opps.append(Opportunity(
                category="political",
                message="Free press provides cover for an effective anti-corruption drive.",
                action_hint="Policy → Anti-Corruption",
            ))

        if c.culture.ethnic_tension > 0.30 and c.culture.ethnic_tension < 0.55 and c.stability.overall > 0.55:
            opps.append(Opportunity(
                category="social",
                message="Good window to reduce ethnic tensions before they escalate.",
                action_hint="Policy → Social → Ethnic Reconciliation",
            ))

        if c.government.civil_liberties < 0.60 and c.government.is_democratic:
            opps.append(Opportunity(
                category="political",
                message="Civil liberties below democratic norms — reform would boost legitimacy.",
                action_hint="Policy → Civil Rights",
            ))

        return opps

    @staticmethod
    def summarise(country: Country, max_warnings: int = 3) -> str:
        """One-line summary for inline display in menus."""
        warnings = Advisor.get_warnings(country)
        critical = [w for w in warnings if w.severity == "CRITICAL"]
        high = [w for w in warnings if w.severity == "HIGH"]
        if critical:
            return f"[bold red]⚠ {len(critical)} CRITICAL risk(s):[/] {critical[0].message}"
        if high:
            return f"[yellow]! {len(high)} HIGH risk(s):[/] {high[0].message}"
        return "[green]✓ No immediate threats detected.[/]"
