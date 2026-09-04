"""
Full CLI game loop for the governance simulation.
"""
from __future__ import annotations
import os
import sys
import json
from typing import List, Optional, Tuple

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..models.country import Country
from ..systems.world import World
from ..systems.engine import SimulationEngine, TurnResult
from ..systems.events import GameEvent
from ..systems.generator import CountryGenerator, ARCHETYPES
from ..systems.advisor import Advisor
from ..persistence.save_load import save_game, load_game
from ..paths import saves_dir
from .display import (
    console,
    print_country_dashboard,
    print_government_detail,
    print_culture_language,
    print_geography,
    print_world_ranking,
    print_relations,
    print_history,
    print_event_popup,
    print_military_detail,
    print_turn_summary,
    print_game_over,
    print_advisor_panel,
    print_ai_country_brief,
    print_objectives,
)


# ── Utilities ────────────────────────────────────────────────────────────────

def _clear() -> None:
    console.clear()


def _pause() -> None:
    Prompt.ask("\n[dim]Press Enter to continue[/]", default="")


def _header(title: str) -> None:
    console.print()
    console.print(Panel(f"[bold white]{title}[/]", box=box.ROUNDED, border_style="blue"))


def _menu(options: List[Tuple[str, str]], title: str = "Choose an action") -> int:
    """Print a numbered menu and return the 1-based choice."""
    console.print(f"\n[bold]{title}[/]")
    for i, (label, desc) in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}.[/] [bold]{label}[/]" + (f" — {desc}" if desc else ""))
    while True:
        raw = Prompt.ask(f"[dim]Enter 1–{len(options)}[/]", default="1")
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        console.print("[red]Invalid choice, try again.[/]")


def _bounded_int(prompt: str, default: int, minimum: int, maximum: int) -> int:
    """Prompt until an integer falls within the requested range."""
    while True:
        raw = Prompt.ask(prompt, default=str(default))
        try:
            value = int(raw)
            if minimum <= value <= maximum:
                return value
        except ValueError:
            pass
        console.print(f"[red]Enter a whole number from {minimum} to {maximum}.[/]")


# ── Archetype descriptions ────────────────────────────────────────────────────

_ARCHETYPE_DESCS = {
    "river_valley":    "Fertile flatlands along a great river. Strong agriculture, centralised rule, high population growth.",
    "coastal_trade":   "Shoreline nation built on commerce. Open economy, diverse culture, natural trade advantages.",
    "island_nation":   "Isolated by sea. Excellent naval power, high trade potential, low invasion risk.",
    "mountain_fortress": "Rugged highlands. Excellent defensibility, rich in minerals, lower agricultural output.",
    "desert_kingdom":  "Arid expanse with oil and mineral wealth. Autocratic traditions, high revenue, fragile stability.",
    "steppe_empire":   "Vast grasslands. Strong cavalry/military heritage, nomadic culture, natural expansion drive.",
    "jungle_state":    "Dense equatorial forest. Rich biodiversity, difficult terrain, lower development baseline.",
    "arctic_outpost":  "Frozen frontier. Strategic location, energy resources, sparse population, high infrastructure costs.",
}


# ── New game setup ───────────────────────────────────────────────────────────

_DIFFICULTY_MODS = {
    "Easy":   {"coup_mod": 0.5,  "rev_mod": 0.5,  "start_stability": 0.15},
    "Normal": {"coup_mod": 1.0,  "rev_mod": 1.0,  "start_stability": 0.0},
    "Hard":   {"coup_mod": 1.3,  "rev_mod": 1.3,  "start_stability": -0.10},
}


