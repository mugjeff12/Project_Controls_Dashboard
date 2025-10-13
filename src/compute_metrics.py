#!/usr/bin/env python3
from __future__ import annotations
"""
compute_metrics.py — Day 4 automation for EVM.
Inputs:  data/project_data.csv
Outputs:
  1) data/metrics.csv
     Columns (exact order): StatusDate,BAC,PV,EV,AC,CPI,SPI,CV,SV,EAC,ETC,VAC
  2) data/tasks_with_ev.csv
     Columns: TaskID,TaskName,StartDate,FinishDate,BAC,PlannedPctComplete,
              ActualPctComplete,ActualCostToDate,PV_task,EV_task,AC_task
Usage:
  python src/compute_metrics.py
  python src/compute_metrics.py --status 2025-10-18
  STATUS_DATE=2025-10-18 python src/compute_metrics.py
  python src/compute_metrics.py --outdir data_alt --decimal 3
"""
import os, argparse, math
import numpy as np
import pandas as pd
from datetime import datetime

DEFAULT_STATUS = "2025-10-18"
REQUIRED_COLS = [
    "TaskID","TaskName","StartDate","FinishDate","BAC",
    "PlannedPctComplete","ActualPctComplete","ActualCostToDate"
]

def parse_args():
    p = argparse.ArgumentParser(description="Compute EVM metrics and exports.")
    p.add_argument("--status", type=str, default=None,
                   help="Status date YYYY-MM-DD (overrides env STATUS_DATE). Default 2025-10-18.")
    p.add_argument("--outdir", type=str, default="data",
                   help="Directory for CSV outputs. Default: data")
    p.add_argument("--decimal", type=int, default=2,
                   help="Rounding for CPI/SPI. Default: 2")
    return p.parse_args()

def resolve_status_date(cli_status):
    s = cli_status or os.getenv("STATUS_DATE", DEFAULT_STATUS)
    datetime.strptime(s, "%Y-%m-%d")  # validate
    return s

def load_data(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input not found: {csv_path}")
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}\nFound: {list(df.columns)}")
    # Parse dates strictly
    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="raise")
    df["FinishDate"] = pd.to_datetime(df["FinishDate"], errors="raise")
    return df

def validate_data(df):
    bad_dates = df[df["FinishDate"] <= df["StartDate"]]
    if not bad_dates.empty:
        raise ValueError("FinishDate must be > StartDate. Bad TaskIDs: " + ", ".join(map(str, bad_dates["TaskID"])))
    for c in ["PlannedPctComplete","ActualPctComplete"]:
        if ((df[c] < 0) | (df[c] > 100)).any():
            bad = df[(df[c] < 0) | (df[c] > 100)]
            raise ValueError(f"{c} must be within [0,100]. Bad TaskIDs: " + ", ".join(map(str, bad["TaskID"])))
    for c in ["BAC","ActualCostToDate"]:
        if (df[c] < 0).any():
            bad = df[df[c] < 0]
            raise ValueError(f"{c} must be non-negative. Bad TaskIDs: " + ", ".join(map(str, bad["TaskID"])))

def compute_task_ev(df):
    out = df.copy()
    out["PV_task"] = out["BAC"] * (out["PlannedPctComplete"]/100.0)
    out["EV_task"] = out["BAC"] * (out["ActualPctComplete"]/100.0)
    out["AC_task"] = out["ActualCostToDate"]
    return out

def safe_div(n, d):
    try:
        if d in (None, 0) or (isinstance(d, float) and np.isnan(d)):
            return np.nan
        return n/d
    except Exception:
        return np.nan

