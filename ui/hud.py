
import math

import pygame

from core import settings as S
from systems.localization import get as loc_get, t
from utils.helpers import clamp

_RES_ORDER  = ("salvage", "data", "relay", "ancient")
_RES_COLORS = {
    "salvage": (180, 140,  80),
    "data":    ( 80, 180, 255),
    "relay":   (140, 220, 160),
    "ancient": (220, 140, 255),
}
_RES_LABEL_KEYS = {
    "salvage": "hud.res_sal",
    "data":    "hud.res_dat",
    "relay":   "hud.res_rel",
    "ancient": "hud.res_tch",
}


def _lerp_color(
    a: tuple[int, int, int], b: tuple[int, int, int], frac: float
) -> tuple[int, int, int]:
    frac = clamp(frac, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * frac),
        int(a[1] + (b[1] - a[1]) * frac),
        int(a[2] + (b[2] - a[2]) * frac),
    )


def _energy_color(p: float) -> tuple[int, int, int]:
    if p > 0.55:
        return _lerp_color((90, 200, 120), (230, 210, 80), (1.0 - p) / 0.45)
    return _lerp_color((230, 210, 80), (220, 60, 70), (0.55 - p) / 0.55)


def _signal_color(p: float) -> tuple[int, int, int]:
    if p > 0.5:
        return _lerp_color((80, 150, 240), (160, 110, 220), (1.0 - p) / 0.5)
    return _lerp_color((160, 110, 220), (210, 50, 70), (0.5 - p) / 0.5)


