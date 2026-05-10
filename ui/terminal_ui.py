
import math
import random

import pygame

from core import settings as S
from systems.localization import LANGUAGES, LANG_LABELS, get as loc_get, t
from systems.terminal_system import SECTIONS, TerminalSystem
from utils.helpers import clamp

_COL_BG          = (4,  9,  5)
_COL_PANEL       = (6, 12,  7, 230)
_COL_TEXT        = (130, 210, 130)
_COL_DIM         = (45,  80,  45)
_COL_ACCENT      = (80, 200, 255)
_COL_AMBER       = (210, 160,  50)
_COL_RED         = (210,  65,  55)
_COL_SEP         = (22,  42,  22)
_COL_SEL_BG      = (12,  30,  14, 180)
_COL_LOCKED      = (30,  52,  30)
_COL_LOCKED_TXT  = (50,  80,  50)
_COL_NEW_DOT     = (80, 200, 130)

_RED_BRACKET_WORDS = frozenset([
    "CORRUPTED", "FAILED", "REDACTED",
    "ПОШКОДЖЕНО", "ПОШКОДЖЕНА", "ЗАСЕКРЕЧЕНО",
])


_BOOT_LINES_FALLBACK = [
    "MARS RELAY STATION — UNIT 07",
    "EMERGENCY OPERATIONS TERMINAL",
    "",
    "LOADING ARCHIVE DATABASE...",
    "CHECKING FILE INTEGRITY...",
    "RESTORING PARTIAL RECORDS...",
    "",
    "ACCESS GRANTED",
]


def _alpha_surf(w: int, h: int, color: tuple) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(color)
    return s


