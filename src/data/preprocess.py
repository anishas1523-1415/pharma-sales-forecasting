import pandas as pd
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "pharma_sales_kaggle"
    / "salesdaily.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def preprocess_daily_data():

    # Load raw data
    df = pd.read_csv(RAW_DATA)

    # Convert date column to datetime
    df["datum"] = pd.to_datetime(df["datum"])

    # Sort chronologically
    df = df.sort_values("datum")

    # Remove duplicate dates if any exist
    df = df.drop_duplicates(subset="datum")

    # Keep only the columns needed for forecasting
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

    df = df[["datum"] + categories]

    # Set date as index
    df = df.set_index("datum")

    # Save processed dataset
    output_path = PROCESSED_DIR / "sales_daily_processed.csv"

    df.to_csv(output_path)

    print("Preprocessing completed.")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    preprocess_daily_data()