class HUD:
    """HUD: lerped energy/signal bars, resource counters, stacked warnings, status messages."""

    def __init__(self) -> None:
        self._font       = pygame.font.SysFont("segoeui", 18)
        self._small_font = pygame.font.SysFont("segoeui", 13)
        self._warn_font  = pygame.font.SysFont("segoeui", 19, bold=True)
        self._prompt_font = pygame.font.SysFont("segoeui", 17, bold=True)
        self._disp_e = 100.0
        self._disp_s = 100.0

    def update(self, dt: float, energy: float, signal: float) -> None:
        k = min(1.0, S.HUD_LERP_SPEED * dt)
        self._disp_e += (energy - self._disp_e) * k
        self._disp_s += (signal - self._disp_s) * k

    def draw(
        self,
        surface: pygame.Surface,
        energy: float,
        signal: float,
        station_resources: dict,
        biome_name: str = "",
        storm_state: str = "idle",
        signal_connected: bool = False,
        connect_key: str = "",
        status_message: str = "",
        status_color: tuple = (255, 255, 255),
    ) -> None:
        connect_prompt = t(connect_key) if connect_key else ""

        pad    = 8
        bar_w  = 200
        bar_h  = 16
        x0     = pad
        y0     = pad

        y_e_label = y0 + 4
        y_e_bar   = y0 + 24
        y_s_label = y_e_bar + bar_h + 8
        y_s_bar   = y_s_label + 20
        y_sep     = y_s_bar + bar_h + 8
        y_res     = y_sep + 8
        y_biome   = y_res + 48   # 2 rows × 22px + 4px gap
        y_conn    = y_biome + 20
        panel_h   = y_conn + 22 - y0 + 4

        bg = pygame.Rect(x0, y0, bar_w + 6, panel_h)
        sh = pygame.Surface(bg.size, pygame.SRCALPHA)
        sh.fill((0, 0, 0, 90))
        surface.blit(sh, (bg.x + 3, bg.y + 4))
        pygame.draw.rect(surface, S.COLOR_HUD_BG, bg, border_radius=6)
        pygame.draw.rect(surface, (18, 16, 24), bg, 1, border_radius=6)

        def _ts(txt: str, pos: tuple, color: tuple) -> None:
            s0 = self._font.render(txt, True, (10, 10, 16))
            surface.blit(s0, (pos[0] + 1, pos[1] + 2))
            surface.blit(self._font.render(txt, True, color), pos)

        _ts(t("hud.energy"), (x0 + 6, y_e_label), S.COLOR_TEXT)
        e_rect = pygame.Rect(x0 + 6, y_e_bar, bar_w, bar_h)
        pygame.draw.rect(surface, (28, 28, 32), e_rect, border_radius=3)
        pygame.draw.rect(surface, (10, 10, 14), e_rect, 1, border_radius=3)
        ep = clamp(self._disp_e / 100.0, 0.0, 1.0)
        if ep > 0:
            pygame.draw.rect(
                surface, _energy_color(ep),
                pygame.Rect(e_rect.x, e_rect.y, max(2, int(bar_w * ep)), bar_h),
                border_radius=3,
            )

        _ts(t("hud.signal"), (x0 + 6, y_s_label), S.COLOR_TEXT)
        s_rect = pygame.Rect(x0 + 6, y_s_bar, bar_w, bar_h)
        pygame.draw.rect(surface, (28, 28, 32), s_rect, border_radius=3)
        pygame.draw.rect(surface, (10, 10, 14), s_rect, 1, border_radius=3)
        sp = clamp(self._disp_s / 100.0, 0.0, 1.0)
        if sp > 0:
            pygame.draw.rect(
                surface, _signal_color(sp),
                pygame.Rect(s_rect.x, s_rect.y, max(2, int(bar_w * sp)), bar_h),
                border_radius=3,
            )

        pygame.draw.line(
            surface, (38, 32, 48),
            (x0 + 6, y_sep), (x0 + bar_w, y_sep), 1,
        )

        col_w = bar_w // 2   # 100 px per column
        for idx, key in enumerate(_RES_ORDER):
            row = idx // 2
            col = idx % 2
            xr  = x0 + 6 + col * col_w
            yr  = y_res + row * 22
            val = station_resources.get(key, 0)
            col_c = _RES_COLORS[key]
            lbl   = t(_RES_LABEL_KEYS[key])

            dot_s = self._small_font.render("■", True, col_c)
            surface.blit(dot_s, (xr, yr + 3))

            lbl_s = self._small_font.render(lbl, True, (105, 96, 120))
            surface.blit(lbl_s, (xr + dot_s.get_width() + 3, yr + 3))

            val_s = self._font.render(str(val), True, col_c)
            surface.blit(val_s, (xr + col_w - val_s.get_width() - 6, yr))

        if biome_name:
            bm_s = self._small_font.render(biome_name, True, (115, 106, 130))
            surface.blit(bm_s, (x0 + 6, y_biome + 2))

        if signal_connected:
            _tick = pygame.time.get_ticks() / 1000.0
            pulse = 0.72 + 0.28 * abs(math.sin(_tick * 5.2))
            conn_col = (int(80 * pulse), int(220 * pulse), int(140 * pulse))
            _ts(t("hud.connected"), (x0 + 6, y_conn), conn_col)

        self._draw_bottom_notifications(
            surface, storm_state, energy, signal,
            connect_key, connect_prompt, status_message, status_color,
        )

    def _draw_bottom_notifications(
        self,
        surface: pygame.Surface,
        storm_state: str,
        energy: float,
        signal: float,
        connect_key: str,
        connect_prompt: str,
        status_message: str,
        status_color: tuple,
    ) -> None:
        now = pygame.time.get_ticks() / 1000.0

        if connect_prompt:
            prompt_col = self._prompt_color_for_key(connect_key)
            pulse = 0.62 + 0.38 * abs(math.sin(now * 3.8))
            self._draw_pill_text(
                surface, connect_prompt, self._prompt_font,
                prompt_col, pulse, S.SCREEN_HEIGHT - 26,
            )

        if status_message:
            s_pulse = 0.72 + 0.28 * abs(math.sin(now * 6.0))
            base_y = S.SCREEN_HEIGHT - 56 if connect_prompt else S.SCREEN_HEIGHT - 26
            self._draw_pill_text(
                surface, status_message, self._warn_font,
                status_color, s_pulse, base_y,
            )

        warns: list[tuple[str, tuple[int, int, int]]] = []
        if storm_state == "buildup":
            warns.append((t("warnings.storm_approaching"), (255, 190, 70)))
        if energy < S.WARN_ENERGY_LOW:
            warns.append((t("warnings.low_energy"), (255, 80, 70)))
        if signal < S.WARN_SIGNAL_LOW:
            warns.append((t("warnings.signal_unstable"), (190, 110, 255)))

        if warns:
            warn_pulse = 0.55 + 0.45 * abs(math.sin(now * 4.5))
            offset_count = (1 if connect_prompt else 0) + (1 if status_message else 0)
            warn_base_y = S.SCREEN_HEIGHT - S.NOTIFICATION_BOTTOM_OFFSET - offset_count * 30
            for i, (text, color) in enumerate(reversed(warns)):
                self._draw_pill_text(
                    surface, text, self._warn_font,
                    color, warn_pulse, warn_base_y - i * 30,
                )

    @staticmethod
    def _prompt_color_for_key(key: str) -> tuple[int, int, int]:
        prompt_types = loc_get("prompt_types") or {}
        ptype = prompt_types.get(key, "connect")
        if ptype == "unstable":
            return (255, 168, 55)
        if ptype == "press":
            return (210, 235, 255)
        return (100, 200, 255)

    def _draw_pill_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple,
        alpha_frac: float,
        y: int,
    ) -> None:
        surf = font.render(text, True, color)
        surf.set_alpha(int(255 * clamp(alpha_frac, 0.0, 1.0)))
        x = (S.SCREEN_WIDTH - surf.get_width()) // 2
        pill_w = surf.get_width() + 20
        pill_h = surf.get_height() + 10
        pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill.fill((0, 0, 0, int(145 * alpha_frac)))
        surface.blit(pill, (x - 10, y - 5))
        surface.blit(surf, (x, y))
