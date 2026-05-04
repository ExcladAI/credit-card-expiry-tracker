from fastapi.testclient import TestClient

import api
import data_store
import notification_settings


def configure_paths(tmp_path, monkeypatch):
    data_file = tmp_path / "cards.csv"
    tags_file = tmp_path / "tags.json"
    image_dir = tmp_path / "images"
    backup_dir = tmp_path / "backups"
    settings_file = tmp_path / "notification_settings.json"

    for module in (data_store, api):
        monkeypatch.setattr(module, "DATA_FILE", str(data_file))
        monkeypatch.setattr(module, "TAGS_FILE", str(tags_file), raising=False)
        monkeypatch.setattr(module, "IMAGE_DIR", str(image_dir))
        monkeypatch.setattr(module, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(data_store, "LOCK_FILE", str(data_file) + ".lock")
    monkeypatch.setattr(notification_settings, "SETTINGS_FILE", str(settings_file))


def test_create_update_and_delete_card(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    created = client.post(
        "/api/cards",
        json={
            "bank": "DBS",
            "name": "Altitude Visa",
            "annualFee": 196.2,
            "expiry": "05/27",
            "last4": "1234",
            "tags": ["miles"],
            "bonus": {"status": "Not Started", "minSpend": 800, "currentSpend": 0},
        },
    )

    assert created.status_code == 200
    cards = created.json()
    assert len(cards) == 1
    assert cards[0]["id"]
    assert cards[0]["feeMonth"] == "May"

    card_id = cards[0]["id"]
    updated = client.post(f"/api/cards/{card_id}/spend", json={"amount": 800})
    assert updated.status_code == 200
    assert updated.json()[0]["bonus"]["status"] == "Met"

    deleted = client.delete(f"/api/cards/{card_id}")
    assert deleted.status_code == 200
    assert deleted.json() == []

    missing = client.delete(f"/api/cards/{card_id}")
    assert missing.status_code == 404


def test_tags_endpoint_removes_tag_from_cards(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    client.post("/api/tags", json={"tags": ["miles", "cashback"]})
    client.post("/api/cards", json={"bank": "UOB", "name": "One", "expiry": "06/27", "tags": ["miles"]})

    response = client.delete("/api/tags/miles")

    assert response.status_code == 200
    assert response.json()["tags"] == ["cashback"]
    assert response.json()["cards"][0]["tags"] == []


def test_explicit_fee_month_is_preserved(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    response = client.post(
        "/api/cards",
        json={
            "bank": "UOB",
            "name": "Lady's Solitaire",
            "expiry": "05/27",
            "feeMonth": "February",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["feeMonth"] == "February"


def test_sort_order_rejects_duplicates(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    first = client.post("/api/cards", json={"bank": "DBS", "name": "One"}).json()[0]
    second = client.post("/api/cards", json={"bank": "UOB", "name": "Two"}).json()[1]

    response = client.post("/api/sort-order", json={"orders": {first["id"]: 1, second["id"]: 1}})

    assert response.status_code == 400
    assert "unique" in response.json()["detail"]


def test_diagnostics_reports_missing_image(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    client.post(
        "/api/cards",
        json={
            "bank": "DBS",
            "name": "Altitude Visa",
            "imageFilename": "missing.png",
        },
    )

    response = client.get("/api/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["issues"] == 1
    assert body["issues"][0]["type"] == "missing_image"


def test_bot_status_reports_unconfigured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    client = TestClient(api.app)

    response = client.get("/api/bot/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["connected"] is False


def test_bot_test_sends_message(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    sent = {}
    def fake_telegram_request(method, payload=None):
        sent["payload"] = payload
        return {"message_id": 99}
    monkeypatch.setattr(api, "telegram_request", fake_telegram_request)
    client = TestClient(api.app)

    response = client.post("/api/bot/test")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "messageId": 99}
    assert "SGT" in sent["payload"]["text"] or "+08" in sent["payload"]["text"]


def test_notification_settings_round_trip(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    payload = {
        "timezone": "Asia/Tokyo",
        "digestTime": "08:30",
        "rules": {
            "feesDue30": False,
            "bonusesDue30": True,
            "reapplyEligible": False,
            "cardExpiry60": True,
            "bonusProgressWeekly": True,
        },
    }
    updated = client.put("/api/notification-settings", json=payload)
    fetched = client.get("/api/notification-settings")

    assert updated.status_code == 200
    assert updated.json()["timezone"] == "Asia/Tokyo"
    assert updated.json()["digestTime"] == "08:30"
    assert updated.json()["rules"]["feesDue30"] is False
    assert fetched.json() == updated.json()


def test_notification_settings_reject_bad_timezone(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    client = TestClient(api.app)

    response = client.put("/api/notification-settings", json={"timezone": "Mars/Base", "digestTime": "10:00"})

    assert response.status_code == 400
