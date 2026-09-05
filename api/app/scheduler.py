from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event, RLock, Thread

from app.refresh import MAX_DOCUMENTS, RefreshManager


class RefreshScheduler:
    """In-process MVP scheduler for infrequent source refreshes.

    Normal audits never invoke this scheduler. Production should replace it with
    a durable queue and stateless workers so schedules survive process restarts.
    """

    def __init__(self, refresh_manager: RefreshManager, interval_hours: int) -> None:
        self.refresh_manager = refresh_manager
        self.interval_hours = interval_hours
        self._stop_event = Event()
        self._lock = RLock()
        self._thread: Thread | None = None
        self._next_run_at: datetime | None = None

    def start(self) -> None:
        if self.interval_hours <= 0:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._next_run_at = datetime.now(UTC) + timedelta(hours=self.interval_hours)
            self._thread = Thread(target=self._run, name="proofmark-refresh-scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "enabled": self.interval_hours > 0,
                "interval_hours": self.interval_hours,
                "next_run_at": self._next_run_at,
                "implementation": "in_process_mvp",
                "production_successor": "durable scheduled job plus stateless refresh workers",
            }

    def _run(self) -> None:
        delay_seconds = self.interval_hours * 60 * 60
        while not self._stop_event.wait(delay_seconds):
            self.refresh_manager.start(MAX_DOCUMENTS)
            with self._lock:
                self._next_run_at = datetime.now(UTC) + timedelta(hours=self.interval_hours)
