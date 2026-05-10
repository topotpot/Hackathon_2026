
import math

import pygame

from core import settings as S
from utils.helpers import clamp


def _smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class EndgameUI:
    """Endgame overlay widgets: phase/level banners, countdown timer, beacon prompt, cinematic sequence."""

    def __init__(self) -> None:
        self._big_font    = pygame.font.SysFont("segoeui", 46, bold=True)
        self._mid_font    = pygame.font.SysFont("segoeui", 26, bold=True)
        self._body_font   = pygame.font.SysFont("segoeui", 20)
        self._small_font  = pygame.font.SysFont("segoeui", 17)
        self._mono_font   = pygame.font.SysFont("consolas", 40, bold=True)

        self._phase_text  = ""
        self._phase_t     = 0.0     # seconds left for phase notification
        self._level_text  = ""
        self._level_t     = 0.0

    # ── update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        self._phase_t = max(0.0, self._phase_t - dt)
        self._level_t = max(0.0, self._level_t - dt)

    def notify_phase(self, phase: int) -> None:
        labels = {
            1: "PHASE 1 — SURVIVAL",
            2: "BASE PARTIALLY RESTORED — PHASE 2: RECOVERY",
            3: "EVACUATION SYSTEMS ONLINE — PHASE 3",
        }
        self._phase_text = labels.get(phase, "")
        self._phase_t    = 6.0

    def notify_level(self, level: int) -> None:
        labels = {
            1: "BASE LEVEL 1 — PARTIAL RESTORATION",
            2: "BASE LEVEL 2 — ACTIVE STATION",
            3: "BASE LEVEL 3 — EVACUATION READY",
        }
        self._level_text = labels.get(level, "")
        self._level_t    = 5.0

    # ── permanent prompts ─────────────────────────────────────────────────────

    def draw_beacon_prompt(self, surface: pygame.Surface, time_s: float) -> None:
        """'PRESS E: ACTIVATE EVACUATION BEACON' — shown near the final beacon."""
        pulse = 0.60 + 0.40 * abs(math.sin(time_s * 4.0))
        col   = (int(80 * pulse), int(245 * pulse), int(130 * pulse))
        text  = "PRESS E — ACTIVATE EVACUATION BEACON"
        surf  = self._mid_font.render(text, True, col)
        surf.set_alpha(int(220 * pulse))
        x = (S.SCREEN_WIDTH - surf.get_width()) // 2
        y = S.SCREEN_HEIGHT - 60
        pill_w, pill_h = surf.get_width() + 24, surf.get_height() + 12
        pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill.fill((0, 0, 0, int(155 * pulse)))
        surface.blit(pill, (x - 12, y - 6))
        surface.blit(surf, (x, y))

    def draw_return_prompt(self, surface: pygame.Surface, time_s: float) -> None:
        """'RETURN TO BASE' — shown once countdown is running."""
        pulse = 0.55 + 0.45 * abs(math.sin(time_s * 5.5))
        col   = (int(255 * pulse), int(180 * pulse), int(60 * pulse))
        text  = "RETURN TO BASE — SHUTTLE INBOUND"
        surf  = self._mid_font.render(text, True, col)
        surf.set_alpha(int(230 * pulse))
        x = (S.SCREEN_WIDTH - surf.get_width()) // 2
        y = S.SCREEN_HEIGHT - 96
        pill_w, pill_h = surf.get_width() + 24, surf.get_height() + 12
        pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill.fill((0, 0, 0, int(160 * pulse)))
        surface.blit(pill, (x - 12, y - 6))
        surface.blit(surf, (x, y))

    # ── countdown display ─────────────────────────────────────────────────────

    def draw_countdown(
        self,
        surface: pygame.Surface,
        remaining: float,
        time_s: float,
    ) -> None:
        """Large top-centre countdown timer (MM:SS)."""
        mins  = int(remaining) // 60
        secs  = int(remaining) % 60
        label = f"{mins:01d}:{secs:02d}"

        urgent = remaining < 60.0
        pulse  = 0.72 + 0.28 * abs(math.sin(time_s * (5.0 if urgent else 2.5)))
        if urgent:
            col = (int(255 * pulse), int(55 * pulse), int(55 * pulse))
        else:
            col = (int(80 * pulse), int(210 * pulse), int(130 * pulse))

        # Background panel
        panel_w, panel_h = 180, 60
        panel_x = (S.SCREEN_WIDTH - panel_w) // 2
        panel_y = 12
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, int(175 * pulse)))
        pygame.draw.rect(panel, (*col, int(90 * pulse)), panel.get_rect(), 2, border_radius=8)
        surface.blit(panel, (panel_x, panel_y))

        # Timer digits
        timer_surf = self._mono_font.render(label, True, col)
        timer_surf.set_alpha(int(250 * pulse))
        surface.blit(
            timer_surf,
            (panel_x + (panel_w - timer_surf.get_width()) // 2,
             panel_y + (panel_h - timer_surf.get_height()) // 2),
        )

        # "EVACUATION" label above
        sub_surf = self._small_font.render("EVACUATION", True, col)
        sub_surf.set_alpha(int(190 * pulse))
        surface.blit(sub_surf, (panel_x + (panel_w - sub_surf.get_width()) // 2, panel_y - 18))

    # ── phase / level notifications ───────────────────────────────────────────

    def draw_notifications(self, surface: pygame.Surface) -> None:
        """Phase/level change banners — fade in/out over their timers."""
        cx = S.SCREEN_WIDTH // 2
        y_base = S.SCREEN_HEIGHT // 2 - 60

        for text, remaining, duration in (
            (self._phase_text, self._phase_t, 6.0),
            (self._level_text, self._level_t, 5.0),
        ):
            if not text or remaining <= 0.0:
                continue
            alpha_frac = _smoothstep(min(1.0, remaining / 0.6)) * _smoothstep(min(1.0, remaining / 0.8))
            a = int(255 * alpha_frac)

            panel_w, panel_h = 560, 48
            px = cx - panel_w // 2
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((4, 18, 8, int(210 * alpha_frac)))
            pygame.draw.rect(panel, (60, 220, 120, int(80 * alpha_frac)),
                             panel.get_rect(), 2, border_radius=6)
            surface.blit(panel, (px, y_base))

            surf = self._mid_font.render(text, True, (90, 240, 140))
            surf.set_alpha(a)
            surface.blit(surf, (cx - surf.get_width() // 2, y_base + (panel_h - surf.get_height()) // 2))
            y_base += 56

    # ── shuttle landing cinematic ─────────────────────────────────────────────

    def draw_cinematic(
        self,
        surface: pygame.Surface,
        progress: float,
        time_s: float,
    ) -> None:
        """
        Full-screen cinematic overlay.  progress = 0.0 → 1.0 over CINEMATIC_DURATION.

        Phases:
          0.00–0.20  beacon flash + text "EVACUATION BEACON ACTIVATED"
          0.20–0.58  shuttle descends; thruster glow; atmospheric rumble
          0.58–0.80  dark overlay; farewell text messages
          0.80–1.00  fade to black
        """
        w, h = S.SCREEN_WIDTH, S.SCREEN_HEIGHT
        cx   = w // 2

        # ── Phase A: beacon flash ─────────────────────────────────────────────
        if progress < 0.20:
            frac  = progress / 0.20
            flash_a = int(80 * _smoothstep(frac) * (1.0 + 0.3 * math.sin(time_s * 18.0)))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((40, 255, 100, flash_a))
            surface.blit(flash, (0, 0))

            text_a = int(255 * _smoothstep(min(1.0, frac / 0.5)))
            msg = self._big_font.render("EVACUATION BEACON ACTIVATED", True, (80, 255, 140))
            msg.set_alpha(text_a)
            surface.blit(msg, msg.get_rect(center=(cx, h // 2)))

        # ── Phase B: shuttle descent ──────────────────────────────────────────
        if 0.15 <= progress <= 0.75:
            ph = clamp((progress - 0.15) / 0.60, 0.0, 1.0)
            self._draw_shuttle(surface, ph, time_s, cx, h)

            # Thruster heat wash
            glow_a = int(60 + 40 * math.sin(time_s * 14.0))
            glow_y = int(h * 0.30 + ph * h * 0.50) + 24
            glow = pygame.Surface((120, 40), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 200, 80, glow_a), glow.get_rect())
            surface.blit(glow, (cx - 60, glow_y), special_flags=pygame.BLEND_ADD)

        # ── Phase C: farewell text ────────────────────────────────────────────
        if 0.58 <= progress <= 0.95:
            ph = clamp((progress - 0.58) / 0.37, 0.0, 1.0)
            dark_a = int(200 * _smoothstep(ph))
            dark = pygame.Surface((w, h), pygame.SRCALPHA)
            dark.fill((0, 0, 0, dark_a))
            surface.blit(dark, (0, 0))

            messages = [
                "Rover systems powered down.",
                "Lifting off from the surface.",
                "Mars grows smaller in the window.",
                "Farewell.",
            ]
            for i, line in enumerate(messages):
                show_at = i / len(messages)
                if ph < show_at:
                    break
                word_ph = clamp((ph - show_at) / (1.0 / len(messages)), 0.0, 1.0)
                fade    = _smoothstep(word_ph) if word_ph < 0.8 else _smoothstep((1.0 - word_ph) / 0.2)
                surf    = self._body_font.render(line, True, (190, 220, 200))
                surf.set_alpha(int(220 * fade))
                surface.blit(surf, surf.get_rect(center=(cx, h // 2 - 40 + i * 32)))

        # ── Phase D: fade to black ────────────────────────────────────────────
        if progress >= 0.80:
            fade_ph = clamp((progress - 0.80) / 0.20, 0.0, 1.0)
            black_a = int(255 * _smoothstep(fade_ph))
            black = pygame.Surface((w, h), pygame.SRCALPHA)
            black.fill((0, 0, 0, black_a))
            surface.blit(black, (0, 0))

    def _draw_shuttle(
        self,
        surface: pygame.Surface,
        descent_t: float,
        time_s: float,
        cx: int,
        h: int,
    ) -> None:
        """Simple shuttle silhouette descending from top of screen."""
        sy = int(h * 0.20 + _smoothstep(descent_t) * h * 0.45)
        rumble_x = int(1.5 * math.sin(time_s * 22.0)) if descent_t > 0.2 else 0
        bx = cx + rumble_x

        # Hull — elongated hexagon
        hull_pts = [
            (bx,       sy - 28),   # nose
            (bx + 18,  sy - 12),
            (bx + 22,  sy + 18),
            (bx + 14,  sy + 30),
            (bx - 14,  sy + 30),
            (bx - 22,  sy + 18),
            (bx - 18,  sy - 12),
        ]
        pygame.draw.polygon(surface, (60, 72, 80), hull_pts)
        pygame.draw.polygon(surface, (90, 110, 120), hull_pts, 2)

        # Cockpit window
        pygame.draw.ellipse(surface, (80, 160, 200),
                            pygame.Rect(bx - 7, sy - 18, 14, 10))
        pygame.draw.ellipse(surface, (140, 210, 255, 120),
                            pygame.Rect(bx - 5, sy - 16, 10, 7))

        # Wing stubs
        for sign in (-1, 1):
            wing_pts = [
                (bx + sign * 22, sy + 4),
                (bx + sign * 38, sy + 16),
                (bx + sign * 32, sy + 26),
                (bx + sign * 22, sy + 20),
            ]
            pygame.draw.polygon(surface, (50, 62, 68), wing_pts)
            pygame.draw.polygon(surface, (80, 100, 110), wing_pts, 1)

        # Engine nozzles — 3
        for i, ex in enumerate((bx - 10, bx, bx + 10)):
            pygame.draw.rect(surface, (40, 44, 50),
                             pygame.Rect(ex - 4, sy + 28, 8, 7))
            # Thruster glow
            flicker = 0.7 + 0.3 * math.sin(time_s * 28.0 + i * 2.1)
            ga = int(180 * flicker)
            g_surf = pygame.Surface((14, 18), pygame.SRCALPHA)
            pygame.draw.ellipse(g_surf, (255, 180, 60, ga), g_surf.get_rect())
            surface.blit(g_surf, (ex - 7, sy + 34), special_flags=pygame.BLEND_ADD)

        # Navigation lights
        nav_blink = abs(math.sin(time_s * 4.8))
        if nav_blink > 0.6:
            pygame.draw.circle(surface, (255, 80, 80),   (bx - 22, sy + 10), 2)
            pygame.draw.circle(surface, (80, 180, 255),  (bx + 22, sy + 10), 2)
