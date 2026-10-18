"""Print the small set of graph paths used in the SignalShield demo."""

from graph_db import rows


def main() -> None:
    print("\n=== Node counts ===")
    for label in ("Company", "Disclosure", "Claim", "ReviewCase", "Decision", "AgentHandoff"):
        print(f"{label}: {rows(f'MATCH (node:{label}) RETURN count(node)')[0][0]}")

    print("\n=== Evidence paths ===")
    evidence = rows("MATCH (claim:Claim)-[:MENTIONS]->(company:Company)-[:PUBLISHED]->(disclosure:Disclosure)-[:SOURCED_FROM]->(source:Source) RETURN claim.id, company.ticker, disclosure.form, disclosure.filed_at, source.name ORDER BY disclosure.filed_at DESC LIMIT 12")
    for claim_id, ticker, form, filed_at, source in evidence:
        print(f"{claim_id} -> {ticker} -> {form} ({filed_at}) -> {source}")

    print("\n=== Demo portfolio exposure ===")
    exposure = rows("MATCH (portfolio:Portfolio)-[:HOLDS]->(position:Position)-[:IN_COMPANY]->(company:Company) RETURN portfolio.name, company.ticker, position.allocation_pct, position.market_value_usd ORDER BY position.allocation_pct DESC")
    for portfolio_name, ticker, allocation_pct, market_value in exposure:
        print(f"{portfolio_name} -> {ticker}: {allocation_pct:.1f}% (${market_value:,.0f})")

    print("\n=== Persisted coordination ===")
    handoffs = rows("MATCH (from:Agent)-[:HANDOFF_TO]->(handoff:AgentHandoff)-[:CREATED]->(review:ReviewCase) RETURN from.name, handoff.to_agent, review.id, review.status ORDER BY handoff.created_at DESC")
    if not handoffs:
        print("No cases yet. Create one in the app to see this path.")
    for from_agent, to_agent, review_id, status in handoffs:
        print(f"{from_agent} -> {to_agent} -> {review_id} [{status}]")


if __name__ == "__main__":
    main()
