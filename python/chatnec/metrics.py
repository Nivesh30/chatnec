"""Minimal in-process counters exposed at GET /metrics in Prometheus text
format. Deliberately dependency-free (no prometheus_client) since the surface
here is small: messages in, replies out, agent errors — each labeled by
platform.
"""
from __future__ import annotations

from collections import defaultdict
from threading import Lock

_COUNTER_HELP = {
    "messages_received_total": "Inbound messages parsed from a platform webhook or push connection.",
    "replies_sent_total": "Replies successfully delivered back to a platform.",
    "agent_errors_total": "Agent handler invocations that raised an exception.",
}


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, str], int] = defaultdict(int)

    def inc(self, counter: str, platform: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[(counter, platform)] += amount

    def render_prometheus(self) -> str:
        with self._lock:
            snapshot = dict(self._counters)

        lines: list[str] = []
        for counter, help_text in _COUNTER_HELP.items():
            lines.append(f"# HELP chatnec_{counter} {help_text}")
            lines.append(f"# TYPE chatnec_{counter} counter")
            rows = sorted((p, v) for (c, p), v in snapshot.items() if c == counter)
            for platform, value in rows:
                lines.append(f'chatnec_{counter}{{platform="{platform}"}} {value}')
        return "\n".join(lines) + "\n"


metrics = Metrics()
