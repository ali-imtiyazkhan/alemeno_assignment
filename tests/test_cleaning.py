from datetime import datetime
import pandas as pd
import pytest
from pandas import NaT

from app.tasks.processing import normalize_date, clean_data


class TestNormalizeDate:
    def test_dd_mm_yyyy(self):
        result = normalize_date("15-01-2024")
        assert result == datetime(2024, 1, 15)

    def test_yyyy_mm_dd_slash(self):
        result = normalize_date("2024/02/10")
        assert result == datetime(2024, 2, 10)

    def test_yyyy_mm_dd_dash(self):
        result = normalize_date("2024-07-15")
        assert result == datetime(2024, 7, 15)

    def test_nan_returns_none(self):
        assert normalize_date(NaT) is None

    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_invalid_format_returns_none(self):
        assert normalize_date("not-a-date") is None


class TestCleanData:
    def test_strips_dollar_from_amount(self):
        df = pd.DataFrame({
            "date": ["15-01-2024"],
            "merchant": ["Test"],
            "amount": ["$100.50"],
            "currency": ["inr"],
            "status": ["success"],
            "category": ["Food"],
            "account_id": ["ACC001"],
            "notes": [""],
        })
        result = clean_data(df)
        assert result.iloc[0]["amount"] == 100.50

    def test_uppercases_status(self):
        df = pd.DataFrame({
            "date": ["15-01-2024"],
            "merchant": ["Test"],
            "amount": ["100"],
            "currency": ["inr"],
            "status": ["success"],
            "category": ["Food"],
            "account_id": ["ACC001"],
            "notes": [""],
        })
        result = clean_data(df)
        assert result.iloc[0]["status"] == "SUCCESS"

    def test_uppercases_currency(self):
        df = pd.DataFrame({
            "date": ["15-01-2024"],
            "merchant": ["Test"],
            "amount": ["100"],
            "currency": ["inr"],
            "status": ["SUCCESS"],
            "category": ["Food"],
            "account_id": ["ACC001"],
            "notes": [""],
        })
        result = clean_data(df)
        assert result.iloc[0]["currency"] == "INR"

    def test_fills_missing_category(self):
        df = pd.DataFrame({
            "date": ["15-01-2024"],
            "merchant": ["Test"],
            "amount": ["100"],
            "currency": ["INR"],
            "status": ["SUCCESS"],
            "category": [None],
            "account_id": ["ACC001"],
            "notes": [""],
        })
        result = clean_data(df)
        assert result.iloc[0]["category"] == "Uncategorised"

    def test_removes_duplicate_rows(self):
        df = pd.DataFrame({
            "date": ["15-01-2024", "15-01-2024"],
            "merchant": ["Amazon", "Amazon"],
            "amount": ["100", "100"],
            "currency": ["INR", "INR"],
            "status": ["SUCCESS", "SUCCESS"],
            "category": ["Shopping", "Shopping"],
            "account_id": ["ACC001", "ACC001"],
            "notes": ["", ""],
        })
        result = clean_data(df)
        assert len(result) == 1

    def test_normalizes_date_format(self):
        df = pd.DataFrame({
            "date": ["2024/02/10"],
            "merchant": ["Test"],
            "amount": ["100"],
            "currency": ["INR"],
            "status": ["SUCCESS"],
            "category": ["Food"],
            "account_id": ["ACC001"],
            "notes": [""],
        })
        result = clean_data(df)
        assert result.iloc[0]["date"] == datetime(2024, 2, 10)
