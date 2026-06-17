import os
import csv
import io
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job, Transaction, JobSummary
from app.schemas import (
    JobOut,
    JobStatusOut,
    TransactionOut,
    CategorySpend,
    NarrativeSummary,
    JobResultsOut,
    JobListOut,
)
from app.tasks.processing import process_job
from app.config import settings

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_job(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, detail="Only CSV files are accepted")

    content = await file.read()
    try:
        reader = csv.DictReader(io.StringIO(content.decode()))
        rows = list(reader)
    except Exception:
        raise HTTPException(400, detail="Invalid CSV file")

    job = Job(
        filename=file.filename,
        status="pending",
        row_count_raw=len(rows),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(settings.UPLOAD_DIR, f"{job.id}.csv")
    with open(filepath, "wb") as f:
        f.write(content)

    process_job.delay(job.id)

    return {"job_id": job.id}


@router.get("/{job_id}/status", response_model=JobStatusOut)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")

    result = JobStatusOut(id=job.id, status=job.status, error_message=job.error_message)
    if job.status == "completed":
        summary = db.query(JobSummary).filter(
            JobSummary.job_id == job_id
        ).first()
        if summary:
            result.summary = {
                "total_spend_inr": summary.total_spend_inr,
                "total_spend_usd": summary.total_spend_usd,
                "anomaly_count": summary.anomaly_count,
                "risk_level": summary.risk_level,
            }
    return result


@router.get("/{job_id}/results", response_model=JobResultsOut)
def get_job_results(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(400, detail="Job not yet completed")

    txns = (
        db.query(Transaction)
        .filter(Transaction.job_id == job_id)
        .all()
    )
    anomalies = [t for t in txns if t.is_anomaly]
    summary = db.query(JobSummary).filter(
        JobSummary.job_id == job_id
    ).first()

    cat_spend_map = {}
    for t in txns:
        cat = t.llm_category or t.category or "Uncategorised"
        if cat not in cat_spend_map:
            cat_spend_map[cat] = {"category": cat, "count": 0, "total": 0.0}
        cat_spend_map[cat]["count"] += 1
        cat_spend_map[cat]["total"] += (t.amount or 0)

    narrative = None
    if summary:
        narrative = NarrativeSummary(
            total_spend_inr=summary.total_spend_inr or 0,
            total_spend_usd=summary.total_spend_usd or 0,
            top_merchants=summary.top_merchants or [],
            anomaly_count=summary.anomaly_count or 0,
            narrative=summary.narrative or "",
            risk_level=summary.risk_level or "low",
        )

    return JobResultsOut(
        transactions=[TransactionOut.from_txn(t) for t in txns],
        anomalies=[TransactionOut.from_txn(t) for t in anomalies],
        category_spend=[CategorySpend(**c) for c in cat_spend_map.values()],
        narrative_summary=narrative,
    )


@router.get("", response_model=list[JobListOut])
def list_jobs(
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return jobs
