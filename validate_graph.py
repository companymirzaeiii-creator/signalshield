"""Fast, repeatable checks for the SignalShield demo graph."""

from graph_db import rows


def scalar(query: str) -> int:
    return int(rows(query)[0][0])


def main() -> None:
    checks = {
        "watchlist companies": scalar("MATCH (company:Company) RETURN count(company)"),
        "official disclosures": scalar("MATCH (disclosure:Disclosure)-[:SOURCED_FROM]->(:Source {id: 'source-sec-edgar'}) RETURN count(disclosure)"),
        "claim-company links": scalar("MATCH (:Claim)-[:MENTIONS]->(:Company) RETURN count(*)"),
        "evidence paths": scalar("MATCH (:Claim)-[:MENTIONS]->(:Company)-[:PUBLISHED]->(:Disclosure)-[:SOURCED_FROM]->(:Source) RETURN count(*)"),
        "demo portfolio positions": scalar("MATCH (:Portfolio)-[:HOLDS]->(:Position)-[:IN_COMPANY]->(:Company) RETURN count(*)"),
    }
    assert checks["watchlist companies"] == 4, checks
    assert checks["official disclosures"] >= 4, checks
    assert checks["claim-company links"] >= 2, checks
    assert checks["evidence paths"] >= 2, checks
    assert checks["demo portfolio positions"] == 4, checks
    for name, value in checks.items():
        print(f"PASS {name}: {value}")


if __name__ == "__main__":
    main()
