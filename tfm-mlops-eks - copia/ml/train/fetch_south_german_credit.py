from ucimlrepo import fetch_ucirepo
import pandas as pd
from pathlib import Path

out_dir = Path("ml/train/data")
out_dir.mkdir(parents=True, exist_ok=True)

ds = fetch_ucirepo(id=522)  # South German Credit
X = ds.data.features
y = ds.data.targets

df = pd.concat([X, y], axis=1)
out_path = out_dir / "south_german_credit.csv"
df.to_csv(out_path, index=False)

print("Saved:", out_path)
print("Columns:", df.columns.tolist())
print("Target unique:", df[df.columns[-1]].unique())
