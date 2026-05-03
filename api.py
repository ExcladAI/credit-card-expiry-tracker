import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from data_store import (
    BACKUP_DIR,
    DATA_FILE,
    DEFAULT_IMAGE,
    IMAGE_DIR,
    MONTH_MAP,
    TAGS_FILE,
    get_card_by_id,
    load_data,
    new_card_id,
    update_data,
)

app = FastAPI(title="Credit Card Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(IMAGE_DIR).mkdir(parents=True, exist_ok=True)
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/card_images", StaticFiles(directory=IMAGE_DIR), name="card_images")


def _json_safe(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def card_to_dict(row):
    data = {column: _json_safe(row[column]) for column in row.index}
    return {
        "id": data["Card ID"],
        "bank": data["Bank"],
        "name": data["Card Name"],
        "annualFee": data["Annual Fee"],
        "expiry": data["Card Expiry (MM/YY)"],
        "feeMonth": data["Month of Annual Fee"],
        "dates": {
            "applied": data["Date Applied"],
            "approved": data["Date Approved"],
            "received": data["Date Received Card"],
            "activated": data["Date Activated Card"],
            "firstCharge": data["First Charge Date"],
            "cancelled": data["Cancellation Date"],
            "reapply": data["Re-apply Date"],
        },
        "imageFilename": data["Image Filename"] or DEFAULT_IMAGE,
        "sortOrder": data["Sort Order"],
        "notes": data["Notes"],
        "tags": [tag.strip() for tag in str(data["Tags"] or "").split(",") if tag.strip()],
        "bonus": {
            "offer": data["Bonus Offer"],
            "minSpend": data["Min Spend"],
            "deadline": data["Min Spend Deadline"],
            "status": data["Bonus Status"],
            "currentSpend": data["Current Spend"],
        },
        "last4": data["Last 4 Digits"],
        "feeHistory": {
            "waivedCount": data["FeeWaivedCount"],
            "paidCount": data["FeePaidCount"],
            "lastActionYear": data["LastFeeActionYear"],
            "lastAction": data["LastFeeAction"],
        },
        "status": "cancelled" if data["Cancellation Date"] else "active",
    }


def cards_response():
    df = load_data().sort_values(by="Sort Order")
    return [card_to_dict(row) for _, row in df.iterrows()]


def explicit_fee_month(payload, expiry):
    requested = str(payload.get("feeMonth") or "").strip()
    if requested:
        return requested
    expiry_month = expiry.split("/", 1)[0] if "/" in expiry else payload.get("expiryMonth", "")
    return MONTH_MAP.get(str(expiry_month).zfill(2), "")


def parse_card_payload(payload):
    expiry = str(payload.get("expiry") or "")
    fee_month = explicit_fee_month(payload, expiry)
    tags = payload.get("tags") or []
    bonus = payload.get("bonus") or {}
    dates = payload.get("dates") or {}
    fee_history = payload.get("feeHistory") or {}
    status = payload.get("status")
    cancellation_date = pd.to_datetime(dates.get("cancelled"), errors="coerce")
    reapply_date = pd.to_datetime(dates.get("reapply"), errors="coerce")
    if status == "active":
        cancellation_date = pd.NaT
        reapply_date = pd.NaT
    elif status == "cancelled" and pd.isna(cancellation_date):
        cancellation_date = pd.Timestamp.today().normalize()
        reapply_date = cancellation_date + pd.DateOffset(months=13)
    return {
        "Bank": payload.get("bank", ""),
        "Card Name": payload.get("name", ""),
        "Annual Fee": payload.get("annualFee", 0.0) or 0.0,
        "Card Expiry (MM/YY)": expiry,
        "Month of Annual Fee": fee_month,
        "Image Filename": payload.get("imageFilename") or DEFAULT_IMAGE,
        "Notes": payload.get("notes", ""),
        "Tags": ",".join(tags) if isinstance(tags, list) else str(tags or ""),
        "Bonus Offer": bonus.get("offer", ""),
        "Min Spend": bonus.get("minSpend", 0.0) or 0.0,
        "Min Spend Deadline": pd.to_datetime(bonus.get("deadline"), errors="coerce"),
        "Bonus Status": bonus.get("status", "Not Started") or "",
        "Last 4 Digits": payload.get("last4", ""),
        "Current Spend": bonus.get("currentSpend", 0.0) or 0.0,
        "Date Applied": pd.to_datetime(dates.get("applied"), errors="coerce"),
        "Date Approved": pd.to_datetime(dates.get("approved"), errors="coerce"),
        "Date Received Card": pd.to_datetime(dates.get("received"), errors="coerce"),
        "Date Activated Card": pd.to_datetime(dates.get("activated"), errors="coerce"),
        "First Charge Date": pd.to_datetime(dates.get("firstCharge"), errors="coerce"),
        "Cancellation Date": cancellation_date,
        "Re-apply Date": reapply_date,
        "FeeWaivedCount": fee_history.get("waivedCount", 0) or 0,
        "FeePaidCount": fee_history.get("paidCount", 0) or 0,
        "LastFeeActionYear": fee_history.get("lastActionYear", 0) or 0,
        "LastFeeAction": fee_history.get("lastAction", ""),
}


def diagnostics_response():
    df = load_data()
    cards = [card_to_dict(row) for _, row in df.sort_values(by="Sort Order").iterrows()]
    issues = []
    image_root = Path(IMAGE_DIR)

    for card in cards:
        label = f"{card['bank']} {card['name']}".strip() or card["id"]
        if not card["bank"] or not card["name"]:
            issues.append({"severity": "error", "type": "missing_identity", "cardId": card["id"], "message": f"{label} is missing bank or card name."})
        if card["imageFilename"] and card["imageFilename"] != DEFAULT_IMAGE and not (image_root / card["imageFilename"]).exists():
            issues.append({"severity": "warning", "type": "missing_image", "cardId": card["id"], "message": f"{label} references a missing image: {card['imageFilename']}."})
        if card["status"] == "active" and card["bonus"]["deadline"] and card["bonus"]["status"] in {"Not Started", "In Progress"}:
            deadline = pd.to_datetime(card["bonus"]["deadline"], errors="coerce")
            if not pd.isna(deadline) and deadline.date() < datetime.now().date():
                issues.append({"severity": "warning", "type": "overdue_bonus", "cardId": card["id"], "message": f"{label} has an overdue welcome bonus deadline."})
        if card["status"] == "active" and card["expiry"]:
            expiry = pd.to_datetime(f"01/{card['expiry']}", format="%d/%m/%y", errors="coerce")
            if not pd.isna(expiry) and expiry + pd.offsets.MonthEnd(0) < pd.Timestamp.today().normalize():
                issues.append({"severity": "warning", "type": "expired_card", "cardId": card["id"], "message": f"{label} appears to be expired."})

    duplicates = df[df["Sort Order"].duplicated(keep=False)].sort_values("Sort Order")
    for _, row in duplicates.iterrows():
        issues.append({
            "severity": "warning",
            "type": "duplicate_sort_order",
            "cardId": row["Card ID"],
            "message": f"{row['Bank']} {row['Card Name']} shares sort order {row['Sort Order']}.",
        })

    return {
        "counts": {
            "cards": len(cards),
            "active": sum(1 for card in cards if card["status"] == "active"),
            "cancelled": sum(1 for card in cards if card["status"] == "cancelled"),
            "issues": len(issues),
            "errors": sum(1 for issue in issues if issue["severity"] == "error"),
            "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
        },
        "issues": issues,
    }


def read_tags():
    if not Path(TAGS_FILE).exists():
        return []
    try:
        return sorted(set(json.loads(Path(TAGS_FILE).read_text())))
    except (json.JSONDecodeError, OSError):
        return []


def write_tags(tags):
    cleaned = sorted(set(tag.strip() for tag in tags if tag and tag.strip()))
    Path(TAGS_FILE).write_text(json.dumps(cleaned, indent=2))
    return cleaned


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/cards")
def list_cards():
    return cards_response()


@app.get("/api/diagnostics")
def diagnostics():
    return diagnostics_response()


@app.post("/api/cards")
async def create_card(payload: dict):
    values = parse_card_payload(payload)

    def add_card(df):
        max_sort = df["Sort Order"].max()
        values["Card ID"] = new_card_id()
        values["Sort Order"] = 1 if pd.isna(max_sort) or max_sort < 1 else int(max_sort + 1)
        return pd.concat([df, pd.DataFrame([values])], ignore_index=True)

    update_data(add_card)
    return cards_response()


@app.put("/api/cards/{card_id}")
async def update_card(card_id: str, payload: dict):
    values = parse_card_payload(payload)

    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        for column, value in values.items():
            df.loc[idx, column] = value
        return df

    update_data(mutate)
    return cards_response()


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: str):
    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return df[df["Card ID"] != card_id].reset_index(drop=True)

    update_data(mutate)
    return cards_response()


@app.post("/api/cards/{card_id}/cancel")
def cancel_card(card_id: str):
    cancel_date = pd.Timestamp.today().normalize()

    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        df.loc[idx, "Cancellation Date"] = cancel_date
        df.loc[idx, "Re-apply Date"] = cancel_date + pd.DateOffset(months=13)
        return df

    update_data(mutate)
    return cards_response()


@app.post("/api/cards/{card_id}/reactivate")
def reactivate_card(card_id: str):
    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        df.loc[idx, "Cancellation Date"] = pd.NaT
        df.loc[idx, "Re-apply Date"] = pd.NaT
        df.loc[idx, "LastFeeActionYear"] = 0
        df.loc[idx, "LastFeeAction"] = ""
        return df

    update_data(mutate)
    return cards_response()


@app.post("/api/cards/{card_id}/spend")
async def add_spend(card_id: str, payload: dict):
    amount = float(payload.get("amount", 0) or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Spend amount must be positive")

    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        new_spend = df.loc[idx, "Current Spend"] + amount
        df.loc[idx, "Current Spend"] = new_spend
        min_spend = df.loc[idx, "Min Spend"]
        if min_spend > 0 and new_spend >= min_spend:
            df.loc[idx, "Bonus Status"] = "Met"
        elif df.loc[idx, "Bonus Status"] == "Not Started":
            df.loc[idx, "Bonus Status"] = "In Progress"
        return df

    update_data(mutate)
    return cards_response()


@app.post("/api/cards/{card_id}/fee-action")
async def fee_action(card_id: str, payload: dict):
    action = payload.get("action")
    if action not in {"Waived", "Paid"}:
        raise HTTPException(status_code=400, detail="Action must be Waived or Paid")

    def mutate(df):
        idx, _ = get_card_by_id(df, card_id)
        if idx is None:
            raise HTTPException(status_code=404, detail="Card not found")
        if action == "Waived":
            df.loc[idx, "FeeWaivedCount"] += 1
        else:
            df.loc[idx, "FeePaidCount"] += 1
        df.loc[idx, "LastFeeAction"] = action
        df.loc[idx, "LastFeeActionYear"] = datetime.now().year
        return df

    update_data(mutate)
    return cards_response()


@app.post("/api/sort-order")
async def sort_order(payload: dict):
    orders = payload.get("orders") or {}
    clean_orders = {}
    for card_id, order in orders.items():
        try:
            order_value = int(order)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Sort order values must be integers") from exc
        if order_value < 1:
            raise HTTPException(status_code=400, detail="Sort order values must be positive")
        clean_orders[card_id] = order_value
    if len(set(clean_orders.values())) != len(clean_orders):
        raise HTTPException(status_code=400, detail="Sort order values must be unique")

    def mutate(df):
        for card_id, order in clean_orders.items():
            idx, _ = get_card_by_id(df, card_id)
            if idx is not None:
                df.loc[idx, "Sort Order"] = order
        return df

    update_data(mutate)
    return cards_response()


@app.get("/api/tags")
def list_tags():
    return read_tags()


@app.post("/api/tags")
async def save_tags(payload: dict):
    return write_tags(payload.get("tags") or [])


@app.delete("/api/tags/{tag}")
def delete_tag(tag: str):
    tags = [item for item in read_tags() if item != tag]
    write_tags(tags)

    def mutate(df):
        def clean(value):
            return ",".join(item for item in str(value or "").split(",") if item.strip() and item.strip() != tag)

        df["Tags"] = df["Tags"].apply(clean)
        return df

    update_data(mutate)
    return {"tags": tags, "cards": cards_response()}


@app.post("/api/images")
async def upload_image(file: UploadFile = File(...)):
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be 5 MB or smaller")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Image must be PNG, JPG, or WebP")

    content = await file.read()
    temp_path = Path(IMAGE_DIR) / f".upload-check-{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
    temp_path.write_bytes(content)
    try:
        Image.open(temp_path).verify()
    except (UnidentifiedImageError, OSError) as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from exc

    filename = f"Custom_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
    final_path = Path(IMAGE_DIR) / filename
    temp_path.replace(final_path)
    return {"filename": filename, "url": f"/card_images/{filename}"}


@app.get("/api/export")
def export_csv():
    if not Path(DATA_FILE).exists():
        raise HTTPException(status_code=404, detail="Data file not found")
    return FileResponse(DATA_FILE, media_type="text/csv", filename="my_cards_export.csv")


@app.post("/api/backups")
def create_backup():
    if not Path(DATA_FILE).exists():
        raise HTTPException(status_code=404, detail="Data file not found")
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"cards_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    backup_path = Path(BACKUP_DIR) / filename
    shutil.copy(DATA_FILE, backup_path)
    files = sorted(Path(BACKUP_DIR).glob("cards_backup_*.csv"), key=os.path.getmtime)
    while len(files) > 5:
        files.pop(0).unlink(missing_ok=True)
    return {"filename": filename}


frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
