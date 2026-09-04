"""
Windowed 2D graphics engine: interactive world map view.

This is a self-contained rendering layer on top of the existing simulation
state. It never mutates the World/Country models — it only visualizes them.
Requires pygame (see requirements.txt).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import pygame

from .layout import compute_layout

if TYPE_CHECKING:
    from ..systems.world import World
    from ..models.country import Country

from ..paths import saves_dir

_SAVES_DIR = saves_dir()
_PAN_SPEED = 12.0

_BG = (12, 16, 24)
_PANEL_BG = (22, 28, 38)
_TEXT = (230, 230, 230)
_DIM = (150, 155, 165)
_EDGE_NEUTRAL = (90, 95, 105)
_GOLD = (230, 190, 60)
_WHITE = (255, 255, 255)

_STANCE_COLORS = {
    "Allied":   (80, 200, 120),
    "Friendly": (110, 190, 140),
    "Neutral":  (110, 115, 125),
    "Tense":    (215, 150, 60),
    "Hostile":  (190, 70, 60),
    "At War":   (230, 40, 40),
}

_MIN_ZOOM, _MAX_ZOOM = 0.3, 4.0

_METRIC_COLORS = {
    "stability": (100, 200, 255),
    "happiness": (255, 200, 100),
    "legitimacy": (180, 130, 255),
    "gdp_growth": (120, 220, 120),
}


def _stability_color(value: float) -> Tuple[int, int, int]:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        t = value / 0.5
        return (int(200 - t * 20), int(60 + t * 130), int(50))
    t = (value - 0.5) / 0.5
    return (int(180 - t * 130), int(190 + t * 20), int(50 + t * 20))


class _Camera:
    def __init__(self) -> None:
        self.offset = [0.0, 0.0]
        self.zoom = 55.0

    def world_to_screen(self, pos: Tuple[float, float], surface_size: Tuple[int, int]) -> Tuple[int, int]:
        cx, cy = surface_size[0] // 2, surface_size[1] // 2
        x = cx + int((pos[0] + self.offset[0]) * self.zoom)
        y = cy + int((pos[1] + self.offset[1]) * self.zoom)
        return x, y


class GraphicsEngine:
    """Interactive world map: pan, zoom, click-to-inspect. ESC or close to exit."""

    def __init__(self, world: "World", width: int = 1280, height: int = 800) -> None:
        self.world = world
        self.width = width
        self.height = height
        self.camera = _Camera()
        self.selected_id: Optional[str] = world.player_id
        self.positions: Dict[str, Tuple[float, float]] = compute_layout(world)
        self._screen_positions: Dict[str, Tuple[int, int]] = {}
        self._panning = False
        self._hover_id: Optional[str] = None
        self._status_message: str = ""
        self._status_timer = 0
        self.view_mode = "map"
        self.show_all_edges = True
        self._fit_camera_to_positions()

    def _fit_camera_to_positions(self) -> None:
        if not self.positions:
            return
        xs = [p[0] for p in self.positions.values()]
        ys = [p[1] for p in self.positions.values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-3)
        map_width = max(200, self.width - 300)
        map_height = max(200, self.height - 160)  # keep clear of the top/bottom overlay text
        self.camera.zoom = max(15.0, min(200.0, (min(map_width, map_height) * 0.8) / span))
        self.camera.offset = [-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0]

    # ── Public entry point ──────────────────────────────────────────────────

    def run(self) -> None:
        pygame.init()
        try:
            screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
            pygame.display.set_caption("Nation Forge — World Map")
            font = pygame.font.SysFont("consolas", 16)
            font_small = pygame.font.SysFont("consolas", 13)
            font_title = pygame.font.SysFont("consolas", 20, bold=True)
            clock = pygame.time.Clock()

            running = True
            while running:
                self.width, self.height = screen.get_size()
                for event in pygame.event.get():
                    running = self._handle_event(event, screen)
                    if not running:
                        break
                self._apply_keyboard_pan()
                self._hover_id = self._node_at(pygame.mouse.get_pos())
                self._render(screen, font, font_small, font_title)
                pygame.display.flip()
                clock.tick(60)
                if self._status_timer > 0:
                    self._status_timer -= 1
        finally:
            pygame.quit()

    # ── Event handling ───────────────────────────────────────────────────────

    def _handle_event(self, event: "pygame.event.Event", screen: "pygame.Surface") -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_r:
                self._fit_camera_to_positions()
            elif event.key == pygame.K_TAB:
                self._cycle_selection(reverse=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_p:
                self._save_screenshot(screen)
            elif event.key == pygame.K_c:
                self.view_mode = "charts" if self.view_mode == "map" else "map"
            elif event.key == pygame.K_e:
                self.show_all_edges = not self.show_all_edges
        elif event.type == pygame.MOUSEWHEEL:
            factor = 1.1 ** event.y
            self.camera.zoom = max(15.0, min(200.0, self.camera.zoom * factor))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._select_at(event.pos)
            elif event.button == 3:
                self._panning = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self._panning = False
        elif event.type == pygame.MOUSEMOTION:
            if self._panning:
                dx, dy = event.rel
                self.camera.offset[0] += dx / self.camera.zoom
                self.camera.offset[1] += dy / self.camera.zoom
        return True

    def _apply_keyboard_pan(self) -> None:
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx += _PAN_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx -= _PAN_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy += _PAN_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy -= _PAN_SPEED
        if dx or dy:
            self.camera.offset[0] += dx / self.camera.zoom
            self.camera.offset[1] += dy / self.camera.zoom

    def _cycle_selection(self, reverse: bool = False) -> None:
        ranking = [c.id for c in self.world.power_ranking()]
        if not ranking:
            return
        if self.selected_id not in ranking:
            self.selected_id = ranking[0]
            return
        idx = ranking.index(self.selected_id)
        idx = (idx - 1 if reverse else idx + 1) % len(ranking)
        self.selected_id = ranking[idx]

    def _save_screenshot(self, screen: "pygame.Surface") -> None:
        os.makedirs(_SAVES_DIR, exist_ok=True)
        filename = f"worldmap_{datetime.now():%Y%m%d_%H%M%S}.png"
        pygame.image.save(screen, os.path.join(_SAVES_DIR, filename))
        self._status_message = f"Saved screenshot: {filename}"
        self._status_timer = 150

    def _node_at(self, mouse_pos: Tuple[int, int]) -> Optional[str]:
        best_id, best_dist = None, 18.0
        for cid, spos in self._screen_positions.items():
            dist = ((spos[0] - mouse_pos[0]) ** 2 + (spos[1] - mouse_pos[1]) ** 2) ** 0.5
            if dist < best_dist:
                best_id, best_dist = cid, dist
        return best_id

    def _select_at(self, mouse_pos: Tuple[int, int]) -> None:
        best_id = self._node_at(mouse_pos)
        if best_id:
            self.selected_id = best_id

    # ── Rendering ────────────────────────────────────────────────────────────

    def _node_radius(self, country: "Country") -> float:
        return 8.0 + min(1.0, country.global_power_score) * 22.0

    def _render(self, screen, font, font_small, font_title) -> None:
        screen.fill(_BG)
        panel_width = 300
        map_size = (self.width - panel_width, self.height)

        self._screen_positions = {}

        if self.view_mode == "charts":
            self._draw_charts(screen, font, font_small, map_size)
        else:
            # Draw every actual relation (not just geographic neighbors) so
            # diplomacy formed with distant nations is reflected accurately.
            for (a_id, b_id), rel in self.world._relations.items():
                if a_id not in self.world.countries or b_id not in self.world.countries:
                    continue
                if not self.show_all_edges and rel.stance.value == "Neutral" and not (
                        rel.treaty_trade or rel.treaty_defense or rel.at_war or rel.sanction_sender):
                    continue
                self._draw_edge(screen, a_id, b_id, map_size)

            for cid, country in self.world.countries.items():
                pos = self.positions.get(cid)
                if pos is None:
                    continue
                spos = self.camera.world_to_screen(pos, map_size)
                self._screen_positions[cid] = spos
                radius = self._node_radius(country)
                color = _stability_color(country.stability.overall)
                pygame.draw.circle(screen, color, spos, int(radius))
                if cid == self.world.player_id:
                    pygame.draw.circle(screen, _GOLD, spos, int(radius) + 3, width=2)
                if cid == self.selected_id:
                    pygame.draw.circle(screen, _WHITE, spos, int(radius) + 6, width=2)
                label = font_small.render(country.name[:14], True, _TEXT)
                screen.blit(label, (spos[0] - label.get_width() // 2, spos[1] + radius + 2))

        self._draw_legend(screen, font_small)
        self._draw_hud(screen, font, font_small, font_title, panel_width)
        self._draw_tooltip(screen, font_small)
        self._draw_status(screen, font_small)
        self._draw_topbar(screen, font_small)

    def _draw_edge(self, screen, a_id: str, b_id: str, map_size: Tuple[int, int]) -> None:
        pos_a, pos_b = self.positions.get(a_id), self.positions.get(b_id)
        if pos_a is None or pos_b is None:
            return
        rel = self.world.get_relation(a_id, b_id)
        color = _STANCE_COLORS.get(rel.stance.value, _EDGE_NEUTRAL)
        width = 3 if rel.at_war else (2 if (rel.treaty_trade or rel.treaty_defense) else 1)
        sa = self.camera.world_to_screen(pos_a, map_size)
        sb = self.camera.world_to_screen(pos_b, map_size)
        pygame.draw.line(screen, color, sa, sb, width)
        if rel.sanction_sender:
            mid = ((sa[0] + sb[0]) // 2, (sa[1] + sb[1]) // 2)
            pygame.draw.rect(screen, (230, 210, 60), (mid[0] - 4, mid[1] - 4, 8, 8))

    def _draw_topbar(self, screen, font_small) -> None:
        countries = list(self.world.countries.values())
        if not countries:
            return
        avg_stability = sum(c.stability.overall for c in countries) / len(countries)
        edge_mode = "all relations" if self.show_all_edges else "treaties/wars only"
        text = font_small.render(
            f"Year {self.world.year}   |   {len(countries)} nations   |   "
            f"Avg. stability {avg_stability:.0%}   |   Showing: {edge_mode} (E to toggle)",
            True, _DIM,
        )
        screen.blit(text, (10, 32))

    def _draw_charts(self, screen, font, font_small, map_size: Tuple[int, int]) -> None:
        x0, y0 = 20, 20
        w, h = map_size[0] - 40, map_size[1] - 140
        pygame.draw.rect(screen, _PANEL_BG, (x0, y0, w, h))
        pygame.draw.rect(screen, _EDGE_NEUTRAL, (x0, y0, w, h), 1)

        country = self.world.countries.get(self.selected_id)
        title = font.render(f"{country.name if country else 'No selection'} — History", True, _TEXT)
        screen.blit(title, (x0 + 10, y0 + 10))

        if not country or len(country.metric_history) < 2:
            screen.blit(font_small.render("Not enough history yet — advance a few years first.", True, _DIM),
                        (x0 + 10, y0 + 44))
            return

        history = country.metric_history
        chart_top = y0 + 50
        chart_h = h - 90

        def normalize(key: str, value: float) -> float:
            if key == "gdp_growth":
                return max(0.0, min(1.0, (value + 0.10) / 0.30))
            return max(0.0, min(1.0, value))

        for key, color in _METRIC_COLORS.items():
            points = []
            for i, (_year, stats) in enumerate(history):
                value = stats.get(key)
                if value is None:
                    continue
                nx = x0 + 10 + (w - 20) * (i / max(1, len(history) - 1))
                ny = chart_top + chart_h * (1 - normalize(key, value))
                points.append((nx, ny))
            if len(points) >= 2:
                pygame.draw.lines(screen, color, False, points, 2)

        lx, ly = x0 + 10, y0 + h - 24
        for key, color in _METRIC_COLORS.items():
            pygame.draw.rect(screen, color, (lx, ly, 12, 12))
            label = font_small.render(key.replace("_", " ").title(), True, _DIM)
            screen.blit(label, (lx + 16, ly - 2))
            lx += 16 + label.get_width() + 18

        years = [pt[0] for pt in history]
        screen.blit(font_small.render(str(years[0]), True, _DIM), (x0 + 10, y0 + h - 48))
        screen.blit(font_small.render(str(years[-1]), True, _DIM), (x0 + w - 50, y0 + h - 48))

    def _draw_tooltip(self, screen, font_small) -> None:
        if not self._hover_id or self._hover_id == self.selected_id:
            return
        country = self.world.countries.get(self._hover_id)
        spos = self._screen_positions.get(self._hover_id)
        if not country or not spos:
            return
        lines = [country.name, f"{country.government.type.value}  |  Power {country.global_power_score:.0%}"]
        if self.world.player_id and country.id != self.world.player_id:
            rel = self.world.get_relation(self.world.player_id, country.id)
            lines.append(f"Relation: {rel.stance.value} ({rel.score:+.2f})")
        text_surfaces = [font_small.render(line, True, _TEXT) for line in lines]
        box_w = max(t.get_width() for t in text_surfaces) + 16
        box_h = sum(t.get_height() for t in text_surfaces) + 12
        box_x = min(spos[0] + 16, self.width - 300 - box_w - 8)
        box_y = max(4, spos[1] - box_h - 8)
        pygame.draw.rect(screen, _PANEL_BG, (box_x, box_y, box_w, box_h))
        pygame.draw.rect(screen, _EDGE_NEUTRAL, (box_x, box_y, box_w, box_h), 1)
        ty = box_y + 6
        for t in text_surfaces:
            screen.blit(t, (box_x + 8, ty))
            ty += t.get_height()

    def _draw_status(self, screen, font_small) -> None:
        if self._status_timer <= 0 or not self._status_message:
            return
        text = font_small.render(self._status_message, True, _GOLD)
        screen.blit(text, (10, 10))

    def _draw_legend(self, screen, font_small) -> None:
        lines = [
            "Drag right mouse / WASD / arrows: pan   Wheel: zoom",
            "Click: select   Tab: cycle nations   R: reset view",
            "C: toggle charts   E: toggle all/significant relations   P: screenshot   Esc: close",
            "Node color: stability (red -> green)   Gold ring: your nation   Yellow square: sanctions",
        ]
        y = self.height - 18 * len(lines) - 8
        for line in lines:
            text = font_small.render(line, True, _DIM)
            screen.blit(text, (10, y))
            y += 18

        swatch_y = y - 18 * len(lines) - 22
        swatch_x = 10
        for label, color in _STANCE_COLORS.items():
            pygame.draw.rect(screen, color, (swatch_x, swatch_y, 12, 12))
            text = font_small.render(label, True, _DIM)
            screen.blit(text, (swatch_x + 16, swatch_y - 2))
            swatch_x += 16 + text.get_width() + 18

    def _draw_hud(self, screen, font, font_small, font_title, panel_width: int) -> None:
        panel_rect = pygame.Rect(self.width - panel_width, 0, panel_width, self.height)
        pygame.draw.rect(screen, _PANEL_BG, panel_rect)
        pygame.draw.line(screen, _EDGE_NEUTRAL, (panel_rect.left, 0), (panel_rect.left, self.height), 1)

        x = panel_rect.left + 16
        y = 16
        year_text = font_title.render(f"Year {self.world.year}", True, _TEXT)
        screen.blit(year_text, (x, y))
        y += 36

        country = self.world.countries.get(self.selected_id) if self.selected_id else None
        if not country:
            screen.blit(font.render("Click a nation to inspect it.", True, _DIM), (x, y))
            return

        rows = [
            (country.name, ""),
            ("Government", country.government.type.value),
            ("Capital", country.capital),
            ("Population", country.population_str),
            ("GDP", country.gdp_str),
            ("GDP / capita", f"${country.economy.gdp_per_capita:,.0f}"),
            ("Stability", f"{country.stability.overall:.0%}"),
            ("Happiness", f"{country.demographics.happiness:.0%}"),
            ("Power Score", f"{country.global_power_score:.0%}"),
            ("Tech Tier", country.technology.tier_name),
        ]
        title_row, rows = rows[0], rows[1:]
        screen.blit(font_title.render(title_row[0], True, _GOLD), (x, y))
        y += 30
        for label, value in rows:
            screen.blit(font_small.render(f"{label}:", True, _DIM), (x, y))
            screen.blit(font_small.render(str(value), True, _TEXT), (x + 130, y))
            y += 22

        if self.world.player_id and country.id != self.world.player_id:
            rel = self.world.get_relation(self.world.player_id, country.id)
            y += 10
            screen.blit(font.render("Relation to you", True, _GOLD), (x, y))
            y += 26
            color = _STANCE_COLORS.get(rel.stance.value, _TEXT)
            screen.blit(font_small.render(f"Stance: {rel.stance.value}", True, color), (x, y))
            y += 22
            screen.blit(font_small.render(f"Score: {rel.score:+.2f}", True, _TEXT), (x, y))


def run_graphics_view(world: "World") -> None:
    """Blocking call: open the interactive world map window until closed."""
    GraphicsEngine(world).run()
