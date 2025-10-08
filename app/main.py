import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aio_pika
from aio_pika.exceptions import AMQPConnectionError
from routes.reservations import router as reservations_router
from db.mongo import close_mongo_connection, connect_to_mongo


#RABBITMQ_URL = "amqp://guest:guest@host.docker.internal:5672/"
RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"
EXCHANGE_NAME = "vendor_reservation"
QUEUE_NAME = "reservation_status_queue"
ROUTING_KEY = "reservation.status"


# ---------- RabbitMQ Listener ----------

async def listen_rabbitmq():
    while True:
        try:
            print("🔄 Connecting to RabbitMQ...")
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await connection.channel()
            exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
            queue = await channel.declare_queue(QUEUE_NAME, durable=True)
            await queue.bind(exchange, ROUTING_KEY)

            print(f"✅ Connected & Listening on queue: {QUEUE_NAME} ({ROUTING_KEY})")
            async with queue.iterator() as queue_iter:
                #print("async with queue.iterator() as queue_iter:")
                async for message in queue_iter:
                    #print("async for message in queue_iter:")
                    async with message.process():
                        data = json.loads(message.body)
                        print(f"📨 Received event: {data}")

        except Exception as e:
            print(f"❌ RabbitMQ connection lost or error: {e}")
            print("⏳ Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()

    # Start RabbitMQ listener เป็น background task
    asyncio.create_task(listen_rabbitmq())
    # loop = asyncio.get_event_loop()
    # loop.create_task(listen_rabbitmq())

    yield

    # Shutdown
    close_mongo_connection()


app = FastAPI(title="Eiei Marketplace Reservation Management", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(reservations_router, prefix="/reservations", tags=["Reservations"])


async def serve_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=7003)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(serve_fastapi())


if __name__ == "__main__":
    asyncio.run(main())
