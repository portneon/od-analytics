import io

SAMPLE_CSV = """FROM,TO,SUBJECT,DATE,STATUS
alerts@acme.com,a@gmail.com,Attendance Alert,2026-07-01 09:00:00,Delivered
alerts@acme.com,b@gmail.com,Payment Reminder,2026-07-01 09:05:00,Delivered
alerts@acme.com,c@yahoo.com,Attendance Alert,2026-07-01 09:10:00,Hard Bounce
"""


def _upload(client, name="Test Dataset"):
    files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV.encode("utf-8")), "text/csv")}
    resp = client.post("/api/v1/datasets/upload", files=files, data={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["dataset_id"]


def test_executive_summary_with_no_datasets_returns_zeros_not_error(client):
    resp = client.get("/api/v1/executive/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_datasets"] == 0
    assert data["total_emails"] == 0
    assert data["delivery_rate"] == 0.0
    assert data["insights"] == []
    assert data["recent_datasets"] == []


def test_executive_summary_rolls_up_across_datasets(client):
    _upload(client, "Dataset One")
    _upload(client, "Dataset Two")

    resp = client.get("/api/v1/executive/summary")
    data = resp.json()["data"]
    assert data["total_datasets"] == 2
    assert data["usable_datasets"] == 2
    assert data["total_emails"] == 6  # 3 events x 2 datasets
    assert data["hard_bounces"] == 2
    assert len(data["recent_datasets"]) == 2


def test_executive_timeline_rolls_up_daily_metrics(client):
    _upload(client)

    resp = client.get("/api/v1/executive/timeline")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == "2026-07-01"
    assert data[0]["total_emails"] == 3
