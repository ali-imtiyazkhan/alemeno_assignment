from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base
from app.api.jobs import router as jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Transaction Processing Pipeline",
    description="AI-Powered Transaction Processing API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs_router, prefix="/jobs")
