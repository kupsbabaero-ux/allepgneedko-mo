#!/usr/bin/env python3
"""
Daily EPG updater for Philippine + selected international channels.
Fetches bulk sources + individual epg.pw channel guides, then merges
EVERYTHING into a single epg.xml (nothing is removed).
"""

from __future__ import annotations

import gzip
import hashlib
import io
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
EPG_DIR = ROOT / "epg"
EPG_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 45
# base64 of "Asia/Manila" → QXNpYS9NYW5pbGE=
EPG_PW_TZ = "timezone=QXNpYS9NYW5pbGE%3D"

# Bulk sources (mirrored individually AND merged into final epg.xml)
BULK_SOURCES: List[Tuple[str, str]] = [
    ("ph-tv-epg.xml", "https://raw.githubusercontent.com/kupsbabaero-ux/networkrival/main/epg/ph-tv-epg.xml"),
    ("epg_PH.xml", "https://epg.pw/xmltv/epg_PH.xml"),
    ("cinemaone-ctc.xml", "https://raw.githubusercontent.com/kupsbabaero-ux/cinemaonephh/refs/heads/main/epg.xml"),
    ("cinema_one_legacy.xml", "https://raw.githubusercontent.com/kupsbabaero-ux/cinemaoneph/refs/heads/main/cinema_one_epg.xml"),
    ("sony-epg.xml", "https://raw.githubusercontent.com/kupsbabaero-ux/sony-ones/refs/heads/main/epg/sony-epg.xml"),
]

# Individual channels from epg.pw (channel_id → friendly name)
EPG_PW_CHANNELS: Dict[str, str] = {
    "470612": "Citytv Calgary",
    "470487": "Citytv Edmonton",
    "470911": "Citytv Montreal",
    "470862": "Citytv Toronto",
    "369786": "HBO Family",
    "484241": "Cinema One Global",
    "369780": "Cartoon Network HD",
    "573024": "A2Z",
    "369848": "Animax",
    "486686": "Arirang",
    "491168": "GMA Pinoy TV",
    "491164": "GMA New TV",
    "491154": "GMA Life TV",
    "492840": "ANC Global",
    "369795": "Cinemax HD",
    "369648": "Discovery Asia HD",
    "2280": "Celestial Classic Movies",
    "491765": "Food Network HD",
    "577100": "Movies Now HD",
    "577049": "Romedy Now",
    "400477": "TNT Sports 1",
    "400480": "TNT Sports 2",
    "400479": "TNT Sports 3",
    "400478": "TNT Sports 4",
    "2323": "TVN",
    "576482": "UFC",
    "492861": "HGTV HD",
    "497971": "Vevo Pop",
    "465291": "Fox Sports 1",
    "369840": "HBO Hits",
    "464953": "HBO Comedy",
    "369758": "HBO Signature",
    "464745": "HBO US / Latino",
    "465302": "HBO West",
    "465104": "HBO Zone",
    "579509": "Kapatid Channel",
    "464884": "National Geographic Wild",
    "465372": "Fox News",
    "464766": "Fox Business",
    "465032": "AMC",
    "579034": "ABC Australia",
    "465059": "NBC",
    "457259": "Eurosport",
    "464912": "NBA TV",
    "573023": "IBC 13",
    "369767": "KBS World",
    "573012": "Knowledge Channel",
    "369832": "Lifetime",
    "573003": "Lotus Macau",
    "464989": "MYX PH",
    "491166": "Nick Jr",
    "573007": "Nickelodeon",
    "572994": "One News",
    "574441": "One PH",
    "572995": "Premier Sports 2",
    "572997": "Premier Sports",
    "573017": "PTV 4",
    "575522": "Rock Entertainment",
    "443416": "Rock Extreme",
    "573006": "SPOTV 2",
    "573013": "SPOTV",
    "573002": "TAP Movies",
    "573005": "TAP Sports",
    "76775": "Fashion TV",
    "456655": "HBO HD",
    "577121": "MNX",
    "577139": "MN+",
    "465261": "MGM+",
    "465375": "MGM Drive-In",
    "465284": "MGM+ Hits",
    "464921": "MGM+ Marquee",
    "399493": "Moonbug Kids",
    "573451": "NHK World",
    "368350": "KIX",
    "427994": "Studio Universal",
    "470497": "Super Channel Fuse",
    "470755": "Super Channel Heart & Home",
    "470877": "Super Channel Quest",
    "470327": "Super Channel Vault",
    "465236": "Tennis Channel",
    "368339": "Thrill",
    "457285": "Travel Channel",
    "470446": "TSN 1",
    "470401": "TSN 2",
    "470389": "TSN 3",
    "470730": "TSN 4",
    "470390": "TSN 5",
    "573018": "TV Maria",
    "463767": "TV5 Monde",
    "369580": "TVN Movies",
    "524145": "TVN Premiere",
    "457365": "Warner TV",
    "465041": "HBO 2",
    "573010": "France 24",
    "524135": "Global Trekker",
    "573014": "DepEd TV",
    "573004": "CNN",
    "573016": "Al Jazeera",
    "369785": "Animal Planet",
    "369716": "AXN",
    "369837": "BBC Earth",
    "369826": "BBC Lifestyle",
    "453387": "BBC World News",
    "575512": "Bilyonaryo",
    "369771": "Bloomberg",
    "492877": "DreamWorks",
    "369586": "Discovery Channel",
    "3362": "Crime & Investigation",
    "456649": "Channel NewsAsia",
    "492837": "CGTN",
    "492872": "CCTV 4",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})


