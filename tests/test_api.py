from unittest.mock import patch
from sqlalchemy.orm import Session

from app.models import Job


@patch("app.api.jobs.process_job.delay")
class TestUpload:
    def test_upload_csv_returns_job_id(self, mock_delay, client, sample_csv):
        resp = client.post(
            "/jobs/upload",
            files={"file": ("test.csv", sample_csv, "text/csv")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], int)
        mock_delay.assert_called_once()

    def test_upload_non_csv_returns_400(self, mock_delay, client):
        resp = client.post(
            "/jobs/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        mock_delay.assert_not_called()


@patch("app.api.jobs.process_job.delay")
class TestListJobs:
    def test_list_jobs_empty(self, mock_delay, client):
        resp = client.get("/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_jobs_with_filter(self, mock_delay, client, db, sample_csv):
        client.post(
            "/jobs/upload",
            files={"file": ("test.csv", sample_csv, "text/csv")},
        )
        resp = client.get("/jobs?status=pending")
        assert resp.status_code == 200

    def test_list_jobs_returns_created_job(self, mock_delay, client, db, sample_csv):
        client.post(
            "/jobs/upload",
            files={"file": ("test.csv", sample_csv, "text/csv")},
        )
        resp = client.get("/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) >= 1
        assert jobs[0]["filename"] == "test.csv"


@patch("app.api.jobs.process_job.delay")
class TestJobStatus:
    def test_status_of_nonexistent_job(self, mock_delay, client):
        resp = client.get("/jobs/99999/status")
        assert resp.status_code == 404

    def test_status_of_pending_job(self, mock_delay, client, db, sample_csv):
        resp = client.post(
            "/jobs/upload",
            files={"file": ("test.csv", sample_csv, "text/csv")},
        )
        job_id = resp.json()["job_id"]
        status_resp = client.get(f"/jobs/{job_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["id"] == job_id
        assert data["status"] == "pending"


class TestJobResults:
    def test_results_of_nonexistent_job(self, client):
        resp = client.get("/jobs/99999/results")
        assert resp.status_code == 404

    def test_results_of_pending_job(self, client, db):
        job_obj = Job(filename="manual.csv", status="pending", row_count_raw=5)
        db.add(job_obj)
        db.commit()
        db.refresh(job_obj)

        resp = client.get(f"/jobs/{job_obj.id}/results")
        assert resp.status_code == 400
        assert "not yet completed" in resp.json()["detail"].lower()
