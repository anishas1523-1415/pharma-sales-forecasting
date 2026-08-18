import pandas as pd
import matplotlib.pyplot as plt
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

plt.figure(figsize=(14, 7))

for category in categories:
    plt.plot(df["datum"], df[category], label=category)

plt.title("Daily Pharmaceutical Sales by Drug Category")
plt.xlabel("Date")
plt.ylabel("Sales")
plt.legend()
plt.tight_layout()

plt.show()