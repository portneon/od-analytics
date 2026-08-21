import io

SAMPLE_CSV = """FROM,TO,SUBJECT,DATE,STATUS
alerts@acme.com,a@gmail.com,Attendance Alert,2026-07-01 09:00:00,Delivered
alerts@acme.com,b@gmail.com,Payment Reminder,2026-07-01 09:05:00,Delivered
alerts@acme.com,c@yahoo.com,Attendance Alert,2026-07-01 09:10:00,Hard Bounce
"""


def _register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Acme Inc", "name": "Alice", "email": "alice@acme.com", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": "alice@acme.com", "password": "password123"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload(client, headers, name="Test Dataset"):
    files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV.encode("utf-8")), "text/csv")}
    resp = client.post("/api/v1/datasets/upload", headers=headers, files=files, data={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["dataset_id"]


def test_executive_summary_empty_tenant_returns_zeros_not_error(client):
    headers = _register_and_login(client)
    resp = client.get("/api/v1/executive/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_datasets"] == 0
    assert data["total_emails"] == 0
    assert data["delivery_rate"] == 0.0
    assert data["insights"] == []
    assert data["recent_datasets"] == []


def test_executive_summary_rolls_up_across_datasets(client):
    headers = _register_and_login(client)
    _upload(client, headers, "Dataset One")
    _upload(client, headers, "Dataset Two")

    resp = client.get("/api/v1/executive/summary", headers=headers)
    data = resp.json()["data"]
    assert data["total_datasets"] == 2
    assert data["usable_datasets"] == 2
    assert data["total_emails"] == 6  # 3 events x 2 datasets
    assert data["hard_bounces"] == 2
    assert len(data["recent_datasets"]) == 2


def test_executive_summary_is_tenant_scoped(client):
    headers_a = _register_and_login(client)
    _upload(client, headers_a)

    client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Other Co", "name": "Bob", "email": "bob-exec@other.com", "password": "password123"},
    )
    login_b = client.post("/api/v1/auth/login", json={"email": "bob-exec@other.com", "password": "password123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['access_token']}"}

    resp = client.get("/api/v1/executive/summary", headers=headers_b)
    data = resp.json()["data"]
    assert data["total_datasets"] == 0


def test_executive_timeline_rolls_up_daily_metrics(client):
    headers = _register_and_login(client)
    _upload(client, headers)

    resp = client.get("/api/v1/executive/timeline", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == "2026-07-01"
    assert data[0]["total_emails"] == 3
