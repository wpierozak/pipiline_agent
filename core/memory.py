from dataclasses import dataclass, field
from typing import Any, List, Optional
import time
import json
from dataclasses import asdict

@dataclass(frozen=True)
class StateSnapshot:
    """
    Immutable record of a state's execution result.
    """
    timestamp: float
    output: str
    context_used: Optional[str] = None

    def __str__(self):
        return json.dumps(asdict(self))

class MemoryLedger:
    """
    A ledger that stores a sequence of immutable state snapshots.
    """
    def __init__(self):
        self._history: List[StateSnapshot] = []
        self._snapshots_number: int = 0

    @property
    def snapshots_number(self) -> int:
        return self._snapshots_number

    def commit(self, output: str, context: Optional[str] = None):
        """
        Commits a new snapshot to the ledger.
        """
        snapshot = StateSnapshot(
            timestamp=time.time(),
            output=output,
            context_used=context
        )
        self._history.append(snapshot)
        self._snapshots_number += 1

    def get_last_snapshot(self) -> Optional[str]:
        """
        Returns the most recent snapshot.
        """
        if not self._history:
            return None
        return str(self._history[-1])

    def get_history(self) -> List[str]:
        """
        Converts the ledger history to a list of formatted strings.
        """
        return [str(s) for s in self._history]
