"""Download a small, reproducible metadata snapshot from the official SEC EDGAR API."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
WATCHLIST = ROOT / "data" / "watchlist.json"
OUTPUT = ROOT / "data" / "sec_disclosures.json"
RAW_DIR = ROOT / "data" / "raw"
FORMS = {"8-K", "10-K", "10-Q", "6-K"}


def sec_headers() -> dict[str, str]:
    # SEC requests a declared, descriptive user agent. Set SEC_USER_AGENT to a real project contact before a public demo.
    return {"User-Agent": os.getenv("SEC_USER_AGENT", "SignalShield hackathon contact@signalshield.local"), "Accept-Encoding": "gzip, deflate"}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    companies = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    collected_at = datetime.now(timezone.utc).isoformat()
    disclosures: list[dict[str, str]] = []

    for company in companies:
        cik = company["cik"].zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = requests.get(url, headers=sec_headers(), timeout=20)
        response.raise_for_status()
        payload = response.json()
        (RAW_DIR / f"CIK{cik}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        recent = payload["filings"]["recent"]
        for index, form in enumerate(recent["form"]):
            if form not in FORMS:
                continue
            accession = recent["accessionNumber"][index]
            primary_document = recent["primaryDocument"][index]
            accession_path = accession.replace("-", "")
            source_url = f"https://www.sec.gov/Archives/edgar/data/{int(company['cik'])}/{accession_path}/{primary_document}"
            disclosures.append({
                "id": f"sec-{company['ticker'].lower()}-{accession_path}",
                "ticker": company["ticker"],
                "form": form,
                "filed_at": recent["filingDate"][index],
                "accession": accession,
                "primary_document": primary_document,
                "source_url": source_url,
                "source_api": url,
                "ingested_at": collected_at,
            })
            if sum(1 for item in disclosures if item["ticker"] == company["ticker"]) >= 12:
                break

    OUTPUT.write_text(json.dumps({"collected_at": collected_at, "source": "SEC EDGAR submissions API", "disclosures": disclosures}, indent=2), encoding="utf-8")
    print(f"Saved {len(disclosures)} official filing metadata records to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
