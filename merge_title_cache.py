"""
Merge Lead Finder title-angle caches from multiple laptops into one file.

USAGE
    python merge_title_cache.py cache_from_alice.json cache_from_bob.json ... -o lead_title_cache.json

WHAT IT DOES
    - Each input file is a lead_title_cache.json copied from a colleague's
      cv_formatter folder.
    - Entries are matched by (family, evidence) — the exact content signature
      Lead Finder itself uses to decide a cache hit. Two entries only count as
      "the same" if they share the identical evidence-token set for the same
      role family; near-duplicates (overlapping but not identical evidence)
      are both kept, since they still represent distinct useful signatures.
    - When the same signature appears in more than one input file, hit counts
      are summed (this reflects real combined usage across your team) and the
      longer/most complete title list is kept.
    - If the merged total exceeds the cache cap (10,000 by default, matching
      app.py's _LEAD_TITLE_CACHE_MAX_ENTRIES), the lowest-hit entries are
      dropped first, not the oldest — under a shared/merged cache, how often
      an entry has actually been reused is a better signal to keep than when
      it happened to be created.

Copy this script + the cache files from each laptop onto one machine, run it,
then copy the resulting output file back into each laptop's cv_formatter
folder (overwriting their old lead_title_cache.json) to give everyone the
combined, deduplicated cache.
"""
import json
import sys
import argparse

DEFAULT_CAP = 10000


def load_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, list) else []
    except Exception as e:
        print(f"  ! Could not read {path}: {e}", file=sys.stderr)
        return []


def signature_key(entry):
    fam = entry.get("family") or ""
    evidence = tuple(sorted(entry.get("evidence") or []))
    return (fam, evidence)


def merge(input_paths, cap=DEFAULT_CAP):
    merged = {}  # signature -> entry
    total_seen = 0
    for path in input_paths:
        entries = load_cache(path)
        print(f"  {path}: {len(entries)} entrie(s)")
        total_seen += len(entries)
        for e in entries:
            if not isinstance(e, dict) or not e.get("family") or not e.get("evidence"):
                continue
            key = signature_key(e)
            if key not in merged:
                merged[key] = dict(e)
                merged[key]["hits"] = int(e.get("hits") or 0)
            else:
                existing = merged[key]
                existing["hits"] = int(existing.get("hits") or 0) + int(e.get("hits") or 0)
                # Keep whichever title list is longer/more complete.
                if len(e.get("titles") or []) > len(existing.get("titles") or []):
                    existing["titles"] = e.get("titles")
                # Keep the earliest creation date for provenance.
                if e.get("created_at") and (not existing.get("created_at") or e["created_at"] < existing["created_at"]):
                    existing["created_at"] = e["created_at"]

    all_entries = list(merged.values())
    dedup_count = len(all_entries)

    if len(all_entries) > cap:
        all_entries.sort(key=lambda e: int(e.get("hits") or 0), reverse=True)
        dropped = len(all_entries) - cap
        all_entries = all_entries[:cap]
        print(f"  Merged total ({dedup_count}) exceeds cap ({cap}); dropped {dropped} lowest-hit entrie(s).")

    by_family = {}
    for e in all_entries:
        by_family[e["family"]] = by_family.get(e["family"], 0) + 1

    return all_entries, total_seen, dedup_count, by_family


def main():
    ap = argparse.ArgumentParser(description="Merge Lead Finder title-angle caches from multiple laptops.")
    ap.add_argument("inputs", nargs="+", help="Path(s) to lead_title_cache.json files to merge")
    ap.add_argument("-o", "--output", default="lead_title_cache.json", help="Output path (default: lead_title_cache.json)")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP, help=f"Max entries to keep (default: {DEFAULT_CAP})")
    args = ap.parse_args()

    print(f"Merging {len(args.inputs)} cache file(s)...")
    all_entries, total_seen, dedup_count, by_family = merge(args.inputs, cap=args.cap)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"entries": all_entries}, f, ensure_ascii=False)

    print()
    print(f"Input entries (before dedup):  {total_seen}")
    print(f"Unique signatures after merge: {dedup_count}")
    print(f"Final entries written:         {len(all_entries)}")
    print(f"By family: " + ", ".join(f"{k}:{v}" for k, v in sorted(by_family.items(), key=lambda x: -x[1])))
    print(f"Wrote merged cache to: {args.output}")
    print()
    print("Next step: copy this file to each laptop's cv_formatter folder,")
    print("overwriting their existing lead_title_cache.json.")


if __name__ == "__main__":
    main()
