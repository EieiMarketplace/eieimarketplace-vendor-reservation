import asyncio
import logging
import motor.motor_asyncio
from core.config import settings

logger = logging.getLogger(__name__)

_mongo_client = None
_database = None


async def connect_to_mongo():
    """Connect to MongoDB with retry logic and store global client & database."""
    global _mongo_client, _database
    # Set a short serverSelectionTimeoutMS so the driver fails fast inside containers
    _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=2000)

    for attempt in range(3):
        try:
            await _mongo_client.admin.command("ping")
            print("Connected Mongo")
            logger.info("Connected to MongoDB on attempt %d", attempt + 1)
            break
        except Exception as e:
            logger.warning("MongoDB connection failed (attempt %d): %s", attempt + 1, e)
            # shorter backoff to fail fast and let docker-compose show the error
            await asyncio.sleep(1)
    else:
        logger.error("Could not connect to MongoDB after %d attempts.", 3)
        raise ConnectionError("MongoDB is not available.")

    _database = _mongo_client[settings.MONGO_DB]
    return _database


def get_database():
    """Return the current database object (connect first if needed)."""
    if _database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return _database


def close_mongo_connection():
    """Close the MongoDB connection pool."""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB connection closed.")
