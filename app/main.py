import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aio_pika
from aio_pika.exceptions import AMQPConnectionError
from messaging.rabbitmq import get_rabbitmq_connection
from  services.reservation import ReservationService
from routes.reservations import router as reservations_router
from db.mongo import close_mongo_connection, connect_to_mongo
from core.config import settings
from crud.reservations import ReservationRepository
 
# ---------- RabbitMQ Listener ----------
# RABBITMQ_URL = "amqp://guest:guest@host.docker.internal:5672/"  

# RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"  #docker run
 
EXCHANGE_NAME = "vendor_reservation"
QUEUE_NAME = "reservation_status_queue"
ROUTING_KEY = "reservation.status"

async def listen_rabbitmq():
    while True:
        try:
            print("🔄 Connecting to RabbitMQ...")
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            channel = await connection.channel()
            exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
            queueChangeStatus = await channel.declare_queue(QUEUE_NAME, durable=True)
            await queueChangeStatus.bind(exchange, ROUTING_KEY)

            print(f"✅ Connected & Listening on queue: {QUEUE_NAME} ({ROUTING_KEY})")
            async with queueChangeStatus.iterator() as queue_iter:
                #print("async with queue.iterator() as queue_iter:")
                async for message in queue_iter:
                    #print("async for message in queue_iter:")
                    async with message.process():
                        data = json.loads(message.body)
                        # ReservationService.change_reservation_status(reservationID=data.reservationID,)
                        print(f"📨 Received event: {data}")
                        if data["event"] == "UPDATE_RESERVATION_STATUS":
                            response = await ReservationRepository.update_reservation_status(data["reservationId"], "VALIDATESLIP")
                            print("Updated reservation status to VALIDATESLIP successfully")

        except Exception as e:
            print(f"❌ RabbitMQ connection lost or error: {e}")
            print("⏳ Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
# ---------- RabbitMQ Listener End ----------

async def setup_rabbitmq():
    connection = await get_rabbitmq_connection()
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        settings.USER_TOPIC1,
        aio_pika.ExchangeType.TOPIC,
        durable=True
    )

    # สร้าง queue ที่จะรับ message จาก exchange
    queue = await channel.declare_queue(
        settings.USER_QUEUE,
        durable=True
    )

    # bind queue กับ exchange ตาม routing key
    await queue.bind(exchange, routing_key=settings.USER_STATUS)

    print("✅ RabbitMQ exchange & queue created and bound successfully!")
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()

    await setup_rabbitmq()
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
    allow_origins=["http://localhost:3000",settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(reservations_router, prefix="/api/reservations", tags=["Reservations"])


async def serve_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=7003)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(serve_fastapi())


if __name__ == "__main__":
    asyncio.run(main())
