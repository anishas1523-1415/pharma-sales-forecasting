import pandas as pd
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle"


files = {
    "Hourly": "saleshourly.csv",
    "Daily": "salesdaily.csv",
    "Weekly": "salesweekly.csv",
    "Monthly": "salesmonthly.csv"
}


for name, filename in files.items():

    print("\n" + "=" * 60)
    print(f"{name.upper()} DATA")
    print("=" * 60)

    df = pd.read_csv(DATA_DIR / filename)

    print("\nShape:")
    print(df.shape)

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nFirst 5 rows:")
    print(df.head())

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nData types:")
    print(df.dtypes)