def setup_new_game() -> Tuple[World, SimulationEngine]:
    _clear()
    console.print(Panel(
        "[bold white]NATION FORGE[/]\n[dim]A Country Governance Simulation[/]",
        box=box.DOUBLE_EDGE,
        border_style="blue",
        expand=False,
    ))
    console.print()

    # Nation name
    name = Prompt.ask("[bold]Name your nation[/]", default="Valdoria")

    # Choose archetype with descriptions
    console.print("\n[bold]Choose your nation's geographic archetype:[/]")
    arch_list = list(ARCHETYPES.keys())
    for i, key in enumerate(arch_list, 1):
        arch = ARCHETYPES[key]
        terrains = ", ".join(t.value for t in arch["terrains"])
        desc = _ARCHETYPE_DESCS.get(key, "")
        console.print(
            f"  [bold cyan]{i}.[/] [bold]{key.replace('_', ' ').title()}[/] — "
            f"[dim]{terrains} / {arch['climate'].value}[/]\n"
            f"      [italic]{desc}[/]"
        )

    while True:
        raw = Prompt.ask(f"\n[dim]Enter 1–{len(arch_list)} (or 0 for random)[/]", default="0")
        try:
            idx = int(raw) - 1
            if idx == -1:
                archetype = None
                break
            if 0 <= idx < len(arch_list):
                archetype = arch_list[idx]
                break
        except ValueError:
            pass
        console.print("[red]Invalid choice.[/]")

    # Difficulty
    console.print("\n[bold]Difficulty:[/]")
    diff_choice = _menu([
        ("Easy",   "Reduced coup/revolution risk, slight stability bonus"),
        ("Normal", "Default simulation parameters"),
        ("Hard",   "Increased political risk, stability penalty from the start"),
    ], "Select difficulty")
    difficulty = ["Easy", "Normal", "Hard"][diff_choice - 1]

    # Start year
    start_year = _bounded_int("[bold]Start year[/]", default=1900, minimum=-5000, maximum=3000)

    # Number of AI nations
    num_ai = _bounded_int(
        "[bold]Number of AI nations in the world[/]", default=5, minimum=1, maximum=20
    )

    console.print("\n[bold]Generating world...[/]")
    gen = CountryGenerator()
    world = World(year=start_year)

    # Player country
    player = gen.generate(archetype=archetype, start_year=start_year, name=name, country_id="player")

    # Apply difficulty modifier
    diff_mod = _DIFFICULTY_MODS[difficulty]
    player.stability.overall = max(0.1, min(1.0, player.stability.overall + diff_mod["start_stability"]))
    world.difficulty = difficulty
    world.add_country(player)
    world.player_id = "player"

    # AI countries
    arch_keys = list(ARCHETYPES.keys())
    for i in range(num_ai):
        ai_arch = arch_keys[i % len(arch_keys)]
        ai_country = gen.generate(archetype=ai_arch, start_year=start_year, country_id=f"ai_{i}")
        world.add_country(ai_country)

    # Wire up neighbors
    all_ids = list(world.countries.keys())
    import random
    rng = random.Random()
    for cid, c in world.countries.items():
        n_neighbors = min(c.geography.neighbor_count, len(all_ids) - 1)
        potential = [oid for oid in all_ids if oid != cid]
        c.neighbor_ids = rng.sample(potential, k=min(n_neighbors, len(potential)))
        for nid in c.neighbor_ids:
            _ = world.get_relation(cid, nid)

    engine = SimulationEngine(world)

    # Generated country summary / confirmation
    _clear()
    console.print("\n[bold]Your Nation — Preview[/]")
    print_country_dashboard(player)
    arch_label = archetype.replace("_", " ").title() if archetype else "Random"
    console.print(
        f"\n[bold]Summary:[/] [cyan]{player.name}[/] — {arch_label} archetype, "
        f"{player.government.type.value}, pop {player.population_str}, "
        f"GDP {player.gdp_str}, stability {player.stability.overall:.0%}"
    )
    if not Confirm.ask("\n[bold]Start the game with this nation?[/]", default=True):
        console.print("[yellow]Restarting setup...[/]")
        return setup_new_game()

    console.print(f"\n[green]World created — {num_ai + 1} nations, difficulty: {difficulty}.[/]")
    _pause()
    return world, engine


# ── Event resolution ─────────────────────────────────────────────────────────

