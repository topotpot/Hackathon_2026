
from typing import List

from pygame import Rect

from entities.player import Player
from entities.resource import Resource
from entities.signal import Signal as MapSignal


class CollisionSystem:


    def player_resources(
        self, player: Player, resources: List[Resource]
    ) -> List[Resource]:
        """Return all resources whose rect overlaps the player rect (does not remove them)."""
        hits: List[Resource] = []
        pr = player.rect
        for r in resources:
            if pr.colliderect(r.rect):
                hits.append(r)
        return hits

    def player_map_signals(
        self, player: Player, map_signals: List[MapSignal]
    ) -> List[MapSignal]:
        hits: List[MapSignal] = []
        pr = player.rect
        for s in map_signals:
            if pr.colliderect(s.rect):
                hits.append(s)
        return hits

    @staticmethod
    def rect_rect(a: Rect, b: Rect) -> bool:
        return a.colliderect(b)
