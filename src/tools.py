"""Tools the agents can call: RAG over the policy, deterministic math, deterministic decision rules."""
from __future__ import annotations

import json
import re
from pathlib import Path

import chromadb
from crewai.tools import tool

ROOT = Path(__file__).resolve().parent.parent
POLICY_FILE = ROOT / "data" / "policy.md"
DB_PATH = ROOT / ".chroma"


# ---------- RAG over the policy ----------
def _collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection("procurement_policy")


def build_policy_index() -> int:
    """Split policy.md on '## ' headings and upsert each section into ChromaDB."""
    text = POLICY_FILE.read_text(encoding="utf-8")
    chunks = [c.strip() for c in re.split(r"(?m)^(?=## )", text) if c.strip().startswith("## ")]
    col = _collection()
    col.upsert(ids=[f"policy-{i}" for i in range(len(chunks))], documents=chunks)
    return len(chunks)


@tool("search_policy")
def search_policy(query: str) -> str:
    """Search the company vendor-contract policy. Input: a short topic such as
    'liability cap', 'auto-renewal notice', 'data breach notification', 'decision rules'.
    Returns the 3 most relevant policy sections with their severity rules."""
    col = _collection()
    if col.count() == 0:
        build_policy_index()
    res = col.query(query_texts=[query], n_results=3)
    return "\n\n---\n\n".join(res["documents"][0])


# ---------- deterministic logic (never left to the LLM) ----------
def decide(num_high: int, num_medium: int) -> str:
    if num_high >= 1:
        return "Escalate to Legal"
    if num_medium >= 3:
        return "Negotiate"
    return "Approve"


def approver_for(total_value: float) -> str:
    if total_value < 1_000_000:
        return "Department Manager"
    if total_value <= 5_000_000:
        return "Finance Head"
    return "CFO and Legal"


@tool("contract_math")
def contract_math(
    annual_fee: float,
    term_months: int,
    liability_cap: float = 0,
    early_termination_fee_pct: float = 0,
) -> str:
    """Compute contract numbers. Inputs: annual_fee (INR), term_months, liability_cap (INR,
    0 if unknown), early_termination_fee_pct (e.g. 20 for 20%).
    Returns JSON with total_contract_value, liability_cap_multiple (cap / annual fee) and
    early_termination_cost_if_exit_after_12_months."""
    total = annual_fee * term_months / 12
    multiple = round(liability_cap / annual_fee, 2) if annual_fee else 0
    remaining = max(total - annual_fee, 0)
    etf = round(remaining * early_termination_fee_pct / 100, 2)
    return json.dumps(
        {
            "total_contract_value": round(total, 2),
            "liability_cap_multiple": multiple,
            "early_termination_cost_if_exit_after_12_months": etf,
        }
    )


@tool("decision_rule")
def decision_rule(num_high: int, num_medium: int, total_contract_value: float) -> str:
    """Apply the company decision rules. Inputs: number of HIGH findings, number of MEDIUM
    findings, total contract value in INR. Returns JSON with the decision and the approver.
    Always use this tool for the final decision; never decide yourself."""
    return json.dumps(
        {"decision": decide(num_high, num_medium), "approver": approver_for(total_contract_value)}
    )
