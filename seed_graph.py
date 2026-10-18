"""Idempotently seed SignalShield's graph from local data and SEC snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from graph_db import get_graph

ROOT = Path(__file__).parent


def load_json(name: str, fallback):
    path = ROOT / "data" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def seed() -> None:
    graph = get_graph()
    companies = load_json("watchlist.json", [])
    claims = load_json("demo_claims.json", [])
    portfolio = load_json("demo_portfolio.json", {})
    sec_snapshot = load_json("sec_disclosures.json", {"disclosures": []})
    graph.query("MERGE (t:Tenant {id: 'tenant-signalshield'}) SET t.name = 'SignalShield demo tenant' MERGE (a:Agent {id: 'agent-evidence'}) SET a.name = 'Evidence analyst' MERGE (c:Agent {id: 'agent-compliance'}) SET c.name = 'Compliance coordinator' MERGE (t)-[:USES]->(a) MERGE (t)-[:USES]->(c)")

    for company in companies:
        graph.query("MERGE (c:Company {ticker: $ticker}) SET c += $properties MERGE (sector:Sector {name: $sector}) MERGE (c)-[:IN_SECTOR]->(sector)", {"ticker": company["ticker"], "sector": company["sector"], "properties": company})

    if portfolio:
        graph.query("MATCH (tenant:Tenant {id: 'tenant-signalshield'}) MERGE (portfolio:Portfolio {id: $id}) SET portfolio.name = $name, portfolio.owner_type = $owner_type, portfolio.disclaimer = $disclaimer MERGE (tenant)-[:HAS_PORTFOLIO]->(portfolio)", portfolio)
        for item in portfolio["positions"]:
            position_id = f"position-{portfolio['id']}-{item['ticker'].lower()}"
            graph.query("MATCH (portfolio:Portfolio {id: $portfolio_id}), (company:Company {ticker: $ticker}) MERGE (position:Position {id: $position_id}) SET position += $properties MERGE (portfolio)-[:HOLDS]->(position) MERGE (position)-[:IN_COMPANY]->(company)", {"portfolio_id": portfolio["id"], "ticker": item["ticker"], "position_id": position_id, "properties": item})

    for claim in claims:
        graph.query("MERGE (claim:Claim {id: $id}) SET claim += $properties MERGE (t:Tenant {id: 'tenant-signalshield'})-[:HAS_CLAIM]->(claim)", {"id": claim["id"], "properties": claim})
        for company in companies:
            if company["ticker"].lower() in claim["text"].lower():
                graph.query("MATCH (claim:Claim {id: $claim_id}), (company:Company {ticker: $ticker}) MERGE (claim)-[:MENTIONS]->(company)", {"claim_id": claim["id"], "ticker": company["ticker"]})

    for filing in sec_snapshot.get("disclosures", []):
        graph.query("MATCH (company:Company {ticker: $ticker}) MERGE (disclosure:Disclosure {id: $id}) SET disclosure += $properties MERGE (company)-[:PUBLISHED]->(disclosure) MERGE (source:Source {id: $source_id}) SET source.name = 'SEC EDGAR', source.kind = 'official filing repository' MERGE (disclosure)-[:SOURCED_FROM]->(source)", {"ticker": filing["ticker"], "id": filing["id"], "source_id": "source-sec-edgar", "properties": filing})
    print(f"Seeded {len(companies)} companies, {len(claims)} illustrative claims, {len(portfolio.get('positions', []))} demo positions, and {len(sec_snapshot.get('disclosures', []))} official disclosures.")


if __name__ == "__main__":
    seed()
