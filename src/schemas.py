from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ContractFields(BaseModel):
    vendor_name: Optional[str] = None
    service_description: Optional[str] = None
    annual_fee: Optional[float] = Field(None, description="INR")
    term_months: Optional[int] = None
    payment_terms_days: Optional[int] = None
    auto_renewal: Optional[bool] = None
    renewal_optout_notice_days: Optional[int] = None
    termination_for_convenience: Optional[bool] = None
    termination_notice_days: Optional[int] = None
    early_termination_fee_pct: Optional[float] = None
    liability_cap_amount: Optional[float] = Field(None, description="INR, derive from multiple or months of fees if needed")
    uptime_sla_pct: Optional[float] = None
    service_credits: Optional[bool] = None
    handles_personal_data: Optional[bool] = None
    dpa_included: Optional[bool] = None
    breach_notification_hours: Optional[int] = None
    data_deletion_days: Optional[int] = None
    security_certification: Optional[str] = None
    vendor_trains_on_customer_data: Optional[bool] = None
    governing_law: Optional[str] = None


class Finding(BaseModel):
    clause: str
    severity: Literal["High", "Medium", "Low"]
    policy_ref: str = Field(description="Policy section number and name")
    evidence: str = Field(description="Short quote from the contract, or 'MISSING'")
    issue: str
    suggested_fix: str


class Verdict(BaseModel):
    findings: list[Finding]
    total_contract_value: float
    decision: Literal["Approve", "Negotiate", "Escalate to Legal"]
    approver: str
    reviewer_notes: str = ""
