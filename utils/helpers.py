"""Shared utility functions: clamp, random_in_rect, rects_overlap."""
import random

from pygame import Rect, Vector2


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def random_in_rect(bounds: Rect) -> Vector2:
    """Return a uniformly random position inside bounds (world or screen space)."""
    x = random.uniform(bounds.left, bounds.right)
    y = random.uniform(bounds.top, bounds.bottom)
    return Vector2(x, y)


def rects_overlap(a: Rect, b: Rect) -> bool:
    return a.colliderect(b)
