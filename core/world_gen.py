
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from pygame import Vector2

from core import settings as S


BiomeId = int


BIOME_DUNES: BiomeId = 0
BIOME_ROCKS: BiomeId = 1
BIOME_MAGNETIC: BiomeId = 2
BIOME_SHADOW: BiomeId = 3


BIOME_NAMES = {
    BIOME_DUNES: "DUNES",
    BIOME_ROCKS: "ROCKS",
    BIOME_MAGNETIC: "MAGNETIC",
    BIOME_SHADOW: "SHADOW",
}


BIOME_COLORS = {
    BIOME_DUNES: (78, 22, 16),
    BIOME_ROCKS: (36, 22, 18),
    BIOME_MAGNETIC: (28, 16, 34),
    BIOME_SHADOW: (10, 8, 14),
}


@dataclass(frozen=True)
class BiomeEffects:
    speed_mul: float
    storm_mul: float
    signal_loss_mul: float
    magnetic_jitter: float
    fake_signal_bonus: float
    resource_density_mul: float
    vignette_mul: float
    glitch_add: float
    fog_mul: float


EFFECTS = {
    BIOME_DUNES: BiomeEffects(
        speed_mul=1.1,
        storm_mul=1.2,
        signal_loss_mul=1.0,
        magnetic_jitter=0.0,
        fake_signal_bonus=0.0,
        resource_density_mul=1.0,
        vignette_mul=1.0,
        glitch_add=0.0,
        fog_mul=1.0,
    ),
    BIOME_ROCKS: BiomeEffects(
        speed_mul=0.7,
        storm_mul=1.0,
        signal_loss_mul=0.5,
        magnetic_jitter=0.0,
        fake_signal_bonus=0.0,
        resource_density_mul=1.0,
        vignette_mul=1.0,
        glitch_add=0.0,
        fog_mul=1.0,
    ),
    BIOME_MAGNETIC: BiomeEffects(
        speed_mul=1.0,
        storm_mul=1.0,
        signal_loss_mul=1.0,
        magnetic_jitter=2.4,
        fake_signal_bonus=0.22,
        resource_density_mul=1.0,
        vignette_mul=1.0,
        glitch_add=0.22,
        fog_mul=1.0,
    ),
    BIOME_SHADOW: BiomeEffects(
        speed_mul=1.0,
        storm_mul=1.0,
        signal_loss_mul=2.0,
        magnetic_jitter=0.0,
        fake_signal_bonus=0.0,
        resource_density_mul=1.5,
        vignette_mul=1.35,
        glitch_add=0.0,
        fog_mul=1.25,
    ),
}


@dataclass(frozen=True)
class SeedBlob:
    """Radial influence source for one biome — multiple blobs per biome produce organic territories."""

    x: float
    y: float
    strength: float
    falloff: float

    def influence(self, px: float, py: float) -> float:
        dx = px - self.x
        dy = py - self.y
        d2 = dx * dx + dy * dy
        d = math.sqrt(d2) + 1.0
        return self.strength / (d ** self.falloff)


