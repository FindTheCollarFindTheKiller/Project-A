"""
Textual-based TUI for the governance simulation.

Every menu, policy screen, and dialog here is operable both by mouse click
and by keyboard, replacing the previous Rich `Prompt`/`Confirm`-driven CLI in
`cli.py`. The pygame world-map graphics engine (`simulation/graphics/engine.py`)
is untouched and is launched as an external, blocking view via `App.suspend()`.
"""
from __future__ import annotations

import os
import random
import sys
from typing import List, Optional, Tuple

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from ..models.country import Country
from ..systems.world import World
from ..systems.engine import SimulationEngine, TurnResult
from ..systems.events import GameEvent
from ..systems.generator import CountryGenerator, ARCHETYPES
from ..systems.advisor import Advisor
from ..persistence.save_load import save_game, load_game
from ..paths import saves_dir
from . import display
from .modals import ConfirmModal, ChoiceModal, InputModal, InfoModal, capture_render


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

_DIFFICULTY_MODS = {
    "Easy":   {"start_stability": 0.15},
    "Normal": {"start_stability": 0.0},
    "Hard":   {"start_stability": -0.10},
}


def _check_game_over(country: Country, result: TurnResult) -> Optional[str]:
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


# ── Main menu ─────────────────────────────────────────────────────────────────

