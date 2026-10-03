"""Keep rescue/threat IDs stable as detected objects shift between frames."""

from .models import Object, WorldState


class ObjectTracker:
    def __init__(self, max_jump: float = 18, missed_limit: int = 2) -> None:
        self.max_jump = max_jump
        self.missed_limit = missed_limit
        self.next_ids = {"human": 1, "threat": 1}
        self.previous: dict[str, dict[str, tuple[Object, int]]] = {"human": {}, "threat": {}}

    def update(self, world: WorldState | None) -> WorldState | None:
        if world is None:
            return None
        results: dict[str, tuple[Object, ...]] = {}
        for kind, objects in (("human", world.targets), ("threat", world.threats)):
            prior = self.previous[kind]
            unmatched = list(objects)
            current: dict[str, tuple[Object, int]] = {}
            matched: list[Object] = []
            candidates = sorted(((old.position.distance(new.position), ident, new)
                                 for ident, (old, _) in prior.items() for new in unmatched),
                                key=lambda pair: (pair[0], pair[1], pair[2].position.x,
                                                  pair[2].position.y))
            for distance, ident, new in candidates:
                if distance > self.max_jump or ident in current or new not in unmatched:
                    continue
                stable = Object(ident, new.position)
                current[ident] = (stable, 0)
                matched.append(stable)
                unmatched.remove(new)
            for new in unmatched:
                ident = f"{kind}_{self.next_ids[kind]}"
                self.next_ids[kind] += 1
                stable = Object(ident, new.position)
                current[ident] = (stable, 0)
                matched.append(stable)
            for ident, (old, missed) in prior.items():
                if ident not in current and missed + 1 <= self.missed_limit:
                    current[ident] = (old, missed + 1)
            self.previous[kind] = current
            results[kind] = tuple(sorted(matched, key=lambda item: item.id))
        return WorldState(world.tick, world.player, results["human"], results["threat"], world.alive)
