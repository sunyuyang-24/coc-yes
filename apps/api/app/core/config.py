from dataclasses import dataclass
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def _csv_env(name: str, fallback: str) -> list[str]:
    raw = os.getenv(name, fallback)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("API_APP_NAME", "COC Yes API")
    version: str = os.getenv("API_VERSION", "0.1.0")
    data_dir: Path = Path(os.getenv("API_DATA_DIR", str(REPO_ROOT / "data" / "runtime")))
    cors_origins: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cors_origins",
            _csv_env("API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
        )


settings = Settings()
