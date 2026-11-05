import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[3]

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path
    # Set LANGUAGEAI_SECURE_COOKIES=1 when served over HTTPS (MVP_DESIGN.md §10).
    secure_cookies: bool = False
    session_ttl_hours: int = 24 * 7
    # IANA name. Decides where a "day" ends for streaks and daily XP caps; set it once at setup.
    # Each award stores its local date, so changing this later never rewrites past XP.
    timezone: str = "UTC"
    # Sidecar services (MVP_DESIGN.md §5). An empty URL means "not configured" and counts as down.
    languagetool_url: str = ""
    ollama_url: str = ""
    model_name: str = "qwen2.5:7b"
    languagetool_timeout: float = 3.0
    # Generous because the target homelab has no GPU; a single graded answer takes several seconds.
    model_timeout: float = 120.0

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "languageai.db"

    @classmethod
    def from_env(cls) -> "Settings":
        timezone = os.environ.get("LANGUAGEAI_TIMEZONE") or "UTC"
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"LANGUAGEAI_TIMEZONE={timezone!r} is not a valid IANA timezone (e.g. 'America/Chicago')")
        return cls(
            timezone=timezone,
            data_dir=Path(os.environ.get("LANGUAGEAI_DATA_DIR", REPO_ROOT / "data")),
            frontend_dist=Path(
                os.environ.get(
                    "LANGUAGEAI_FRONTEND_DIST",
                    REPO_ROOT / "src/frontend/spanish-ranked/dist",
                )
            ),
            secure_cookies=os.environ.get("LANGUAGEAI_SECURE_COOKIES", "") in ("1", "true"),
            session_ttl_hours=int(os.environ.get("LANGUAGEAI_SESSION_TTL_HOURS", 24 * 7)),
            languagetool_url=os.environ.get("LANGUAGEAI_LANGUAGETOOL_URL", ""),
            ollama_url=os.environ.get("LANGUAGEAI_OLLAMA_URL", ""),
            model_name=os.environ.get("LANGUAGEAI_MODEL") or "qwen2.5:7b",
            languagetool_timeout=float(os.environ.get("LANGUAGEAI_LANGUAGETOOL_TIMEOUT", 3.0)),
            model_timeout=float(os.environ.get("LANGUAGEAI_MODEL_TIMEOUT", 120.0)),
        )
