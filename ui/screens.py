
import math
import random

import pygame

from core import settings as S
from core.state_manager import GameState
from systems.localization import get as loc_get, lang_label, t


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class Screens:
    """Static overlay screens: main menu, 5-page info manual, win, game-over. Rendered over the live game world."""

    _INFO_PAGES = 5

    def __init__(self) -> None:
        self._title_font   = pygame.font.SysFont("segoeui", 44, bold=True)
        self._heading_font = pygame.font.SysFont("segoeui", 20, bold=True)
        self._body_font    = pygame.font.SysFont("segoeui", 20)
        self._small_font   = pygame.font.SysFont("segoeui", 15)
        self._info_start_ms = 0
        self._info_page = 0
        self._last_state: GameState | None = None
        self._game_completed = False
        self._death_message = ""

    def set_completed(self, completed: bool) -> None:
        self._game_completed = completed

    def nav_info(self, delta: int) -> None:
        self._info_page = (self._info_page + delta) % self._INFO_PAGES
        self._info_start_ms = pygame.time.get_ticks()

    def draw(self, surface: pygame.Surface, state: GameState) -> None:
        if state != self._last_state:
            if state == GameState.INFO:
                self._info_start_ms = pygame.time.get_ticks()
                self._info_page = 0
            elif state == GameState.GAME_OVER:
                msgs = loc_get("menu.over_messages") or []
                self._death_message = random.choice(msgs) if msgs else ""
            self._last_state = state
        if state == GameState.MENU:
            self._draw_menu(surface)
        elif state == GameState.INFO:
            self._draw_info(surface)
        elif state == GameState.WIN:
            self._draw_win(surface)
        elif state == GameState.EVACUATION_WIN:
            self._draw_evacuation_win(surface)
        elif state == GameState.GAME_OVER:
            self._draw_game_over(surface)

    def _draw_menu(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks() / 1000.0

        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 148))
        surface.blit(overlay, (0, 0))

        cx = S.SCREEN_WIDTH // 2
        cy = S.SCREEN_HEIGHT // 2

        if self._game_completed:
            # Signal Restored variant — green palette, different text
            pulse = 0.82 + 0.18 * math.sin(now * 1.4)
            title_col = (
                int(_clamp(60  * pulse, 0, 255)),
                int(_clamp(245 * pulse, 0, 255)),
                int(_clamp(130 * pulse, 0, 255)),
            )
            title = self._title_font.render(t("menu.signal_restored_title"), True, title_col)
            surface.blit(title, title.get_rect(center=(cx, cy - 72)))

            sub = self._body_font.render(t("menu.signal_restored_tagline"), True, (140, 210, 168))
            surface.blit(sub, sub.get_rect(center=(cx, cy - 24)))

            line_alpha = int(70 + 50 * math.sin(now * 0.8))
            line_surf = pygame.Surface((290, 1), pygame.SRCALPHA)
            line_surf.fill((60, 160, 100, line_alpha))
            surface.blit(line_surf, (cx - 145, cy - 4))

            hint_start = self._body_font.render(t("menu.signal_restored_start"), True, (195, 232, 210))
            hint_info  = self._small_font.render(t("menu.info"),  True, (120, 168, 138))
            hint_lang  = self._small_font.render(
                t("menu.language_hint", lang=lang_label()), True, (100, 140, 118)
            )
            surface.blit(hint_start, hint_start.get_rect(center=(cx, cy + 26)))
            surface.blit(hint_info,  hint_info.get_rect(center=(cx, cy + 56)))
            surface.blit(hint_lang,  hint_lang.get_rect(center=(cx, cy + 80)))
        else:
            pulse = 0.85 + 0.15 * math.sin(now * 1.6)
            title_col = (
                int(_clamp(200 * pulse, 0, 255)),
                int(_clamp(155 * pulse, 0, 255)),
                int(_clamp(255 * pulse, 0, 255)),
            )
            title = self._title_font.render(t("menu.title"), True, title_col)
            surface.blit(title, title.get_rect(center=(cx, cy - 72)))

            sub = self._body_font.render(t("menu.tagline"), True, (175, 155, 200))
            surface.blit(sub, sub.get_rect(center=(cx, cy - 24)))

            line_alpha = int(80 + 50 * math.sin(now * 0.9))
            line_surf = pygame.Surface((290, 1), pygame.SRCALPHA)
            line_surf.fill((110, 80, 140, line_alpha))
            surface.blit(line_surf, (cx - 145, cy - 4))

            hint_start = self._body_font.render(t("menu.start"), True, (220, 218, 235))
            hint_info  = self._small_font.render(t("menu.info"),  True, (155, 150, 175))
            hint_lang  = self._small_font.render(
                t("menu.language_hint", lang=lang_label()), True, (130, 120, 160)
            )
            surface.blit(hint_start, hint_start.get_rect(center=(cx, cy + 26)))
            surface.blit(hint_info,  hint_info.get_rect(center=(cx, cy + 56)))
            surface.blit(hint_lang,  hint_lang.get_rect(center=(cx, cy + 80)))

    # ------------------------------------------------------------------ info

    def _draw_info(self, surface: pygame.Surface) -> None:
        elapsed = (pygame.time.get_ticks() - self._info_start_ms) / 1000.0
        alpha   = int(min(255, elapsed / 0.30 * 255))

        # Dark overlay
        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 168))
        surface.blit(overlay, (0, 0))

        # Terminal panel
        panel_w, panel_h = 622, 452
        panel_x = (S.SCREEN_WIDTH  - panel_w) // 2
        panel_y = (S.SCREEN_HEIGHT - panel_h) // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((7, 5, 13, 238))
        pygame.draw.rect(panel, (58, 44, 78), panel.get_rect(), 2, border_radius=8)
        surface.blit(panel, (panel_x, panel_y))

        GOLD   = (255, 200,  80)
        TEAL   = (100, 200, 240)
        TEXT   = (210, 210, 215)
        DIM    = (130, 122, 148)
        DIMMER = ( 80,  74,  96)
        H  = self._heading_font
        S_ = self._small_font

        # ── page titles and content ───────────────────────────────────────────
        titles = loc_get("manual.titles") or []
        title_text = titles[self._info_page] if self._info_page < len(titles) else ""

        # Header: corner tag + section title
        tag_s = S_.render(f"UNIT-07 // MISSION DATABASE", True, DIMMER)
        tag_s.set_alpha(alpha)
        surface.blit(tag_s, (panel_x + 16, panel_y + 12))

        title_s = H.render(f"◈  {title_text}", True, TEAL)
        title_s.set_alpha(alpha)
        surface.blit(title_s, (panel_x + 16, panel_y + 30))

        page_s = S_.render(t("manual.page_label", n=self._info_page + 1, total=self._INFO_PAGES), True, DIMMER)
        page_s.set_alpha(alpha)
        surface.blit(page_s, (panel_x + panel_w - page_s.get_width() - 16, panel_y + 30))

        # Separator line under header
        sep1_y = panel_y + 56
        pygame.draw.line(surface, (52, 40, 68), (panel_x + 10, sep1_y), (panel_x + panel_w - 10, sep1_y), 1)

        # ── Content ──────────────────────────────────────────────────────────
        lines = loc_get(f"manual.section_{self._info_page}") or []
        y = sep1_y + 10
        for line in lines:
            if not line:
                y += 8
                continue
            is_header = (line == line.upper() and 2 <= len(line) <= 32)
            if is_header:
                surf = H.render(line, True, GOLD)
                surf.set_alpha(alpha)
                surface.blit(surf, (panel_x + 18, y))
                y += surf.get_height() + 5
            else:
                surf = S_.render(line, True, TEXT)
                surf.set_alpha(alpha)
                surface.blit(surf, (panel_x + 26, y))
                y += surf.get_height() + 3

        # ── Footer ────────────────────────────────────────────────────────────
        foot_y = panel_y + panel_h - 34
        pygame.draw.line(surface, (44, 34, 58), (panel_x + 10, foot_y - 8), (panel_x + panel_w - 10, foot_y - 8), 1)

        # Page dot indicators
        dot_w    = 14
        dot_total = self._INFO_PAGES * dot_w - 2
        dot_x0   = panel_x + (panel_w - dot_total) // 2
        for i in range(self._INFO_PAGES):
            col = (*TEAL, alpha) if i == self._info_page else (*DIMMER, min(alpha, 160))
            ds  = pygame.Surface((dot_w - 2, 4), pygame.SRCALPHA)
            ds.fill(col)
            surface.blit(ds, (dot_x0 + i * dot_w, foot_y - 16))

        hint_s = S_.render(t("manual.nav_hint"), True, DIM)
        hint_s.set_alpha(alpha)
        surface.blit(hint_s, (panel_x + (panel_w - hint_s.get_width()) // 2, foot_y))

    # ------------------------------------------------------------------ win

    def _draw_win(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks() / 1000.0

        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 32, 18, 172))
        surface.blit(overlay, (0, 0))

        pulse = 0.82 + 0.18 * math.sin(now * 2.4)
        col = (
            int(_clamp(130 * pulse, 0, 255)),
            int(_clamp(255 * pulse, 0, 255)),
            int(_clamp(155 * pulse, 0, 255)),
        )
        title = self._title_font.render(t("menu.win_title"), True, col)
        hint  = self._body_font.render(t("menu.win_hint"),  True, (195, 218, 200))
        cx, cy = S.SCREEN_WIDTH // 2, S.SCREEN_HEIGHT // 2
        surface.blit(title, title.get_rect(center=(cx, cy - 24)))
        surface.blit(hint,  hint.get_rect(center=(cx, cy + 32)))

    # -------------------------------------------------------- evacuation win

    def _draw_evacuation_win(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks() / 1000.0

        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((2, 22, 10, 185))
        surface.blit(overlay, (0, 0))

        cx, cy = S.SCREEN_WIDTH // 2, S.SCREEN_HEIGHT // 2

        # Title pulse
        pulse = 0.82 + 0.18 * math.sin(now * 1.8)
        col = (
            int(_clamp(60  * pulse, 0, 255)),
            int(_clamp(255 * pulse, 0, 255)),
            int(_clamp(130 * pulse, 0, 255)),
        )
        title = self._title_font.render("EVACUATION COMPLETE", True, col)
        surface.blit(title, title.get_rect(center=(cx, cy - 56)))

        # Subtitle lines
        lines = [
            ("You made it off Mars.", (195, 230, 205)),
            ("The signal reached home.", (165, 210, 185)),
            ("", (0, 0, 0)),
            ("Press SPACE to return to menu.", (155, 180, 165)),
        ]
        y = cy
        for text, color in lines:
            if not text:
                y += 12
                continue
            surf = self._body_font.render(text, True, color)
            surface.blit(surf, surf.get_rect(center=(cx, y)))
            y += surf.get_height() + 8

    # ----------------------------------------------------------------- game over

    def _draw_game_over(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks() / 1000.0

        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((38, 8, 8, 165))
        surface.blit(overlay, (0, 0))

        pulse = 0.80 + 0.20 * math.sin(now * 3.0)
        col = (
            int(_clamp(255 * pulse, 0, 255)),
            int(_clamp(75 * pulse, 0, 255)),
            int(_clamp(75 * pulse, 0, 255)),
        )
        cx, cy = S.SCREEN_WIDTH // 2, S.SCREEN_HEIGHT // 2

        title = self._title_font.render(t("menu.over_title"), True, col)
        surface.blit(title, title.get_rect(center=(cx, cy - 38)))

        if self._death_message:
            msg = self._body_font.render(self._death_message, True, (188, 120, 120))
            surface.blit(msg, msg.get_rect(center=(cx, cy + 8)))

        hint = self._small_font.render(t("menu.over_hint"), True, (168, 130, 130))
        surface.blit(hint, hint.get_rect(center=(cx, cy + 44)))
