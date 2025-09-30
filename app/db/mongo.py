import asyncio
import motor.motor_asyncio
from fastapi import FastAPI
from core.config import settings

mongodb_client = None

async def connect_to_mongo():
    global mongodb_client, db
    mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URL)
    # retry until Mongo is ready
    for attempt in range(10):
        try:
            await mongodb_client.admin.command("ping")
            break
        except Exception:
            await asyncio.sleep(1)
    db = mongodb_client[settings.MONGO_DB]
    if db == None : print("DB object:", db)
    else: print("Connected mongo db")
    return db
    

def close_mongo_connection():
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
