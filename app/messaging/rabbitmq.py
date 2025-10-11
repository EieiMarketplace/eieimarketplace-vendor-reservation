import asyncio
import aio_pika
import json
from typing import Dict, Any
from core.config import settings
import logging
from core.config import settings
logger = logging.getLogger(__name__)
import os
from dotenv import load_dotenv
load_dotenv()

 
 
# Connection object for reuse
_connection = None

async def get_rabbitmq_connection():
    """
    Get or establish a connection to RabbitMQ
    """
    global _connection
    if _connection is None or _connection.is_closed:
        try:
            _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise
    return _connection

async def send_message(exchange_name: str, routing_key: str, message: Dict[str, Any]):
    """
    Send a message to a RabbitMQ exchange
    
    Args:
        exchange_name: The name of the exchange
        routing_key: The routing key for the message
        message: The message content as a dictionary
    """
    try:
        connection = await get_rabbitmq_connection()
        channel = await connection.channel()
        
        # Declare exchange
        exchange = await channel.declare_exchange(
            exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Serialize message to JSON
        message_body = json.dumps(message).encode()
        
        # Create a message with content type
        amqp_message = aio_pika.Message(
            body=message_body,
            content_type="application/json" ,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        # Publish message
        await exchange.publish(
            amqp_message,
            routing_key=routing_key
        )
        print(f"Publishing event to exchange={exchange_name}, routing_key={routing_key}, payload={message}")
        #logger.info(f"Sent message to {exchange_name} with routing key {routing_key}")
    except Exception as e:
        print(f"Failed to send message to RabbitMQ: {str(e)}")
        raise

async def send_request_for_userInfo(userId: str,token:str, custom_payload: Dict[str, Any] = None):
    """
    Send a message to get user info
    
    """
    # UserInfoMessageRequest
    message = custom_payload or {
        "event": settings.USER_EVENT,
        "userId": userId,
        "token": token
    }
    
    await send_message(
        exchange_name=settings.USER_TOPIC1,
        routing_key=settings.USER_STATUS,
        message=message
    )
    print("Send Message Successfully!")
async def close_rabbitmq_connection():
    """
    Close the RabbitMQ connection
    """
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("Closed RabbitMQ connection")
        _connection = None