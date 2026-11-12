"""Read-only, room-scoped memory probe for cognition experiments.

Uses KLONE's existing room permission resolver and MemoryService; no direct SQL,
no bypass of access guards, and no memory content in experiment responses.
"""
from __future__ import annotations

from dataclasses import dataclass

from .api import _resolve_rooms
from .memory import MemoryService
from .repository import KloneRepository


@dataclass(frozen=True)
class MemoryProbe:
    room_id: str
    event_count: int
    episode_count: int
    entity_count: int
    corrected_event_count: int
    sampled_limit: int
    truncated: bool

    def public_summary(self) -> dict:
        return {
            "room_id": self.room_id,
            "event_count": self.event_count,
            "episode_count": self.episode_count,
            "entity_count": self.entity_count,
            "corrected_event_count": self.corrected_event_count,
            "sampled_limit": self.sampled_limit,
            "truncated": self.truncated,
            "note": "Counts reflect a bounded sample, not total database counts.",
        }


def probe_memory(repository: KloneRepository, room_id: str, limit: int = 50) -> MemoryProbe:
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    # The resolver enforces room access; never trust a supplied room identifier.
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    service = MemoryService(repository)
    events = service.query_events(room_id=room.id, limit=limit, offset=0, include_corrected=True)
    episodes = service.query_episodes(room_id=room.id, limit=limit, offset=0, include_corrected=True)
    entities = repository.list_memory_entities(room_id=room.id, limit=limit, offset=0)
    corrected = sum(bool(row.get("corrected_at")) for row in events)
    return MemoryProbe(
        room_id=room.id,
        event_count=len(events),
        episode_count=len(episodes),
        entity_count=len(entities),
        corrected_event_count=corrected,
        sampled_limit=limit,
        truncated=any(len(group) == limit for group in (events, episodes, entities)),
    )
