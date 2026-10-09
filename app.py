import io
from pathlib import Path

import pandas as pd
import streamlit as st

from src.crew import log_human_decision, run_review

st.set_page_config(page_title="Vendor Contract Review Agents", layout="wide")
st.title("Vendor Contract Review: Multi-Agent Domain Expert")
st.caption("Extractor -> Policy Analyst (RAG) -> Risk Reviewer -> Memo Writer, with a human final call.")

samples = sorted(Path("data/sample_contracts").glob("*.txt"))
src = st.radio("Contract source", ["Sample", "Paste text", "Upload file"], horizontal=True)
text, name = "", "pasted"
if src == "Sample":
    pick = st.selectbox("Sample contract", samples, format_func=lambda p: p.name)
    text, name = pick.read_text(encoding="utf-8"), pick.name
elif src == "Paste text":
    text = st.text_area("Paste contract text", height=250)
else:
    up = st.file_uploader("Upload .txt or .pdf", type=["txt", "pdf"])
    if up:
        name = up.name
        if up.name.lower().endswith(".pdf"):
            from pypdf import PdfReader

            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(up.read())).pages)
        else:
            text = up.read().decode("utf-8", errors="ignore")

with st.expander("Contract text", expanded=False):
    st.text(text or "(empty)")

if st.button("Run review", type="primary", disabled=not text.strip()):
    with st.spinner("Four agents are working (about 1-2 minutes)..."):
        try:
            st.session_state["out"] = run_review(text)
            st.session_state["name"] = name
        except Exception as e:
            st.error(f"Run failed: {e}")

out = st.session_state.get("out")
if out:
    v = out["verdict"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Decision", v["decision"])
    c2.metric("Approver", v["approver"])
    c3.metric("Total value (INR)", f"{v['total_contract_value']:,.0f}")
    if out["guardrail_override"]:
        st.warning("The rule-based guardrail corrected the LLM's decision to match company policy.")

    st.subheader("Findings")
    if v["findings"]:
        df = pd.DataFrame(v["findings"])
        order = {"High": 0, "Medium": 1, "Low": 2}
        df = df.sort_values("severity", key=lambda s: s.map(order))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("No policy violations found.")

    st.subheader("Memo")
    st.markdown(out["memo"])
    with st.expander("Extracted fields"):
        st.json(out["fields"])

    st.subheader("Human review")
    choice = st.selectbox("Your final decision", ["Approve", "Negotiate", "Escalate to Legal"],
                          index=["Approve", "Negotiate", "Escalate to Legal"].index(v["decision"]))
    notes = st.text_input("Notes (required if you override)")
    if st.button("Record decision"):
        if choice != v["decision"] and not notes.strip():
            st.error("Add a note when overriding the agents.")
        else:
            log_human_decision(st.session_state["name"], v["decision"], choice, notes)
            st.success("Saved to logs/human_review.jsonl")
