"""Remove only demo review workflow history from the SignalShield graph.

This preserves the seeded companies, claims, SEC disclosure metadata, sources,
and illustrative portfolio.  It exists to prepare a clean demo recording.
"""

import argparse

from graph_db import get_graph, rows


HISTORY_LABELS = ("Decision", "ReviewCase", "AgentHandoff")


def count(label: str) -> int:
    return int(rows(f"MATCH (node:{label}) RETURN count(node)")[0][0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear SignalShield review workflow history.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required acknowledgement before deleting review cases, decisions, and handoffs.",
    )
    args = parser.parse_args()

    before = {label: count(label) for label in HISTORY_LABELS}
    print("Review history currently stored:", before)
    if not args.confirm:
        print("Nothing was deleted. Re-run with: python reset_review_history.py --confirm")
        return

    graph = get_graph()
    # Delete dependent nodes individually so all attached relationships disappear too.
    for label in HISTORY_LABELS:
        graph.query(f"MATCH (node:{label}) DETACH DELETE node")

    after = {label: count(label) for label in HISTORY_LABELS}
    assert not any(after.values()), after
    print("Review history cleared:", after)
    print("Preserved: companies, claims, SEC disclosures, sources, and demo portfolio.")


if __name__ == "__main__":
    main()
