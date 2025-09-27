from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from random import Random

from .models import BoardState, IterLogEntry, SimRequest, SimResult, now_iso


@dataclass
class ArtifactPool:
    robots: int = 0
    robots_tapped: int = 0
    treasures: int = 0
    treasures_tapped: int = 0
    other: int = 0
    other_tapped: int = 0

    def untapped_count(self) -> int:
        return (
            (self.robots - self.robots_tapped)
            + (self.treasures - self.treasures_tapped)
            + (self.other - self.other_tapped)
        )

    def tap_one(self, kind: str) -> bool:
        if kind == "robot" and self.robots - self.robots_tapped > 0:
            self.robots_tapped += 1
            return True
        if kind == "treasure" and self.treasures - self.treasures_tapped > 0:
            self.treasures_tapped += 1
            return True
        if kind == "other" and self.other - self.other_tapped > 0:
            self.other_tapped += 1
            return True
        return False

    def untap_one(self, kind: str) -> None:
        if kind == "robot" and self.robots_tapped > 0:
            self.robots_tapped -= 1
        elif kind == "treasure" and self.treasures_tapped > 0:
            self.treasures_tapped -= 1
        elif kind == "other" and self.other_tapped > 0:
            self.other_tapped -= 1


def choose_tap_targets(pool: ArtifactPool) -> list[str]:
    """Pick exactly two tap kinds while preserving Robots:
    - Tap 'other' first (if available)
    - Prefer tapping 'treasure' over 'robot'
    - Only tap robots if unavoidable
    - Return [] if you can't pay the full cost
    """
    unt_other = pool.other - pool.other_tapped
    unt_robot = pool.robots - pool.robots_tapped
    unt_treas = pool.treasures - pool.treasures_tapped

    if (unt_other + unt_robot + unt_treas) < 2:
        return []

    picks: list[str] = []

    # 1) First pick: 'other' if available
    if unt_other > 0:
        picks.append("other")
        unt_other -= 1

    # 2) Second pick (or first if no 'other'): prefer treasure, then other, then robot
    if len(picks) < 2:
        if unt_treas > 0:
            picks.append("treasure")
            unt_treas -= 1
        elif unt_other > 0:
            picks.append("other")
            unt_other -= 1
        elif unt_robot > 0:
            picks.append("robot")
            unt_robot -= 1

    # 3) If still short (e.g., need two of a kind), fill with preference: other → treasure → robot
    if len(picks) < 2:
        for k, n in (("other", unt_other), ("treasure", unt_treas), ("robot", unt_robot)):
            if n > 0:
                picks.append(k)
                break

    return picks if len(picks) == 2 else []


def simulate(req: SimRequest) -> SimResult:
    used_seed = req.seed if req.seed is not None else int(datetime.now().timestamp() * 1_000_000)
    rng = Random(used_seed)

    pool = ArtifactPool(other=req.untapped_other_init)
    pbox_counters = 0
    pbox_tapped = False

    mana = 0
    hist = defaultdict(int)

    iterations = 0
    log: list[IterLogEntry] = []

    while iterations < req.max_iters:
        # Step 1: Activate Puzzlebox (tap it, +1 mana)
        pbox_tapped = True
        mana += 1

        # Step 2: Roll and resolve Mr. House
        r = rng.randint(1, 20)
        hist[r] += 1

        created_robots = 0
        created_treasures = 0
        if 4 <= r <= 5:
            created_robots = 1
        elif 6 <= r <= 20:
            created_robots = 1
            created_treasures = 1

        pool.robots += created_robots
        pool.treasures += created_treasures
        pbox_counters += r

        reason = ""
        if req.stop_when_counters_ge_100 and pbox_counters >= 100:
            reason = "Reached ≥100 PB counters"
        elif req.stop_treasures_ge is not None and pool.treasures >= req.stop_treasures_ge:
            reason = f"Reached Treasures ≥ {req.stop_treasures_ge}"
        elif req.stop_robots_ge is not None and pool.robots >= req.stop_robots_ge:
            reason = f"Reached Robots ≥ {req.stop_robots_ge}"
        elif req.stop_mana_ge is not None and mana >= req.stop_mana_ge:
            reason = f"Reached PB Mana ≥ {req.stop_mana_ge}"

        if reason:
            log.append(
                IterLogEntry(
                    iter=iterations + 1,
                    roll=r,
                    created={"robots": created_robots, "treasures": created_treasures},
                    tapped_for_clock=[],
                    note=reason,
                )
            )
            iterations += 1
            break

        # Step 3: Try to untap Puzzlebox via Clock of Omens
        tapped_for_clock: list[str] = []
        note = ""
        if pool.untapped_count() >= 2:
            targets = choose_tap_targets(pool)
            if len(targets) == 2:
                for k in targets:
                    pool.tap_one(k)
                    tapped_for_clock.append(k)
                pbox_tapped = False
            else:
                note = "Could not find two valid artifacts to tap."
        else:
            note = "Insufficient untapped artifacts to pay Clock."

        log.append(
            IterLogEntry(
                iter=iterations + 1,
                roll=r,
                created={"robots": created_robots, "treasures": created_treasures},
                tapped_for_clock=tapped_for_clock,
                note=note,
            )
        )
        iterations += 1

        if pbox_tapped:
            break

    result = SimResult(
        run_timestamp=now_iso(),
        used_seed=used_seed,
        iterations=iterations,
        roll_log=log,
        final_board_state=BoardState(
            robots={
                "total": pool.robots,
                "tapped": pool.robots_tapped,
                "untapped": pool.robots - pool.robots_tapped,
            },
            treasures={
                "total": pool.treasures,
                "tapped": pool.treasures_tapped,
                "untapped": pool.treasures - pool.treasures_tapped,
            },
            other_artifacts={
                "total": pool.other,
                "tapped": pool.other_tapped,
                "untapped": pool.other - pool.other_tapped,
            },
            puzzlebox={
                "counters": pbox_counters,
                "ready_for_next_activation": (not pbox_tapped),
            },
            mana=mana,
        ),
        roll_histogram={k: hist.get(k, 0) for k in range(1, 21)},
    )
    return result
