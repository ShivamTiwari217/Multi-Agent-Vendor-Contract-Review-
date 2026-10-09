"""Run all sample contracts and compare agent decisions with expected ones.
Usage (from project root): python -m eval.eval"""
import time
from pathlib import Path

import pandas as pd

from src.crew import run_review

EXPECTED = {
    "contract_good.txt": {"decision": "Approve", "min_high": 0},
    "contract_medium.txt": {"decision": "Negotiate", "min_high": 0},
    "contract_risky.txt": {"decision": "Escalate to Legal", "min_high": 3},
}
rows = []
for name, exp in EXPECTED.items():
    text = (Path("data/sample_contracts") / name).read_text(encoding="utf-8")
    t0 = time.time()
    out = run_review(text)
    v = out["verdict"]
    highs = sum(f["severity"] == "High" for f in v["findings"])
    meds = sum(f["severity"] == "Medium" for f in v["findings"])
    rows.append(
        {
            "contract": name,
            "expected": exp["decision"],
            "got": v["decision"],
            "match": v["decision"] == exp["decision"],
            "high": highs,
            "medium": meds,
            "guardrail_override": out["guardrail_override"],
            "seconds": round(time.time() - t0, 1),
        }
    )
df = pd.DataFrame(rows)
print(df.to_string(index=False))
print(f"\nDecision accuracy: {df['match'].mean():.0%}")
df.to_csv("eval/results.csv", index=False)