class MainMenuScreen(Screen):
    CSS = """
    MainMenuScreen {
        align: center middle;
    }
    #menu-box {
        width: 60;
        border: round $accent;
        padding: 1 2;
    }
    #menu-box Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        save_dir = saves_dir()
        try:
            n_saves = sum(1 for f in os.listdir(save_dir) if f.endswith(".json")) if os.path.isdir(save_dir) else 0
        except OSError:
            n_saves = 0
        with Container(id="menu-box"):
            yield Label("[bold bright_yellow]N A T I O N   F O R G E[/]", classes="title")
            yield Label("A Country Governance Simulation\n", classes="subtitle")
            yield Button("New Game", id="new", variant="success")
            yield Button(f"Load Game ({n_saves} save{'s' if n_saves != 1 else ''})", id="load", variant="primary")
            yield Button("Quit", id="quit", variant="error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new":
            self.app.push_screen(NewGameSetupScreen())
        elif event.button.id == "load":
            self.app.push_screen(LoadGameScreen())
        elif event.button.id == "quit":
            self.app.exit()


# ── New game setup ───────────────────────────────────────────────────────────

class NewGameSetupScreen(Screen):
    CSS = """
    NewGameSetupScreen {
        align: center middle;
    }
    #setup-box {
        width: 80;
        border: round $accent;
        padding: 1 2;
    }
    #setup-box Label {
        margin-top: 1;
    }
    #setup-box Button {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        arch_options = [("Random", "__random__")] + [
            (key.replace("_", " ").title(), key) for key in ARCHETYPES.keys()
        ]
        with VerticalScroll(id="setup-box"):
            yield Label("[bold]Name your nation[/]")
            yield Input(value="Valdoria", id="name")
            yield Label("[bold]Geographic archetype[/]")
            yield Select(arch_options, value="__random__", id="archetype")
            yield Label("[bold]Difficulty[/]")
            yield Select(
                [("Easy", "Easy"), ("Normal", "Normal"), ("Hard", "Hard")],
                value="Normal", id="difficulty",
            )
            yield Label("[bold]Start year[/]")
            yield Input(value="1900", id="start_year")
            yield Label("[bold]Number of AI nations[/]")
            yield Input(value="5", id="num_ai")
            yield Button("Generate World", id="generate", variant="success")
            yield Button("← Back", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "generate":
            self._generate()

    @work(exclusive=True)
    async def _generate(self) -> None:
        name = self.query_one("#name", Input).value.strip() or "Valdoria"
        archetype_val = self.query_one("#archetype", Select).value
        archetype = None if archetype_val == "__random__" else archetype_val
        difficulty = self.query_one("#difficulty", Select).value

        try:
            start_year = int(self.query_one("#start_year", Input).value)
        except ValueError:
            start_year = 1900
        try:
            num_ai = max(1, min(20, int(self.query_one("#num_ai", Input).value)))
        except ValueError:
            num_ai = 5

        gen = CountryGenerator()
        world = World(year=start_year)
        player = gen.generate(archetype=archetype, start_year=start_year, name=name, country_id="player")
        diff_mod = _DIFFICULTY_MODS[difficulty]
        player.stability.overall = max(0.1, min(1.0, player.stability.overall + diff_mod["start_stability"]))
        world.difficulty = difficulty
        world.add_country(player)
        world.player_id = "player"

        arch_keys = list(ARCHETYPES.keys())
        for i in range(num_ai):
            ai_arch = arch_keys[i % len(arch_keys)]
            ai_country = gen.generate(archetype=ai_arch, start_year=start_year, country_id=f"ai_{i}")
            world.add_country(ai_country)

        all_ids = list(world.countries.keys())
        rng = random.Random()
        for cid, c in world.countries.items():
            n_neighbors = min(c.geography.neighbor_count, len(all_ids) - 1)
            potential = [oid for oid in all_ids if oid != cid]
            c.neighbor_ids = rng.sample(potential, k=min(n_neighbors, len(potential)))
            for nid in c.neighbor_ids:
                _ = world.get_relation(cid, nid)

        engine = SimulationEngine(world)

        preview = capture_render(display.print_country_dashboard, player)
        confirmed = await self.app.push_screen_wait(InfoModalConfirm(preview, title=f"Preview — {player.name}"))
        if not confirmed:
            return

        self.app.pop_screen()
        self.app.push_screen(GameDashboardScreen(world, engine))


class InfoModalConfirm(ConfirmModal):
    """A confirm dialog that also shows a Rich renderable preview above the
    Yes/No buttons (used for the new-game preview)."""

    def __init__(self, renderable, *, title: str = "") -> None:
        super().__init__("Start the game with this nation?")
        self._renderable = renderable
        self._title = title

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            if self._title:
                yield Label(self._title, classes="title")
            yield Static(self._renderable)
            yield Label(self._message)
            with Horizontal():
                yield Button("Start", id="yes", variant="success")
                yield Button("Regenerate", id="no", variant="default")


# ── Load game ─────────────────────────────────────────────────────────────────

class LoadGameScreen(Screen):
    CSS = """
    LoadGameScreen {
        align: center middle;
    }
    #load-box {
        width: 90%;
        max-height: 80%;
        border: round $accent;
        padding: 1 2;
    }
    #load-box Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="load-box"):
            yield Label("[bold]Saved Games[/]")
            self._previews = self._load_previews()
            if not self._previews:
                yield Label("[dim]No saves found.[/]")
            for i, (fname, desc) in enumerate(self._previews):
                yield Button(f"{fname} — {desc}", id=f"save-{i}")
            yield Button("← Back", id="back")
        yield Footer()

    @staticmethod
    def _load_previews() -> List[Tuple[str, str]]:
        import json
        save_dir = saves_dir()
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.app.pop_screen()
        elif button_id.startswith("save-"):
            idx = int(button_id.split("-", 1)[1])
            fname = self._previews[idx][0]
            self._load(fname)

    @work(exclusive=True)
    async def _load(self, fname: str) -> None:
        path = os.path.join(saves_dir(), fname)
        try:
            world = load_game(path)
            engine = SimulationEngine(world)
        except Exception as e:
            await self.app.push_screen_wait(InfoModal(f"[red]Failed to load: {e}[/]"))
            return
        self.app.pop_screen()
        self.app.push_screen(GameDashboardScreen(world, engine))


# ── Game dashboard (main game loop) ──────────────────────────────────────────

class GameDashboardScreen(Screen):
    CSS = """
    GameDashboardScreen {
        layout: vertical;
    }
    #dashboard-body {
        height: 1fr;
        padding: 1 2;
    }
    #action-bar {
        height: auto;
        padding: 0 2 1 2;
    }
    #action-bar Button {
        margin-right: 1;
    }
    """

    def __init__(self, world: World, engine: SimulationEngine) -> None:
        super().__init__()
        self.world = world
        self.engine = engine

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="dashboard-body"):
            yield Static(id="dashboard-content")
        with Horizontal(id="action-bar"):
            yield Button("Next Year →", id="next_year", variant="success")
            yield Button("Policy", id="policy")
            yield Button("Foreign Affairs", id="diplomacy")
            yield Button("Inspect", id="inspect")
            yield Button("World Map", id="world_map")
            yield Button("Save Game", id="save")
            yield Button("Quit to Menu", id="quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        player = self.world.player_country
        if not player:
            return
        content = capture_render(display.print_country_dashboard, player)
        summary_line = Advisor.summarise(player)
        from rich.console import Group
        from rich.panel import Panel
        combined = Group(content, Panel(summary_line, title="[bold yellow]Advisor[/]"))
        self.query_one("#dashboard-content", Static).update(combined)
        self.title = f"Year {player.current_year} — {player.name}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "next_year":
            self._advance_turn()
        elif button_id == "policy":
            self._policy_flow()
        elif button_id == "diplomacy":
            self._diplomacy_flow()
        elif button_id == "inspect":
            self._inspect_flow()
        elif button_id == "world_map":
            self._launch_world_map()
        elif button_id == "save":
            self._save()
        elif button_id == "quit":
            self._quit_to_menu()

    @work(exclusive=True)
    async def _quit_to_menu(self) -> None:
        if await self.app.push_screen_wait(ConfirmModal("Return to the main menu? Unsaved progress will be lost.", default=False)):
            self.app.pop_screen()

    @work(exclusive=True)
    async def _save(self) -> None:
        path = save_game(self.world)
        await self.app.push_screen_wait(InfoModal(f"[green]Game saved to {path}[/]"))

    def _launch_world_map(self) -> None:
        try:
            from ..graphics.engine import run_graphics_view
        except ImportError:
            self.notify("The graphics engine requires pygame. Install with: pip install -r requirements.txt", severity="error")
            return
        with self.app.suspend():
            try:
                run_graphics_view(self.world)
            except Exception as exc:
                print(f"Graphics engine error: {exc}")

    @work(exclusive=True)
    async def _advance_turn(self) -> None:
        player = self.world.player_country
        if not player:
            return
        ai_results = self.engine.advance_world_turn(auto_resolve_events=True)
        result = self.engine.advance_turn(player, auto_resolve_events=False)
        war_logs = self.engine.world.advance_world_year()

        for event, country in result.pending_choices:
            await self._resolve_event(event, country)

        all_events = result.all_events
        ai_logs = [entry for ai_result in ai_results.values() for entry in ai_result.log
                   if entry.startswith(("[AI]", "[WAR]", "[ESPIONAGE]"))]
        summary = capture_render(
            display.print_turn_summary, player, all_events, result.log,
            world_logs=ai_logs + war_logs,
        )
        await self.app.push_screen_wait(InfoModal(summary, title=f"Year {player.current_year - 1} Report"))

        reason = _check_game_over(player, result)
        self._refresh()
        if reason:
            game_over = capture_render(display.print_game_over, player, reason)
            await self.app.push_screen_wait(InfoModal(game_over, title="Game Over"))
            self.app.pop_screen()

    async def _resolve_event(self, event: GameEvent, country: Country) -> None:
        popup = capture_render(display.print_event_popup, event)
        if event.choices:
            options = [(choice.label, i) for i, choice in enumerate(event.choices)]
            choice_idx = await self.app.push_screen_wait(
                ChoiceModal(f"EVENT: {event.name}", options, allow_cancel=False)
            )
            if choice_idx is None:
                choice_idx = 0
            self.engine.resolve_event(event, country, choice_idx)
        else:
            await self.app.push_screen_wait(InfoModal(popup, title=f"EVENT: {event.name}"))
            self.engine.resolve_event(event, country, None)

    # ── Policy ────────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _policy_flow(self) -> None:
        player = self.world.player_country
        while True:
            choice = await self.app.push_screen_wait(ChoiceModal("Policy Domain", [
                ("Budget Allocation", "budget"),
                ("Tax Policy", "tax"),
                ("Social Policy", "social"),
                ("Military Policy", "military"),
                ("Trade Policy", "trade"),
                ("Research Funding", "research"),
                ("Civil Rights", "civil_rights"),
                ("Anti-Corruption", "anti_corruption"),
                ("Language Policy", "language"),
                ("Immigration Policy", "immigration"),
            ]))
            if choice is None:
                break
            logs = await self._apply_policy_domain(player, choice)
            if logs:
                await self.app.push_screen_wait(InfoModal(
                    "\n".join(f"[green]✓[/] {log}" for log in logs), title="Policy Applied",
                ))
                self._refresh()

    async def _apply_policy_domain(self, player: Country, domain: str) -> List[str]:
        gov = player.government
        if domain == "budget":
            dept_list = list(gov.budget_allocation.keys())
            options = [(f"{d.replace('_', ' ').title()} ({gov.budget_allocation[d]:.1%})", d) for d in dept_list]
            dept = await self.app.push_screen_wait(ChoiceModal("Adjust Department", options))
            if dept is None:
                return []
            raw = await self.app.push_screen_wait(InputModal(
                f"New allocation for {dept.replace('_', ' ').title()} (e.g. 0.20)",
                default=f"{gov.budget_allocation[dept]:.2f}",
            ))
            try:
                pct = float(raw) if raw is not None else None
            except ValueError:
                pct = None
            if pct is None:
                return []
            if await self.app.push_screen_wait(ConfirmModal("Apply this change?")):
                return self.engine.apply_policy(player, "budget", **{dept: pct})
            return []

        if domain == "tax":
            raw = await self.app.push_screen_wait(InputModal(
                "New tax rate (0.05–0.65)", default=f"{gov.tax_rate:.2f}",
            ))
            try:
                new_rate = float(raw) if raw is not None else None
            except ValueError:
                new_rate = None
            if new_rate is None:
                return []
            if await self.app.push_screen_wait(ConfirmModal("Apply this change?")):
                return self.engine.apply_policy(player, "tax", rate=new_rate)
            return []

        if domain == "social":
            target = await self.app.push_screen_wait(ChoiceModal("Social Policy", [
                ("Gender Equality", "gender_equality"),
                ("Ethnic Reconciliation", "ethnic_reconciliation"),
                ("Strengthen Press Freedom", "press_freedom"),
                ("Restrict Press", "restrict_press"),
            ]))
            if target is None:
                return []
            return self.engine.apply_policy(player, "social", target=target)

        if domain == "military":
            action = await self.app.push_screen_wait(ChoiceModal("Military Policy", [
                ("Expand Military (10%)", ("increase_size", 1.1)),
                ("Expand Military (25%)", ("increase_size", 1.25)),
                ("Initiate Nuclear Program", ("nuclear_program", None)),
            ]))
            if action is None:
                return []
            act, factor = action
            if act == "nuclear_program":
                if await self.app.push_screen_wait(ConfirmModal(
                    "Initiating a nuclear program will incur heavy costs. Proceed?", default=False,
                )):
                    return self.engine.apply_policy(player, "military", action="nuclear_program")
                return []
            return self.engine.apply_policy(player, "military", action=act, factor=factor)

        if domain == "trade":
            action = await self.app.push_screen_wait(ChoiceModal("Trade Policy", [
                ("Sign Trade Agreement", "open"),
                ("Impose Protectionist Tariffs", "protectionist"),
            ]))
            if action is None:
                return []
            return self.engine.apply_policy(player, "trade", action=action)

        if domain == "research":
            return self.engine.apply_policy(player, "research", boost=0.005)

        if domain == "civil_rights":
            if await self.app.push_screen_wait(ConfirmModal("Pass Civil Rights Act?")):
                return self.engine.apply_policy(player, "civil_rights")
            return []

        if domain == "anti_corruption":
            if await self.app.push_screen_wait(ConfirmModal("Launch Anti-Corruption Drive?")):
                return self.engine.apply_policy(player, "anti_corruption")
            return []

        if domain == "language":
            action = await self.app.push_screen_wait(ChoiceModal("Language Policy", [
                ("Bilingual Education", "bilingual"),
                ("Promote Official Language", "promote"),
                ("Suppress Minority Languages", "suppress"),
            ]))
            if action is None:
                return []
            return self.engine.apply_policy(player, "language", action=action)

        if domain == "immigration":
            action = await self.app.push_screen_wait(ChoiceModal("Immigration Policy", [
                ("Open Immigration", "open"),
                ("Restrict Immigration", "restrict"),
            ]))
            if action is None:
                return []
            return self.engine.apply_policy(player, "immigration", action=action)

        return []

    # ── Diplomacy ─────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _diplomacy_flow(self) -> None:
        player = self.world.player_country
        while True:
            relations_view = capture_render(display.print_relations, player, self.world)
            action = await self.app.push_screen_wait(ChoiceModal("Diplomatic Action", [
                ("View World Rankings", "rankings"),
                ("Impose Sanctions", "sanction"),
                ("Lift Sanctions", "lift_sanction"),
                ("Sign Trade Agreement", "trade"),
                ("Sign Defense Pact", "defense"),
                ("Inspect Nation", "inspect"),
                ("Declare War", "war"),
                ("Sue for Peace", "peace"),
                ("Espionage", "espionage"),
            ]))
            if action is None:
                break
            await self._do_diplomacy(player, action)

    async def _select_nation(self, title: str, exclude_id: str) -> Optional[str]:
        others = [(cid, c) for cid, c in self.world.countries.items() if cid != exclude_id]
        if not others:
            await self.app.push_screen_wait(InfoModal("[dim]No other nations.[/]"))
            return None
        options = []
        for cid, c in others:
            rel = self.world.get_relation(exclude_id, cid)
            options.append((f"{c.name} [{rel.stance.value}] ({rel.score:+.2f})", cid))
        return await self.app.push_screen_wait(ChoiceModal(title, options))

    async def _do_diplomacy(self, player: Country, action: str) -> None:
        if action == "rankings":
            rankings = capture_render(display.print_world_ranking, self.world)
            await self.app.push_screen_wait(InfoModal(rankings, title="World Power Rankings"))
            return

        if action == "inspect":
            target_id = await self._select_nation("Select nation to inspect", player.id)
            if target_id is None:
                return
            target = self.world.countries[target_id]
            rel = self.world.get_relation(player.id, target_id)
            dashboard = capture_render(display.print_country_dashboard, target)
            brief = capture_render(display.print_ai_country_brief, target, rel)
            from rich.console import Group
            await self.app.push_screen_wait(InfoModal(Group(dashboard, brief), title=target.name))
            return

        if action == "war":
            target_id = await self._select_nation("Select nation to declare war on", player.id)
            if target_id is None:
                return
            target = self.world.countries[target_id]
            if await self.app.push_screen_wait(ConfirmModal(
                f"Declaring war on {target.name} will severely damage international relations "
                f"and destabilise your economy. Proceed?", default=False,
            )):
                logs = self.world.declare_war(player.id, target_id)
                await self.app.push_screen_wait(InfoModal(
                    "\n".join([f"[bold red]War declared on {target.name}![/]"] + [l[5:].strip() for l in logs])
                ))
            return

        if action == "peace":
            at_war_with = [(other, rel) for other, rel in self.world.relations_for(player.id) if rel.at_war]
            if not at_war_with:
                await self.app.push_screen_wait(InfoModal("[dim]You are not currently at war with anyone.[/]"))
                return
            options = [(f"{other.name} (your war exhaustion: {player.military.war_exhaustion:.0%})", other.id) for other, _ in at_war_with]
            target_id = await self.app.push_screen_wait(ChoiceModal("Sue for Peace", options))
            if target_id is None:
                return
            target = self.world.countries[target_id]
            ok = self.world.sue_for_peace(player.id, target_id)
            msg = f"[green]Peace agreed with {target.name}.[/]" if ok else "[red]Peace offer failed.[/]"
            await self.app.push_screen_wait(InfoModal(msg))
            return

        if action == "espionage":
            target_id = await self._select_nation("Select target nation", player.id)
            if target_id is None:
                return
            target = self.world.countries[target_id]
            op = await self.app.push_screen_wait(ChoiceModal("Espionage Operation", [
                ("Steal Technology", "steal_tech"),
                ("Sabotage Economy", "sabotage_economy"),
                ("Incite Unrest", "incite_unrest"),
            ]))
            if op is None:
                return
            if await self.app.push_screen_wait(ConfirmModal(
                f"Covert operations carry a risk of exposure that will damage relations. Proceed against {target.name}?",
                default=False,
            )):
                log = self.world.attempt_espionage(player.id, target_id, op)
                if log:
                    await self.app.push_screen_wait(InfoModal(f"[magenta]{log[11:].strip()}[/]"))
            return

        # sanction / lift_sanction / trade / defense — target-based simple actions
        target_id = await self._select_nation("Select target nation", player.id)
        if target_id is None:
            return
        target = self.world.countries[target_id]
        if action == "sanction":
            self.world.impose_sanctions(player.id, target_id)
            msg = f"[yellow]Sanctions imposed on {target.name}.[/]"
        elif action == "lift_sanction":
            self.world.lift_sanctions(player.id, target_id)
            msg = f"[green]Sanctions lifted on {target.name}.[/]"
        elif action == "trade":
            self.world.sign_trade_agreement(player.id, target_id)
            msg = f"[green]Trade agreement signed with {target.name}.[/]"
        elif action == "defense":
            self.world.sign_defense_pact(player.id, target_id)
            msg = f"[blue]Defense pact signed with {target.name}.[/]"
        else:
            return
        await self.app.push_screen_wait(InfoModal(msg))

    # ── Inspect ───────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _inspect_flow(self) -> None:
        player = self.world.player_country
        while True:
            choice = await self.app.push_screen_wait(ChoiceModal("Inspect", [
                ("Government Detail", "government"),
                ("Culture & Language", "culture"),
                ("Geography & Resources", "geography"),
                ("Military Detail", "military"),
                ("History Log", "history"),
                ("Advisor Report", "advisor"),
                ("Objectives", "objectives"),
                ("World Rankings", "rankings"),
            ]))
            if choice is None:
                break
            renderable = None
            title = ""
            if choice == "government":
                renderable = capture_render(display.print_government_detail, player)
                title = "Government Detail"
            elif choice == "culture":
                renderable = capture_render(display.print_culture_language, player)
                title = "Culture & Language"
            elif choice == "geography":
                renderable = capture_render(display.print_geography, player)
                title = "Geography & Resources"
            elif choice == "military":
                renderable = capture_render(display.print_military_detail, player)
                title = "Military Detail"
            elif choice == "history":
                renderable = capture_render(display.print_history, player, n=15)
                title = "History Log"
            elif choice == "advisor":
                warnings = Advisor.get_warnings(player)
                opportunities = Advisor.get_opportunities(player)
                renderable = capture_render(display.print_advisor_panel, warnings, opportunities)
                title = "Advisor Report"
            elif choice == "objectives":
                renderable = capture_render(display.print_objectives, player, self.world, player.founding_year)
                title = "Objectives"
            elif choice == "rankings":
                renderable = capture_render(display.print_world_ranking, self.world)
                title = "World Rankings"
            if renderable is not None:
                await self.app.push_screen_wait(InfoModal(renderable, title=title))


# ── App ───────────────────────────────────────────────────────────────────────

class NationForgeApp(App):
    """Nation Forge — mouse- and keyboard-driven governance simulation TUI."""

    TITLE = "Nation Forge"
    CSS = """
    .title {
        text-style: bold;
        content-align: center middle;
        width: 100%;
    }
    .subtitle {
        color: $text-muted;
        content-align: center middle;
        width: 100%;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run_tui() -> None:
    NationForgeApp().run()
