import json
import os
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SETTINGS_FILE = os.getenv("NOTIFICATION_SETTINGS_FILE", "notification_settings.json")

DEFAULT_SETTINGS = {
    "timezone": "Asia/Singapore",
    "digestTime": "10:00",
    "rules": {
        "feesDue30": True,
        "bonusesDue30": True,
        "reapplyEligible": True,
        "cardExpiry60": False,
        "bonusProgressWeekly": False,
    },
}


def normalize_settings(settings):
    incoming = settings or {}
    normalized = {
        "timezone": str(incoming.get("timezone") or DEFAULT_SETTINGS["timezone"]),
        "digestTime": str(incoming.get("digestTime") or DEFAULT_SETTINGS["digestTime"]),
        "rules": {**DEFAULT_SETTINGS["rules"], **(incoming.get("rules") or {})},
    }
    notification_timezone(normalized["timezone"])
    hour, minute = parse_digest_time(normalized["digestTime"])
    normalized["digestTime"] = f"{hour:02d}:{minute:02d}"
    normalized["rules"] = {key: bool(value) for key, value in normalized["rules"].items()}
    return normalized


def load_notification_settings():
    path = Path(SETTINGS_FILE)
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        return normalize_settings(json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError, ValueError):
        return DEFAULT_SETTINGS.copy()


def save_notification_settings(settings):
    normalized = normalize_settings(settings)
    path = Path(SETTINGS_FILE)
    if path.is_dir():
        shutil.rmtree(path)
    path.write_text(json.dumps(normalized, indent=2))
    return normalized


def notification_timezone(name=None):
    timezone_name = name or load_notification_settings()["timezone"]
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc


def parse_digest_time(value):
    try:
        hour_text, minute_text = str(value).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Notification time must be HH:MM") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Notification time must be HH:MM")
    return hour, minute
