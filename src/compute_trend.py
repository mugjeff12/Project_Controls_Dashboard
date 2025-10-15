#!/usr/bin/env python3
from __future__ import annotations
import os, sys, argparse
from datetime import datetime
import pandas as pd
import numpy as np

HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.append(HERE)

# Reuse Day 4 helpers
import compute_metrics as cm

def parse_args():
    p = argparse.ArgumentParser(description="Build EVM trend across multiple status dates.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--status-list", type=str, help="Comma-separated YYYY-MM-DD dates.")
    g.add_argument("--status-file", type=str, help="Path to a text file with one YYYY-MM-DD per line.")
    p.add_argument("--outdir", type=str, default="data", help="Output directory (default: data).")
    p.add_argument("--decimal", type=int, default=2, help="Rounding for CPI/SPI ratios (default: 2).")
    p.add_argument("--append", action="store_true", help="Append to metrics_history.csv if it exists.")
    p.add_argument("--dedupe", action="store_true", help="Drop duplicate StatusDate rows keeping the LAST one.")
    p.add_argument("--debug", action="store_true", help="Print per-date planned%% samples for sanity.")
    return p.parse_args()

def read_status_dates(args) -> list[str]:
    if args.status_list:
        dates = [d.strip() for d in args.status_list.split(",") if d.strip()]
    else:
        if not os.path.exists(args.status_file):
            raise FileNotFoundError(f"Status file not found: {args.status_file}")
        with open(args.status_file, "r", encoding="utf-8") as f:
            dates = [ln.strip() for ln in f if ln.strip()]
    # Validate format strictly
    for s in dates:
        datetime.strptime(s, "%Y-%m-%d")
    return dates

# Linear planned % from Start/Finish vs StatusDate (clamped 0..1)
def planned_pct_from_dates(start_ts: pd.Timestamp, finish_ts: pd.Timestamp, status_date_str: str) -> float:
    t = pd.to_datetime(status_date_str)
    if pd.isna(start_ts) or pd.isna(finish_ts):
        return 0.0
    if t <= start_ts:
        return 0.0
    if t >= finish_ts:
        return 1.0
    total = (finish_ts - start_ts).total_seconds()
    if total <= 0:
        return 0.0
    done = (t - start_ts).total_seconds()
    return max(0.0, min(1.0, done / total))

def main():
    args = parse_args()

    dates = read_status_dates(args)

    # Locate input
    in_csv = os.path.join("data", "project_data.csv")
    if not os.path.exists(in_csv):
        alt = os.path.normpath(os.path.join(HERE, "..", "data", "project_data.csv"))
        if os.path.exists(alt):
            in_csv = alt
        else:
            raise FileNotFoundError(f"Could not find {in_csv} from CWD {os.getcwd()} or script dir.")

    # Load baseline once and validate
    df = cm.load_data(in_csv)
    cm.validate_data(df)

    # Optional per-date actuals & costs
    progress_path = os.path.join("data", "progress_log.csv")
    have_progress = os.path.exists(progress_path)
    if have_progress:
        prog = pd.read_csv(progress_path)
        required_prog = {"StatusDate", "TaskID", "ActualPctComplete", "ActualCostToDate"}
        if not required_prog.issubset(set(prog.columns)):
            raise ValueError(f"progress_log.csv must include columns: {required_prog}")
        prog["StatusDate"] = pd.to_datetime(prog["StatusDate"]).dt.strftime("%Y-%m-%d")

    rows = []
    for s in dates:
        # Start from baseline each loop
        tmp = df.copy()

        # 1) Recompute PlannedPctComplete from dates (linear ramp)
        tmp["PlannedPctComplete"] = tmp.apply(
            lambda r: 100.0 * planned_pct_from_dates(r["StartDate"], r["FinishDate"], s),
            axis=1
        )

        # 2) If we have progress for this date, override Actuals & Costs
        if have_progress:
            prog_s = prog[prog["StatusDate"] == s].copy()
            if not prog_s.empty:
                tmp = tmp.merge(
                    prog_s[["TaskID", "ActualPctComplete", "ActualCostToDate"]],
                    on="TaskID", how="left", suffixes=("", "_prog")
                )
                # Override when provided
                if "ActualPctComplete_prog" in tmp.columns:
                    tmp["ActualPctComplete"] = tmp["ActualPctComplete_prog"].fillna(tmp["ActualPctComplete"])
                if "ActualCostToDate_prog" in tmp.columns:
                    tmp["ActualCostToDate"]  = tmp["ActualCostToDate_prog"].fillna(tmp["ActualCostToDate"])
                tmp = tmp.drop(columns=[c for c in ["ActualPctComplete_prog","ActualCostToDate_prog"] if c in tmp.columns])

        # Optional debug: show a few planned% values changing by date
        if args.debug:
            sample = tmp.loc[tmp["TaskID"].isin([1, 3, 4]), ["TaskID","PlannedPctComplete"]].to_dict("records")
            print(f"[DEBUG] {s} planned% sample:", sample)

        # Task-level EV for this status date (with updated planned/actuals)
        tasks_ev = cm.compute_task_ev(tmp)

        # Project-level metrics row (use positional args to be compatible with your Day-4 signature)
        m = cm.compute_project_metrics(tasks_ev, s, args.decimal)
        rows.append(m.iloc[0].to_dict())

    hist = pd.DataFrame(rows, columns=[
        "StatusDate","BAC","PV","EV","AC","CPI","SPI","CV","SV","EAC","ETC","VAC"
    ])

    os.makedirs(args.outdir, exist_ok=True)
    hist_path = os.path.join(args.outdir, "metrics_history.csv")

    if args.append and os.path.exists(hist_path):
        old = pd.read_csv(hist_path)
        combined = pd.concat([old, hist], ignore_index=True)
        if args.dedupe:
            combined = combined.drop_duplicates(subset=["StatusDate"], keep="last")
        combined.to_csv(hist_path, index=False)
    else:
        hist.to_csv(hist_path, index=False)

    # Console summary
    def fm_money(x):
        try: return f"${int(x)}"
        except: return "nan"

    print("EVM Trend Summary:")
    for _, r in hist.iterrows():
        print(
            f"{r['StatusDate']} | BAC {fm_money(r['BAC'])} | PV {fm_money(r['PV'])} | EV {fm_money(r['EV'])} | "
            f"AC {fm_money(r['AC'])} | CPI {r['CPI']} | SPI {r['SPI']} | EAC {fm_money(r['EAC'])} | VAC {fm_money(r['VAC'])}"
        )
    print(f"\nWrote trend file: {hist_path}")

if __name__ == "__main__":
    main()
