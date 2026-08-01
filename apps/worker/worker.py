"""
Worker — обработчик заказов (consumer).
Слушает очередь RabbitMQ, берёт заказы по одному, "обрабатывает"
(в демо — ждёт 3 сек) и меняет статус в Postgres на 'completed'.
Не веб-сервер: нет HTTP, нет порта. Просто бесконечно слушает очередь.
"""
import os
import time
import json

import pika
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalog:catalog@localhost:5432/catalog")
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


def wait_for_deps(retries: int = 30, delay: float = 2.0):
    """Ждём и БД, и RabbitMQ."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)).close()
            return
        except Exception:
            print(f"[worker] deps not ready ({attempt}/{retries}), retrying...")
            time.sleep(delay)
    raise RuntimeError("Dependencies not reachable")


def process_order(ch, method, properties, body):
    """Обработать одно сообщение из очереди."""
    data = json.loads(body)
    order_id = data["order_id"]
    print(f"[worker] processing order {order_id}...")
    time.sleep(3)  # имитация обработки (проверка оплаты, склад и т.п.)
    with SessionLocal() as session:
        order = session.get(Order, order_id)
        if order:
            order.status = "completed"
            session.commit()
            print(f"[worker] order {order_id} completed")
    # Подтверждаем обработку (ack) — теперь сообщение удаляется из очереди
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    wait_for_deps()
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    # Брать по одному сообщению за раз (справедливое распределение между воркерами)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_order)
    print("[worker] waiting for messages...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
