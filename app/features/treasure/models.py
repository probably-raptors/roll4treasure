from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from uuid import uuid4
from datetime import datetime
import random

class Card(BaseModel):
    id: str
    name: str
    type_line: str = ""
    oracle_text: str = ""
    tag: str = "utility"   # "curse" | "rock" | "utility"
    img: Optional[str] = None          # URL (local /img-cache/... or remote fallback)
    scry: Optional[str] = None         # Scryfall page URL
    oracle_id: Optional[str] = None    # for dedupe / lookups

class PileState(BaseModel):
    cards: List[Card]          # top is index 0
    revealed: List[Card] = []  # buffer during a “strike gold”

class Player(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    digs_this_game: int = 0
    dug_this_turn: bool = False
    gains: List[Card] = []  # cards taken

class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    players: List[Player]
    turn_idx: int = 0
    turn_num: int = 1
    pile: PileState
    log: List[str] = []

    # gate UI until images are prefetched
    is_ready: bool = False
    precache_total: int = 0
    precache_done: int = 0
    precache_error: Optional[str] = None

    # revealed cards when 6 is rolled
    pending_choices: List[Card] = []
    pending_player_id: Optional[str] = None

    closed_at: Optional[str] = None

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

SESSIONS: Dict[str, Session] = {}

def current_player(s: Session) -> Player:
    return s.players[s.turn_idx]

def shuffle_bottom_random(s: Session, cards: List[Card]) -> None:
    random.shuffle(cards)
    s.pile.cards.extend(cards)

def roll_d6() -> int:
    return random.randint(1, 6)
