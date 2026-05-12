"""Scrape the most populous Portuguese cities from Wikipedia and download
their lead images.

Usage:
    python scrape_portuguese_cities.py [--limit N] [--out DIR]

The script:
  1. Fetches "List of cities in Portugal" and parses the population table.
  2. Sorts cities by population (descending) and keeps the top N.
  3. For each city, calls the Wikipedia REST summary API to get the lead
     image URL, then downloads it to OUT/<slug>.<ext>.

Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Optional

WIKI = "https://en.wikipedia.org"
LIST_URL = f"{WIKI}/wiki/List_of_cities_in_Portugal"
SUMMARY_API = f"{WIKI}/api/rest_v1/page/summary/"
USER_AGENT = (
    "PortugueseCitiesScraper/1.0 "
    "(https://github.com/nunoteixeiramota/image-refac; educational use)"
)


def http_get(url: str, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": accept}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class CityTableParser(HTMLParser):
    """Extract (city_name, population) rows from the first wikitable on the page.

    The "List of cities in Portugal" article contains a sortable table with
    columns roughly: City | Municipality | District | Region | Population.
    We grab the first cell (city link text) and the last numeric cell of each
    row.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_wikitable = False
        self.table_depth = 0
        self.in_row = False
        self.in_cell = False
        self.cell_text: list[str] = []
        self.first_link_text: Optional[str] = None
        self.in_first_link = False
        self.row_cells: list[str] = []
        self.row_first_links: list[Optional[str]] = []
        self.rows: list[tuple[Optional[str], list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)
        if tag == "table":
            cls = attr_dict.get("class", "") or ""
            if not self.in_wikitable and "wikitable" in cls:
                self.in_wikitable = True
                self.table_depth = 1
            elif self.in_wikitable:
                self.table_depth += 1
        elif self.in_wikitable and tag == "tr":
            self.in_row = True
            self.row_cells = []
            self.row_first_links = []
        elif self.in_wikitable and tag in ("td", "th"):
            self.in_cell = True
            self.cell_text = []
            self.first_link_text = None
            self.in_first_link = False
        elif self.in_cell and tag == "a" and self.first_link_text is None:
            self.in_first_link = True
            self.first_link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.in_wikitable:
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_wikitable = False
        elif self.in_wikitable and tag == "tr" and self.in_row:
            self.in_row = False
            if self.row_cells:
                first_link = self.row_first_links[0] if self.row_first_links else None
                self.rows.append((first_link, self.row_cells))
        elif self.in_wikitable and tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            cell = " ".join("".join(self.cell_text).split()).strip()
            self.row_cells.append(cell)
            self.row_first_links.append(self.first_link_text)
        elif tag == "a" and self.in_first_link:
            self.in_first_link = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_text.append(data)
            if self.in_first_link and self.first_link_text is not None:
                self.first_link_text += data


def parse_population(text: str) -> Optional[int]:
    cleaned = re.sub(r"\[[^\]]*\]", "", text)  # strip footnotes like [1]
    cleaned = cleaned.replace("\xa0", " ")
    m = re.search(r"\d[\d,\. ]*", cleaned)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    return int(digits) if digits else None


def scrape_city_list() -> list[tuple[str, int]]:
    html = http_get(LIST_URL, accept="text/html").decode("utf-8", errors="replace")
    parser = CityTableParser()
    parser.feed(html)

    cities: dict[str, int] = {}
    for first_link, cells in parser.rows:
        if not first_link or len(cells) < 2:
            continue
        name = first_link.strip()
        if not name or name.lower() in {"city", "municipality", "district"}:
            continue
        # Try cells from the right; pick the largest plausible population value.
        best: Optional[int] = None
        for cell in reversed(cells):
            pop = parse_population(cell)
            if pop and pop > 500:  # ignore stray small numbers (year columns, etc.)
                if best is None or pop > best:
                    best = pop
                break
        if best is None:
            continue
        # Keep largest if the same city appears twice.
        if name not in cities or best > cities[name]:
            cities[name] = best

    return sorted(cities.items(), key=lambda kv: kv[1], reverse=True)


def fetch_image_url(title: str) -> Optional[str]:
    url = SUMMARY_API + urllib.parse.quote(title.replace(" ", "_"))
    try:
        data = json.loads(http_get(url, accept="application/json").decode("utf-8"))
    except Exception as e:
        print(f"  ! summary failed for {title}: {e}", file=sys.stderr)
        return None
    original = data.get("originalimage") or {}
    thumb = data.get("thumbnail") or {}
    return original.get("source") or thumb.get("source")


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return s or "city"


def download(url: str, dest_dir: str, slug: str) -> Optional[str]:
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}:
        ext = ".jpg"
    path = os.path.join(dest_dir, slug + ext)
    try:
        data = http_get(url, accept="image/*")
    except Exception as e:
        print(f"  ! download failed: {e}", file=sys.stderr)
        return None
    with open(path, "wb") as f:
        f.write(data)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20, help="number of top cities to fetch")
    ap.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "portuguese_cities"),
        help="output directory for images",
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"Fetching city list from {LIST_URL}")
    cities = scrape_city_list()
    if not cities:
        print("No cities parsed from the list page.", file=sys.stderr)
        return 1

    top = cities[: args.limit]
    print(f"Top {len(top)} cities by population:")
    for name, pop in top:
        print(f"  {name:<30} {pop:>10,}")

    manifest: list[dict] = []
    for name, pop in top:
        print(f"\n{name} (pop {pop:,})")
        img_url = fetch_image_url(name)
        if not img_url:
            print("  - no image available")
            manifest.append({"city": name, "population": pop, "image": None})
            continue
        print(f"  image: {img_url}")
        slug = slugify(name)
        saved = download(img_url, args.out, slug)
        if saved:
            size = os.path.getsize(saved)
            print(f"  saved {saved} ({size:,} bytes)")
        manifest.append(
            {"city": name, "population": pop, "image_url": img_url, "file": saved}
        )

    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nWrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
