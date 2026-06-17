from fastapi import FastAPI
from app.database import engine, Base
from app.api.jobs import router as jobs_router

app = FastAPI(
    title="Transaction Processing Pipeline",
    description="AI-Powered Transaction Processing API",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(jobs_router, prefix="/jobs")
