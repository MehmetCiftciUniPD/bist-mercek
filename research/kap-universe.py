"""Capture issuers on KAP's four main equity-market segments."""
import argparse
from datetime import date
import json
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

from lxml import html

SOURCE = "https://kap.org.tr/tr/Pazarlar"
SEGMENTS = {"YILDIZ PAZAR", "ANA PAZAR", "ALT PAZAR", "YAKIN İZLEME PAZARI"}
ROOT = Path(__file__).resolve().parents[1]


def collect(document):
    issuers = {}
    segment = None
    for row in html.fromstring(document).xpath("//tr"):
        cells = row.xpath("./td")
        if len(cells) == 1:
            heading = cells[0].text_content().strip()
            segment = next((name for name in SEGMENTS if heading.startswith(name)), None)
        if not segment or len(cells) != 4:
            continue
        codes = cells[1].xpath(".//a")
        names = cells[2].xpath(".//a[contains(@href,'/sirket-bilgileri/ozet/')]")
        if not codes or not names:
            continue
        profile = urljoin(SOURCE, names[0].get("href"))
        issuer = issuers.setdefault(profile, {
            "name": names[0].text_content().strip(),
            "kapProfile": profile,
            "codes": set(),
            "segments": set(),
        })
        issuer["codes"].update(code.text_content().strip() for code in codes)
        issuer["segments"].add(segment)
    if len(issuers) < 500:
        raise ValueError(f"Expected at least 500 issuer records, parsed {len(issuers)}")
    return [
        {**issuer, "codes": sorted(issuer["codes"]), "segments": sorted(issuer["segments"])}
        for issuer in sorted(issuers.values(), key=lambda entry: min(entry["codes"]))
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--html", type=Path, help="Optional downloaded KAP market page")
    args = parser.parse_args()
    if args.html:
        document = args.html.read_bytes()
    else:
        with urlopen(SOURCE, timeout=30) as response:
            document = response.read()
    companies = collect(document)
    target = ROOT / "data" / "kap-universe.json"
    target.write_text(json.dumps({"date": args.date.isoformat(), "source": SOURCE, "companies": companies}, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(companies)} issuers, {sum(len(i['codes']) for i in companies)} codes")
