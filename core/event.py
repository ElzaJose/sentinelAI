# core/event.py

from dataclasses import dataclass, field
from typing import Dict, Any
import uuid
import datetime


@dataclass
class Event:
    source: str
    event_type: str
    severity: str
    context: Dict[str, Any]

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    def to_dict(self):
        return self.__dict__