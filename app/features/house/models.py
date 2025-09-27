from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SimRequest(BaseModel):
    """Validated inputs to the simulator."""

    model_config = ConfigDict(extra="forbid")  # reject unknown keys

    untapped_other_init: int
    stop_when_counters_ge_100: bool = False
    stop_treasures_ge: int | None = None
    stop_robots_ge: int | None = None
    stop_mana_ge: int | None = None

    seed: int | None = None
    max_iters: int = 10_000_000

    @field_validator("seed", "stop_treasures_ge", "stop_robots_ge", "stop_mana_ge", mode="before")
    @classmethod
    def empty_seed_to_none(cls, v):
        return None if v in ("", None) else v


class IterLogEntry(BaseModel):
    iter: int
    roll: int
    created: dict[str, int]
    tapped_for_clock: list[str]
    note: str


class BoardState(BaseModel):
    robots: dict[str, int]
    treasures: dict[str, int]
    other_artifacts: dict[str, int]
    puzzlebox: dict[str, int | bool]
    mana: int


class SimResult(BaseModel):
    run_timestamp: str
    used_seed: int
    iterations: int
    roll_log: list[IterLogEntry]
    final_board_state: BoardState
    roll_histogram: dict[int, int]  # 1..20 -> counts


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