def compute_project_metrics(tasks_ev, status_date, dec=2):
    PV = float(tasks_ev["PV_task"].sum())
    EV = float(tasks_ev["EV_task"].sum())
    AC = float(tasks_ev["AC_task"].sum())
    BAC = float(tasks_ev["BAC"].sum())

    CPI = safe_div(EV, AC)
    SPI = safe_div(EV, PV)
    CV = EV - AC
    SV = EV - PV

    if (isinstance(CPI, float) and (np.isnan(CPI) or CPI <= 0)) or CPI is None:
        EAC = np.nan
    else:
        EAC = BAC / CPI
    ETC = EAC - AC if not (isinstance(EAC, float) and np.isnan(EAC)) else np.nan
    VAC = BAC - EAC if not (isinstance(EAC, float) and np.isnan(EAC)) else np.nan

    r_money = lambda x: float(np.round(x)) if not (isinstance(x, float) and np.isnan(x)) else np.nan
    r_ratio = lambda x: float(np.round(x, dec)) if not (isinstance(x, float) and np.isnan(x)) else np.nan

    row = {
        "StatusDate": status_date,
        "BAC": r_money(BAC),
        "PV": r_money(PV),
        "EV": r_money(EV),
        "AC": r_money(AC),
        "CPI": r_ratio(CPI),
        "SPI": r_ratio(SPI),
        "CV": r_money(CV),
        "SV": r_money(SV),
        "EAC": r_money(EAC),
        "ETC": r_money(ETC),
        "VAC": r_money(VAC),
    }
    cols = ["StatusDate","BAC","PV","EV","AC","CPI","SPI","CV","SV","EAC","ETC","VAC"]
    return pd.DataFrame([row], columns=cols)

def write_outputs(tasks_ev, metrics, outdir):
    os.makedirs(outdir, exist_ok=True)
    tasks_cols = ["TaskID","TaskName","StartDate","FinishDate","BAC",
                  "PlannedPctComplete","ActualPctComplete","ActualCostToDate",
                  "PV_task","EV_task","AC_task"]
    tasks_out = tasks_ev[tasks_cols].copy()
    for c in ["StartDate","FinishDate"]:
        tasks_out[c] = tasks_out[c].dt.strftime("%Y-%m-%d")
    tasks_path = os.path.join(outdir, "tasks_with_ev.csv")
    tasks_out.to_csv(tasks_path, index=False)

    metrics_path = os.path.join(outdir, "metrics.csv")
    metrics.to_csv(metrics_path, index=False)
    return tasks_path, metrics_path

def print_summary(metrics):
    m = metrics.iloc[0].to_dict()
    interp = []
    if not math.isnan(m["CPI"]):
        interp.append("CPI<1 → over budget" if m["CPI"] < 1 else ("CPI>1 → under budget" if m["CPI"] > 1 else "CPI=1 → on budget"))
    if not math.isnan(m["SPI"]):
        interp.append("SPI<1 → behind schedule" if m["SPI"] < 1 else ("SPI>1 → ahead of schedule" if m["SPI"] > 1 else "SPI=1 → on schedule"))
    print(
        f"Status {m['StatusDate']} | BAC ${int(m['BAC'])} | PV ${int(m['PV'])} | EV ${int(m['EV'])} | AC ${int(m['AC'])} | "
        f"CPI {m['CPI']} | SPI {m['SPI']} | EAC ${'nan' if math.isnan(m['EAC']) else int(m['EAC'])} | VAC ${'nan' if math.isnan(m['VAC']) else int(m['VAC'])}"
    )
    print("Interpretation:", "; ".join(interp) if interp else "No indices available.")

def main():
    args = parse_args()
    status_date = resolve_status_date(args.status)

    in_csv = os.path.join("data","project_data.csv")
    if not os.path.exists(in_csv):
        # support running from script dir as CWD
        here = os.path.dirname(__file__)
        alt = os.path.normpath(os.path.join(here, "..", "data", "project_data.csv"))
        if os.path.exists(alt):
            in_csv = alt
        else:
            raise FileNotFoundError(f"Could not find {in_csv} from CWD {os.getcwd()} or script dir.")

    df = load_data(in_csv)
    validate_data(df)
    tasks_ev = compute_task_ev(df)
    metrics = compute_project_metrics(tasks_ev, status_date, dec=args.decimal)

    tasks_path, metrics_path = write_outputs(tasks_ev, metrics, args.outdir)
    print_summary(metrics)
    print(f"\nWrote:\n  - {tasks_path}\n  - {metrics_path}")

if __name__ == "__main__":
    main()

