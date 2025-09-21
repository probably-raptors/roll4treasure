from typing import Optional, Dict, List, Union
from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime

class SimRequest(BaseModel):
    """Validated inputs to the simulator."""
    model_config = ConfigDict(extra="forbid")  # reject unknown keys

    untapped_other_init: int
    stop_when_counters_ge_100: bool = False
    stop_treasures_ge: Optional[int] = None
    stop_robots_ge: Optional[int] = None
    stop_mana_ge: Optional[int] = None

    seed: Optional[int] = None
    max_iters: int = 10_000_000

    @field_validator("seed", "stop_treasures_ge", "stop_robots_ge", "stop_mana_ge", mode="before")
    @classmethod
    def empty_seed_to_none(cls, v):
        return None if v in ("", None) else v

class IterLogEntry(BaseModel):
    iter: int
    roll: int
    created: Dict[str, int]
    tapped_for_clock: List[str]
    note: str

class BoardState(BaseModel):
    robots: Dict[str, int]
    treasures: Dict[str, int]
    other_artifacts: Dict[str, int]
    puzzlebox: Dict[str, Union[int, bool]]
    mana: int

class SimResult(BaseModel):
    run_timestamp: str
    used_seed: int
    iterations: int
    roll_log: List[IterLogEntry]
    final_board_state: BoardState
    roll_histogram: Dict[int, int]  # 1..20 -> counts

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
