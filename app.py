"""Streamlit demo for evidence-first investment claim review."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agent import analyze_claim, create_claim, create_review_case, open_review_cases, record_review_decision
from graph_db import rows

ROOT = Path(__file__).parent
DEMO_CLAIMS = json.loads((ROOT / "data" / "demo_claims.json").read_text(encoding="utf-8"))

st.set_page_config(page_title="SignalShield", page_icon=":material/verified_user:", layout="wide")
st.title("SignalShield")
st.caption("Evidence-first review for investment claims — not investment advice, a trading signal, or a fraud finding.")

try:
    metrics = {
        "companies": rows("MATCH (c:Company) RETURN count(c)")[0][0],
        "official_filings": rows("MATCH (d:Disclosure) RETURN count(d)")[0][0],
        "review_cases": rows("MATCH (r:ReviewCase {status: 'open'}) RETURN count(r)")[0][0],
        "decisions": rows("MATCH (d:Decision) RETURN count(d)")[0][0],
    }
    first, second, third, fourth = st.columns(4)
    first.metric("Watchlist companies", metrics["companies"])
    second.metric("Official filing metadata", metrics["official_filings"])
    third.metric("Open review cases", metrics["review_cases"])
    fourth.metric("Persisted decisions", metrics["decisions"])
except Exception as error:
    st.error(f"FalkorDB is not reachable: {error}")
    st.stop()

st.info("Official evidence is SEC EDGAR filing metadata downloaded by `ingest_sec.py`. Bundled claims are illustrative examples, explicitly not market facts.", icon=":material/info:")

with st.sidebar:
    st.header("Track coverage")
    st.success("Track 1: review case + agent handoff")
    st.success("Track 2: persisted human decisions")
    st.success("Track 3: source-backed evidence graph")

mode = st.radio("Choose a claim source", ["Illustrative demo claim", "Paste a claim for review"], horizontal=True)
claim_id = None
if mode == "Illustrative demo claim":
    selected = st.selectbox("Illustrative claim", DEMO_CLAIMS, format_func=lambda item: item["text"])
    claim_id = selected["id"]
else:
    with st.form("claim_input"):
        text = st.text_area("Claim text", placeholder="Paste a public investment claim here. Do not include private information.", max_chars=1500)
        author = st.text_input("Source label (optional)", value="User-submitted")
        submitted = st.form_submit_button("Add and analyze", type="primary")
    if submitted:
        try:
            claim_id = create_claim(text, author)
            st.session_state["claim_id"] = claim_id
        except ValueError as error:
            st.warning(str(error))
    claim_id = st.session_state.get("claim_id", claim_id)

if claim_id:
    try:
        result = analyze_claim(claim_id)
        st.subheader(result.verdict)
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Review flags")
            for flag in result.flags:
                st.warning(flag, icon=":material/flag:")
            if st.button("Create compliance review case", type="primary"):
                case_id = create_review_case(claim_id, "P2")
                st.success(f"Review case created: {case_id}")
        with right:
            st.markdown("#### Matched companies")
            if result.ticker_rows:
                company_table = pd.DataFrame(result.ticker_rows, columns=["Ticker", "Company", "Sector"])
                st.dataframe(company_table, hide_index=True, width="stretch")
            else:
                st.caption("No configured watchlist ticker was found.")
            st.markdown("#### Linked official filings")
            if result.filings:
                filing_table = pd.DataFrame(result.filings, columns=["Ticker", "Form", "Filed", "Official SEC source"])
                st.dataframe(
                    filing_table,
                    column_config={"Official SEC source": st.column_config.LinkColumn("Official SEC source", display_text="Open official source")},
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.caption("Run `python ingest_sec.py`, then `python seed_graph.py` to add live official metadata.")
        if result.portfolio_rows:
            st.markdown("#### Demo portfolio exposure")
            st.caption("Illustrative portfolio only — never a real client account, recommendation, or suitability assessment.")
            exposure_table = pd.DataFrame(result.portfolio_rows, columns=["Portfolio", "Ticker", "Allocation", "Market value (USD)", "Position role"])
            exposure_table["Allocation"] = exposure_table["Allocation"].map(lambda value: f"{float(value):.1f}%")
            exposure_table["Market value (USD)"] = exposure_table["Market value (USD)"].map(lambda value: f"${float(value):,.0f}")
            st.dataframe(exposure_table, hide_index=True, width="stretch")
        with st.expander("Evidence graph path"):
            st.markdown("\n".join(f"- {step}" for step in result.trace))
        with st.expander("Visual evidence graph"):
            dot = ["digraph {", "rankdir=LR;", "node [shape=box style=rounded fontname=Arial];", 'claim [label="Claim" color="#ff4b4b"];', 'source [label="SEC EDGAR\\nofficial source" color="#1f77b4"];']
            for ticker, company_name, _sector in result.ticker_rows:
                company_id = f"company_{ticker}"
                dot.append(f'{company_id} [label="{ticker}\\n{company_name}"];')
                dot.append(f"claim -> {company_id} [label=MENTIONS];")
            for index, (ticker, form, filed_at, _url) in enumerate(result.filings):
                filing_id = f"filing_{index}"
                dot.append(f'{filing_id} [label="{form}\\n{filed_at}"];')
                dot.append(f"company_{ticker} -> {filing_id} [label=PUBLISHED];")
                dot.append(f"{filing_id} -> source [label=SOURCED_FROM];")
            for index, (portfolio_name, ticker, allocation_pct, _market_value, _tier) in enumerate(result.portfolio_rows):
                portfolio_id, position_id = f"portfolio_{index}", f"position_{index}"
                dot.append(f'{portfolio_id} [label="Demo portfolio\\n{portfolio_name}" color="#7c3aed"];')
                dot.append(f'{position_id} [label="{allocation_pct:.1f}% allocation" color="#7c3aed"];')
                dot.append(f"{portfolio_id} -> {position_id} [label=HOLDS];")
                dot.append(f"{position_id} -> company_{ticker} [label=IN_COMPANY];")
            dot.append("}")
            st.graphviz_chart("\n".join(dot), width="stretch")
    except Exception as error:
        st.error(f"Could not analyze the claim: {error}")

st.divider()
st.subheader("Persistent review memory")
st.caption("This section remains after a refresh because review outcomes are written to FalkorDB, not Streamlit session state.")
cases = open_review_cases()
if cases:
    with st.form("resolve_case"):
        selected_case = st.selectbox("Open review case", cases, format_func=lambda item: f"{item[0]} — {item[1]}")
        outcome = st.selectbox("Human decision", ["monitor", "escalate", "close"])
        rationale = st.text_area("Decision rationale", placeholder="Why is this outcome appropriate?", max_chars=600)
        resolved = st.form_submit_button("Save decision to graph")
    if resolved:
        try:
            decision_id = record_review_decision(selected_case[0], outcome, rationale)
            st.success(f"Persistent decision saved: {decision_id}")
        except ValueError as error:
            st.warning(str(error))
else:
    st.caption("Create a review case above, then save a human outcome here.")

recent_decisions = rows("MATCH (decision:Decision)-[:ABOUT]->(claim:Claim) RETURN decision.outcome, decision.rationale, decision.created_at, claim.id ORDER BY decision.created_at DESC LIMIT 5")
if recent_decisions:
    st.markdown("#### Recent saved decisions")
    decision_table = pd.DataFrame(recent_decisions, columns=["Outcome", "Rationale", "Saved at", "Claim"])
    st.dataframe(decision_table, hide_index=True, width="stretch")
