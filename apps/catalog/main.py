"""
Catalog service — отдаёт список товаров из PostgreSQL.
Намеренно простой: одна таблица products, пара эндпоинтов.
Это "чёрный ящик" — DevOps-обвязка важнее внутренностей.
"""
import os
import time

from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String, Numeric, text
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Конфигурация из окружения ---
# DATABASE_URL приходит снаружи (из docker-compose / k8s), а не хардкодится.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://catalog:catalog@localhost:5432/catalog",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)


app = FastAPI(title="Catalog Service")


def wait_for_db(retries: int = 10, delay: float = 2.0) -> None:
    """Ждём, пока Postgres поднимется (важно в контейнерах — БД стартует не мгновенно)."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            print(f"[catalog] DB not ready (attempt {attempt}/{retries}), retrying...")
            time.sleep(delay)
    raise RuntimeError("Database is not reachable")


@app.on_event("startup")
def startup() -> None:
    wait_for_db()
    Base.metadata.create_all(engine)
    # Наполним таблицу демо-товарами, если пусто.
    with SessionLocal() as session:
        if session.query(Product).count() == 0:
            session.add_all([
                Product(name="Keyboard", price=49.90),
                Product(name="Mouse", price=25.00),
                Product(name="Monitor", price=199.99),
            ])
            session.commit()


@app.get("/health")
def health() -> dict:
    """Health-check — понадобится в Docker/k8s, чтобы знать, жив ли сервис."""
    return {"status": "ok"}


@app.get("/products")
def list_products() -> list[dict]:
    with SessionLocal() as session:
        products = session.query(Product).all()
        return [
            {"id": p.id, "name": p.name, "price": float(p.price)}
            for p in products
        ]