def resolve_pending_events(pending: List[Tuple[GameEvent, Country]], engine: SimulationEngine) -> None:
    for event, country in pending:
        _clear()
        print_event_popup(event)
        if event.choices:
            while True:
                raw = Prompt.ask(
                    f"\n[bold]Your choice (1–{len(event.choices)})[/]",
                    default="1"
                )
                try:
                    choice_idx = int(raw) - 1
                    if 0 <= choice_idx < len(event.choices):
                        break
                except ValueError:
                    pass
                console.print("[red]Invalid.[/]")
            engine.resolve_event(event, country, choice_idx)
            chosen = event.choices[choice_idx]
            console.print(f"\n[green]→ You chose: {chosen.label}[/]")
        else:
            engine.resolve_event(event, country, None)
        _pause()


# ── Game-over detection ───────────────────────────────────────────────────────

def _check_game_over(country: Country, result: TurnResult) -> Optional[str]:
    """Return a reason string if the game is over, else None."""
    for msg in result.log:
        if "REVOLUTION" in msg:
            return "A popular revolution has overthrown your government."
        if "COUP" in msg:
            return "Your military has seized power in a coup d'état."
    if country.stability.overall < 0.08:
        return "The state has collapsed. Order has completely broken down."
    if country.government.legitimacy < 0.04:
        return "Your government has lost all legitimacy and disintegrated."
    return None


# ── Policy menus ─────────────────────────────────────────────────────────────

def _policy_preview(country: Country, domain: str, **kwargs) -> None:
    """Print a simple projection of a policy change before applying it."""
    c = country
    gov = c.government
    lines = ["[bold dim]Projected effects:[/]"]

    if domain == "tax":
        new_rate = float(kwargs.get("rate", gov.tax_rate))
        delta = new_rate - gov.tax_rate
        lines.append(f"  GDP growth: {-delta * 0.1 * 100:+.2f}%")
        lines.append(f"  Happiness: {-delta * 0.3 * 100:+.1f}%")

    elif domain == "budget":
        for key, val in kwargs.items():
            if key in gov.budget_allocation:
                old = gov.budget_allocation[key]
                diff = float(val) - old
                lines.append(f"  {key.replace('_', ' ').title()}: {old:.1%} → {float(val):.1%} ({diff:+.1%})")

    elif domain == "research":
        current = c.technology.rd_spending_gdp
        boost = float(kwargs.get("boost", 0.005))
        new_val = min(0.08, current + boost)
        lines.append(f"  R&D spending: {current:.1%} → {new_val:.1%} of GDP")
        lines.append(f"  [dim]Tech advancement rate will increase gradually[/]")

    elif domain == "civil_rights":
        lines.append(f"  Civil liberties: {gov.civil_liberties:.0%} → ~{min(1.0, gov.civil_liberties + 0.10):.0%}")
        lines.append(f"  Happiness: ~+5%   Legitimacy: ~+8%")

    elif domain == "anti_corruption":
        lines.append(f"  Corruption: {gov.corruption:.0%} → ~{max(0.05, gov.corruption - 0.12):.0%}")
        lines.append(f"  [yellow]Legitimacy: ~-5% (short-term political resistance)[/]")

    console.print(Panel("\n".join(lines), box=box.SIMPLE))


