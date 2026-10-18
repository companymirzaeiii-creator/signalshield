"""Explainable, bounded review logic. It never gives trading advice or alleges fraud."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from graph_db import get_graph, rows

CERTAINTY_TERMS = ("guaranteed", "definitely", "no downside", "risk-free", "sure", "must rise")
URGENCY_TERMS = ("buy before", "act now", "today only", "before friday", "limited time")


@dataclass
class ReviewResult:
    claim_id: str
    ticker_rows: list[tuple]
    filings: list[tuple]
    portfolio_rows: list[tuple]
    flags: list[str]
    verdict: str
    trace: list[str]


def create_claim(text: str, author: str = "User-submitted") -> str:
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > 1500:
        raise ValueError("Enter a claim between 1 and 1,500 characters.")
    claim_id = f"claim-user-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    graph = get_graph()
    graph.query("MATCH (tenant:Tenant {id: 'tenant-signalshield'}) MERGE (claim:Claim {id: $id}) SET claim.text = $text, claim.author = $author, claim.source_type = 'user-submitted text', claim.published_at = $created_at MERGE (tenant)-[:HAS_CLAIM]->(claim)", {"id": claim_id, "text": cleaned, "author": author[:120], "created_at": created_at})
    for ticker in re.findall(r"\b[A-Z]{1,5}\b", cleaned.upper()):
        graph.query("MATCH (claim:Claim {id: $claim_id}), (company:Company {ticker: $ticker}) MERGE (claim)-[:MENTIONS]->(company)", {"claim_id": claim_id, "ticker": ticker})
    return claim_id


def analyze_claim(claim_id: str) -> ReviewResult:
    claim_rows = rows("MATCH (claim:Claim {id: $id}) RETURN claim.text", {"id": claim_id})
    if not claim_rows:
        raise ValueError("The selected claim does not exist in the graph.")
    text = str(claim_rows[0][0])
    ticker_rows = rows("MATCH (:Claim {id: $id})-[:MENTIONS]->(company:Company) RETURN company.ticker, company.name, company.sector ORDER BY company.ticker", {"id": claim_id})
    filings = rows("MATCH (:Claim {id: $id})-[:MENTIONS]->(company:Company)-[:PUBLISHED]->(disclosure:Disclosure) RETURN company.ticker, disclosure.form, disclosure.filed_at, disclosure.source_url ORDER BY disclosure.filed_at DESC LIMIT 8", {"id": claim_id})
    portfolio_rows = rows("MATCH (:Claim {id: $id})-[:MENTIONS]->(company:Company)<-[:IN_COMPANY]-(position:Position)<-[:HOLDS]-(portfolio:Portfolio) RETURN portfolio.name, company.ticker, position.allocation_pct, position.market_value_usd, position.risk_tier ORDER BY position.allocation_pct DESC", {"id": claim_id})
    lowered = text.lower()
    flags = []
    if any(term in lowered for term in CERTAINTY_TERMS):
        flags.append("Uses certainty language; investment outcomes cannot be verified as guaranteed.")
    if any(term in lowered for term in URGENCY_TERMS):
        flags.append("Uses urgency language; this is a reason for a human reviewer to check the evidence first.")
    if not ticker_rows:
        flags.append("No supported ticker was identified in the configured watchlist.")
    if ticker_rows and not filings:
        flags.append("No official SEC filing snapshot is linked yet. Run the official-data ingestion before relying on coverage.")
    if filings:
        flags.append(f"Found {len(filings)} linked official filing record(s). Their existence supports review, not the claim's prediction.")
    if portfolio_rows:
        total_exposure = sum(float(item[2]) for item in portfolio_rows)
        flags.append(f"Illustrative portfolio exposure: {total_exposure:.1f}% of the demo portfolio is linked to the mentioned company or companies.")
    if len(flags) >= 2 and (any(term in lowered for term in CERTAINTY_TERMS) or not filings):
        verdict = "Priority review recommended"
    else:
        verdict = "Evidence review recommended"
    trace = ["Claim → MENTIONS → Company", "Company → PUBLISHED → SEC disclosure", "Portfolio → HOLDS → Position → IN_COMPANY → Company", "Claim → ReviewCase → AgentHandoff (after a reviewer creates a case)"]
    return ReviewResult(claim_id, ticker_rows, filings, portfolio_rows, flags, verdict, trace)


def create_review_case(claim_id: str, priority: str) -> str:
    if priority not in {"P1", "P2", "P3"}:
        raise ValueError("Invalid priority.")
    case_id, handoff_id = f"case-{uuid4().hex[:8]}", f"handoff-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    get_graph().query("MATCH (claim:Claim {id: $claim_id}), (evidence:Agent {id: 'agent-evidence'}), (compliance:Agent {id: 'agent-compliance'}), (tenant:Tenant {id: 'tenant-signalshield'}) MERGE (review:ReviewCase {id: $case_id}) SET review.title = 'Review investment claim', review.status = 'open', review.priority = $priority, review.created_at = $created_at MERGE (review)-[:REVIEWS]->(claim) MERGE (tenant)-[:HAS_CASE]->(review) MERGE (handoff:AgentHandoff {id: $handoff_id}) SET handoff.from_agent = evidence.name, handoff.to_agent = compliance.name, handoff.created_at = $created_at MERGE (evidence)-[:HANDOFF_TO]->(handoff) MERGE (handoff)-[:CREATED]->(review) MERGE (handoff)-[:ROUTED_TO]->(compliance)", {"claim_id": claim_id, "case_id": case_id, "handoff_id": handoff_id, "priority": priority, "created_at": created_at})
    return case_id


def open_review_cases() -> list[tuple]:
    return rows("MATCH (review:ReviewCase {status: 'open'})-[:REVIEWS]->(claim:Claim) RETURN review.id, review.priority, claim.text ORDER BY review.created_at DESC")


def record_review_decision(case_id: str, decision: str, rationale: str) -> str:
    """Store a human-approved outcome as durable semantic memory for later reviewers."""
    if decision not in {"monitor", "escalate", "close"} or not rationale.strip() or len(rationale) > 600:
        raise ValueError("Choose an outcome and enter a rationale of up to 600 characters.")
    decision_id = f"decision-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    get_graph().query("MATCH (review:ReviewCase {id: $case_id, status: 'open'})-[:REVIEWS]->(claim:Claim), (tenant:Tenant {id: 'tenant-signalshield'}) MERGE (decision:Decision {id: $decision_id}) SET decision.outcome = $outcome, decision.rationale = $rationale, decision.created_at = $created_at SET review.status = 'resolved' MERGE (review)-[:RESOLVED_WITH]->(decision) MERGE (decision)-[:ABOUT]->(claim) MERGE (tenant)-[:HAS_DECISION]->(decision)", {"case_id": case_id, "decision_id": decision_id, "outcome": decision, "rationale": rationale.strip(), "created_at": created_at})
    return decision_id
