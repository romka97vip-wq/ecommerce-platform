"""
Orders service — принимает заказы (producer).
Паттерн: НЕ обрабатывает заказ сам, а пишет его в Postgres со статусом
'pending' и кладёт задание в очередь RabbitMQ, сразу отвечая клиенту.
Обработку делает отдельный worker (consumer). Это асинхронность/decoupling.
"""
import os
import time
import json

import pika
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://orders:orders@localhost:5432/orders")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = "orders"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending")


app = FastAPI(title="Orders Service")


class OrderRequest(BaseModel):
    product_id: int
    quantity: int


def wait_for_db(retries: int = 15, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            print(f"[orders] DB not ready ({attempt}/{retries}), retrying...")
            time.sleep(delay)
    raise RuntimeError("Database is not reachable")


def publish_to_queue(order_id: int) -> None:
    """Кладём задание в RabbitMQ."""
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps({"order_id": order_id}),
        properties=pika.BasicProperties(delivery_mode=2),  # сообщение переживёт рестарт брокера
    )
    connection.close()


@app.on_event("startup")
def startup() -> None:
    wait_for_db()
    Base.metadata.create_all(engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/orders")
def create_order(req: OrderRequest) -> dict:
    # 1. Сохраняем заказ в БД со статусом pending
    with SessionLocal() as session:
        order = Order(product_id=req.product_id, quantity=req.quantity, status="pending")
        session.add(order)
        session.commit()
        order_id = order.id
    # 2. Кладём задание в очередь (worker обработает асинхронно)
    publish_to_queue(order_id)
    # 3. Сразу отвечаем клиенту — не ждём обработки
    return {"order_id": order_id, "status": "pending"}


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    with SessionLocal() as session:
        order = session.get(Order, order_id)
        if order is None:
            return {"error": "not found"}
        return {
            "order_id": order.id,
            "product_id": order.product_id,
            "quantity": order.quantity,
            "status": order.status,
        }
