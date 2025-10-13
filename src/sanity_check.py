import pandas as pd, os

os.makedirs("data", exist_ok=True)
df = pd.DataFrame({"hello": ["world"], "pi": [3.14159]})
out = "data/sanity.csv"
df.to_csv(out, index=False)
print("Wrote", out)
print(pd.read_csv(out))