def menu_policy(country: Country, engine: SimulationEngine) -> None:
    while True:
        _clear()
        _header(f"Policy — {country.name}")
        choice = _menu([
            ("Budget Allocation",   "Adjust spending across departments"),
            ("Tax Policy",          "Change the national tax rate"),
            ("Social Policy",       "Gender equality, press freedom, ethnic reconciliation"),
            ("Military Policy",     "Expand forces or initiate programs"),
            ("Trade Policy",        "Sign agreements or impose tariffs"),
            ("Research Funding",    "Boost R&D spending"),
            ("Civil Rights",        "Pass civil rights legislation"),
            ("Anti-Corruption",     "Launch an anti-corruption drive"),
            ("Language Policy",     "Change official language stance"),
            ("Immigration Policy",  "Open or restrict immigration"),
            ("← Back",             ""),
        ], "Policy Domain")

        logs: List[str] = []

        if choice == 11:
            break

        elif choice == 1:
            console.print("\n[bold]Current budget:[/]")
            for dept, share in sorted(country.government.budget_allocation.items(), key=lambda x: -x[1]):
                from .display import _bar
                console.print(f"  {dept.replace('_', ' ').title():<22} {_bar(share * 3, 10)} {share:.1%}")
            console.print("\n[dim]Adjust one department (others auto-balance).[/]")
            dept_list = list(country.government.budget_allocation.keys())
            for i, d in enumerate(dept_list, 1):
                console.print(f"  {i}. {d.replace('_', ' ').title()}")
            raw = Prompt.ask("Department number", default="1")
            try:
                di = int(raw) - 1
                if not 0 <= di < len(dept_list):
                    raise ValueError
                dept = dept_list[di]
                pct = Prompt.ask(
                    f"New allocation for [bold]{dept.replace('_', ' ').title()}[/] (e.g. 0.20)",
                    default=f"{country.government.budget_allocation[dept]:.2f}"
                )
                _policy_preview(country, "budget", **{dept: float(pct)})
                if Confirm.ask("Apply this change?", default=True):
                    logs = engine.apply_policy(country, "budget", **{dept: float(pct)})
            except (ValueError, IndexError):
                console.print("[red]Invalid input.[/]")

        elif choice == 2:
            current = country.government.tax_rate
            console.print(f"\nCurrent tax rate: [bold]{current:.1%}[/]")
            raw = Prompt.ask("New tax rate (0.05–0.65)", default=f"{current:.2f}")
            try:
                new_rate = float(raw)
                _policy_preview(country, "tax", rate=new_rate)
                if Confirm.ask("Apply this change?", default=True):
                    logs = engine.apply_policy(country, "tax", rate=new_rate)
            except ValueError:
                console.print("[red]Invalid.[/]")

        elif choice == 3:
            pol_choice = _menu([
                ("Gender Equality",          "Pass gender equality legislation"),
                ("Ethnic Reconciliation",    "Launch reconciliation programs"),
                ("Strengthen Press Freedom", "Expand press protections"),
                ("Restrict Press",           "Impose media controls"),
                ("← Back",                  ""),
            ], "Social Policy")
            targets = ["gender_equality", "ethnic_reconciliation", "press_freedom", "restrict_press"]
            if pol_choice <= 4:
                logs = engine.apply_policy(country, "social", target=targets[pol_choice - 1])

        elif choice == 4:
            mil_choice = _menu([
                ("Expand Military (10%)",    "Increase active forces by 10%"),
                ("Expand Military (25%)",    "Increase active forces by 25%"),
                ("Initiate Nuclear Program", "Begin nuclear weapons development"),
                ("← Back",                  ""),
            ], "Military Policy")
            if mil_choice == 1:
                logs = engine.apply_policy(country, "military", action="increase_size", factor=1.1)
            elif mil_choice == 2:
                logs = engine.apply_policy(country, "military", action="increase_size", factor=1.25)
            elif mil_choice == 3:
                if Confirm.ask("Initiating a nuclear program will incur heavy costs. Proceed?"):
                    logs = engine.apply_policy(country, "military", action="nuclear_program")

        elif choice == 5:
            trade_choice = _menu([
                ("Sign Trade Agreement",        "Open new trade relations"),
                ("Impose Protectionist Tariffs", "Reduce trade in favour of domestic industry"),
                ("← Back",                      ""),
            ], "Trade Policy")
            if trade_choice == 1:
                logs = engine.apply_policy(country, "trade", action="open")
            elif trade_choice == 2:
                logs = engine.apply_policy(country, "trade", action="protectionist")

        elif choice == 6:
            _policy_preview(country, "research", boost=0.005)
            logs = engine.apply_policy(country, "research", boost=0.005)

        elif choice == 7:
            _policy_preview(country, "civil_rights")
            if Confirm.ask("Pass Civil Rights Act?", default=True):
                logs = engine.apply_policy(country, "civil_rights")

        elif choice == 8:
            _policy_preview(country, "anti_corruption")
            if Confirm.ask("Launch Anti-Corruption Drive?", default=True):
                logs = engine.apply_policy(country, "anti_corruption")

        elif choice == 9:
            lang_choice = _menu([
                ("Bilingual Education",     "Promote multiple languages — boosts literacy"),
                ("Promote Official Language", "Single language campaign — boosts identity"),
                ("Suppress Minority Languages", "Restrict minority tongues — risks ethnic tension"),
                ("← Back", ""),
            ], "Language Policy")
            actions = ["bilingual", "promote", "suppress"]
            if lang_choice <= 3:
                logs = engine.apply_policy(country, "language", action=actions[lang_choice - 1])

        elif choice == 10:
            imm_choice = _menu([
                ("Open Immigration",    "Accept more immigrants — boosts population and growth"),
                ("Restrict Immigration", "Tighten borders — reduces immigration flow"),
                ("← Back",              ""),
            ], "Immigration Policy")
            if imm_choice == 1:
                logs = engine.apply_policy(country, "immigration", action="open")
            elif imm_choice == 2:
                logs = engine.apply_policy(country, "immigration", action="restrict")

        if logs:
            console.print()
            for log in logs:
                console.print(f"[green]✓[/] {log}")
            _pause()


