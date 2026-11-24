"""Thread-safe, in-memory primary/secondary inventory simulation."""

from collections import deque
from dataclasses import dataclass
from threading import Condition, Thread
from time import monotonic


@dataclass(frozen=True)
class Snapshot:
    stock: int
    version: int


class InventorySystem:
    """Single-writer replication with ordered asynchronous delivery.

    A condition protects state and the replication queue. Pausing and reading
    therefore cannot race with a secondary update. Versions distinguish a
    caught-up replica from one that happens to have the same stock value.
    """

    def __init__(self, stock: int = 10):
        self._validate(stock)
        self._condition = Condition()
        self._primary = Snapshot(stock, 0)
        self._secondary = Snapshot(stock, 0)
        self._pending = deque()
        self._paused = False
        self._closed = False
        self._worker = Thread(target=self._replicate, name="replication-worker", daemon=True)
        self._worker.start()

    @staticmethod
    def _validate(stock):
        if type(stock) is not int or stock < 0:
            raise ValueError("stock must be a nonnegative integer")

    def read(self, replica: str) -> Snapshot:
        """Client reads can target either replica independently."""
        with self._condition:
            if replica == "primary":
                return self._primary
            if replica == "secondary":
                return self._secondary
            raise ValueError("replica must be 'primary' or 'secondary'")

    def update(self, stock: int) -> Snapshot:
        """Acknowledge the primary write before requiring secondary delivery."""
        self._validate(stock)
        with self._condition:
            if self._closed:
                raise RuntimeError("system is closed")
            self._primary = Snapshot(stock, self._primary.version + 1)
            self._pending.append(self._primary)
            self._condition.notify_all()
            return self._primary

    def pause_replication(self):
        with self._condition:
            self._paused = True

    def resume_replication(self):
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def wait_for_version(self, version: int, timeout: float = 3.0):
        """Wait for delivery of a write, with a bounded failure timeout."""
        deadline = monotonic() + timeout
        with self._condition:
            while self._secondary.version < version:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"secondary did not reach version {version}")
                if self._closed:
                    raise RuntimeError("system closed before replication completed")
                self._condition.wait(remaining)

    def _replicate(self):
        with self._condition:
            while True:
                self._condition.wait_for(
                    lambda: self._closed or (self._pending and not self._paused)
                )
                if self._closed:
                    return
                self._secondary = self._pending.popleft()
                self._condition.notify_all()

    def close(self):
        """Stop the worker; queued writes are not durable across shutdown."""
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        self._worker.join()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
