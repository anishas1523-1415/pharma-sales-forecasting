import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle"

df = pd.read_csv(DATA_DIR / "salesdaily.csv")

df["datum"] = pd.to_datetime(df["datum"])
df = df.sort_values("datum")
df = df.set_index("datum")

# Analyze N02BE
series = df["N02BE"]

# Decompose using yearly seasonality
decomposition = seasonal_decompose(
    series,
    model="additive",
    period=365
)

decomposition.plot()

plt.suptitle(
    "N02BE Sales - Trend and Seasonality Decomposition",
    fontsize=14
)

plt.tight_layout()
plt.show()