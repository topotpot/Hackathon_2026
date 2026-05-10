
import math
import random

import pygame
from pygame import Vector2

from utils.helpers import clamp


class Landmark:


    CULL_MARGIN = 600

    def __init__(self, position: Vector2, ltype: str, seed: int) -> None:
        self.position = Vector2(position)
        self.ltype = ltype
        self._seed = seed
        self._rng = random.Random(seed)
        self._blink_t = self._rng.uniform(0.0, 4.0)
        self._rot_t = self._rng.uniform(0.0, math.tau)
        self._pulse_t = self._rng.uniform(0.0, 3.0)
        self._surf, self._anchor_y = self._build()



    def update(self, dt: float) -> None:
        self._blink_t += dt
        self._rot_t += dt * 0.38
        self._pulse_t += dt

    def draw(
        self,
        surface: pygame.Surface,
        offset: Vector2,
        cam_dist: float,
        time_s: float,
    ) -> None:
        cx = int(self.position.x + offset.x)
        cy = int(self.position.y + offset.y)
        sw, sh = surface.get_size()
        if not (
            -self.CULL_MARGIN < cx < sw + self.CULL_MARGIN
            and -self.CULL_MARGIN < cy < sh + self.CULL_MARGIN
        ):
            return

        sw2, _ = self._surf.get_size()
        blit_x = cx - sw2 // 2
        blit_y = cy - self._anchor_y


        fog = clamp(1.0 - (cam_dist - 250) / 1800.0, 0.06, 1.0)
        if fog < 0.96:
            self._surf.set_alpha(int(255 * fog))
        else:
            self._surf.set_alpha(255)
        surface.blit(self._surf, (blit_x, blit_y))

        self._draw_animated(surface, cx, cy, int(255 * fog), time_s)

    def _build(self) -> tuple[pygame.Surface, int]:
        dispatch = {
            "mega_relay": self._build_mega_relay,
            "colony_ship": self._build_colony_ship,
            "buried_facility": self._build_buried_facility,
            "satellite_dish": self._build_satellite_dish,
        }
        return dispatch.get(self.ltype, self._build_mega_relay)()

    def _build_mega_relay(self) -> tuple[pygame.Surface, int]:
        W, H = 160, 225
        anchor = 210
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        rng = self._rng
        cx = W // 2


        pygame.draw.ellipse(s, (12, 8, 6, 65), pygame.Rect(cx - 38, anchor - 4, 76, 20))


        leg_pts = [(-42, H - 2), (42, H - 2), (-58, H - 4), (56, H - 4)]
        leg_top_y = anchor - 5
        for lx, ly in leg_pts:
            pygame.draw.line(s, (40, 34, 28), (cx, leg_top_y), (cx + lx, ly), 2)
        for lx, ly in [(-42, H - 2), (42, H - 2)]:
            pygame.draw.line(s, (52, 44, 36), (cx, leg_top_y), (cx + lx, ly), 1)

        mast_top = 14
        for seg in range(8):
            y0 = mast_top + seg * ((anchor - mast_top) // 8)
            y1 = mast_top + (seg + 1) * ((anchor - mast_top) // 8)
            thick = max(2, 9 - seg)
            mid_shade = min(255, 45 + seg * 4)
            pygame.draw.line(s, (mid_shade, mid_shade - 6, mid_shade - 12), (cx, y0), (cx, y1), thick)

        pygame.draw.line(s, (78, 65, 52), (cx + 2, mast_top), (cx + 2, anchor - 5), 1)


        for fi, bfrac in enumerate([0.25, 0.50, 0.75]):
            by = mast_top + int((anchor - mast_top) * bfrac)
            bw = int(14 + (1.0 - bfrac) * 32)
            pygame.draw.line(s, (60, 50, 42), (cx - bw, by), (cx + bw, by), 2)

            prev_by = mast_top + int((anchor - mast_top) * ([0.0, 0.25, 0.50][fi]))
            pygame.draw.line(s, (46, 38, 30), (cx - bw, by), (cx - bw // 2, prev_by + 10), 1)
            pygame.draw.line(s, (46, 38, 30), (cx + bw, by), (cx + bw // 2, prev_by + 10), 1)


        arm_y = mast_top + int((anchor - mast_top) * 0.28)
        arm_ex = cx + 62
        arm_ey = arm_y - 22
        pygame.draw.line(s, (55, 46, 38), (cx, arm_y), (arm_ex, arm_ey), 4)

        pygame.draw.arc(s, (50, 42, 34),
                        pygame.Rect(arm_ex - 24, arm_ey - 26, 48, 30),
                        math.pi * 0.05, math.pi * 0.95, 4)
        pygame.draw.arc(s, (68, 56, 44),
                        pygame.Rect(arm_ex - 18, arm_ey - 20, 36, 22),
                        math.pi * 0.10, math.pi * 0.90, 2)

        pygame.draw.line(s, (42, 35, 28), (arm_ex, arm_ey - 13), (arm_ex, arm_ey), 2)


        arm2_y = arm_y + 22
        pygame.draw.line(s, (42, 35, 28), (cx, arm2_y), (cx - 34, arm2_y - 10), 2)
        pygame.draw.arc(s, (38, 32, 26),
                        pygame.Rect(cx - 48, arm2_y - 18, 30, 18),
                        math.pi * 0.05, math.pi * 0.95, 2)


        pygame.draw.line(s, (46, 38, 30), (cx, mast_top + 8), (cx + 10, mast_top), 2)

        # Warning light housings (dark markers; lit by animation)
        for ly in [mast_top + 3, mast_top + int((anchor - mast_top) * 0.38)]:
            pygame.draw.circle(s, (32, 20, 16), (cx, ly), 4)

        for _ in range(6):
            rx = cx + rng.randint(-5, 5)
            ry = rng.randint(mast_top + 18, anchor - 20)
            rl = rng.randint(6, 18)
            pygame.draw.line(s, (52, 25, 14, 70), (rx, ry), (rx + rng.randint(-2, 2), ry + rl), 1)

        return s, anchor

    def _build_colony_ship(self) -> tuple[pygame.Surface, int]:
        W, H = 320, 185
        anchor = 155
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        rng = self._rng
        cx = W // 2

        hull_cy = anchor - 32
        hull_w, hull_h = 260, 58
        tilt = rng.uniform(-0.14, 0.14)

        pygame.draw.ellipse(s, (14, 9, 7, 80), pygame.Rect(cx - 115, anchor - 8, 230, 26))

        # Buried lower hull (sand overlay; drawn first so hull appears on top)
        bury = pygame.Surface((W, 50), pygame.SRCALPHA)
        for row in range(50):
            fa = int(230 * (row / 50) ** 0.65)
            pygame.draw.line(bury, (54, 26, 16, fa), (0, row), (W, row))
        s.blit(bury, (0, anchor - 22))

        hull_surf = pygame.Surface((hull_w + 16, hull_h + 16), pygame.SRCALPHA)
        pygame.draw.ellipse(hull_surf, (44, 37, 32), pygame.Rect(8, 8, hull_w, hull_h))
        pygame.draw.ellipse(hull_surf, (60, 50, 40), pygame.Rect(10, 10, hull_w - 4, hull_h - 4), 3)
        for i in range(1, 5):
            py = 8 + int(hull_h * i / 5)
            pygame.draw.line(hull_surf, (30, 25, 20), (8, py), (8 + hull_w, py), 1)
        for i in range(1, 9):
            px = 8 + int(hull_w * i / 9)
            pygame.draw.line(hull_surf, (30, 25, 20), (px, 8), (px, 8 + hull_h), 1)
        for _ in range(4):
            dmx = rng.randint(20, hull_w - 20)
            dmy = rng.randint(8, hull_h - 8)
            pygame.draw.circle(hull_surf, (22, 16, 12), (dmx, dmy + 8), rng.randint(4, 9))

        rot_hull = pygame.transform.rotate(hull_surf, math.degrees(-tilt))
        rh_rect = rot_hull.get_rect(center=(cx, hull_cy))
        s.blit(rot_hull, rh_rect.topleft)

        nx = cx + int(hull_w // 2 * math.cos(tilt)) - 10
        ny = hull_cy + int(hull_w // 2 * math.sin(tilt))
        nose_pts = [
            (nx, ny - 16), (nx + 38, ny - 5),
            (nx + 34, ny + 12), (nx - 4, ny + 10),
        ]
        pygame.draw.polygon(s, (34, 27, 21), nose_pts)
        pygame.draw.polygon(s, (50, 40, 32), nose_pts, 2)
        pygame.draw.line(s, (24, 18, 14), (nx + 8, ny - 12), (nx + 22, ny + 8), 1)
        pygame.draw.line(s, (24, 18, 14), (nx + 18, ny - 8), (nx + 30, ny + 5), 1)

        bx = cx - int(hull_w // 2 * math.cos(tilt)) + 12
        by = hull_cy - int(hull_w // 2 * math.sin(tilt))
        for off, r in [((0, 0), 18), ((-14, 3), 11), ((14, -4), 11)]:
            px, py = bx + off[0], by + off[1]
            pygame.draw.circle(s, (26, 20, 16), (px, py), r)
            pygame.draw.circle(s, (42, 34, 26), (px, py), r, 2)
            pygame.draw.circle(s, (18, 13, 10), (px, py), r - 5)

        pygame.draw.circle(s, (26, 20, 13), (cx - 62, hull_cy - 16), 4)
        pygame.draw.circle(s, (26, 20, 13), (cx + 45, hull_cy - 14), 4)

        for ax_off in [-80, 60]:
            pygame.draw.line(s, (42, 35, 28),
                             (cx + ax_off, hull_cy - 22),
                             (cx + ax_off + rng.randint(-4, 4), hull_cy - 36), 2)

        for _ in range(14):
            dx = rng.randint(-105, 105)
            dy = rng.randint(-6, 14)
            dw, dh = rng.randint(4, 15), rng.randint(2, 6)
            a = rng.randint(120, 195)
            pygame.draw.rect(s, (38, 30, 24, a),
                             pygame.Rect(cx + dx, anchor - 4 + dy, dw, dh), border_radius=1)

        return s, anchor

    def _build_buried_facility(self) -> tuple[pygame.Surface, int]:
        W, H = 200, 155
        anchor = 132
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        rng = self._rng
        cx = W // 2

        block_top = anchor - 68
        block_h = 62

        pygame.draw.ellipse(s, (12, 8, 6, 70), pygame.Rect(cx - 78, anchor - 6, 156, 22))

        bury = pygame.Surface((W, 40), pygame.SRCALPHA)
        for row in range(40):
            fa = int(225 * (row / 40) ** 0.6)
            pygame.draw.line(bury, (52, 24, 16, fa), (0, row), (W, row))
        s.blit(bury, (0, anchor - 16))

        pygame.draw.rect(s, (36, 28, 22), pygame.Rect(cx - 75, block_top, 150, block_h), border_radius=2)
        pygame.draw.rect(s, (50, 40, 32), pygame.Rect(cx - 75, block_top, 150, block_h), 2, border_radius=2)

        for i in range(1, 5):
            px = cx - 75 + int(150 * i / 5)
            pygame.draw.line(s, (26, 20, 16), (px, block_top + 5), (px, block_top + block_h - 5), 1)
        pygame.draw.line(s, (26, 20, 16),
                         (cx - 75, block_top + block_h // 2),
                         (cx + 75, block_top + block_h // 2), 1)

        # Blast doors — asymmetric, left door slightly more open
        door_y = block_top + 10
        door_h = 48
        dl_w = 46
        pygame.draw.rect(s, (30, 24, 18), pygame.Rect(cx - dl_w, door_y, dl_w - 3, door_h))
        pygame.draw.rect(s, (46, 36, 28), pygame.Rect(cx - dl_w, door_y, dl_w - 3, door_h), 2)
        pygame.draw.rect(s, (22, 17, 12),
                         pygame.Rect(cx - dl_w + 5, door_y + 9, dl_w - 15, door_h - 18),
                         border_radius=1)
        dr_w = 34
        pygame.draw.rect(s, (30, 24, 18), pygame.Rect(cx + 3, door_y, dr_w, door_h))
        pygame.draw.rect(s, (46, 36, 28), pygame.Rect(cx + 3, door_y, dr_w, door_h), 2)
        pygame.draw.rect(s, (22, 17, 12),
                         pygame.Rect(cx + 7, door_y + 9, dr_w - 12, door_h - 18),
                         border_radius=1)
        pygame.draw.rect(s, (6, 4, 8), pygame.Rect(cx - 4, door_y, 8, door_h))

        pygame.draw.rect(s, (55, 44, 35), pygame.Rect(cx - dl_w - 2, door_y - 4, dl_w + dr_w + 8, 5))

        pygame.draw.circle(s, (30, 18, 14), (cx, block_top + 4), 6)
        pygame.draw.circle(s, (44, 28, 20), (cx, block_top + 4), 6, 1)

        for vx_off, vh in [(-55, 24), (52, 18), (-35, 14)]:
            vx = cx + vx_off
            pygame.draw.rect(s, (40, 32, 26), pygame.Rect(vx - 5, block_top - vh, 10, vh))
            pygame.draw.rect(s, (54, 44, 36), pygame.Rect(vx - 5, block_top - vh, 10, vh), 1)
            pygame.draw.ellipse(s, (28, 22, 18), pygame.Rect(vx - 8, block_top - vh - 4, 16, 8))

        for px_off, py_off, pl in [(-44, -3, 22), (40, -6, 18), (-22, -2, 14)]:
            end_x = cx + px_off + rng.randint(4, pl)
            end_y = anchor + py_off - rng.randint(4, 14)
            pygame.draw.line(s, (44, 35, 26),
                             (cx + px_off, anchor + py_off),
                             (end_x, end_y), 3)
            pygame.draw.circle(s, (36, 28, 20), (cx + px_off, anchor + py_off), 4)

        return s, anchor

    def _build_satellite_dish(self) -> tuple[pygame.Surface, int]:
        W, H = 162, 195
        anchor = 178
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        rng = self._rng
        cx = W // 2

        tower_bot = anchor - 4
        tower_top = anchor - 82

        pygame.draw.ellipse(s, (12, 8, 6, 62), pygame.Rect(cx - 42, tower_bot - 4, 84, 18))

        pygame.draw.rect(s, (46, 38, 30), pygame.Rect(cx - 22, tower_bot - 8, 44, 10), border_radius=2)
        pygame.draw.rect(s, (60, 50, 40), pygame.Rect(cx - 22, tower_bot - 8, 44, 10), 1, border_radius=2)

        for seg in range(6):
            y0 = tower_top + seg * ((tower_bot - tower_top) // 6)
            y1 = tower_top + (seg + 1) * ((tower_bot - tower_top) // 6)
            thick = max(2, 8 - seg)
            v = min(255, 42 + seg * 5)
            pygame.draw.line(s, (v, v - 8, v - 16), (cx, y0), (cx, y1), thick)
        pygame.draw.line(s, (72, 60, 48), (cx + 2, tower_top + 4), (cx + 2, tower_bot - 8), 1)

        for sx_off, sy_frac in [(-44, 0.85), (42, 0.85), (-30, 0.45), (28, 0.45)]:
            sy = tower_top + int((tower_bot - tower_top) * sy_frac)
            pygame.draw.line(s, (38, 30, 24), (cx, sy), (cx + sx_off, tower_bot - 2), 2)

        for frac in [0.3, 0.6]:
            by = tower_top + int((tower_bot - tower_top) * frac)
            bw = int(8 + frac * 18)
            pygame.draw.line(s, (52, 42, 34), (cx - bw, by), (cx + bw, by), 1)

        pygame.draw.circle(s, (54, 46, 38), (cx, tower_top), 8)
        pygame.draw.circle(s, (38, 30, 24), (cx, tower_top), 8, 2)
        pygame.draw.circle(s, (62, 52, 42), (cx, tower_top), 4)

        self._dish_tilt = rng.uniform(-0.50, 0.50)
        dish_r = 46
        dish_cy = tower_top - 10
        dish_size = dish_r * 2 + 6
        dish_surf = pygame.Surface((dish_size, dish_size), pygame.SRCALPHA)
        dcx, dcy = dish_size // 2, dish_size // 2
        pygame.draw.arc(dish_surf, (48, 40, 32),
                        pygame.Rect(2, 2, dish_size - 4, dish_size - 4),
                        math.pi * 0.02, math.pi * 0.98, 4)
        pygame.draw.arc(dish_surf, (65, 54, 42),
                        pygame.Rect(10, 10, dish_size - 20, dish_size - 20),
                        math.pi * 0.05, math.pi * 0.95, 2)
        for ri in range(5):
            ra = math.pi * ri / 4
            rx1 = dcx + int(math.cos(ra) * (dish_size // 2 - 3))
            ry1 = dcy - int(abs(math.sin(ra)) * (dish_size // 2 - 3))
            pygame.draw.line(dish_surf, (40, 33, 26), (dcx, dcy), (rx1, ry1), 1)
        pygame.draw.line(dish_surf, (55, 46, 36), (dcx, dcy), (dcx, 4), 2)
        pygame.draw.circle(dish_surf, (26, 18, 12), (dcx, 5), 4)  # feed housing

        rot_dish = pygame.transform.rotate(dish_surf, math.degrees(-self._dish_tilt))
        rd_rect = rot_dish.get_rect(center=(cx, dish_cy))
        s.blit(rot_dish, rd_rect.topleft)

        # Feed arm tip screen offset (relative to cx, dish_cy) for animation
        self._feed_off_x = int(math.sin(self._dish_tilt) * (dish_r - 6))
        self._feed_off_y = dish_cy - (tower_top - 10) - int(math.cos(self._dish_tilt) * (dish_r - 6))
        self._feed_anchor_offset = (
            self._feed_off_x,
            dish_cy - anchor + self._feed_off_y,
        )

        return s, anchor

    def _draw_animated(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        alpha: int,
        time_s: float,
    ) -> None:
        if alpha < 8:
            return
        top_y = cy - self._anchor_y  # top of structure in screen space

        if self.ltype == "mega_relay":
            self._anim_mega_relay(surface, cx, cy, top_y, alpha)
        elif self.ltype == "colony_ship":
            self._anim_colony_ship(surface, cx, cy, top_y, alpha)
        elif self.ltype == "buried_facility":
            self._anim_buried_facility(surface, cx, cy, top_y, alpha)
        else:
            self._anim_satellite_dish(surface, cx, cy, top_y, alpha)

    def _draw_glow(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        col: tuple,
        inner_r: int,
        outer_r: int,
        alpha: int,
    ) -> None:
        if alpha < 5:
            return
        g = pygame.Surface((outer_r * 2 + 2, outer_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (*col, min(255, int(alpha * 0.45))), (outer_r + 1, outer_r + 1), outer_r)
        pygame.draw.circle(g, (*col, min(255, alpha)), (outer_r + 1, outer_r + 1), inner_r)
        surface.blit(g, (x - outer_r - 1, y - outer_r - 1), special_flags=pygame.BLEND_ADD)

    def _anim_mega_relay(
        self, surface: pygame.Surface, cx: int, cy: int, top_y: int, alpha: int
    ) -> None:
        struct_h = self._anchor_y  # height of structure in pixels

        tip_y = top_y + 16
        fast = 0.5 + 0.5 * math.sin(self._blink_t * 4.5 + self._seed)
        if fast > 0.48:
            r = min(255, int(195 * fast))
            la = int(alpha * fast * 0.92)
            self._draw_glow(surface, cx, tip_y, (r, 35, 22), 4, 8, la)

        mid_y = top_y + int(struct_h * 0.40)
        slow = 0.5 + 0.5 * math.sin(self._blink_t * 1.9 + self._seed + 1.5)
        if slow > 0.42:
            r = min(255, int(160 * slow))
            la = int(alpha * slow * 0.68)
            self._draw_glow(surface, cx, mid_y, (r, 80, 18), 3, 6, la)

        arm_len = 13
        rot_ang = self._rot_t
        ax1 = cx + int(math.cos(rot_ang) * arm_len)
        ay1 = tip_y + 6 + int(math.sin(rot_ang) * arm_len * 0.38)
        la = int(alpha * 0.45)
        if la > 15:
            arm_surf = pygame.Surface((arm_len * 2 + 6, arm_len + 6), pygame.SRCALPHA)
            la_c = min(255, la)
            pygame.draw.line(
                arm_surf,
                (55, 115, 175, la_c),
                (arm_len + 3, 3 + arm_len // 2),
                (ax1 - cx + arm_len + 3, ay1 - (tip_y + 6) + 3 + arm_len // 2),
                1,
            )
            surface.blit(arm_surf, (cx - arm_len - 3, tip_y + 6 - 3 - arm_len // 2),
                         special_flags=pygame.BLEND_ADD)

    def _anim_colony_ship(
        self, surface: pygame.Surface, cx: int, cy: int, top_y: int, alpha: int
    ) -> None:
        # Hull approximate center Y in screen space
        hull_y = cy - self._anchor_y + int(self._anchor_y * 0.62)
        pulse = 0.42 + 0.58 * abs(math.sin(self._pulse_t * 0.85 + self._seed))
        la = int(alpha * pulse * 0.88)
        if la < 6:
            return
        self._draw_glow(surface, cx - 64, hull_y - 14, (205, 158, 55), 4, 8, la)
        self._draw_glow(surface, cx + 47, hull_y - 12, (175, 90, 35), 3, 7, int(la * 0.8))

    def _anim_buried_facility(
        self, surface: pygame.Surface, cx: int, cy: int, top_y: int, alpha: int
    ) -> None:
        door_warn_y = top_y + 4  # block_top+4 is near the surface top
        blink = math.sin(self._blink_t * 2.8 + self._seed)
        if blink > 0.15:
            intensity = (blink - 0.15) / 0.85
            r = min(255, int(225 * intensity))
            la = int(alpha * intensity * 0.90)
            self._draw_glow(surface, cx, door_warn_y, (r, 48, 18), 5, 10, la)

    def _anim_satellite_dish(
        self, surface: pygame.Surface, cx: int, cy: int, top_y: int, alpha: int
    ) -> None:
        if not hasattr(self, "_feed_anchor_offset"):
            return
        fdx, fdy = self._feed_anchor_offset
        fx = cx + fdx
        fy = cy - self._anchor_y + fdy + self._anchor_y  # simplifies to cy + fdy? No...
        # Correct: feed tip is at surface (cx in surface = W//2; feed_off from anchor)
        # top_y = cy - anchor_y; feed tip in surface coords = anchor_y + feed_dy
        fy = cy - self._anchor_y + (self._anchor_y + self._feed_anchor_offset[1])
        fx = cx + self._feed_anchor_offset[0]

        pulse = 0.5 + 0.5 * abs(math.sin(self._pulse_t * 3.4 + self._seed))
        la = int(alpha * pulse * 0.88)
        if la < 5:
            return
        self._draw_glow(surface, fx, fy, (72, 195, 255), 3, 7, la)

        dish_cy_screen = cy - self._anchor_y + (self._anchor_y - 82 - 10)
        ring_phase = (self._pulse_t * 0.45 + self._seed) % 1.0
        if ring_phase < 0.55:
            rr = int(8 + ring_phase * 55)
            ra = int(48 * (1.0 - ring_phase / 0.55) * (alpha / 255))
            if ra > 3:
                rs = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(rs, (72, 195, 255, ra), (rr + 2, rr + 2), rr, 1)
                surface.blit(rs, (cx - rr - 2, dish_cy_screen - rr - 2))
