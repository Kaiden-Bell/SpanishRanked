import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path
    # Set LANGUAGEAI_SECURE_COOKIES=1 when served over HTTPS (MVP_DESIGN.md §10).
    secure_cookies: bool = False
    session_ttl_hours: int = 24 * 7

    @property
    def db_path(self) -> Path:
        return self.data_dir / "languageai.db"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("LANGUAGEAI_DATA_DIR", REPO_ROOT / "data")),
            frontend_dist=Path(
                os.environ.get(
                    "LANGUAGEAI_FRONTEND_DIST",
                    REPO_ROOT / "src/frontend/spanish-ranked/dist",
                )
            ),
            secure_cookies=os.environ.get("LANGUAGEAI_SECURE_COOKIES", "") in ("1", "true"),
            session_ttl_hours=int(os.environ.get("LANGUAGEAI_SESSION_TTL_HOURS", 24 * 7)),
        )
