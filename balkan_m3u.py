#!/usr/bin/env python3
"""
Builds one merged Balkan IPTV playlist from the iptv-org country lists.

Usage:
    python3 balkan_m3u.py                 # merge + dedupe only (fast)
    python3 balkan_m3u.py --check         # also drop streams that don't respond
    python3 balkan_m3u.py -o /path/balkan.m3u --check --workers 40

Needs only Python 3.8+ (no extra packages).
"""
import argparse
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://iptv-org.github.io/iptv/countries/{}.m3u"
COUNTRIES = {
    "mk": "North Macedonia",
    "rs": "Serbia",
    "hr": "Croatia",
    "ba": "Bosnia and Herzegovina",
    "me": "Montenegro",
    "al": "Albania",
    "xk": "Kosovo",
    "si": "Slovenia",
    "bg": "Bulgaria",
}
UA = {"User-Agent": "Mozilla/5.0 (balkan-m3u merger)"}


def fetch_text(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse(text):
    """Yield (extinf_line, [extra_lines], url) entries."""
    extinf, extras = None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            extinf, extras = line, []
        elif line.startswith("#"):
            if extinf:
                extras.append(line)
        elif extinf:
            yield extinf, extras, line
            extinf, extras = None, []


def set_group(extinf, group):
    if 'group-title="' in extinf:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', extinf)
    return extinf.replace("#EXTINF:", f'#EXTINF:', 1).replace(
        ",", f' group-title="{group}",', 1
    ) if "," in extinf else extinf


def alive(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status >= 400:
                return False
            r.read(512)  # make sure data actually flows
            return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="balkan.m3u")
    ap.add_argument("--check", action="store_true", help="drop dead streams")
    ap.add_argument("--workers", type=int, default=30)
    args = ap.parse_args()

    entries, seen = [], set()
    for code, name in COUNTRIES.items():
        try:
            text = fetch_text(BASE.format(code))
        except Exception as e:
            print(f"[skip] {code}: {e}", file=sys.stderr)
            continue
        n = 0
        for extinf, extras, url in parse(text):
            if url in seen:
                continue
            seen.add(url)
            entries.append((set_group(extinf, name), extras, url))
            n += 1
        print(f"{name}: {n} channels")

    if args.check:
        print(f"Checking {len(entries)} streams (this can take a few minutes)...")
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            ok = list(ex.map(lambda e: alive(e[2]), entries))
        entries = [e for e, good in zip(entries, ok) if good]
        print(f"{len(entries)} streams alive")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for extinf, extras, url in entries:
            f.write(extinf + "\n")
            for x in extras:
                f.write(x + "\n")
            f.write(url + "\n")
    print(f"Wrote {len(entries)} channels to {args.output}")


if __name__ == "__main__":
    main()
