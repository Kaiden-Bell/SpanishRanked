import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path

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
        )
