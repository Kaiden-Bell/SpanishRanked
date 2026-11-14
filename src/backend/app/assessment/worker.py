"""Background grading: free sentences are graded by the local model, which can take a while, so the
learner keeps using the app and is told when the result is ready.

A quiz waits in the queue while it is SUBMITTED with no grading_error. A failure records the error and
takes it out of the queue until the learner retries. Quizzes queued before a restart are picked up at
startup. inline=True grades synchronously (tests, and setups with background grading turned off).
"""

import logging
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import db
from ..clients.grammar import GrammarChecker
from ..clients.model import LanguageModel
from . import grade as grading

log = logging.getLogger(__name__)


def queue(conn, assessment_id: int) -> None:
    """Put a SUBMITTED quiz (back) in the queue: clearing the error is what marks it waiting."""
    with conn:
        conn.execute("UPDATE assessments SET grading_error = NULL WHERE id = ? AND status = 'SUBMITTED'",
                     (assessment_id,))


class Grader:
    def __init__(self, db_path: Path, model: LanguageModel, grammar: GrammarChecker, tz: ZoneInfo, *,
                 inline: bool = False):
        self._db_path, self.model, self.grammar, self.tz, self.inline = db_path, model, grammar, tz, inline
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._run_lock = threading.Lock()

    def start(self) -> None:
        if self.inline or self._thread:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="quiz-grader", daemon=True)
        self._thread.start()
        self._wake.set()  # resume anything queued before a restart

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def kick(self) -> None:
        if self.inline:
            self.run_pending()
        else:
            self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=300)
            self._wake.clear()
            if self._stop.is_set():
                return
            try:
                self.run_pending()
            except Exception:  # never let the worker die; the next kick retries
                log.exception("quiz grading failed")

    def run_pending(self, limit: int = 50) -> int:
        done = 0
        with self._run_lock, closing(db.connect(self._db_path)) as conn:
            while done < limit and not self._stop.is_set():
                row = conn.execute(
                    "SELECT id, user_id FROM assessments WHERE status = 'SUBMITTED' AND grading_error IS NULL"
                    " ORDER BY id LIMIT 1"
                ).fetchone()
                if row is None:
                    break
                try:
                    grading.grade_assessment(conn, row["user_id"], row["id"], self.model, self.grammar, self.tz,
                                             datetime.now(timezone.utc))
                except Exception as exc:  # out of the queue, so one broken quiz can't block the rest
                    log.exception("grading quiz %s failed", row["id"])
                    conn.rollback()
                    grading._record_error(conn, row["id"], f"Grading failed unexpectedly ({type(exc).__name__}).")
                done += 1
        return done
