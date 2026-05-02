import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from filelock import FileLock

load_dotenv()

DATA_FILE = os.getenv("DATA_FILE", "my_cards.csv")
TAGS_FILE = os.getenv("TAGS_FILE", "my_tags.json")
IMAGE_DIR = os.getenv("IMAGE_DIR", "card_images")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
DEFAULT_IMAGE = "default.png"
LOCK_FILE = f"{DATA_FILE}.lock"

DATE_COLUMNS = [
    "Date Applied",
    "Date Approved",
    "Date Received Card",
    "Date Activated Card",
    "First Charge Date",
    "Cancellation Date",
    "Re-apply Date",
    "Min Spend Deadline",
]

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_MAP = {f"{i + 1:02d}": name for i, name in enumerate(MONTH_NAMES)}

ALL_COLUMNS = [
    "Card ID",
    "Bank",
    "Card Name",
    "Annual Fee",
    "Card Expiry (MM/YY)",
    "Month of Annual Fee",
    "Date Applied",
    "Date Approved",
    "Date Received Card",
    "Date Activated Card",
    "First Charge Date",
    "Image Filename",
    "Sort Order",
    "Notes",
    "Cancellation Date",
    "Re-apply Date",
    "Tags",
    "Bonus Offer",
    "Min Spend",
    "Min Spend Deadline",
    "Bonus Status",
    "Last 4 Digits",
    "Current Spend",
    "FeeWaivedCount",
    "FeePaidCount",
    "LastFeeActionYear",
    "LastFeeAction",
]

COLUMN_DTYPES = {
    "Card ID": "object",
    "Bank": "object",
    "Card Name": "object",
    "Annual Fee": "float",
    "Card Expiry (MM/YY)": "object",
    "Month of Annual Fee": "object",
    "Date Applied": "datetime64[ns]",
    "Date Approved": "datetime64[ns]",
    "Date Received Card": "datetime64[ns]",
    "Date Activated Card": "datetime64[ns]",
    "First Charge Date": "datetime64[ns]",
    "Image Filename": "object",
    "Sort Order": "int",
    "Notes": "object",
    "Cancellation Date": "datetime64[ns]",
    "Re-apply Date": "datetime64[ns]",
    "Tags": "object",
    "Bonus Offer": "object",
    "Min Spend": "float",
    "Min Spend Deadline": "datetime64[ns]",
    "Bonus Status": "object",
    "Last 4 Digits": "object",
    "Current Spend": "float",
    "FeeWaivedCount": "int",
    "FeePaidCount": "int",
    "LastFeeActionYear": "int",
    "LastFeeAction": "object",
}

DEFAULTS = {
    "Card ID": "",
    "Bank": "",
    "Card Name": "",
    "Annual Fee": 0.0,
    "Card Expiry (MM/YY)": "",
    "Month of Annual Fee": "",
    "Image Filename": DEFAULT_IMAGE,
    "Sort Order": 99,
    "Notes": "",
    "Tags": "",
    "Bonus Offer": "",
    "Min Spend": 0.0,
    "Bonus Status": "",
    "Last 4 Digits": "",
    "Current Spend": 0.0,
    "FeeWaivedCount": 0,
    "FeePaidCount": 0,
    "LastFeeActionYear": 0,
    "LastFeeAction": "",
}


def new_card_id() -> str:
    return uuid.uuid4().hex


def ensure_storage() -> None:
    Path(IMAGE_DIR).mkdir(parents=True, exist_ok=True)
    if not Path(DATA_FILE).exists():
        save_data(pd.DataFrame(columns=ALL_COLUMNS))


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=ALL_COLUMNS).astype(COLUMN_DTYPES)


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for column in ALL_COLUMNS:
        if column not in df.columns:
            if column in DATE_COLUMNS:
                df[column] = pd.NaT
            elif column == "Sort Order":
                df[column] = range(1, len(df) + 1)
            else:
                df[column] = DEFAULTS.get(column, "")

    df = df[ALL_COLUMNS]

    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["Annual Fee"] = pd.to_numeric(df["Annual Fee"], errors="coerce").fillna(0.0)
    df["Sort Order"] = pd.to_numeric(df["Sort Order"], errors="coerce").fillna(99).astype(int)
    df["Min Spend"] = pd.to_numeric(df["Min Spend"], errors="coerce").fillna(0.0)
    df["Current Spend"] = pd.to_numeric(df["Current Spend"], errors="coerce").fillna(0.0)
    df["FeeWaivedCount"] = pd.to_numeric(df["FeeWaivedCount"], errors="coerce").fillna(0).astype(int)
    df["FeePaidCount"] = pd.to_numeric(df["FeePaidCount"], errors="coerce").fillna(0).astype(int)
    df["LastFeeActionYear"] = pd.to_numeric(df["LastFeeActionYear"], errors="coerce").fillna(0).astype(int)

    text_columns = [col for col in ALL_COLUMNS if col not in DATE_COLUMNS and col not in {
        "Annual Fee",
        "Sort Order",
        "Min Spend",
        "Current Spend",
        "FeeWaivedCount",
        "FeePaidCount",
        "LastFeeActionYear",
    }]
    for column in text_columns:
        default = DEFAULTS.get(column, "")
        df[column] = df[column].fillna(default).astype(str)

    df["Last 4 Digits"] = df["Last 4 Digits"].str.replace(r"\.0$", "", regex=True)

    missing_ids = df["Card ID"].str.strip().eq("") | df["Card ID"].duplicated()
    for idx in df[missing_ids].index:
        df.loc[idx, "Card ID"] = new_card_id()

    return df.astype(COLUMN_DTYPES)


def load_data() -> pd.DataFrame:
    ensure_storage()
    with FileLock(LOCK_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
        except pd.errors.EmptyDataError:
            return _empty_frame()
        normalized = normalize_data(df)
        if not df.equals(normalized):
            normalized.to_csv(DATA_FILE, index=False)
        return normalized


def save_data(df: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_data(df) if not df.empty else _empty_frame()
    with FileLock(LOCK_FILE):
        normalized.to_csv(DATA_FILE, index=False)
    return normalized


@contextmanager
def locked_data():
    ensure_storage()
    with FileLock(LOCK_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
        except pd.errors.EmptyDataError:
            df = _empty_frame()
        normalized = normalize_data(df)
        yield normalized
        normalize_data(normalized).to_csv(DATA_FILE, index=False)


def update_data(mutator):
    ensure_storage()
    with FileLock(LOCK_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
        except pd.errors.EmptyDataError:
            df = _empty_frame()
        df = normalize_data(df)
        result = mutator(df)
        df_to_save = result if isinstance(result, pd.DataFrame) else df
        normalize_data(df_to_save).to_csv(DATA_FILE, index=False)
        return result


def get_card_by_id(df: pd.DataFrame, card_id: str):
    matches = df.index[df["Card ID"] == card_id].tolist()
    if not matches:
        return None, None
    idx = matches[0]
    return idx, df.loc[idx]