class TerminalUI:


    def __init__(self) -> None:
        self._section_idx = 0
        self._entry_idx   = 0
        self._list_scroll = 0
        self._max_list    = 8
        self._content_scroll = 0

        self._boot_t = 1.6
        self._scan_offset = 0.0
        self._glitch_t = 0.0
        self._cursor_blink = 0.0

        self._font_head  = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_body  = pygame.font.SysFont("consolas", 12)
        self._font_small = pygame.font.SysFont("consolas", 11)

    
        self._scanline = self._build_scanlines(S.SCREEN_WIDTH, S.SCREEN_HEIGHT)


    def open(self) -> None:
        self._boot_t = 1.6
        self._entry_idx = 0
        self._list_scroll = 0
        self._content_scroll = 0

    @property
    def current_section(self) -> str:
        return SECTIONS[self._section_idx]

    def update(self, dt: float) -> None:
        if self._boot_t > 0.0:
            self._boot_t = max(0.0, self._boot_t - dt)
        self._scan_offset = (self._scan_offset + dt * 28.0) % 6.0
        self._cursor_blink = (self._cursor_blink + dt * 2.6) % 1.0
        if self._glitch_t > 0.0:
            self._glitch_t = max(0.0, self._glitch_t - dt)
        elif random.random() < 0.007:
            self._glitch_t = random.uniform(0.04, 0.14)


    def nav_up(self) -> None:
        self._entry_idx = max(0, self._entry_idx - 1)
        self._clamp_list_scroll()
        self._content_scroll = 0

    def nav_down(self, max_entries: int) -> None:
        if max_entries > 0:
            self._entry_idx = min(max_entries - 1, self._entry_idx + 1)
        self._clamp_list_scroll()
        self._content_scroll = 0

    def scroll_content_up(self) -> None:
        self._content_scroll = max(0, self._content_scroll - 1)

    def scroll_content_down(self) -> None:
        self._content_scroll += 1

    def prev_section(self) -> None:
        self._section_idx = (self._section_idx - 1) % len(SECTIONS)
        self._entry_idx = 0
        self._list_scroll = 0
        self._content_scroll = 0

    def next_section(self) -> None:
        self._section_idx = (self._section_idx + 1) % len(SECTIONS)
        self._entry_idx = 0
        self._list_scroll = 0
        self._content_scroll = 0

    def _clamp_list_scroll(self) -> None:
        if self._entry_idx < self._list_scroll:
            self._list_scroll = self._entry_idx
        elif self._entry_idx >= self._list_scroll + self._max_list:
            self._list_scroll = self._entry_idx - self._max_list + 1


    def draw(
        self,
        surface: pygame.Surface,
        terminal: TerminalSystem,
        gs: dict,
        time_s: float,
    ) -> None:
        W, H = S.SCREEN_WIDTH, S.SCREEN_HEIGHT

        ov = _alpha_surf(W, H, (2, 5, 2, 235))
        surface.blit(ov, (0, 0))

        if self._boot_t > 0.0:
            self._draw_boot(surface, time_s)
            surface.blit(self._scanline, (0, 0))
            return


        panel = _alpha_surf(W - 40, H - 32, _COL_PANEL)
        surface.blit(panel, (20, 16))

        self._draw_header(surface, time_s)
        self._draw_section_tabs(surface)
        self._draw_content(surface, terminal, gs, time_s)
        self._draw_footer(surface)

        surface.blit(self._scanline, (0, 0))

        if self._glitch_t > 0.0:
            self._draw_glitch(surface)



    def _draw_header(self, surface: pygame.Surface, time_s: float) -> None:
        flicker = 0.88 + 0.12 * abs(math.sin(time_s * 7.3))
        col = tuple(int(c * flicker) for c in _COL_ACCENT)
        title = self._font_head.render(t("terminal_ui.header"), True, col)
        surface.blit(title, (28, 22))

        sub = self._font_small.render(t("terminal_ui.subheader"), True, _COL_DIM)
        surface.blit(sub, (28, 38))
        pygame.draw.line(surface, _COL_SEP, (28, 52), (S.SCREEN_WIDTH - 28, 52), 1)

    def _draw_section_tabs(self, surface: pygame.Surface) -> None:
        tab_y = 56
        tab_w = (S.SCREEN_WIDTH - 56) // len(SECTIONS)
        for i, sec in enumerate(SECTIONS):
            selected = (i == self._section_idx)
            tx = 28 + i * tab_w
            label = t(f"sections.{sec}")
            if selected:
                bg = _alpha_surf(tab_w - 2, 24, (12, 30, 12, 200))
                surface.blit(bg, (tx + 1, tab_y - 1))
                col = _COL_ACCENT
            else:
                col = _COL_DIM
            ts = self._font_small.render(label, True, col)
            surface.blit(ts, (tx + (tab_w - ts.get_width()) // 2, tab_y + 3))
        pygame.draw.line(surface, _COL_SEP, (28, tab_y + 26), (S.SCREEN_WIDTH - 28, tab_y + 26), 1)

    def _draw_content(
        self,
        surface: pygame.Surface,
        terminal: TerminalSystem,
        gs: dict,
        time_s: float,
    ) -> None:
        section = SECTIONS[self._section_idx]
        entries = terminal.get_all_for_section(section, gs)

        content_top = 88
        list_x, list_w = 28, 178
        div_x = list_x + list_w + 4
        detail_x = div_x + 6
        detail_w = S.SCREEN_WIDTH - detail_x - 28


        pygame.draw.line(
            surface, _COL_SEP,
            (div_x, content_top), (div_x, S.SCREEN_HEIGHT - 32), 1,
        )

        row_h = 20
        visible = entries[self._list_scroll: self._list_scroll + self._max_list]
        for vi, e in enumerate(visible):
            real_idx = self._list_scroll + vi
            selected = (real_idx == self._entry_idx)
            ey = content_top + vi * row_h
            locked = terminal.is_locked(e, gs)
            is_new = not terminal.is_read(e["id"])

            if selected:
                bg = _alpha_surf(list_w, row_h - 2, _COL_SEL_BG)
                surface.blit(bg, (list_x, ey))

            if locked:
                title_col = _COL_LOCKED_TXT
                title_text = "[LOCKED]"
            else:
                title_col = _COL_TEXT if not selected else _COL_ACCENT
                title_text = e["title"]


            max_chars = list_w // 7
            if len(title_text) > max_chars:
                title_text = title_text[: max_chars - 1] + "…"

            ts = self._font_small.render(title_text, True, title_col)
            surface.blit(ts, (list_x + 6, ey + 4))

            if is_new and not locked:
                pygame.draw.circle(surface, _COL_NEW_DOT, (list_x + 2, ey + row_h // 2), 2)

        if len(entries) > self._max_list:
            hint = self._font_small.render(
                f"{self._entry_idx + 1}/{len(entries)}",
                True, _COL_DIM,
            )
            surface.blit(hint, (list_x, content_top + self._max_list * row_h + 2))


        if not entries:
            no_s = self._font_small.render(t("terminal_ui.no_entries"), True, _COL_DIM)
            surface.blit(no_s, (detail_x, content_top))
            return

        entry = entries[min(self._entry_idx, len(entries) - 1)]
        locked = terminal.is_locked(entry, gs)

        if not locked:
            terminal.mark_read(entry["id"])


        fc = self._font_small.render(
            f"FILE: {entry.get('file_code', entry['id'])}", True, _COL_DIM
        )
        surface.blit(fc, (detail_x, content_top))

        pygame.draw.line(
            surface, _COL_SEP,
            (detail_x, content_top + 14),
            (detail_x + detail_w, content_top + 14), 1,
        )

        if locked:
            self._draw_locked_entry(surface, detail_x, detail_w, content_top + 20, entry, gs)
        elif entry.get("_settings"):
            self._draw_settings_content(surface, detail_x, detail_w, content_top + 20)
        else:
            self._draw_entry_content(surface, detail_x, detail_w, content_top + 20, entry, time_s)

    def _draw_entry_content(
        self,
        surface: pygame.Surface,
        dx: int, dw: int, dy: int,
        entry: dict,
        time_s: float,
    ) -> None:
        lines = entry.get("lines", [])
        line_h = 15
        max_visible = (S.SCREEN_HEIGHT - dy - 36) // line_h

        self._content_scroll = clamp(
            self._content_scroll, 0, max(0, len(lines) - max_visible)
        )
        visible_lines = lines[self._content_scroll: self._content_scroll + max_visible]

        for i, line in enumerate(visible_lines):
            ly = dy + i * line_h
            if not line:
                continue
            col = self._line_color(line)

            if line.isupper() and random.random() < 0.003:
                col = tuple(max(0, c - 30) for c in col)
            ls = self._font_body.render(line, True, col)
            surface.blit(ls, (dx, ly))


        if len(lines) > max_visible:
            pct = int(self._content_scroll / max(1, len(lines) - max_visible) * 100)
            si = self._font_small.render(
                t("terminal_ui.scroll_hint", pct=pct), True, _COL_DIM
            )
            surface.blit(si, (dx, S.SCREEN_HEIGHT - 46))


        if self._cursor_blink < 0.5 and self._content_scroll >= max(0, len(lines) - max_visible):
            cy = dy + min(len(visible_lines), max_visible) * line_h
            cs = self._font_body.render("_", True, _COL_TEXT)
            surface.blit(cs, (dx, cy))

    def _draw_locked_entry(
        self,
        surface: pygame.Surface,
        dx: int, dw: int, dy: int,
        entry: dict,
        gs: dict,
    ) -> None:
        lines: list[str] = [
            "",
            t("terminal_ui.access_restricted"),
            "",
            t("terminal_ui.file_unavailable"),
            t("terminal_ui.recovery_requires"),
        ]
        u = entry.get("unlock", {})
        if isinstance(u, dict):
            if "biome" in u:
                lines.append(f"  — {t('terminal_ui.explore_biome', biome=u['biome'])}")
            if "storms" in u:
                lines.append(f"  — {t('terminal_ui.survive_storms', n=u['storms'])}")
            if "towers" in u:
                lines.append(f"  — {t('terminal_ui.activate_towers', n=u['towers'])}")
            if "data" in u:
                lines.append(f"  — {t('terminal_ui.recover_data', n=u['data'])}")
            if "level" in u:
                lines.append(f"  — {t('terminal_ui.reach_level', n=u['level'])}")
        lines += ["", t("terminal_ui.continue_expedition")]

        for i, line in enumerate(lines):
            col = _COL_RED if line.strip() == t("terminal_ui.access_restricted") else _COL_LOCKED_TXT
            if line.startswith("  —"):
                col = _COL_AMBER
            ls = self._font_body.render(line, True, col)
            surface.blit(ls, (dx, dy + i * 16))

    def _draw_settings_content(
        self,
        surface: pygame.Surface,
        dx: int, dw: int, dy: int,
    ) -> None:
        from systems.localization import current_lang, lang_label
        cur = current_lang()
        lines: list[tuple[str, tuple]] = [
            (t("settings.header"), _COL_ACCENT),
            ("", _COL_TEXT),
            (f"{t('settings.current_lang')}:  {lang_label(cur)}", _COL_TEXT),
            ("", _COL_TEXT),
            (t("settings.switch_hint"), _COL_AMBER),
            ("", _COL_TEXT),
            (t("settings.available"), _COL_DIM),
        ]
        for lang in LANGUAGES:
            marker = "►" if lang == cur else " "
            lines.append((f"  {marker} [{lang.upper()}] {LANG_LABELS.get(lang, lang.upper())}", _COL_TEXT if lang == cur else _COL_DIM))

        line_h = 18
        for i, (text, col) in enumerate(lines):
            if not text:
                continue
            ls = self._font_body.render(text, True, col)
            surface.blit(ls, (dx, dy + i * line_h))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        foot_y = S.SCREEN_HEIGHT - 28
        pygame.draw.line(
            surface, _COL_SEP,
            (28, foot_y - 4), (S.SCREEN_WIDTH - 28, foot_y - 4), 1,
        )
        hs = self._font_small.render(t("terminal_ui.hints"), True, _COL_DIM)
        surface.blit(hs, ((S.SCREEN_WIDTH - hs.get_width()) // 2, foot_y))

    def _draw_boot(self, surface: pygame.Surface, time_s: float) -> None:
        W, H = S.SCREEN_WIDTH, S.SCREEN_HEIGHT
        total = 1.6
        elapsed = total - self._boot_t
        progress = elapsed / total

        boot_lines = loc_get("terminal_ui.boot_lines") or _BOOT_LINES_FALLBACK

        cx = W // 2
        cy = H // 2 - 60

        show_count = int(progress * (len(boot_lines) + 1))

        for i, line in enumerate(boot_lines[:show_count]):
            if not line:
                continue
            flicker = 0.85 + 0.15 * abs(math.sin(time_s * 12.0 + i * 0.7))
            if i == len(boot_lines) - 1:   
                col = _COL_ACCENT
            elif i == 0:                   
                col = tuple(int(c * flicker) for c in _COL_TEXT)
            else:
                col = _COL_DIM
            ls = self._font_body.render(line, True, col)
            surface.blit(ls, (cx - ls.get_width() // 2, cy + i * 18))


        bar_y = cy + len(boot_lines) * 18 + 12
        bar_w = 220
        bar_filled = int(bar_w * progress)
        pygame.draw.rect(surface, _COL_DIM, (cx - bar_w // 2, bar_y, bar_w, 8), 1)
        if bar_filled > 0:
            pygame.draw.rect(
                surface, _COL_TEXT,
                (cx - bar_w // 2, bar_y, bar_filled, 8),
            )


        if int(time_s * 3.0) % 2 == 0:
            cs = self._font_body.render("_", True, _COL_TEXT)
            surface.blit(cs, (cx - bar_w // 2, bar_y + 14))

    def _draw_glitch(self, surface: pygame.Surface) -> None:
        W, H = S.SCREEN_WIDTH, S.SCREEN_HEIGHT
        n = random.randint(1, 3)
        for _ in range(n):
            gw = random.randint(60, 200)
            gh = random.randint(1, 3)
            gx = random.randint(0, W - gw)
            gy = random.randint(20, H - 20)
            col = random.choice([_COL_TEXT, _COL_ACCENT, _COL_AMBER])
            gs = pygame.Surface((gw, gh), pygame.SRCALPHA)
            gs.fill((*col, random.randint(18, 55)))
            surface.blit(gs, (gx, gy))


    @staticmethod
    def _line_color(line: str) -> tuple:
        if not line:
            return _COL_TEXT
        stripped = line.lstrip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inner = stripped[1:-1]
            if any(kw in inner for kw in _RED_BRACKET_WORDS):
                return _COL_RED
            return _COL_AMBER
        if line.isupper() and len(line) > 3 and not line.startswith(" "):
            return _COL_ACCENT
        if stripped.startswith("—") or stripped.startswith("..."):
            return tuple(int(c * 0.75) for c in _COL_TEXT)
        if stripped.startswith("  ") or stripped.startswith("  "):
            return _COL_AMBER
        return _COL_TEXT

    @staticmethod
    def _build_scanlines(w: int, h: int) -> pygame.Surface:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 3):
            pygame.draw.line(s, (0, 0, 0, 20), (0, y), (w, y))
        return s
