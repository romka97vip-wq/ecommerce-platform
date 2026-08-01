"""
Cart service — корзина пользователя, хранится в Redis.
Redis выбран потому что: быстро (в памяти), простые пары ключ-значение,
поддержка TTL (заброшенная корзина сама удалится). Данные не критичны —
потерять корзину не страшно, в отличие от каталога/заказов.
Это "чёрный ящик" — DevOps-обвязка важнее внутренностей.
"""
import os
import time

import redis
from fastapi import FastAPI
from pydantic import BaseModel

# Адрес Redis приходит из окружения (compose/k8s), не хардкодится.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Корзина живёт 24 часа, потом Redis сам её удалит (TTL).
CART_TTL_SECONDS = 24 * 60 * 60

r = redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="Cart Service")


class CartItem(BaseModel):
    product_id: int
    quantity: int


def wait_for_redis(retries: int = 10, delay: float = 2.0) -> None:
    """Ждём, пока Redis поднимется (в контейнерах зависимости стартуют не мгновенно)."""
    for attempt in range(1, retries + 1):
        try:
            r.ping()
            return
        except Exception:
            print(f"[cart] Redis not ready (attempt {attempt}/{retries}), retrying...")
            time.sleep(delay)
    raise RuntimeError("Redis is not reachable")


@app.on_event("startup")
def startup() -> None:
    wait_for_redis()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/cart/{user_id}")
def get_cart(user_id: str) -> dict:
    """Вернуть содержимое корзины пользователя."""
    items = r.hgetall(f"cart:{user_id}")
    return {
        "user_id": user_id,
        "items": [{"product_id": int(k), "quantity": int(v)} for k, v in items.items()],
    }


@app.post("/cart/{user_id}/items")
def add_item(user_id: str, item: CartItem) -> dict:
    """Добавить товар в корзину (обновляет количество)."""
    key = f"cart:{user_id}"
    r.hset(key, str(item.product_id), item.quantity)
    r.expire(key, CART_TTL_SECONDS)  # продлеваем жизнь корзины
    return {"status": "added", "product_id": item.product_id, "quantity": item.quantity}


@app.delete("/cart/{user_id}")
def clear_cart(user_id: str) -> dict:
    """Очистить корзину."""
    r.delete(f"cart:{user_id}")
    return {"status": "cleared", "user_id": user_id}
