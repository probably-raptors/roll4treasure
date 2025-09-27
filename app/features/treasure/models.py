from __future__ import annotations

import random
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str
    name: str
    type_line: str = ""
    oracle_text: str = ""
    tag: str = "utility"  # "curse" | "rock" | "utility"
    img: str | None = None  # URL (local /img-cache/... or remote fallback)
    scry: str | None = None  # Scryfall page URL
    oracle_id: str | None = None  # for dedupe / lookups


class PileState(BaseModel):
    cards: list[Card]  # top is index 0
    revealed: list[Card] = []  # buffer during a “strike gold”


class Player(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    digs_this_game: int = 0
    dug_this_turn: bool = False
    gains: list[Card] = []  # cards taken


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    players: list[Player]
    turn_idx: int = 0
    turn_num: int = 1
    pile: PileState
    log: list[str] = []

    # gate UI until images are prefetched
    is_ready: bool = False
    precache_total: int = 0
    precache_done: int = 0
    precache_error: str | None = None

    # revealed cards when 6 is rolled
    pending_choices: list[Card] = []
    pending_player_id: str | None = None

    closed_at: str | None = None

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None


SESSIONS: dict[str, Session] = {}


def current_player(s: Session) -> Player:
    return s.players[s.turn_idx]


def shuffle_bottom_random(s: Session, cards: list[Card]) -> None:
    random.shuffle(cards)
    s.pile.cards.extend(cards)


def roll_d6() -> int:
    return random.randint(1, 6)
