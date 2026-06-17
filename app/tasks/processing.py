import os
import re
import json
import time
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Job, Transaction, JobSummary
from app.tasks.worker import celery_app
from app.config import settings

CATEGORIES = [
    "Food", "Shopping", "Travel", "Transport",
    "Utilities", "Cash Withdrawal", "Entertainment", "Other",
]

DOMESTIC_MERCHANTS = ["Swiggy", "Ola", "IRCTC"]


def normalize_date(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    for fmt in ("%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def clean_data(df):
    df = df.copy()
    df["date"] = df["date"].apply(normalize_date)
    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .astype(float)
    )
    df["currency"] = df["currency"].str.upper()
    df["status"] = df["status"].str.upper()
    df["category"] = df["category"].fillna("Uncategorised")
    df = df.drop_duplicates()
    df = df.reset_index(drop=True)
    return df


def detect_anomalies(df):
    df = df.copy()
    df["is_anomaly"] = False
    df["anomaly_reason"] = ""

    for account in df["account_id"].unique():
        mask = df["account_id"] == account
        median = df.loc[mask, "amount"].median()
        if pd.isna(median) or median == 0:
            continue
        outlier_mask = mask & (df["amount"] > 3 * median)
        df.loc[outlier_mask, "is_anomaly"] = True
        df.loc[outlier_mask, "anomaly_reason"] = (
            df.loc[outlier_mask, "anomaly_reason"] +
            "Amount exceeds 3x account median; "
        )

    usd_domestic = (
        (df["currency"] == "USD") &
        (df["merchant"].isin(DOMESTIC_MERCHANTS))
    )
    df.loc[usd_domestic, "is_anomaly"] = True
    df.loc[usd_domestic, "anomaly_reason"] = (
        df.loc[usd_domestic, "anomaly_reason"] +
        "USD transaction with domestic-only merchant; "
    )

    df["anomaly_reason"] = df["anomaly_reason"].str.strip("; ")
    return df


def extract_json(text):
    if not text:
        return None
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_llm():
    key = settings.GEMINI_API_KEY
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-flash-latest")


def call_llm_with_retry(llm, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = llm.generate_content(prompt)
            return resp.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    return None


def batch_classify(df_uncategorized, llm):
    if df_uncategorized.empty or llm is None:
        return {}

    txns_lines = []
    for i, row in df_uncategorized.iterrows():
        notes = row.get("notes", "")
        txns_lines.append(
            f"Index {i}: merchant={row['merchant']}, amount={row['amount']}, "
            f"currency={row['currency']}, notes={notes}"
        )

    prompt = (
        "You are a transaction classifier. For each transaction below, assign exactly one category "
        f"from: {', '.join(CATEGORIES)}.\n"
        "Return ONLY a JSON array of objects with fields 'index' (integer) and 'category' (string).\n"
        "Transactions:\n" + "\n".join(txns_lines)
    )

    text = call_llm_with_retry(llm, prompt)
    results = extract_json(text)
    if not isinstance(results, list):
        return {}

    mapping = {}
    for item in results:
        idx = item.get("index")
        cat = item.get("category")
        if idx is not None and cat in CATEGORIES:
            mapping[idx] = cat
    return mapping


def _to_native(val):
    if hasattr(val, "item"):
        return val.item()
    if isinstance(val, (float, int)):
        return val
    return float(val) if val else 0


def generate_narrative_summary(df, anomaly_count, llm):
    total_inr = _to_native(df[df["currency"] == "INR"]["amount"].sum())
    total_usd = _to_native(df[df["currency"] == "USD"]["amount"].sum())
    top_merchants_dict = (
        df.groupby("merchant")["amount"]
        .sum()
        .nlargest(3)
        .to_dict()
    )
    top_merchants_list = list(top_merchants_dict.keys())
    total_inr_val = _to_native(round(total_inr, 2)) if total_inr else 0.0
    total_usd_val = _to_native(round(total_usd, 2)) if total_usd else 0.0

    result = {
        "total_spend_inr": total_inr_val,
        "total_spend_usd": total_usd_val,
        "top_merchants": top_merchants_list,
        "anomaly_count": anomaly_count,
        "narrative": "",
        "risk_level": "low",
    }

    if llm is None:
        return result

    prompt = (
        "You are a financial analyst. Based on these transaction statistics, produce a JSON summary.\n"
        f"Total spend in INR: {total_inr_val:.2f}\n"
        f"Total spend in USD: {total_usd_val:.2f}\n"
        f"Top 3 merchants: {json.dumps(top_merchants_dict)}\n"
        f"Number of flagged anomalies: {anomaly_count}\n"
        "Return a JSON object with:\n"
        '- "narrative": a 2-3 sentence spending analysis\n'
        '- "risk_level": one of "low", "medium", or "high"\n'
        "Return ONLY valid JSON."
    )

    text = call_llm_with_retry(llm, prompt)
    llm_data = extract_json(text) or {}
    result["narrative"] = llm_data.get("narrative", "")
    result["risk_level"] = llm_data.get("risk_level", "low")
    return result


def save_transactions(db: Session, job_id: int, df):
    for _, row in df.iterrows():
        txn = Transaction(
            job_id=job_id,
            txn_id=row.get("txn_id") if pd.notna(row.get("txn_id")) else None,
            date=row["date"],
            merchant=row.get("merchant"),
            amount=_to_native(row["amount"]),
            currency=row["currency"],
            status=row["status"],
            category=row.get("category"),
            account_id=row.get("account_id"),
            is_anomaly=row.get("is_anomaly", False),
            anomaly_reason=row.get("anomaly_reason") or None,
            llm_category=row.get("llm_category") or None,
            llm_failed=row.get("llm_failed", False),
        )
        db.add(txn)


@celery_app.task(bind=True)
def process_job(self, job_id: int):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()

        filepath = os.path.join(settings.UPLOAD_DIR, f"{job_id}.csv")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Uploaded file {filepath} not found")

        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip().str.lower()

        job.row_count_raw = len(df)
        db.commit()

        df_clean = clean_data(df)
        job.row_count_clean = len(df_clean)
        db.commit()

        df_clean = detect_anomalies(df_clean)

        llm = get_llm()
        uncat_mask = df_clean["category"] == "Uncategorised"
        df_uncat = df_clean[uncat_mask].copy()

        llm_mapping = {}
        if not df_uncat.empty:
            try:
                llm_mapping = batch_classify(df_uncat, llm)
            except Exception:
                pass

        df_clean["llm_category"] = None
        df_clean["llm_failed"] = False
        for idx, row in df_uncat.iterrows():
            cat = llm_mapping.get(idx)
            if cat:
                df_clean.at[idx, "llm_category"] = cat
                df_clean.at[idx, "category"] = cat
            else:
                df_clean.at[idx, "llm_failed"] = True

        anomaly_count = int(df_clean["is_anomaly"].sum())

        summary_data = generate_narrative_summary(df_clean, anomaly_count, llm)

        save_transactions(db, job_id, df_clean)

        job_summary = JobSummary(
            job_id=job_id,
            total_spend_inr=summary_data["total_spend_inr"],
            total_spend_usd=summary_data["total_spend_usd"],
            top_merchants=summary_data["top_merchants"],
            anomaly_count=summary_data["anomaly_count"],
            narrative=summary_data["narrative"],
            risk_level=summary_data["risk_level"],
        )
        db.add(job_summary)

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
