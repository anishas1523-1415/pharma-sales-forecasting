import pandas as pd
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle"

df = pd.read_csv(DATA_DIR / "salesdaily.csv")

df["datum"] = pd.to_datetime(df["datum"])

categories = [
    "M01AB",
    "M01AE",
    "N02BA",
    "N02BE",
    "N05B",
    "N05C",
    "R03",
    "R06"
]

results = []

for category in categories:

    series = df[category]

    mean = series.mean()
    std = series.std()

    upper_limit = mean + (2 * std)

    anomaly_count = (series > upper_limit).sum()

    results.append({
        "Category": category,
        "Average Sales": round(mean, 2),
        "Minimum": round(series.min(), 2),
        "Maximum": round(series.max(), 2),
        "Std Dev": round(std, 2),
        "Volatility %": round((std / mean) * 100, 2),
        "Anomalies": int(anomaly_count)
    })


results_df = pd.DataFrame(results)

print("\nCATEGORY ANALYSIS")
print("=" * 80)
print(results_df.to_string(index=False))