 
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from db.mongo import close_mongo_connection, connect_to_mongo
 

app = FastAPI(title="Eiei Marketplace Reservation Management")
list = [ 
       
        "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],       
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],          
    allow_headers=["*"],          
)
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    close_mongo_connection()

# app.include_router(market.router, prefix="/reservations", tags=["Reservations"])

async def serve_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=7003)
    server = uvicorn.Server(config)
    await server.serve()
    
async def main():
    await asyncio.gather(
        serve_fastapi(),
    )

if __name__ == "__main__":
    asyncio.run(main())