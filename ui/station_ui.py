
import math

import pygame

from core import settings as S
from systems.localization import t
from systems.station_system import CATS, UPGRADES, _BY_CAT
from utils.helpers import clamp

_RES_COLORS = {
    "salvage": (180, 140, 80),
    "data":    (80, 180, 255),
    "relay":   (140, 220, 160),
    "ancient": (220, 140, 255),
}


class StationUI:
    """Category-based upgrade terminal overlay. FINAL tab shows evac_protocol gated behind all 16 upgrades."""

    def __init__(self) -> None:
        self._cat_idx = 0
        self._sel_idx = 0
        self._scroll   = 0          # first visible upgrade index in current category
        self._max_visible = 5
        self._purchase_flash_t = 0.0
        self._purchase_flash_msg = ""
        self._flash_col = (255, 255, 255)

        self._font_title  = pygame.font.SysFont("segoeui", 22, bold=True)
        self._font_head   = pygame.font.SysFont("segoeui", 17, bold=True)
        self._font_body   = pygame.font.SysFont("segoeui", 15)
        self._font_small  = pygame.font.SysFont("segoeui", 13)

    # ---- navigation ----

    def _cat_list(self) -> list[dict]:
        return _BY_CAT[CATS[self._cat_idx]]

    def _clamp_sel(self) -> None:
        n = len(self._cat_list())
        if n == 0:
            self._sel_idx = 0
            return
        self._sel_idx = clamp(self._sel_idx, 0, n - 1)
        if self._sel_idx < self._scroll:
            self._scroll = self._sel_idx
        elif self._sel_idx >= self._scroll + self._max_visible:
            self._scroll = self._sel_idx - self._max_visible + 1

    def nav_up(self) -> None:
        self._sel_idx -= 1
        self._clamp_sel()

    def nav_down(self) -> None:
        self._sel_idx += 1
        self._clamp_sel()

    def prev_cat(self) -> None:
        self._cat_idx = (self._cat_idx - 1) % len(CATS)
        self._sel_idx = 0
        self._scroll = 0

    def next_cat(self) -> None:
        self._cat_idx = (self._cat_idx + 1) % len(CATS)
        self._sel_idx = 0
        self._scroll = 0

    def try_purchase(self, station) -> bool:
        items = self._cat_list()
        if not items:
            return False
        uid = items[self._sel_idx]["id"]
        if station.has(uid):
            self._flash("already_installed", (160, 160, 160))
            return False
        if station.is_locked(uid):
            self._flash(station.lock_message_key(uid), (190, 80, 70))
            return False
        if station.purchase(uid):
            self._flash("installed_flash", (80, 220, 140))
            return True
        else:
            self._flash("insufficient", (220, 80, 80))
            return False

    def _flash(self, key: str, col: tuple) -> None:
        self._purchase_flash_msg = t(f"station_ui.{key}")
        self._purchase_flash_t = 1.8
        self._flash_col = col

    def update(self, dt: float) -> None:
        if self._purchase_flash_t > 0.0:
            self._purchase_flash_t = max(0.0, self._purchase_flash_t - dt)

    # ---- drawing ----

    def draw(self, surface: pygame.Surface, station, time_s: float) -> None:
        W, H = S.SCREEN_WIDTH, S.SCREEN_HEIGHT

        # ---- Dark overlay ----
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((8, 6, 12, 215))
        surface.blit(overlay, (0, 0))

        # ---- Header ----
        panel_x, panel_y = 28, 20
        panel_w = W - 56

        title_pulse = 0.80 + 0.20 * abs(math.sin(time_s * 2.2))
        title_col = tuple(int(c * title_pulse) for c in (100, 190, 255))
        title_surf = self._font_title.render(t("station_ui.title"), True, title_col)
        surface.blit(title_surf, (panel_x, panel_y))

        # Horizontal separator
        sep_y = panel_y + 30
        pygame.draw.line(surface, (55, 45, 70), (panel_x, sep_y), (panel_x + panel_w, sep_y), 1)

        # ---- Resource bar ----
        res_y = sep_y + 10
        res_values = {
            "salvage": station.salvage,
            "data":    station.data_fragments,
            "relay":   station.relay_components,
            "ancient": station.ancient_tech,
        }
        rx = panel_x + 8
        for key in ("salvage", "data", "relay", "ancient"):
            label = t(f"res_labels.{key}")
            col   = _RES_COLORS[key]
            val   = res_values[key]
            icon_s = self._font_body.render(f"{label}  ×{val}", True, col)
            surface.blit(icon_s, (rx, res_y))
            rx += icon_s.get_width() + 36

        # Station level indicator (right-aligned)
        lvl = station.station_level()
        _lvl_keys = ["level_offline", "level_minimal", "level_partial", "level_operational"]
        lvl_cols  = [(160, 80, 60), (180, 140, 60), (120, 180, 255), (80, 220, 140)]
        lvl_text  = f"{t('station_ui.station_prefix')}  [{t(f'station_ui.{_lvl_keys[lvl]}')}]"
        lvl_s = self._font_small.render(lvl_text, True, lvl_cols[lvl])
        surface.blit(lvl_s, (panel_x + panel_w - lvl_s.get_width(), res_y))

        pygame.draw.line(surface, (55, 45, 70), (panel_x, res_y + 24), (panel_x + panel_w, res_y + 24), 1)

        # ---- Category tabs ----
        tab_y = res_y + 34
        tab_w = panel_w // len(CATS)
        for i, cat in enumerate(CATS):
            selected = (i == self._cat_idx)
            tx = panel_x + i * tab_w
            label = t(f"upgrade_cats.{cat}")
            if selected:
                bg_s = pygame.Surface((tab_w - 4, 26), pygame.SRCALPHA)
                bg_s.fill((55, 45, 72, 200))
                surface.blit(bg_s, (tx + 2, tab_y - 2))
                col = (120, 195, 255)
            else:
                col = (90, 82, 105)
            tab_s = self._font_head.render(label, True, col)
            surface.blit(tab_s, (tx + (tab_w - tab_s.get_width()) // 2, tab_y))

        pygame.draw.line(surface, (55, 45, 70), (panel_x, tab_y + 28), (panel_x + panel_w, tab_y + 28), 1)

        # ---- Upgrade list ----
        items = self._cat_list()
        list_y = tab_y + 38
        row_h = 56
        desc_col = (130, 120, 145)

        visible = items[self._scroll: self._scroll + self._max_visible]
        for vi, u in enumerate(visible):
            real_idx = self._scroll + vi
            selected = (real_idx == self._sel_idx)
            iy = list_y + vi * row_h
            uid = u["id"]
            purchased    = station.has(uid)
            locked       = station.is_locked(uid)
            can_afford   = station.can_afford(uid)
            experimental = u.get("experimental", False)

            # Row background
            if selected:
                bg_col = (50, 28, 28, 180) if locked else (42, 34, 60, 190)
                bg = pygame.Surface((panel_w, row_h - 4), pygame.SRCALPHA)
                bg.fill(bg_col)
                surface.blit(bg, (panel_x, iy))
                brd_col = (110, 48, 48) if locked else (80, 60, 110)
                pygame.draw.rect(surface, brd_col,
                                 pygame.Rect(panel_x, iy, panel_w, row_h - 4), 1, border_radius=3)

            # Status marker
            if purchased:
                mark, mark_col = "✓", (80, 210, 130)
            elif locked:
                mark, mark_col = "■", (140, 50, 50)
            elif can_afford:
                mark, mark_col = "►", (120, 195, 255)
            else:
                mark, mark_col = "·", (80, 72, 95)

            if purchased:
                name_col = (80, 210, 130)
            elif locked:
                name_col = (120, 72, 72)
            else:
                name_col = (200, 195, 215)

            mk_s = self._font_head.render(mark, True, mark_col)
            surface.blit(mk_s, (panel_x + 6, iy + 6))

            name_text = t(f"upgrades.{uid}.name")
            if experimental:
                name_text += f"  {t('station_ui.experimental_tag')}"
            nm_s = self._font_head.render(name_text, True, name_col)
            surface.blit(nm_s, (panel_x + 26, iy + 6))

            desc_text = (
                t(f"station_ui.{station.lock_message_key(uid)}") if locked
                else t(f"upgrades.{uid}.desc")
            )
            desc_col_actual = (140, 62, 62) if locked else desc_col
            desc_s = self._font_body.render(desc_text, True, desc_col_actual)
            surface.blit(desc_s, (panel_x + 26, iy + 26))

            # Cost (right side)
            if not purchased:
                cost = u["cost"]
                cost_parts = []
                for key in ("salvage", "data", "relay", "ancient"):
                    if cost.get(key, 0) > 0:
                        lbl  = t(f"res_labels.{key}")
                        ccol = _RES_COLORS[key]
                        cost_parts.append((f"{cost[key]}× {lbl}", ccol))

                cx_right = panel_x + panel_w - 8
                for text, ccol in reversed(cost_parts):
                    cs = self._font_small.render(text, True, ccol if can_afford else (80, 72, 95))
                    cx_right -= cs.get_width() + 12
                    surface.blit(cs, (cx_right, iy + 8))
            else:
                inst_s = self._font_small.render(t("station_ui.installed_badge"), True, (60, 160, 100))
                surface.blit(inst_s, (panel_x + panel_w - inst_s.get_width() - 8, iy + 8))

        # Scroll indicator
        if len(items) > self._max_visible:
            sc_s = self._font_small.render(
                f"{self._sel_idx + 1} / {len(items)}", True, (80, 72, 95)
            )
            surface.blit(sc_s, (panel_x + panel_w - sc_s.get_width(), list_y + self._max_visible * row_h))

        # ---- Flash message ----
        if self._purchase_flash_t > 0.0:
            fa = clamp(self._purchase_flash_t / 0.6, 0.0, 1.0)
            fl_s = self._font_head.render(self._purchase_flash_msg, True, self._flash_col)
            fl_s.set_alpha(int(255 * fa))
            surface.blit(fl_s, ((W - fl_s.get_width()) // 2, H - 60))

        # ---- Footer ----
        foot_y = H - 30
        pygame.draw.line(surface, (40, 34, 55), (panel_x, foot_y - 6), (panel_x + panel_w, foot_y - 6), 1)
        hint_s = self._font_small.render(t("station_ui.hints"), True, (75, 68, 90))
        surface.blit(hint_s, ((W - hint_s.get_width()) // 2, foot_y))