class BiomeMap:
    """Cell-based biome grid baked at world gen time. blend_at() returns top-2 biome IDs + blend_t for smooth transitions."""

    def __init__(self, w: int, h: int, cell: int) -> None:
        self.w = w
        self.h = h
        self.cell = max(16, int(cell))
        self.cols = max(1, int(math.ceil(w / self.cell)))
        self.rows = max(1, int(math.ceil(h / self.cell)))
        n = self.cols * self.rows
        self.primary: list[int] = [BIOME_DUNES] * n
        self.a_id: list[int] = [BIOME_DUNES] * n
        self.b_id: list[int] = [BIOME_DUNES] * n
        self.blend_t: list[float] = [0.0] * n

    def _idx(self, cx: int, cy: int) -> int:
        return cy * self.cols + cx

    def cell_at(self, x: float, y: float) -> tuple[int, int]:
        cx = int(x // self.cell)
        cy = int(y // self.cell)
        cx = 0 if cx < 0 else (self.cols - 1 if cx >= self.cols else cx)
        cy = 0 if cy < 0 else (self.rows - 1 if cy >= self.rows else cy)
        return (cx, cy)

    def biome_at(self, x: float, y: float) -> int:
        cx, cy = self.cell_at(x, y)
        return self.primary[self._idx(cx, cy)]

    def blend_at(self, x: float, y: float) -> tuple[int, int, float]:
        cx, cy = self.cell_at(x, y)
        i = self._idx(cx, cy)
        return (self.a_id[i], self.b_id[i], self.blend_t[i])


class ResourceDistributor:
    """Places resources and signal towers with spatial spread guarantees and biome-weighted fake-signal ratios."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def distribute_resources(self, biome_map: BiomeMap, total: int) -> list[Vector2]:
        margin = 80
        min_dist_sq = 350.0 ** 2

        # Grid-based spawn: divide world into NxN cells, pick `total` distinct cells.
        # ceil(sqrt(total * 2)) gives enough cells for even coverage without overcrowding.
        n_cells = max(3, int(math.ceil(math.sqrt(total * 2))))
        cell_w = S.WORLD_WIDTH / n_cells
        cell_h = S.WORLD_HEIGHT / n_cells

        cells = [(cx, cy) for cy in range(n_cells) for cx in range(n_cells)]
        self.rng.shuffle(cells)

        out: list[Vector2] = []
        for cx, cy in cells:
            if len(out) >= total:
                break
            x0 = max(margin, cx * cell_w + 40)
            y0 = max(margin, cy * cell_h + 40)
            x1 = min(S.WORLD_WIDTH - margin, (cx + 1) * cell_w - 40)
            y1 = min(S.WORLD_HEIGHT - margin, (cy + 1) * cell_h - 40)
            if x1 <= x0 or y1 <= y0:
                continue
            for _ in range(8):
                px = self.rng.uniform(x0, x1)
                py = self.rng.uniform(y0, y1)
                if all((px - p.x) ** 2 + (py - p.y) ** 2 >= min_dist_sq for p in out):
                    out.append(Vector2(px, py))
                    break

        while len(out) < total:
            out.append(Vector2(
                self.rng.uniform(margin, S.WORLD_WIDTH - margin),
                self.rng.uniform(margin, S.WORLD_HEIGHT - margin),
            ))
        return out

    def distribute_signals(self, biome_map: BiomeMap, total: int, base_real_chance: float) -> list[tuple[Vector2, bool]]:
        out: list[tuple[Vector2, bool]] = []
        step = max(80, biome_map.cell * 2)
        for _ in range(total * 6):
            if len(out) >= total:
                break
            px = self.rng.uniform(64, S.WORLD_WIDTH - 64)
            py = self.rng.uniform(64, S.WORLD_HEIGHT - 64)
            a, b, t = biome_map.blend_at(px, py)
            eff_a = EFFECTS[a]
            eff_b = EFFECTS[b]
            fake_bonus = eff_a.fake_signal_bonus * (1.0 - t) + eff_b.fake_signal_bonus * t
            real_ch = max(0.05, min(0.95, base_real_chance - fake_bonus))
            is_real = self.rng.random() < real_ch
            out.append((Vector2(px, py), is_real))
        while len(out) < total:
            out.append(
                (
                    Vector2(
                        self.rng.uniform(64, S.WORLD_WIDTH - 64),
                        self.rng.uniform(64, S.WORLD_HEIGHT - 64),
                    ),
                    self.rng.random() < base_real_chance,
                )
            )
        return out


class WorldGenerator:
    """Runs the full 3-pass world gen pipeline from a single seed; same seed always produces identical worlds."""

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self.rng = random.Random(self.seed)

    def _make_blobs(self, biome_id: int, n: int) -> list[SeedBlob]:
        blobs: list[SeedBlob] = []
        for _ in range(n):
            x = self.rng.uniform(0, S.WORLD_WIDTH)
            y = self.rng.uniform(0, S.WORLD_HEIGHT)
            strength = self.rng.uniform(0.9, 1.6) * (1.1 if biome_id == BIOME_DUNES else 1.0)
            falloff = self.rng.uniform(1.55, 2.4)
            blobs.append(SeedBlob(x, y, strength, falloff))
        return blobs

    def generate_biome_map(self) -> BiomeMap:
        """
        Build the biome map in three passes:
          1. Score each cell against all SeedBlobs — top-2 biomes become a_id/b_id
          2. Compute blend_t from how close the top-2 scores are (close → ~0.5, far → 0.0)
          3. Two iterations of 3×3 majority-vote smoothing to remove isolated single cells
        The horizontal drift bias (DUNES west, SHADOW east) is subtle but makes the world
        read left-to-right as "safer → more dangerous" without feeling forced.
        """
        bm = BiomeMap(S.WORLD_WIDTH, S.WORLD_HEIGHT, S.BIOME_CELL_SIZE)

        blobs = {
            BIOME_DUNES: self._make_blobs(BIOME_DUNES, 7),
            BIOME_ROCKS: self._make_blobs(BIOME_ROCKS, 7),
            BIOME_MAGNETIC: self._make_blobs(BIOME_MAGNETIC, 6),
            BIOME_SHADOW: self._make_blobs(BIOME_SHADOW, 6),
        }


        for cy in range(bm.rows):
            py = (cy + 0.5) * bm.cell
            for cx in range(bm.cols):
                px = (cx + 0.5) * bm.cell

                scores: list[tuple[float, int]] = []
                for bid, bb in blobs.items():
                    s = 0.0
                    for blob in bb:
                        s += blob.influence(px, py)

                    drift = (px / max(1.0, float(S.WORLD_WIDTH))) - 0.5
                    if bid == BIOME_DUNES:
                        s *= 1.0 + 0.12 * (-drift)
                    elif bid == BIOME_SHADOW:
                        s *= 1.0 + 0.12 * (drift)
                    scores.append((s, bid))

                scores.sort(reverse=True, key=lambda t: t[0])
                s0, a = scores[0]
                s1, b = scores[1]
                i = bm._idx(cx, cy)
                bm.a_id[i] = a
                bm.b_id[i] = b


                denom = max(1e-6, s0 + s1)
                diff = abs(s0 - s1) / denom

                thr = 0.22
                if diff < thr:
                    u = diff / thr
                    t = 0.5 + 0.5 * (1.0 - u) * (1.0 if self.rng.random() < 0.5 else -1.0)
                    t = max(0.0, min(1.0, t))
                else:
                    t = 0.0
                bm.blend_t[i] = t
                bm.primary[i] = a if t < 0.5 else b


        sm = bm.primary[:]
        for _ in range(2):
            out = sm[:]
            for cy in range(bm.rows):
                for cx in range(bm.cols):
                    i = bm._idx(cx, cy)
                    votes = {BIOME_DUNES: 0, BIOME_ROCKS: 0, BIOME_MAGNETIC: 0, BIOME_SHADOW: 0}
                    for oy in (-1, 0, 1):
                        yy = cy + oy
                        if yy < 0 or yy >= bm.rows:
                            continue
                        for ox in (-1, 0, 1):
                            xx = cx + ox
                            if xx < 0 or xx >= bm.cols:
                                continue
                            votes[sm[bm._idx(xx, yy)]] += 1
                    out[i] = max(votes.items(), key=lambda kv: kv[1])[0]
            sm = out
        bm.primary = sm
        return bm

    def generate(self, resource_total: int, signal_total: int, real_signal_chance: float) -> tuple[BiomeMap, list[Vector2], list[tuple[Vector2, bool]]]:
        bm = self.generate_biome_map()
        dist = ResourceDistributor(self.rng)
        resources = dist.distribute_resources(bm, resource_total)
        signals = dist.distribute_signals(bm, signal_total, real_signal_chance)
        return (bm, resources, signals)
