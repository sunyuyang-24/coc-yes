"""Shared dependencies for room routers — avoids circular imports."""

from app.core.config import settings
from app.modules.rooms.connection_manager import RoomConnectionManager
from app.modules.rooms.store import RoomStore

store = RoomStore(settings.data_dir / "rooms.json")
manager = RoomConnectionManager()
