import io

SAMPLE_CSV = """FROM,TO,SUBJECT,DATE,STATUS,SMTP CODE,DELIVERY INFORMATION,REMOTE IP,REMOTE MTA,RELAY,MESSAGE ID
alerts@acme.com,a@gmail.com,Attendance Alert,2026-07-01 09:00:00,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<1@acme.com>
alerts@acme.com,b@gmail.com,Payment Reminder,2026-07-01 09:05:00,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<2@acme.com>
alerts@acme.com,c@yahoo.com,Attendance Alert,2026-07-01 09:10:00,Hard Bounce,5.1.1,550 5.1.1 no such user,10.0.0.2,mx2.zoho.com,relay-a,<3@acme.com>
alerts@acme.com,d@yahoo.com,Payment Reminder,2026-07-01 09:15:00,Soft Bounce,4.2.2,mailbox full,10.0.0.2,mx2.zoho.com,relay-a,<4@acme.com>
alerts@acme.com,not-an-email,Attendance Alert,2026-07-01 09:20:00,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<5@acme.com>
alerts@acme.com,e@gmail.com,Payment Reminder,,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<6@acme.com>
"""


def _upload(client):
    files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV.encode("utf-8")), "text/csv")}
    resp = client.post("/api/v1/datasets/upload", files=files, data={"name": "Test Dataset"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["dataset_id"]


def test_upload_processes_synchronously_in_background_task(client):
    dataset_id = _upload(client)

    status_resp = client.get(f"/api/v1/datasets/{dataset_id}/status")
    assert status_resp.json()["data"]["status"] in ("COMPLETED", "PARTIAL")


def test_data_quality_report_reflects_injected_bad_rows(client):
    dataset_id = _upload(client)

    quality = client.get(f"/api/v1/datasets/{dataset_id}/quality").json()["data"]
    assert quality["rows"] == 6
    assert quality["invalid_rows"] == 2  # malformed email row + missing timestamp row
    assert quality["malformed_emails"] == 1
    assert quality["missing_timestamps"] == 1
    assert quality["missing_open_data"] is True
    assert quality["missing_click_data"] is True


def test_overview_analytics_reflects_valid_rows(client):
    dataset_id = _upload(client)

    overview = client.get(f"/api/v1/datasets/{dataset_id}/analytics/overview").json()["data"]
    assert overview["total_emails"] == 4
    assert overview["successful"] == 2
    assert overview["hard_bounces"] == 1
    assert overview["soft_bounces"] == 1
    assert overview["delivery_rate"] == 50.0


def test_bounce_reasons_have_business_labels(client):
    dataset_id = _upload(client)

    bounces = client.get(f"/api/v1/datasets/{dataset_id}/analytics/bounces").json()["data"]
    categories = {b["bounce_category"] for b in bounces}
    assert "MAILBOX_NOT_FOUND" in categories
    assert "MAILBOX_FULL" in categories
    labels = {b["business_label"] for b in bounces}
    assert "Recipient mailbox does not exist" in labels


def test_application_metrics_classified_by_subject(client):
    dataset_id = _upload(client)

    apps = client.get(f"/api/v1/datasets/{dataset_id}/analytics/applications").json()["data"]
    categories = {a["category"] for a in apps}
    assert "Attendance" in categories
    assert "Payment" in categories


def test_recipient_risk_scores_computed(client):
    dataset_id = _upload(client)

    recipients = client.get(
        f"/api/v1/datasets/{dataset_id}/analytics/recipients", params={"sort_by": "failure_rate"}
    ).json()["data"]
    assert len(recipients) == 4
    assert all("risk_score" in r for r in recipients)


def test_ask_endpoint_falls_back_without_llm_key(client):
    dataset_id = _upload(client)

    resp = client.post(f"/api/v1/datasets/{dataset_id}/ask", json={"question": "Which domain has the highest bounce rate?"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ai_available"] is False
    assert len(data["tool_calls"]) == 1


def test_report_pdf_download(client):
    dataset_id = _upload(client)

    resp = client.post(f"/api/v1/datasets/{dataset_id}/reports", params={"format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


COMMA_RECIPIENTS_CSV = """FROM,TO,SUBJECT,DATE,STATUS,SMTP CODE,DELIVERY INFORMATION,REMOTE IP,REMOTE MTA,RELAY,MESSAGE ID
alerts@acme.com,"a@gmail.com, b@gmail.com",Attendance Alert,2026-07-01 09:00:00,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<1@acme.com>
alerts@acme.com,c@gmail.com,Payment Reminder,2026-07-01 09:05:00,Delivered,,,10.0.0.1,mx1.zoho.com,relay-a,<2@acme.com>
"""


def test_comma_separated_recipients_are_split_into_separate_events(client):
    files = {"file": ("test.csv", io.BytesIO(COMMA_RECIPIENTS_CSV.encode("utf-8")), "text/csv")}
    resp = client.post("/api/v1/datasets/upload", files=files, data={"name": "Comma Test"})
    dataset_id = resp.json()["data"]["dataset_id"]

    quality = client.get(f"/api/v1/datasets/{dataset_id}/quality").json()["data"]
    assert quality["rows"] == 2
    assert quality["invalid_rows"] == 0

    overview = client.get(f"/api/v1/datasets/{dataset_id}/analytics/overview").json()["data"]
    assert overview["total_emails"] == 3  # a@gmail.com, b@gmail.com, c@gmail.com

    recipients = client.get(f"/api/v1/datasets/{dataset_id}/analytics/recipients").json()["data"]
    assert {r["name"] for r in recipients} == {"a@gmail.com", "b@gmail.com", "c@gmail.com"}

    status_resp = client.get(f"/api/v1/datasets/{dataset_id}/status").json()["data"]
    assert status_resp["status"] == "COMPLETED"  # fan-out must not make failed_rows go negative


ALL_INVALID_CSV = """FROM,TO,SUBJECT,DATE,STATUS
alerts@acme.com,not-an-email,Attendance Alert,,Delivered
alerts@acme.com,also-not-an-email,Payment Reminder,,Delivered
"""


def test_dataset_with_zero_valid_rows_is_marked_failed_not_partial(client):
    files = {"file": ("bad.csv", io.BytesIO(ALL_INVALID_CSV.encode("utf-8")), "text/csv")}
    resp = client.post("/api/v1/datasets/upload", files=files, data={"name": "All Invalid"})
    dataset_id = resp.json()["data"]["dataset_id"]

    status_resp = client.get(f"/api/v1/datasets/{dataset_id}/status").json()["data"]
    assert status_resp["status"] == "FAILED"


def test_delete_dataset_removes_it_and_its_events(client):
    dataset_id = _upload(client)

    resp = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    get_resp = client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_resp.status_code == 404

    list_resp = client.get("/api/v1/datasets")
    assert dataset_id not in {d["id"] for d in list_resp.json()["data"]}
