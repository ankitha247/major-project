import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


async def connect_db() -> None:
    global _client, _db

    from app.core.config import settings

    logger.info("Connecting to MongoDB...")
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client[settings.DB_NAME]

    await _client.admin.command("ping")
    logger.info("MongoDB connected successfully.")


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db