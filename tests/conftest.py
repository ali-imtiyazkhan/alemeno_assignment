import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_transactions.db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_csv():
    return (
        "txn_id,date,merchant,amount,currency,status,category,account_id,notes\n"
        "TXN001,15-01-2024,Amazon,5000.00,INR,success,Shopping,ACC001,\n"
        "TXN002,2024/02/10,Swiggy,$250.00,USD,failed,,ACC002,SUSPICIOUS\n"
        "TXN003,10-03-2024,Flipkart,3000.00,INR,SUCCESS,Shopping,ACC001,\n"
        "TXN001,15-01-2024,Amazon,5000.00,INR,success,Shopping,ACC001,\n"
    )


@pytest.fixture
def sample_csv_invalid():
    return b"not,csv,format\nthis|is|not|csv"
