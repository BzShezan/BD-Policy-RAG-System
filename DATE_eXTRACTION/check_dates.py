"""Coverage report and sanity check on extracted dates.

Writes to a file rather than the terminal, because cmd.exe on this
machine cannot render Bengali.

Two things to look at in the output: the year distribution, and the
source breakdown. A cluster of 2005 dates would mean the reference-memo
trap caught something. A dominance of 'filename' would mean most dates
are month precision only.
"""

import json
import os
from collections import Counter

from DATE_eXTRACTION import config


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def report(filename, out):
    path = os.path.join(config.PROCESSED_DIR, filename)
    if not os.path.exists(path):
        return

    clauses = load_jsonl(path)
    if not clauses:
        return

    # One entry per document, not per clause
    docs = {}
    for c in clauses:
        docs[c.get("doc_id", "")] = (
            c.get("circular_date", ""),
            c.get("date_source", "none"),
        )

    dated = {d: v for d, v in docs.items() if v[0]}
    undated = [d for d, v in docs.items() if not v[0]]

    out.write("\n" + "=" * 70 + "\n")
    out.write(f"{filename}\n")
    out.write("=" * 70 + "\n")
    out.write(f"documents: {len(docs)}\n")
    out.write(f"dated:     {len(dated)} ({len(dated) / len(docs) * 100:.1f}%)\n\n")

    out.write("by source:\n")
    for s, n in Counter(v[1] for v in docs.values()).most_common():
        out.write(f"  {s}: {n}\n")

    out.write("\nby year:\n")
    for y, n in sorted(Counter(v[0][:4] for v in dated.values()).items()):
        flag = "   <-- check this" if y < "1990" or y > "2027" else ""
        out.write(f"  {y}: {n}{flag}\n")

    out.write("\nsample dated documents:\n")
    for doc, (date, source) in list(dated.items())[:15]:
        out.write(f"  {date} [{source}] {doc[:60]}\n")

    if undated:
        out.write(f"\nundated documents ({len(undated)}):\n")
        for doc in undated[:20]:
            out.write(f"  {doc[:70]}\n")


def main():
    with open("date_report.txt", "w", encoding="utf-8") as out:
        for filename in config.TARGET_FILES:
            report(filename, out)
    print("written to date_report.txt")


if __name__ == "__main__":
    main()