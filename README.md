# Vendor Contract Review: Multi-Agent Domain Expert

Four CrewAI agents review a vendor contract against a company policy and produce a decision memo.

## Process being automated
Procurement/legal review of vendor contracts: read contract, check against policy, assess risk, route for approval.

## Agents
| Agent | Role | Tools |
|---|---|---|
| Contract Intake Specialist | Extract structured fields (Pydantic) | none |
| Procurement Policy Analyst | Check every clause against policy | `search_policy` (ChromaDB RAG), `contract_math` |
| Risk Reviewer | Challenge findings, fix severities, final verdict | `search_policy`, `decision_rule` |
| Decision Memo Writer | One-page executive memo | none |

Design choices worth defending in your report:
- **RAG over policy**: the analyst cites the policy section instead of relying on model memory.
- **Deterministic tools for math and decisions**: the LLM never does arithmetic or picks the final decision.
- **Guardrail**: `enforce_rules()` recomputes decision and approver in Python and overrides the LLM if it drifts.
- **Reviewer agent** as a second pair of eyes (self-critique pattern).
- **Human-in-the-loop**: reviewer accepts or overrides, and the override is logged.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your API key and MODEL_NAME
```

## Run
```bash
streamlit run app.py                                         # UI
python run_cli.py data/sample_contracts/contract_risky.txt   # CLI
python -m eval.eval                                          # evaluation on 3 test cases
```

## Test cases
| File | Expected decision | Why |
|---|---|---|
| contract_good.txt | Approve | Fully compliant |
| contract_medium.txt | Negotiate | 3 Medium issues (payment net 20, 90-day renewal notice, London courts) |
| contract_risky.txt | Escalate to Legal | Low liability cap, 120-day renewal, no termination right, no breach clause, model training on data, no certification |

## Swap the domain
Replace `data/policy.md`, the fields in `src/schemas.py`, and the task descriptions in `src/crew.py`.

## Limitations (include in report)
LLM extraction errors on messy scans, policy is synthetic, single-document context only, no legal advice.
