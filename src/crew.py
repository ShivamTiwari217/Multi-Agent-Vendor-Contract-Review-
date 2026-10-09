"""Four-agent crew: Extractor -> Policy Analyst -> Risk Reviewer -> Memo Writer."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import LLM, Agent, Crew, Process, Task
from dotenv import load_dotenv

from src.schemas import ContractFields, Verdict
from src.tools import (
    approver_for,
    build_policy_index,
    contract_math,
    decide,
    decision_rule,
    search_policy,
)

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


def get_llm() -> LLM:
    return LLM(model=os.getenv("MODEL_NAME", "gpt-4o-mini"), temperature=0.1)


def build_crew(verbose: bool = False):
    llm = get_llm()

    extractor = Agent(
        role="Contract Intake Specialist",
        goal="Turn a raw vendor contract into accurate structured fields without guessing.",
        backstory="Ten years in procurement operations. You write null when a contract is silent, never a guess.",
        llm=llm,
        allow_delegation=False,
    )
    analyst = Agent(
        role="Procurement Policy Analyst",
        goal="Check every contract term against company policy and cite the exact policy section.",
        backstory="Senior analyst. You always look up the policy before judging a clause and you quote the contract as evidence.",
        tools=[search_policy, contract_math],
        llm=llm,
        allow_delegation=False,
    )
    reviewer = Agent(
        role="Risk Reviewer",
        goal="Challenge the analyst's findings, fix wrong severities, catch missed issues, and issue the verdict.",
        backstory="Skeptical internal auditor. You reject any finding with no evidence and you never decide by gut: you use the decision tool.",
        tools=[search_policy, decision_rule],
        llm=llm,
        allow_delegation=False,
    )
    writer = Agent(
        role="Decision Memo Writer",
        goal="Write a one-page memo a busy executive can act on in two minutes.",
        backstory="Former consultant. Short sentences, concrete asks, no filler.",
        llm=llm,
        allow_delegation=False,
    )

    t_extract = Task(
        description=(
            "Read the contract below and fill every field. Use null for anything the contract does not state. "
            "Do not guess. Convert liability caps to INR amounts (for example '2x annual fees' = 2 times the annual fee).\n\n"
            "CONTRACT:\n{contract_text}"
        ),
        expected_output="Structured contract fields.",
        agent=extractor,
        output_pydantic=ContractFields,
    )
    t_analyze = Task(
        description=(
            "Using the extracted fields and the original contract, check the contract against ALL policy topics: "
            "liability cap, termination, auto-renewal, payment terms, data protection, security certification, "
            "service levels, data use/IP, governing law. For each topic call search_policy, and call contract_math "
            "for the numeric checks. List every VIOLATION or MISSING required clause with: clause, severity "
            "(High/Medium/Low), policy section, evidence quote from the contract (or MISSING), issue, suggested fix. "
            "Ignore compliant clauses.\n\nORIGINAL CONTRACT:\n{contract_text}"
        ),
        expected_output="A list of violations with severity, policy reference, evidence, issue and fix.",
        agent=analyst,
        context=[t_extract],
    )
    t_review = Task(
        description=(
            "Review the analyst's findings critically. 1) Verify each severity against the policy (use search_policy). "
            "2) Drop findings with no evidence that are not genuinely missing clauses. 3) Add any violation the analyst missed. "
            "4) Count High and Medium findings, compute total contract value, then call decision_rule once. "
            "5) Output the final verdict using the decision and approver EXACTLY as the tool returned them. "
            "Only violations go in findings.\n\nORIGINAL CONTRACT:\n{contract_text}"
        ),
        expected_output="Structured verdict with findings, total contract value, decision and approver.",
        agent=reviewer,
        context=[t_extract, t_analyze],
        output_pydantic=Verdict,
    )
    t_memo = Task(
        description=(
            "Write a one-page markdown memo with these sections: Recommendation (decision + one-line why), "
            "Contract Snapshot (vendor, fee, term, total value), Key Issues (High first, each with a policy reference), "
            "Negotiation Asks (concrete asks per issue), Approval Route. Use only facts from the context."
        ),
        expected_output="A markdown decision memo.",
        agent=writer,
        context=[t_extract, t_review],
    )

    crew = Crew(
        agents=[extractor, analyst, reviewer, writer],
        tasks=[t_extract, t_analyze, t_review, t_memo],
        process=Process.sequential,
        verbose=verbose,
    )
    return crew, t_extract, t_review, t_memo


def enforce_rules(verdict: Verdict, fields: ContractFields | None) -> tuple[Verdict, bool]:
    """Guardrail: recompute decision/approver in plain Python and override the LLM if it drifted."""
    highs = sum(f.severity == "High" for f in verdict.findings)
    meds = sum(f.severity == "Medium" for f in verdict.findings)
    total = verdict.total_contract_value
    if fields and fields.annual_fee and fields.term_months:
        total = fields.annual_fee * fields.term_months / 12
    decision, approver = decide(highs, meds), approver_for(total)
    overridden = (decision != verdict.decision) or (approver != verdict.approver)
    fixed = verdict.model_copy(update={"decision": decision, "approver": approver, "total_contract_value": total})
    return fixed, overridden


def run_review(contract_text: str, verbose: bool = False) -> dict:
    build_policy_index()
    crew, t_extract, t_review, t_memo = build_crew(verbose)
    crew.kickoff(inputs={"contract_text": contract_text})

    fields = t_extract.output.pydantic if t_extract.output else None
    verdict = t_review.output.pydantic if t_review.output else None
    if verdict is None:
        raise RuntimeError("Reviewer did not return a valid structured verdict. Re-run, or try a stronger MODEL_NAME.")
    verdict, overridden = enforce_rules(verdict, fields)
    return {
        "fields": fields.model_dump() if fields else {},
        "verdict": verdict.model_dump(),
        "memo": t_memo.output.raw if t_memo.output else "",
        "guardrail_override": overridden,
    }


def log_human_decision(contract_name: str, ai_decision: str, human_decision: str, notes: str) -> None:
    """Human-in-the-loop: record whether the human accepted or overrode the agents."""
    (ROOT / "logs").mkdir(exist_ok=True)
    row = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "contract": contract_name,
        "ai_decision": ai_decision,
        "human_decision": human_decision,
        "notes": notes,
    }
    with open(ROOT / "logs" / "human_review.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
