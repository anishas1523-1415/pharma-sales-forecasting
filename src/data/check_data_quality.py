import pandas as pd
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle"

df = pd.read_csv(DATA_DIR / "salesdaily.csv")

df["datum"] = pd.to_datetime(df["datum"])

df = df.sort_values("datum")

print("\nDATA QUALITY CHECK")
print("=" * 60)

# Date range
print("\nDate range:")
print("Start:", df["datum"].min())
print("End:  ", df["datum"].max())

# Duplicate dates
duplicate_dates = df["datum"].duplicated().sum()

print("\nDuplicate dates:", duplicate_dates)

# Missing dates
expected_dates = pd.date_range(
    start=df["datum"].min(),
    end=df["datum"].max(),
    freq="D"
)

actual_dates = pd.DatetimeIndex(df["datum"])

missing_dates = expected_dates.difference(actual_dates)

print("Expected number of daily dates:", len(expected_dates))
print("Actual number of dates:", len(actual_dates))
print("Missing dates:", len(missing_dates))

if len(missing_dates) > 0:
    print("\nFirst missing dates:")
    print(missing_dates[:10])

# Missing values
print("\nMissing values by column:")
print(df.isnull().sum())