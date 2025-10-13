import pandas as pd
from datetime import datetime

CSV_PATH = "../data/project_data.csv"   # file should be at <project_root>/data/project_data.csv
STATUS = "2025-10-18"                # as-of date for checks
status_dt = pd.to_datetime(STATUS)

# ---- Load & basic schema checks
df = pd.read_csv(CSV_PATH, parse_dates=["StartDate","FinishDate"])
print("Columns:", list(df.columns))
print(df.head(3), "\n")

required = {"TaskID","TaskName","StartDate","FinishDate","BAC",
            "PlannedPctComplete","ActualPctComplete","ActualCostToDate"}
missing = required - set(df.columns)
assert not missing, f"Missing columns: {missing}"

assert (df["FinishDate"] > df["StartDate"]).all(), "Some FinishDate <= StartDate."
assert (df["PlannedPctComplete"].between(0,100)).all(), "Planned % out of [0,100]."
assert (df["ActualPctComplete"].between(0,100)).all(), "Actual % out of [0,100]."
assert (df["BAC"] >= 0).all(), "Negative BAC found."
assert (df["ActualCostToDate"] >= 0).all(), "Negative ActualCostToDate found."

total_bac = df["BAC"].sum()
print(f"Total BAC: {total_bac:,.0f}")

# ---- Cross-check: Planned % implied by dates (linear) vs your PlannedPctComplete
def planned_fraction(row, t):
    if t <= row["StartDate"]:
        return 0.0
    if t >= row["FinishDate"]:
        return 1.0
    total = max((row["FinishDate"] - row["StartDate"]).days, 1)
    done = (t - row["StartDate"]).days
    return max(0.0, min(1.0, done/total))

df["_PlannedPct_fromDates"] = df.apply(lambda r: planned_fraction(r, status_dt)*100, axis=1)

diff = (df["PlannedPctComplete"] - df["_PlannedPct_fromDates"]).abs()
off = df[diff > 10][["TaskID","TaskName","PlannedPctComplete","_PlannedPct_fromDates"]]
if len(off):
    print("\n⚠️ Planned% differs >10% vs date-based expectation; review these rows:")
    print(off.to_string(index=False))
else:
    print("\nPlanned% looks consistent with the schedule dates (±10%).")

# ---- Preview PV/EV/AC and CPI/SPI (full pipeline comes Day 4–5)
df["PV_task"] = df["BAC"] * (df["PlannedPctComplete"]/100.0)
df["EV_task"] = df["BAC"] * (df["ActualPctComplete"]/100.0)
df["AC_task"] = df["ActualCostToDate"]

PV = df["PV_task"].sum()
EV = df["EV_task"].sum()
AC = df["AC_task"].sum()

CPI = (EV/AC) if AC > 0 else float("nan")
SPI = (EV/PV) if PV > 0 else float("nan")

print(f"\nPreview Totals @ {STATUS}")
print(f"PV = {PV:,.0f}   EV = {EV:,.0f}   AC = {AC:,.0f}")
print(f"CPI = {CPI:.2f}   SPI = {SPI:.2f}")

# Optional: write a debug file with task-level PV/EV/AC
df_out = df[["TaskID","TaskName","BAC","PlannedPctComplete","ActualPctComplete",
             "ActualCostToDate","PV_task","EV_task","AC_task"]]
df_out.to_csv("data/tasks_with_ev_preview.csv", index=False)
print("\nWrote data/tasks_with_ev_preview.csv")
