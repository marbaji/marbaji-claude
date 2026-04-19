from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InitResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    upserted: dict[str, list[str]] = field(default_factory=dict)
    ensured: list[str] = field(default_factory=list)
    next_step: str = ""