# ── Diplomacy menu ────────────────────────────────────────────────────────────

def menu_diplomacy(country: Country, world: World, engine: SimulationEngine) -> None:
    while True:
        _clear()
        _header(f"Foreign Affairs — {country.name}")
        print_relations(country, world)
        console.print()
        choice = _menu([
            ("View World Rankings",  "See all nations ranked by power"),
            ("Impose Sanctions",     "Apply economic pressure on a nation"),
            ("Lift Sanctions",       "Remove sanctions"),
            ("Sign Trade Agreement", "Establish trade treaty with a nation"),
            ("Sign Defense Pact",    "Form mutual defense treaty"),
            ("Inspect Nation",       "View a nation's full dashboard"),
            ("Declare War",          "Declare open war on another nation"),
            ("Sue for Peace",        "Offer to end an active war"),
            ("Espionage",            "Covertly steal tech, sabotage, or incite unrest"),
            ("← Back",              ""),
        ], "Diplomatic Action")

        if choice == 10:
            break

        elif choice == 1:
            _clear()
            print_world_ranking(world)
            _pause()

        elif choice == 6:
            others = [(cid, c) for cid, c in world.countries.items() if cid != country.id]
            if not others:
                console.print("[dim]No other nations.[/]")
                _pause()
                continue
            console.print("\n[bold]Select nation to inspect:[/]")
            for i, (cid, c) in enumerate(others, 1):
                rel = world.get_relation(country.id, cid)
                console.print(f"  {i}. {c.name} [{rel.stance.value}]")
            raw = Prompt.ask("Nation number", default="1")
            try:
                ti = int(raw) - 1
                if 0 <= ti < len(others):
                    target_id, target = others[ti]
                    rel = world.get_relation(country.id, target_id)
                    _clear()
                    print_country_dashboard(target)
                    console.print()
                    print_ai_country_brief(target, rel)
                    _pause()
            except (ValueError, IndexError):
                console.print("[red]Invalid.[/]")

        elif choice == 7:
            others = [(cid, c) for cid, c in world.countries.items() if cid != country.id]
            console.print("\n[bold]Select nation to declare war on:[/]")
            for i, (cid, c) in enumerate(others, 1):
                rel = world.get_relation(country.id, cid)
                console.print(f"  {i}. {c.name} (relation: {rel.score:+.2f})")
            raw = Prompt.ask("Nation number", default="1")
            try:
                ti = int(raw) - 1
                if 0 <= ti < len(others):
                    target_id, target = others[ti]
                    console.print(f"\n[bold red]⚠ WARNING: Declaring war on {target.name} will severely damage "
                                  f"international relations and destabilise your economy.[/]")
                    if Confirm.ask(f"Declare war on {target.name}?", default=False):
                        extra_logs = world.declare_war(country.id, target_id)
                        console.print(f"[bold red]War declared on {target.name}![/]")
                        for entry in extra_logs:
                            console.print(f"[red]{entry[5:].strip()}[/]")
                        _pause()
            except (ValueError, IndexError):
                console.print("[red]Invalid.[/]")

        elif choice == 8:
            at_war_with = [(other, rel) for other, rel in world.relations_for(country.id) if rel.at_war]
            if not at_war_with:
                console.print("[dim]You are not currently at war with anyone.[/]")
                _pause()
                continue
            console.print("\n[bold]Select nation to sue for peace with:[/]")
            for i, (other, rel) in enumerate(at_war_with, 1):
                console.print(f"  {i}. {other.name} (your war exhaustion: {country.military.war_exhaustion:.0%})")
            raw = Prompt.ask("Nation number", default="1")
            try:
                ti = int(raw) - 1
                if 0 <= ti < len(at_war_with):
                    target = at_war_with[ti][0]
                    if world.sue_for_peace(country.id, target.id):
                        console.print(f"[green]Peace agreed with {target.name}.[/]")
                    else:
                        console.print("[red]Peace offer failed.[/]")
                    _pause()
            except (ValueError, IndexError):
                console.print("[red]Invalid.[/]")

        elif choice == 9:
            others = [(cid, c) for cid, c in world.countries.items() if cid != country.id]
            if not others:
                console.print("[dim]No other nations.[/]")
                _pause()
                continue
            console.print("\n[bold]Select target nation:[/]")
            for i, (cid, c) in enumerate(others, 1):
                rel = world.get_relation(country.id, cid)
                console.print(f"  {i}. {c.name} [{rel.stance.value}] ({rel.score:+.2f})")
            raw = Prompt.ask("Nation number", default="1")
            try:
                ti = int(raw) - 1
                if not 0 <= ti < len(others):
                    raise ValueError
                target_id, target = others[ti]
            except (ValueError, IndexError):
                console.print("[red]Invalid.[/]")
                continue
            op_choice = _menu([
                ("Steal Technology",  "Attempt to acquire the target's research secrets"),
                ("Sabotage Economy",  "Attempt to disrupt the target's economic growth"),
                ("Incite Unrest",     "Attempt to stir up protests within the target"),
                ("← Back",           ""),
            ], "Espionage Operation")
            operations = ["steal_tech", "sabotage_economy", "incite_unrest"]
            if op_choice <= 3:
                console.print("[dim]Covert operations carry a risk of exposure that will damage relations.[/]")
                if Confirm.ask(f"Proceed against {target.name}?", default=False):
                    log = world.attempt_espionage(country.id, target_id, operations[op_choice - 1])
                    if log:
                        console.print(f"[magenta]{log[11:].strip()}[/]")
                    _pause()

        elif choice in (2, 3, 4, 5):
            others = [(cid, c) for cid, c in world.countries.items() if cid != country.id]
            if not others:
                console.print("[dim]No other nations.[/]")
                _pause()
                continue
            console.print("\n[bold]Select target nation:[/]")
            for i, (cid, c) in enumerate(others, 1):
                rel = world.get_relation(country.id, cid)
                console.print(f"  {i}. {c.name} [{rel.stance.value}] ({rel.score:+.2f})")
            raw = Prompt.ask("Nation number", default="1")
            try:
                ti = int(raw) - 1
                if 0 <= ti < len(others):
                    target_id = others[ti][0]
                    target_name = others[ti][1].name
                    if choice == 2:
                        world.impose_sanctions(country.id, target_id)
                        console.print(f"[yellow]Sanctions imposed on {target_name}.[/]")
                    elif choice == 3:
                        world.lift_sanctions(country.id, target_id)
                        console.print(f"[green]Sanctions lifted on {target_name}.[/]")
                    elif choice == 4:
                        world.sign_trade_agreement(country.id, target_id)
                        console.print(f"[green]Trade agreement signed with {target_name}.[/]")
                    elif choice == 5:
                        world.sign_defense_pact(country.id, target_id)
                        console.print(f"[blue]Defense pact signed with {target_name}.[/]")
                    _pause()
            except (ValueError, IndexError):
                console.print("[red]Invalid.[/]")


