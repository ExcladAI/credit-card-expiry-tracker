import pandas as pd

import data_store


def configure_store(tmp_path, monkeypatch):
    data_file = tmp_path / "cards.csv"
    monkeypatch.setattr(data_store, "DATA_FILE", str(data_file))
    monkeypatch.setattr(data_store, "LOCK_FILE", str(data_file) + ".lock")
    monkeypatch.setattr(data_store, "IMAGE_DIR", str(tmp_path / "card_images"))
    monkeypatch.setattr(data_store, "BACKUP_DIR", str(tmp_path / "backups"))
    return data_file


def test_load_data_migrates_old_csv_and_adds_card_ids(tmp_path, monkeypatch):
    data_file = configure_store(tmp_path, monkeypatch)
    pd.DataFrame(
        [
            {
                "Bank": "Test_Bank",
                "Card Name": "Rewards",
                "Annual Fee": "bad-number",
                "Date Applied": "not-a-date",
            }
        ]
    ).to_csv(data_file, index=False)

    df = data_store.load_data()

    assert list(df.columns) == data_store.ALL_COLUMNS
    assert df.loc[0, "Card ID"]
    assert df.loc[0, "Annual Fee"] == 0.0
    assert pd.isna(df.loc[0, "Date Applied"])


def test_update_data_keeps_multiple_mutations(tmp_path, monkeypatch):
    configure_store(tmp_path, monkeypatch)
    data_store.save_data(
        pd.DataFrame(
            [
                {
                    "Card ID": "card-1",
                    "Bank": "Bank",
                    "Card Name": "Card",
                    "Annual Fee": 100,
                    "Sort Order": 1,
                }
            ]
        )
    )

    def add_spend(df):
        df.loc[df["Card ID"] == "card-1", "Current Spend"] += 25
        return df

    def waive_fee(df):
        idx = df.index[df["Card ID"] == "card-1"][0]
        df.loc[idx, "FeeWaivedCount"] += 1
        df.loc[idx, "LastFeeAction"] = "Waived"
        return df

    data_store.update_data(add_spend)
    data_store.update_data(waive_fee)

    df = data_store.load_data()
    row = df.loc[df["Card ID"] == "card-1"].iloc[0]
    assert row["Current Spend"] == 25
    assert row["FeeWaivedCount"] == 1
    assert row["LastFeeAction"] == "Waived"


def test_duplicate_or_blank_card_ids_are_repaired(tmp_path, monkeypatch):
    data_file = configure_store(tmp_path, monkeypatch)
    pd.DataFrame(
        [
            {"Card ID": "dup", "Bank": "A", "Card Name": "One"},
            {"Card ID": "dup", "Bank": "B", "Card Name": "Two"},
            {"Card ID": "", "Bank": "C", "Card Name": "Three"},
        ]
    ).to_csv(data_file, index=False)

    df = data_store.load_data()

    assert df["Card ID"].str.strip().ne("").all()
    assert df["Card ID"].is_unique
