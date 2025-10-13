import pandas as pd
from datetime import date, timedelta

# === Simulated Bruce Power Turbine Maintenance Schedule ===
# Status Date: 2025-10-18

tasks = [
    (1, "Outage Planning & Permits", 0, 5, 8000, 1.0, 1.0, 7900),
    (2, "Unit Shutdown & Cooldown", 6, 10, 12000, 1.0, 0.9, 12500),
    (3, "Turbine Casing Inspection", 11, 17, 18000, 0.8, 0.6, 14000),
    (4, "Blade Replacement", 18, 27, 40000, 0.6, 0.5, 22000),
    (5, "Rotor Balancing", 28, 33, 15000, 0.4, 0.3, 6000),
    (6, "Functional Testing", 34, 38, 12000, 0.2, 0.1, 2000),
    (7, "Startup & Synchronization", 39, 43, 15000, 0.0, 0.0, 0),
    (8, "Closeout & Documentation", 44, 48, 10000, 0.0, 0.0, 0),
]

# Anchor date: October 1, 2025
start0 = date(2025, 10, 1)

rows = []
for tid, name, d0, d1, bac, pplan, pact, acost in tasks:
    rows.append({
        "TaskID": tid,
        "TaskName": name,
        "StartDate": (start0 + timedelta(days=d0)).isoformat(),
        "FinishDate": (start0 + timedelta(days=d1)).isoformat(),
        "BAC": bac,
        "PlannedPctComplete": pplan * 100,
        "ActualPctComplete": pact * 100,
        "ActualCostToDate": acost
    })

df = pd.DataFrame(rows)

# Save to the main 'data' folder
output_path = "../data/project_data.csv"
df.to_csv(output_path, index=False)

print(f"✅ Created {output_path}")
print(df)