# ── Inspect menu ──────────────────────────────────────────────────────────────

def menu_inspect(country: Country, world: World) -> None:
    while True:
        _clear()
        _header(f"Inspect — {country.name}")
        choice = _menu([
            ("Government Detail",   ""),
            ("Culture & Language",  ""),
            ("Geography & Resources", ""),
            ("Military Detail",     ""),
            ("History Log",         ""),
            ("Advisor Report",      "Full advisor warning and opportunity analysis"),
            ("Objectives",          "View national objectives progress"),
            ("World Rankings",      ""),
            ("← Back",             ""),
        ])
        if choice == 9:
            break
        _clear()
        if choice == 1:
            print_government_detail(country)
        elif choice == 2:
            print_culture_language(country)
        elif choice == 3:
            print_geography(country)
        elif choice == 4:
            print_military_detail(country)
        elif choice == 5:
            print_history(country, n=15)
        elif choice == 6:
            warnings = Advisor.get_warnings(country)
            opportunities = Advisor.get_opportunities(country)
            print_advisor_panel(warnings, opportunities)
        elif choice == 7:
            print_objectives(country, world, country.founding_year)
        elif choice == 8:
            print_world_ranking(world)
        _pause()


# ── Load game screen ──────────────────────────────────────────────────────────

def _load_save_preview(save_dir: str) -> List[Tuple[str, str]]:
    """Parse save files and return list of (filename, description) pairs."""
    saves = []
    if not os.path.exists(save_dir):
        return saves
    for fname in sorted(os.listdir(save_dir), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(save_dir, fname)
        try:
            with open(path) as f:
                raw = json.load(f)
            # Extract header info from the raw JSON without full deserialisation
            countries = raw.get("countries", {})
            player_id = raw.get("player_id")
            year = raw.get("year", "?")
            if player_id and player_id in countries:
                pc = countries[player_id]
                pname = pc.get("name", "Unknown")
                gov_type = pc.get("government", {}).get("type", "?")
                stab = pc.get("stability", {}).get("overall", 0.0)
                gdp = pc.get("economy", {}).get("gdp_total", 0.0)
                desc = f"{pname} | {gov_type} | Year {year} | Stability {stab:.0%} | GDP ${gdp:.0f}B"
            else:
                desc = fname
            saves.append((fname, desc))
        except Exception:
            saves.append((fname, fname))
    return saves


# ── Graphics ─────────────────────────────────────────────────────────────────

def _launch_graphics(world: World) -> None:
    try:
        from ..graphics.engine import run_graphics_view
    except ImportError:
        console.print("[red]The graphics engine requires pygame. Install with: pip install -r requirements.txt[/]")
        _pause()
        return
    console.print("[dim]Opening world map window — close it or press Esc to return.[/]")
    try:
        run_graphics_view(world)
    except Exception as exc:
        console.print(f"[red]Graphics engine error: {exc}[/]")
        _pause()


# ── Main game loop ───────────────────────────────────────────────────────────

def game_loop(world: World, engine: SimulationEngine) -> None:
    player = world.player_country
    if not player:
        console.print("[red]No player country found.[/]")
        return

    start_year = player.founding_year

    while True:
        _clear()
        print_country_dashboard(player)

        # Inline advisor summary before menu
        console.print()
        summary_line = Advisor.summarise(player)
        console.print(Panel(summary_line, title="[bold yellow]Advisor[/]", box=box.SIMPLE, padding=(0, 1)))

        choice = _menu([
            ("Next Year →",    f"Advance to {player.current_year + 1}"),
            ("Policy",         "Adjust laws, budget, and spending"),
            ("Foreign Affairs", "Diplomacy, trade agreements, sanctions"),
            ("Inspect",        "Detailed stats: government, culture, geography, military"),
            ("World Map",      "Open the interactive graphical world map"),
            ("Save Game",      ""),
            ("Quit",           ""),
        ], f"Year {player.current_year} — What will you do?")

        if choice == 1:
            _clear()
            console.print("[dim]Simulating AI nations...[/]")
            ai_results = engine.advance_world_turn(auto_resolve_events=True)

            # Advance player
            result = engine.advance_turn(player, auto_resolve_events=False)

            # Advance world diplomacy and year counter once per calendar year
            war_logs = engine.world.advance_world_year()

            # Resolve player-choice events first (needs player input before summary)
            if result.pending_choices:
                resolve_pending_events(result.pending_choices, engine)

            # Show turn summary
            _clear()
            all_events = result.all_events
            ai_logs = [entry for ai_result in ai_results.values() for entry in ai_result.log
                       if entry.startswith(("[AI]", "[WAR]", "[ESPIONAGE]"))]
            print_turn_summary(player, all_events, result.log, world_logs=ai_logs + war_logs)
            _pause()

            # Check for game over
            reason = _check_game_over(player, result)
            if reason:
                _clear()
                print_game_over(player, reason)
                _pause()
                return

        elif choice == 2:
            menu_policy(player, engine)

        elif choice == 3:
            menu_diplomacy(player, world, engine)

        elif choice == 4:
            menu_inspect(player, world)

        elif choice == 5:
            _launch_graphics(world)

        elif choice == 6:
            path = save_game(world)
            console.print(f"[green]Game saved to {path}[/]")
            _pause()

        elif choice == 7:
            if Confirm.ask("Quit the game?"):
                console.print("[dim]Goodbye.[/]")
                sys.exit(0)


# ── Entry point ──────────────────────────────────────────────────────────────

def run_cli() -> None:
    from rich.align import Align

    _clear()

    title = Text.assemble(
        "\n",
        ("N A T I O N   F O R G E\n", "bold bright_yellow"),
        ("─" * 42 + "\n", "dim"),
        ("A Country Governance Simulation\n\n", "bold white"),
        ("Lead your nation from ancient kingdoms to modern superpowers.\n", "dim"),
        ("Every policy, treaty, and crisis shapes your legacy.", "dim"),
        "\n",
    )
    console.print(Panel(Align.center(title), box=box.DOUBLE_EDGE, border_style="bright_blue", padding=(0, 4)))
    console.print()

    save_dir = saves_dir()
    try:
        n_saves = sum(1 for f in os.listdir(save_dir) if f.endswith(".json")) if os.path.isdir(save_dir) else 0
    except OSError:
        n_saves = 0

    load_desc = f"{n_saves} save{'s' if n_saves != 1 else ''} available" if n_saves else "No saves found"

    console.print("[dim]Tip: Open [bold]Policy[/] each turn to govern. The [bold]Advisor[/] highlights critical risks.[/]\n")

    choice = _menu([
        ("New Game",  "Generate a new world and begin your rule"),
        ("Load Game", load_desc),
        ("Quit",      ""),
    ], "Main Menu")

    if choice == 1:
        world, engine = setup_new_game()
        game_loop(world, engine)

    elif choice == 2:
        previews = _load_save_preview(save_dir)
        if not previews:
            console.print("[yellow]No saves found.[/]")
            _pause()
            return

        t = Table(title="Saved Games", box=box.ROUNDED)
        t.add_column("#",    style="dim",  width=4)
        t.add_column("File", style="bold")
        t.add_column("Nation / State")
        for i, (fname, desc) in enumerate(previews, 1):
            t.add_row(str(i), fname, desc)
        console.print(t)

        while True:
            raw = Prompt.ask(f"Save number (1–{len(previews)})", default="1")
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(previews):
                    break
            except ValueError:
                pass
            console.print("[red]Enter one of the listed save numbers.[/]")

        fname, _ = previews[idx]
        path = os.path.join(save_dir, fname)
        try:
            world = load_game(path)
            engine = SimulationEngine(world)
            game_loop(world, engine)
        except Exception as e:
            console.print(f"[red]Failed to load: {e}[/]")
            _pause()

    else:
        sys.exit(0)
