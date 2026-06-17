import pandas as pd

from app.tasks.processing import detect_anomalies


class TestDetectAnomalies:
    def test_no_anomaly_for_normal_transactions(self):
        df = pd.DataFrame({
            "account_id": ["ACC001", "ACC001", "ACC001"],
            "amount": [100.0, 200.0, 150.0],
            "currency": ["INR", "INR", "INR"],
            "merchant": ["Amazon", "Flipkart", "Swiggy"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].sum() == 0

    def test_flags_outlier_above_3x_median(self):
        df = pd.DataFrame({
            "account_id": ["ACC001", "ACC001", "ACC001", "ACC001"],
            "amount": [100.0, 110.0, 90.0, 1000.0],
            "currency": ["INR", "INR", "INR", "INR"],
            "merchant": ["A", "B", "C", "D"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[3] == True
        assert "median" in result["anomaly_reason"].iloc[3]

    def test_does_not_flag_normal_amounts(self):
        df = pd.DataFrame({
            "account_id": ["ACC001", "ACC001", "ACC001"],
            "amount": [100.0, 200.0, 150.0],
            "currency": ["INR", "INR", "INR"],
            "merchant": ["A", "B", "C"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].sum() == 0

    def test_flags_usd_with_domestic_merchant_swiggy(self):
        df = pd.DataFrame({
            "account_id": ["ACC001"],
            "amount": [100.0],
            "currency": ["USD"],
            "merchant": ["Swiggy"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True
        assert "domestic-only" in result["anomaly_reason"].iloc[0]

    def test_flags_usd_with_domestic_merchant_ola(self):
        df = pd.DataFrame({
            "account_id": ["ACC001"],
            "amount": [100.0],
            "currency": ["USD"],
            "merchant": ["Ola"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True

    def test_flags_usd_with_domestic_merchant_irctc(self):
        df = pd.DataFrame({
            "account_id": ["ACC001"],
            "amount": [100.0],
            "currency": ["USD"],
            "merchant": ["IRCTC"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True

    def test_does_not_flag_inr_with_domestic_merchant(self):
        df = pd.DataFrame({
            "account_id": ["ACC001"],
            "amount": [100.0],
            "currency": ["INR"],
            "merchant": ["Swiggy"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == False

    def test_does_not_flag_usd_with_international_merchant(self):
        df = pd.DataFrame({
            "account_id": ["ACC001"],
            "amount": [100.0],
            "currency": ["USD"],
            "merchant": ["Amazon"],
        })
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == False
