"""Usage: python run_cli.py data/sample_contracts/contract_risky.txt"""
import sys
from pathlib import Path

from src.crew import run_review

if len(sys.argv) < 2:
    sys.exit("Usage: python run_cli.py <contract.txt>")

out = run_review(Path(sys.argv[1]).read_text(encoding="utf-8"), verbose=True)
v = out["verdict"]
print("\n" + "=" * 70)
print(f"DECISION: {v['decision']}  |  APPROVER: {v['approver']}  |  VALUE: INR {v['total_contract_value']:,.0f}")
if out["guardrail_override"]:
    print("(guardrail corrected the LLM's decision)")
for f in v["findings"]:
    print(f"- [{f['severity']}] {f['clause']} ({f['policy_ref']}): {f['issue']}")
print("\n" + out["memo"])
