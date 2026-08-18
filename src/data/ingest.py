import pandas as pd
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Location of raw Kaggle data
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle"


def load_data():
    hourly = pd.read_csv(DATA_DIR / "saleshourly.csv")
    daily = pd.read_csv(DATA_DIR / "salesdaily.csv")
    weekly = pd.read_csv(DATA_DIR / "salesweekly.csv")
    monthly = pd.read_csv(DATA_DIR / "salesmonthly.csv")

    return hourly, daily, weekly, monthly


if __name__ == "__main__":
    hourly, daily, weekly, monthly = load_data()

    print("HOURLY DATA")
    print(hourly.head())
    print(hourly.shape)
    print()

    print("DAILY DATA")
    print(daily.head())
    print(daily.shape)
    print()

    print("WEEKLY DATA")
    print(weekly.head())
    print(weekly.shape)
    print()

    print("MONTHLY DATA")
    print(monthly.head())
    print(monthly.shape)