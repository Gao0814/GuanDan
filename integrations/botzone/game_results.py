"""Optional low-sensitivity per-game result records for a manual batch."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TextIO

from .result_observability import RESULT_CATEGORIES


GAME_RESULT_SCHEMA = "botzone_manual_batch_game_result"
GAME_RESULT_VERSION = 1


class GameResultRecorder:
    """Append one fixed-schema outcome after each ACK-qualified finish."""

    __slots__ = ("path", "failed", "_stream", "_recorded", "_closed")

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.failed = False
        self._recorded = 0
        self._closed = False
        try:
            self._stream: TextIO = self.path.open("x", encoding="utf-8", newline="\n")
        except OSError:
            raise ValueError("game_results_output_unavailable") from None

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    @property
    def recorded_count(self) -> int:
        return self._recorded

    def record(self, category: str) -> None:
        """Best-effort append; failures never escape into connector flow."""

        if self.failed or self._closed:
            return
        if not isinstance(category, str) or category not in RESULT_CATEGORIES:
            self.failed = True
            return
        payload = {
            "game_no": self._recorded + 1,
            "result": category,
            "schema": GAME_RESULT_SCHEMA,
            "version": GAME_RESULT_VERSION,
        }
        try:
            self._stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except (OSError, ValueError):
            self.failed = True
            return
        self._recorded += 1

    def close(self) -> None:
        if self._closed:
            return
        try:
            if not self.failed:
                self._stream.flush()
                os.fsync(self._stream.fileno())
        except (OSError, ValueError):
            self.failed = True
        try:
            self._stream.close()
        except OSError:
            self.failed = True
        self._closed = True
