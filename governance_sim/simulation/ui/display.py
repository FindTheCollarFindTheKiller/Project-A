"""
Rich terminal display helpers for the governance simulation.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich import box

if TYPE_CHECKING:
    from ..models.country import Country
    from ..systems.world import World, BilateralRelation
    from ..systems.events import GameEvent
    from ..systems.advisor import Warning, Opportunity

console = Console()

# ── Formatting primitives ────────────────────────────────────────────────────

def _bar(value: float, width: int = 12) -> str:
    value = max(0.0, min(1.0, value))
    filled = int(round(value * width))
    empty = width - filled
    return f"[green]{'█' * filled}[/][dim]{'░' * empty}[/]"


def _pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def _color_score(value: float, low: float = 0.33, high: float = 0.66) -> str:
    pct = _pct(value)
    if value >= high:
        return f"[green]{pct}[/]"
    if value >= low:
        return f"[yellow]{pct}[/]"
    return f"[red]{pct}[/]"


def _color_score_inv(value: float, low: float = 0.33, high: float = 0.66) -> str:
    """Inverted: lower = better (e.g. corruption, unemployment). Shows actual value."""
    pct = _pct(value)
    inverted = 1.0 - value
    if inverted >= high:
        return f"[green]{pct}[/]"
    if inverted >= low:
        return f"[yellow]{pct}[/]"
    return f"[red]{pct}[/]"


def _trend(value: float) -> str:
    if value > 0.005:
        return f"[green]+{value * 100:.1f}%[/]"
    if value < -0.005:
        return f"[red]{value * 100:.1f}%[/]"
    return f"[dim]{value * 100:.1f}%[/]"


def _delta_arrow(current: float, prev: Optional[float], threshold: float = 0.005) -> str:
    """Return a coloured arrow showing direction of change."""
    if prev is None:
        return "[dim]—[/]"
    diff = current - prev
    if diff > threshold:
        return "[green]▲[/]"
    if diff < -threshold:
        return "[red]▼[/]"
    return "[dim]→[/]"


# Map EventType to display icons
_EVENT_ICONS = {
    "ECONOMIC": "💰",
    "TRIGGERED": "⚖️ ",
    "RANDOM": "🎲",
    "DIPLOMATIC": "🌍",
    "MILITARY": "⚔️ ",
    "CULTURAL": "🎭",
}

_SEVERITY_COLORS = {
    "CRITICAL": "bold red",
    "HIGH": "yellow",
    "MEDIUM": "cyan",
    "LOW": "dim",
}

_SEVERITY_ICONS = {
    "CRITICAL": "⚠",
    "HIGH": "!",
    "MEDIUM": "·",
    "LOW": "·",
}


# ── Main dashboard ───────────────────────────────────────────────────────────

def print_country_dashboard(country: "Country") -> None:
    c = country
    prev = c.previous_stats
    console.print()

    # ── Era & header ─────────────────────────────────────────────────────────
    era = _era_name(c.current_year, c.technology.tier_name)
    header_text = Text(justify="center")
    header_text.append(f"  {c.name.upper()}  ", style="bold white on dark_blue")
    header_text.append(f"  {c.capital}  |  {era}  |  Year {c.current_year}  ", style="dim")
    console.print(Panel(header_text, box=box.DOUBLE_EDGE, border_style="blue"))

    # ── Budget line ───────────────────────────────────────────────────────────
    revenue = c.economy.gdp_total * c.government.tax_rate
    allocated = revenue * sum(c.government.budget_allocation.values())
    delivered = revenue * sum(c.government.effective_spending.values())
    leakage = max(0.0, allocated - delivered)
    budget_line = (
        f"[dim]Tax Revenue:[/] [cyan]${revenue:.1f}B[/]  "
        f"[dim]Allocated:[/] [cyan]${allocated:.1f}B[/]  "
        f"[dim]Delivered:[/] [green]${delivered:.1f}B[/]  "
        f"[dim]Leakage:[/] [yellow]${leakage:.1f}B[/]  "
        f"[dim]Pop:[/] [cyan]{c.population_str}[/]  "
        f"[dim]GDP:[/] [cyan]{c.gdp_str}[/]  "
        f"[dim]GDP/cap:[/] [cyan]${c.economy.gdp_per_capita:,.0f}[/]"
    )
    console.print(Panel(budget_line, box=box.SIMPLE, padding=(0, 1)))

    # ── Three metric columns ──────────────────────────────────────────────────
    def _kv(label: str, val: str, arrow: str = "", bar_val: Optional[float] = None) -> str:
        b = f" {_bar(bar_val)}" if bar_val is not None else ""
        a = f" {arrow}" if arrow else ""
        return f"[bold]{label:<18}[/]{val}{b}{a}"

    gov_rows = [
        _kv("Stability",       _color_score(c.stability.overall),         _delta_arrow(c.stability.overall,           prev.get("stability")),           c.stability.overall),
        _kv("Legitimacy",      _color_score(c.government.legitimacy),      _delta_arrow(c.government.legitimacy,       prev.get("legitimacy")),           c.government.legitimacy),
        _kv("Civil Liberties", _color_score(c.government.civil_liberties), _delta_arrow(c.government.civil_liberties, prev.get("civil_liberties")),     c.government.civil_liberties),
        _kv("Press Freedom",   _color_score(c.government.press_freedom),   _delta_arrow(c.government.press_freedom,   prev.get("press_freedom")),       c.government.press_freedom),
        _kv("Corruption",      _color_score_inv(c.government.corruption),  _delta_arrow(c.government.corruption,      prev.get("corruption"), 0.003),   c.government.corruption),
        _kv("Mil. Loyalty",    _color_score(c.government.military_loyalty), ""),
    ]
    dev_rows = [
        _kv("Education",       _color_score(c.demographics.education_index),  _delta_arrow(c.demographics.education_index,  prev.get("education")),   c.demographics.education_index),
        _kv("Healthcare",      _color_score(c.demographics.healthcare_index),  _delta_arrow(c.demographics.healthcare_index, prev.get("healthcare")),  c.demographics.healthcare_index),
        _kv("Happiness",       _color_score(c.demographics.happiness),         _delta_arrow(c.demographics.happiness,         prev.get("happiness")),   c.demographics.happiness),
        _kv("Tech Tier",       f"[cyan]{c.technology.tier_name}[/]"),
        _kv("Soft Power",      _color_score(c.culture.soft_power),             _delta_arrow(c.culture.soft_power,            prev.get("soft_power")),  c.culture.soft_power),
        _kv("Power Score",     _color_score(c.global_power_score),             "",                                                                      c.global_power_score),
    ]
    econ_rows = [
        _kv("GDP Growth",      _trend(c.economy.gdp_growth)),
        _kv("Unemployment",    _color_score_inv(c.economy.unemployment, 0.07, 0.15), _delta_arrow(c.economy.unemployment, prev.get("unemployment"), 0.005)),
        _kv("Inequality (Gini)", _color_score_inv(c.economy.gini_coefficient), _delta_arrow(c.economy.gini_coefficient, prev.get("gini"), 0.005)),
        _kv("Inflation",       _color_score_inv(c.economy.inflation, 0.05, 0.10)),
        _kv("Trade Balance",   f"[{'green' if c.economy.trade_balance >= 0 else 'red'}]${c.economy.trade_balance:+.1f}B[/]"),
        _kv("Debt / GDP",      _color_score_inv(min(1.0, c.economy.foreign_debt_gdp))),
    ]

    console.print(Columns([
        Panel("\n".join(gov_rows),  title="[bold]Governance[/]",   box=box.ROUNDED, width=40),
        Panel("\n".join(dev_rows),  title="[bold]Development[/]",  box=box.ROUNDED, width=40),
        Panel("\n".join(econ_rows), title="[bold]Economy[/]",      box=box.ROUNDED, width=40),
    ]))

    # ── Risk panel ────────────────────────────────────────────────────────────
    _print_risk_panel(c)


def _era_name(year: int, tech_tier: str) -> str:
    if "Pre" in tech_tier or "Agricultural" in tech_tier:
        return "Age of Sail" if year < 1800 else "Pre-Industrial Era"
    if "Early Industrial" in tech_tier:
        return "Age of Steam"
    if "Industrial" in tech_tier:
        return "Industrial Age" if year < 1920 else "Age of Industry"
    if "Digital" in tech_tier:
        return "Information Age"
    if "Advanced" in tech_tier:
        return "Post-Industrial Age"
    return "Modern Era"


def _print_risk_panel(c: "Country") -> None:
    risks = [
        ("Revolution", c.stability.revolution_risk, 0.30, 0.50),
        ("Coup",       c.stability.coup_risk,        0.20, 0.40),
        ("Separatism", c.stability.separatism_risk,  0.30, 0.55),
        ("Civil War",  c.stability.civil_war_risk,   0.10, 0.25),
        ("Protest",    c.stability.protest_level,    0.35, 0.60),
    ]
    parts = []
    for name, val, med, hi in risks:
        color = "red bold" if val >= hi else ("yellow" if val >= med else "green")
        icon = "⚠" if val >= hi else ("!" if val >= med else "·")
        parts.append(f"[{color}]{icon} {name}:[/] [{color}]{val:.0%}[/]")
    console.print(Panel("   ".join(parts), title="[bold]Risk Indicators[/]", box=box.ROUNDED))


# ── Advisor panel ─────────────────────────────────────────────────────────────

def print_advisor_panel(warnings: List["Warning"], opportunities: List["Opportunity"]) -> None:
    from ..systems.advisor import Warning, Opportunity
    lines = []
    if not warnings and not opportunities:
        lines.append("[green]✓ No significant threats or opportunities detected.[/]")
    else:
        for w in warnings[:6]:
            color = _SEVERITY_COLORS.get(w.severity, "white")
            icon = _SEVERITY_ICONS.get(w.severity, "·")
            lines.append(f"[{color}]{icon} [{w.severity}] {w.message}[/]")
            lines.append(f"[dim]   → {w.recommendation}[/]")
        if opportunities:
            lines.append("")
            lines.append("[bold cyan]Opportunities:[/]")
            for o in opportunities[:3]:
                lines.append(f"  [cyan]▶[/] {o.message}")
                lines.append(f"[dim]    {o.action_hint}[/]")
    console.print(Panel("\n".join(lines), title="[bold yellow]Royal Advisor[/]", box=box.ROUNDED))


def print_advisor_inline(country: "Country") -> None:
    """Compact 1-line advisor summary for embedding in menus."""
    from ..systems.advisor import Advisor
    console.print(Advisor.summarise(country))


# ── Turn summary ──────────────────────────────────────────────────────────────

def print_turn_summary(country: "Country", events: List["GameEvent"], log: List[str]) -> None:
    c = country
    prev = c.previous_stats
    year = c.current_year - 1  # summary is for the year just completed

    console.print()
    console.print(Rule(f"[bold white] Year {year} — Annual Report [/]", style="blue"))

    # Events section
    if events or log:
        event_lines = []
        seen_names = set()
        for event in events:
            if event.name not in seen_names:
                seen_names.add(event.name)
                icon = _EVENT_ICONS.get(event.type.name, "·")
                sev_color = "red" if event.severity > 0.65 else ("yellow" if event.severity > 0.35 else "green")
                event_lines.append(f"  {icon} [{sev_color}]{event.name}[/] — {event.description[:70]}")
        for entry in log:
            if entry not in [f"  · {e.name}" for e in events]:
                icon = "⚔️ " if "COUP" in entry or "REVOLUTION" in entry else "·"
                color = "red bold" if ("COUP" in entry or "REVOLUTION" in entry) else "dim"
                event_lines.append(f"  {icon} [{color}]{entry.lstrip('[').rstrip(']')}[/]")
        if event_lines:
            console.print(Panel(
                "\n".join(event_lines),
                title="[bold]Events This Year[/]",
                box=box.ROUNDED,
            ))

    # Key changes table
    if prev:
        delta_table = Table(title="Key Changes", box=box.SIMPLE, show_header=True, header_style="bold")
        delta_table.add_column("Metric",      style="bold", min_width=22)
        delta_table.add_column("Last Year",   justify="right", min_width=10)
        delta_table.add_column("This Year",   justify="right", min_width=10)
        delta_table.add_column("Change",      justify="right", min_width=8)

        def _add_row(label: str, cur: float, prev_val: Optional[float],
                     fmt=lambda v: _pct(v), invert: bool = False) -> None:
            if prev_val is None:
                return
            delta = cur - prev_val
            arrow = _delta_arrow(cur, prev_val)
            if invert:
                change_color = "red" if delta > 0.005 else ("green" if delta < -0.005 else "dim")
            else:
                change_color = "green" if delta > 0.005 else ("red" if delta < -0.005 else "dim")
            sign = "+" if delta >= 0 else ""
            delta_table.add_row(
                label,
                fmt(prev_val),
                fmt(cur),
                f"[{change_color}]{sign}{fmt(delta)} {arrow}[/]",
            )

        _add_row("Stability",       c.stability.overall,            prev.get("stability"))
        _add_row("Happiness",       c.demographics.happiness,       prev.get("happiness"))
        _add_row("Legitimacy",      c.government.legitimacy,        prev.get("legitimacy"))
        _add_row("GDP Growth",      c.economy.gdp_growth,           prev.get("gdp_growth"),  fmt=lambda v: f"{v*100:+.1f}%")
        _add_row("GDP / Capita",    c.economy.gdp_per_capita,       prev.get("gdp_per_capita"), fmt=lambda v: f"${v:,.0f}")
        _add_row("Unemployment",    c.economy.unemployment,         prev.get("unemployment"), invert=True)
        _add_row("Corruption",      c.government.corruption,        prev.get("corruption"),  invert=True)
        _add_row("Education",       c.demographics.education_index, prev.get("education"))
        _add_row("Military Str.",   c.military.conventional_strength, prev.get("military_strength"))
        console.print(delta_table)


# ── Game over ─────────────────────────────────────────────────────────────────

def print_game_over(country: "Country", reason: str) -> None:
    console.print()
    lines = [
        f"[bold red]{reason}[/]",
        "",
        f"[bold]Nation:[/]      {country.name}",
        f"[bold]Years ruled:[/] {country.current_year - country.founding_year}",
        f"[bold]Final year:[/]  {country.current_year}",
        f"[bold]Government:[/]  {country.government.type.value}",
        f"[bold]Stability:[/]   {_pct(country.stability.overall)}",
        f"[bold]GDP/capita:[/]  ${country.economy.gdp_per_capita:,.0f}",
        f"[bold]Population:[/]  {country.population_str}",
        f"[bold]Tech tier:[/]   {country.technology.tier_name}",
    ]
    console.print(Panel(
        "\n".join(lines),
        title="[bold red on white] ⚡ GAME OVER ⚡ [/]",
        box=box.DOUBLE_EDGE,
        border_style="red",
    ))


# ── Objectives ────────────────────────────────────────────────────────────────

def print_objectives(country: "Country", world: "World", start_year: int) -> None:
    c = country
    target_year = start_year + 50

    def _prog(val: float, target: float) -> str:
        pct = min(1.0, val / target) if target > 0 else 0.0
        done = pct >= 1.0
        color = "green" if done else "yellow"
        tick = "✓" if done else " "
        return f"[{color}]{tick} {_bar(pct, 10)} {pct:.0%}[/]"

    ranking = world.power_ranking()
    total = max(4, len(ranking))
    rank = (ranking.index(c) + 1) if c in ranking else total
    top3_progress = max(0.0, (total - rank) / max(1, total - 3))

    objectives = [
        ("Reach Digital Tech Tier",         _prog(c.technology.tier.value, 4)),
        (f"Stability > 75% by {target_year}", _prog(c.stability.overall, 0.75)),
        ("Happiness > 70%",                 _prog(c.demographics.happiness, 0.70)),
        ("Literacy > 90%",                  _prog(c.language.literacy_rate, 0.90)),
        (f"Top-3 World Power by {target_year}", _prog(top3_progress, 1.0)),
    ]
    t = Table(title="National Objectives", box=box.ROUNDED)
    t.add_column("Objective", style="bold", min_width=32)
    t.add_column("Progress", min_width=20)
    for label, prog in objectives:
        t.add_row(label, prog)
    console.print(t)


# ── Event popup ───────────────────────────────────────────────────────────────

def print_event_popup(event: "GameEvent") -> None:
    severity_color = "red" if event.severity > 0.65 else ("yellow" if event.severity > 0.35 else "green")
    icon = _EVENT_ICONS.get(event.type.name, "·")
    sev_bar = _bar(event.severity, 8)

    console.print()
    console.print(Panel(
        f"{event.description}\n\n[dim]Severity: {sev_bar} {_pct(event.severity)}[/]",
        title=f"[bold {severity_color}]{icon} EVENT: {event.name}[/]",
        box=box.DOUBLE,
        border_style=severity_color,
    ))

    if event.choices:
        console.print("[bold]How will you respond?[/]")
        for i, choice in enumerate(event.choices, 1):
            # Build a compact effects preview
            effect_parts = []
            for path, delta in list(choice.effects.items())[:3]:
                key = path.split(".")[-1].replace("_", " ").title()
                if isinstance(delta, (int, float)):
                    sign = "+" if delta > 0 else ""
                    effect_parts.append(f"{key}: {sign}{delta:.0%}" if abs(delta) < 1 else f"{key}: {sign}{delta:.0f}")
            effects_str = f"  [dim]({', '.join(effect_parts)})[/]" if effect_parts else ""
            console.print(f"  [bold cyan]{i}.[/] [bold]{choice.label}[/] — {choice.description}{effects_str}")


# ── Detail views ──────────────────────────────────────────────────────────────

def print_government_detail(country: "Country") -> None:
    c = country
    t = Table(title=f"Government — {c.name}", box=box.ROUNDED, show_header=False)
    t.add_column("Field", style="bold", min_width=24)
    t.add_column("Value")
    t.add_row("Type",                 c.government.type.value)
    t.add_row("Election System",      c.government.election_system.value)
    t.add_row("Succession",           c.government.succession_type.value)
    t.add_row("Years in Power",       str(c.government.years_in_power))
    t.add_row("Tax Rate",             _pct(c.government.tax_rate))
    t.add_row("Executive Strength",   _bar(c.government.executive_strength))
    t.add_row("Legislative Strength", _bar(c.government.legislative_strength))
    t.add_row("Judicial Independence",_bar(c.government.judicial_independence))
    t.add_row("Military Loyalty",     _bar(c.government.military_loyalty))
    t.add_section()
    t.add_row("[bold]Budget Allocation[/]", "")
    for dept, share in sorted(c.government.budget_allocation.items(), key=lambda x: -x[1]):
        t.add_row(f"  {dept.replace('_', ' ').title()}", f"{_bar(share * 3, 10)} {_pct(share)}")
    console.print(t)


def print_culture_language(country: "Country") -> None:
    c = country
    ct = Table(title="Culture & Society", box=box.ROUNDED, show_header=False)
    ct.add_column("Field", style="bold", min_width=24)
    ct.add_column("Value")
    ct.add_row("Dominant Religion",    c.culture.dominant_religion.value)
    ct.add_row("Religious Influence",  _bar(c.culture.religious_influence))
    ct.add_row("Individualism",        _bar(c.culture.individualism))
    ct.add_row("Power Distance",       _bar(c.culture.power_distance))
    ct.add_row("Long-term Orient.",    _bar(c.culture.long_term_orientation))
    ct.add_row("Gender Equality",      _bar(c.culture.gender_equality))
    ct.add_row("Ethnic Diversity",     _bar(c.culture.ethnic_diversity))
    ct.add_row("Ethnic Tension",       _bar(c.culture.ethnic_tension))
    ct.add_row("National Identity",    _bar(c.culture.national_identity))
    ct.add_row("Social Cohesion",      _bar(c.culture.social_cohesion))

    lt = Table(title="Language", box=box.ROUNDED, show_header=False)
    lt.add_column("Field", style="bold", min_width=20)
    lt.add_column("Value")
    lt.add_row("Official Languages",   ", ".join(c.language.official_languages))
    lt.add_row("Language Family",      c.language.dominant_family.value)
    lt.add_row("Script System",        c.language.script_system.value)
    lt.add_row("Literacy Rate",        _color_score(c.language.literacy_rate))
    lt.add_row("Linguistic Diversity", _bar(c.language.linguistic_diversity))
    lt.add_row("Language Policy",      c.language.policy.value)
    console.print(Columns([ct, lt]))


def print_geography(country: "Country") -> None:
    g = country.geography
    t = Table(title="Geography & Resources", box=box.ROUNDED, show_header=False)
    t.add_column("Field", style="bold", min_width=24)
    t.add_column("Value")
    t.add_row("Climate",              g.climate_zone.value)
    t.add_row("Terrain",              ", ".join(tr.value for tr in g.terrain_types))
    t.add_row("Area",                 f"{g.area_km2:,.0f} km²")
    t.add_row("Coastline",            f"{g.coastline_km:,.0f} km" if not g.is_landlocked else "Landlocked")
    t.add_row("Rivers",               str(g.river_count))
    t.add_row("Neighbors",            str(g.neighbor_count))
    t.add_row("Border Defensibility", _bar(g.border_defensibility))
    t.add_row("Trade Access",         _bar(g.trade_access))
    t.add_section()
    t.add_row("[bold]Natural Resources[/]", "")
    for rt, abundance in sorted(g.natural_resources.items(), key=lambda x: -x[1]):
        t.add_row(f"  {rt.value}", _bar(abundance))
    if g.natural_disaster_risk:
        t.add_section()
        t.add_row("[bold]Disaster Risks[/]", "")
        for dt, risk in sorted(g.natural_disaster_risk.items(), key=lambda x: -x[1]):
            t.add_row(f"  {dt.value}", _bar(risk))
    console.print(t)


def print_military_detail(country: "Country") -> None:
    m = country.military
    t = Table(title=f"Military — {country.name}", box=box.ROUNDED, show_header=False)
    t.add_column("Field", style="bold", min_width=24)
    t.add_column("Value")
    t.add_row("Active Forces",         f"{m.size:,}")
    t.add_row("Reserve Forces",        f"{m.reserve_size:,}")
    t.add_row("Tech Tier",             m.tech_tier.name)
    t.add_row("Doctrine",              m.doctrine.value)
    t.add_row("Nuclear Capability",    "[red]YES[/]" if m.has_nuclear else "[dim]No[/]")
    t.add_row("Defense Spending",      f"{_pct(m.defense_spending_gdp)} of GDP")
    t.add_row("Morale",                _bar(m.morale))
    t.add_row("Training Quality",      _bar(m.training_quality))
    t.add_row("Equipment Quality",     _bar(m.equipment_quality))
    t.add_row("Conventional Strength", _bar(m.conventional_strength))
    t.add_row("Deterrence Score",      _bar(m.deterrence_score))
    console.print(t)


def print_world_ranking(world: "World") -> None:
    t = Table(title=f"World Power Rankings — {world.year}", box=box.ROUNDED)
    t.add_column("#",          style="dim",  width=3)
    t.add_column("Nation",     style="bold")
    t.add_column("Government")
    t.add_column("GDP Total")
    t.add_column("GDP/Cap")
    t.add_column("Pop")
    t.add_column("HDI")
    t.add_column("Power")
    t.add_column("Stability")
    t.add_column("Tech")

    for i, c in enumerate(world.power_ranking(), 1):
        player_marker = " [yellow]★[/]" if c.id == world.player_id else ""
        t.add_row(
            str(i),
            c.name + player_marker,
            c.government.type.value,
            c.gdp_str,
            f"${c.economy.gdp_per_capita:,.0f}",
            c.population_str,
            _pct(c.demographics.hdi),
            _bar(c.global_power_score, 8),
            _color_score(c.stability.overall),
            c.technology.tier_name,
        )
    console.print(t)


def print_relations(country: "Country", world: "World") -> None:
    rels = world.relations_for(country.id)
    if not rels:
        console.print("[dim]No known diplomatic relations.[/]")
        return
    t = Table(title=f"Diplomatic Relations — {country.name}", box=box.ROUNDED)
    t.add_column("Nation",    style="bold")
    t.add_column("Stance")
    t.add_column("Score",     justify="right")
    t.add_column("Treaties")
    for other, rel in rels:
        treaties = []
        if rel.treaty_trade:
            treaties.append("[green]Trade[/]")
        if rel.treaty_defense:
            treaties.append("[blue]Defense[/]")
        if rel.at_war:
            treaties.append("[bold red]AT WAR[/]")
        if rel.sanction_sender:
            treaties.append("[yellow]Sanctions[/]")
        score_color = "green" if rel.score > 0.25 else ("red" if rel.score < -0.25 else "yellow")
        t.add_row(
            other.name,
            rel.stance.value,
            f"[{score_color}]{rel.score:+.2f}[/]",
            " ".join(treaties) if treaties else "[dim]None[/]",
        )
    console.print(t)


def print_history(country: "Country", n: int = 10) -> None:
    if not country.history:
        console.print("[dim]No recorded history.[/]")
        return
    t = Table(title=f"History — {country.name} (last {n} events)", box=box.ROUNDED)
    t.add_column("Year",  style="dim", width=6)
    t.add_column("Event", style="bold")
    t.add_column("Description")
    for event in country.history[-n:]:
        desc = event.description[:90]
        if len(event.description) > 90:
            desc += "…"
        t.add_row(str(event.year), event.title, desc)
    console.print(t)


def print_ai_country_brief(country: "Country", relation: Optional["BilateralRelation"] = None) -> None:
    c = country
    lines = [
        f"[bold]{c.name}[/]  |  {c.government.type.value}  |  {c.technology.tier_name}",
        f"[dim]Capital:[/] {c.capital}   [dim]Pop:[/] {c.population_str}   [dim]GDP:[/] {c.gdp_str}   [dim]GDP/cap:[/] ${c.economy.gdp_per_capita:,.0f}",
        f"[dim]Stability:[/] {_color_score(c.stability.overall)}   [dim]Happiness:[/] {_color_score(c.demographics.happiness)}   [dim]Power Score:[/] {_pct(c.global_power_score)}",
    ]
    if relation is not None:
        score_color = "green" if relation.score > 0.25 else ("red" if relation.score < -0.25 else "yellow")
        lines.append(f"[dim]Your relation:[/] [{score_color}]{relation.score:+.2f}[/] ({relation.stance.value})")
    console.print(Panel("\n".join(lines), title=f"[bold]{c.name}[/]", box=box.ROUNDED))