def manila_date_str(days_offset: int = 0) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=8) + timedelta(days=days_offset)
    return now.strftime("%Y%m%d")


def download(url: str, retries: int = 2) -> Optional[bytes]:
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"  [warn] download failed ({attempt+1}): {url} → {e}")
            if attempt == retries:
                return None
    return None


def save_xml(path: Path, content: bytes) -> bool:
    """Write XML + .gz. Return True if content actually changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    old_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    path.write_bytes(content)
    gz_path = path.with_suffix(path.suffix + ".gz")
    with gzip.open(gz_path, "wb") as f:
        f.write(content)

    new_hash = hashlib.sha256(content).hexdigest()
    changed = old_hash != new_hash
    size_kb = len(content) / 1024
    print(f"  → {path.name} ({size_kb:.1f} KB) {'UPDATED' if changed else 'unchanged'}")
    return changed


def epg_pw_url(channel_id: str, date_str: str) -> str:
    return (
        f"https://epg.pw/api/epg.xml?lang=en&date={date_str}"
        f"&channel_id={channel_id}&{EPG_PW_TZ}"
    )


def parse_xmltv(raw: bytes) -> Optional[ET.Element]:
    try:
        return ET.parse(io.BytesIO(raw)).getroot()
    except ET.ParseError as e:
        print(f"  [warn] parse error: {e}")
        return None


class Merger:
    """Accumulate channels + programmes, keep first occurrence of each channel id."""

    def __init__(self) -> None:
        self.channels: Dict[str, ET.Element] = {}  # id → <channel>
        self.programmes: List[ET.Element] = []
        self.seen_prog: Set[str] = set()  # channel|start|stop to avoid exact dups

    def add(self, root: ET.Element) -> None:
        for ch in root.findall("channel"):
            cid = ch.get("id")
            if cid and cid not in self.channels:
                self.channels[cid] = ch

        for prog in root.findall("programme"):
            cid = prog.get("channel") or ""
            start = prog.get("start") or ""
            stop = prog.get("stop") or ""
            key = f"{cid}|{start}|{stop}"
            if key in self.seen_prog:
                continue
            self.seen_prog.add(key)
            self.programmes.append(prog)

    def to_bytes(self) -> bytes:
        root = ET.Element("tv")
        root.set("generator-info-name", "ph-epg-auto")
        root.set("generator-info-url", "https://github.com/")
        root.set("date", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S +0000"))

        for ch in self.channels.values():
            root.append(ch)
        for prog in self.programmes:
            root.append(prog)

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def fetch_bulk(merger: Merger) -> int:
    """Download bulk sources, save individually, feed into merger. Returns # changed files."""
    changed = 0
    print("\n=== Bulk sources ===")
    for filename, url in BULK_SOURCES:
        print(f"Fetching {filename} ...")
        data = download(url)
        if not data:
            print("  SKIP (failed)")
            continue
        if b"<tv" not in data[:3000] and b"<?xml" not in data[:300]:
            print("  SKIP (not XMLTV-looking)")
            continue

        if save_xml(EPG_DIR / filename, data):
            changed += 1

        root = parse_xmltv(data)
        if root is not None:
            before = len(merger.channels)
            merger.add(root)
            print(f"  merged +{len(merger.channels) - before} new channels")
    return changed


def fetch_epg_pw_channels(merger: Merger) -> int:
    """Fetch today+tomorrow for each listed channel and feed into merger."""
    print("\n=== epg.pw individual channels ===")
    today = manila_date_str(0)
    tomorrow = manila_date_str(1)
    got = 0

    for cid, name in EPG_PW_CHANNELS.items():
        for d in (today, tomorrow):
            url = epg_pw_url(cid, d)
            data = download(url, retries=1)
            if data and b"<programme" in data:
                root = parse_xmltv(data)
                if root is not None:
                    merger.add(root)
                    got += 1
                    print(f"  ✓ {name} ({cid}) {d}")
                    continue
            print(f"  ✗ {name} ({cid}) {d}")
    return got


def write_index() -> None:
    lines = [
        "# Auto-updated EPG files",
        "",
        f"Last run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Main combined file (use this)",
        "",
        "- `epg.xml` / `epg.xml.gz` — **lahat ng sources naka-merge** (bulk + individual epg.pw channels)",
        "",
        "## Individual mirrors (optional)",
        "",
    ]
    for p in sorted(EPG_DIR.glob("*.xml")):
        if p.name == "epg.xml":
            continue
        size = p.stat().st_size / 1024
        lines.append(f"- `{p.name}` ({size:.1f} KB)")
    lines.append("")
    lines.append("## Raw URLs (after push)")
    lines.append("")
    lines.append("```")
    lines.append("https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/epg/epg.xml")
    lines.append("https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/epg/epg.xml.gz")
    lines.append("```")
    (EPG_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print(f"EPG update started at {datetime.now(timezone.utc).isoformat()}")
    print(f"Manila date: {manila_date_str()}")

    merger = Merger()
    changed = 0

    changed += fetch_bulk(merger)
    fetch_epg_pw_channels(merger)

    print("\n=== Writing combined epg.xml ===")
    print(f"  channels: {len(merger.channels)}")
    print(f"  programmes: {len(merger.programmes)}")
    combined = merger.to_bytes()
    if save_xml(EPG_DIR / "epg.xml", combined):
        changed += 1

    write_index()
    print(f"\nDone. {changed} file(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
