#!/usr/bin/env python3
"""Turn the legal documents in data/raw into section-level chunks (data/processed/chunks.jsonl).

Usage (from repo root):
    python scripts/ingest.py                 # ingest every enabled source in data/sources.yaml
    python scripts/ingest.py --dump-text     # also write the cleaned text per source for eyeballing

How it works
  1. Find each enabled source's file in data/raw. A hand-corrected `<name>.txt` beside a PDF wins over the PDF.
  2. Extract text (pypdf for PDFs), drop gazette headers/footnotes/page numbers.
  3. Detect section headings ("4. Procedure for ...") with a monotonic 1,2,3... rule, so the table of contents
     and stray numbered lines do not create fake sections. A trailing SCHEDULE becomes its own section.
  4. One chunk per section; long sections are split at sub-section markers "(2)".
  5. Print a report. READ IT: gaps in section numbers or tiny chunks mean the text needs hand-fixing.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.retrieval import Chunk  # noqa: E402

MAX_WORDS = 350

_NOISE = [
    re.compile(r"gazette\s+of\s+pakistan", re.I),
    re.compile(r"^\s*(?:\d\s*)?(?:Subs\.|Ins\.|Omitted|Added|Rep\.)\b.*$", re.I),
    re.compile(r"^\s*Price\s*:.*$", re.I),
    re.compile(r"^\s*\[?\*+\]?\s*$"),
    re.compile(r"^\s*\d{1,3}\s*$"),  # lone page numbers
    re.compile(r"^\s*(?:Page\s+)?\d+\s+of\s+\d+\s*$", re.I),
]
_HEADING = re.compile(r"^\s*(\d{1,3})\s*\.\s*(.*)$")
_SCHEDULE = re.compile(r"^\s*(?:THE\s+)?SCHEDULE\b")


@dataclass
class Section:
    num: str
    heading: str
    body: str


# ---------------------------------------------------------------------------------------------------
def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def clean_text(text: str) -> str:
    lines = []
    for line in text.replace("\r", "").split("\n"):
        if any(rx.search(line) for rx in _NOISE):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines)


def _collapse(s: str) -> str:
    return " ".join(s.split())


def split_sections(text: str) -> list[Section]:
    """Find 1,2,3... section headings. Returns [] when fewer than 3 are found."""
    lines = text.split("\n")
    offsets, pos = [], 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1

    cands = []  # (line_index, number)
    for i, ln in enumerate(lines):
        m = _HEADING.match(ln)
        if m:
            cands.append((i, int(m.group(1))))

    def build_sequence(start: int) -> list[tuple[int, int]]:
        seq = [cands[start]]
        for cand in cands[start + 1 :]:
            if cand[1] == seq[-1][1] + 1:
                seq.append(cand)
        return seq

    best: list[tuple[int, int]] = []
    best_score = -1.0
    for idx, (_, num) in enumerate(cands):
        if num != 1:
            continue
        seq = build_sequence(idx)
        if len(seq) < 3:
            continue
        bodies = []
        for a, b in zip(seq, seq[1:]):
            bodies.append(offsets[b[0]] - offsets[a[0]])
        score = statistics.median(bodies) if bodies else 0
        if score > best_score:
            best, best_score = seq, score
    if len(best) < 3:
        return []

    # Optional trailing schedule after the last numbered section
    last_line = best[-1][0]
    sched_line = next((i for i in range(last_line + 1, len(lines)) if _SCHEDULE.match(lines[i]) and lines[i].strip().upper() == lines[i].strip()), None)

    sections: list[Section] = []
    bounds = [b[0] for b in best] + ([sched_line] if sched_line is not None else []) + [len(lines)]
    for k, (line_idx, num) in enumerate(best):
        end = bounds[k + 1]
        first = _HEADING.match(lines[line_idx])
        rest = first.group(2).strip() if first else ""
        body_lines = lines[line_idx + 1 : end]
        heading = rest
        if not heading and body_lines:
            heading = body_lines[0].strip()
            body_lines = body_lines[1:]
        # headings in gazette text end at the first full stop or dash; keep the short title only
        title = re.split(r"[\.—–]-?\s", heading, maxsplit=1)[0].strip(" .-—")
        remainder = heading[len(title):].strip(" .-—") if heading.startswith(title) else ""
        body = _collapse(" ".join([remainder, *body_lines]))
        sections.append(Section(str(num), _collapse(title)[:140], body))
    if sched_line is not None:
        sections.append(Section("Schedule", "Schedule", _collapse(" ".join(lines[sched_line:]))))
    return sections


def window_chunks(text: str, size: int = 300, overlap: int = 50) -> list[Section]:
    words = _collapse(text).split()
    out, i, k = [], 0, 1
    while i < len(words):
        out.append(Section(f"window-{k}", "", " ".join(words[i : i + size])))
        i += size - overlap
        k += 1
    return out


def pack(body: str, max_words: int = MAX_WORDS) -> list[str]:
    """Split a long section at sub-section markers, then sentences, into pieces <= max_words."""
    if len(body.split()) <= max_words:
        return [body]
    pieces = re.split(r"(?<=[\.;:])\s+(?=\(\d{1,2}\)\s)", body)
    refined: list[str] = []
    for p in pieces:
        if len(p.split()) > max_words * 1.5:
            refined += re.split(r"(?<=\.)\s+(?=[A-Z])", p)
        else:
            refined.append(p)
    out, cur = [], []
    for p in refined:
        if cur and len(" ".join(cur + [p]).split()) > max_words:
            out.append(" ".join(cur))
            cur = []
        cur.append(p)
    if cur:
        out.append(" ".join(cur))
    return out


def build_chunks(source: dict, text: str, as_of: str) -> tuple[list[Chunk], list[str]]:
    warnings: list[str] = []
    sections = split_sections(text)
    if not sections:
        warnings.append("Fewer than 3 numbered sections found: fell back to fixed-size windows. Hand-fix the text.")
        sections = window_chunks(text)
    chunks: list[Chunk] = []
    for sec in sections:
        parts = pack(sec.body)
        if len(sec.body.split()) < 8 and sec.num != "Schedule":
            warnings.append(f"Section {sec.num} is very short ({len(sec.body.split())} words): check extraction.")
        for n, part in enumerate(parts, start=1):
            suffix = f":p{n}" if len(parts) > 1 else ""
            chunks.append(
                Chunk(
                    id=f"{source['id']}:s{sec.num}{suffix}",
                    source_id=source["id"],
                    act=source["act"],
                    jurisdiction=source["jurisdiction"],
                    topic=source["topic"],
                    section=sec.num,
                    heading=sec.heading,
                    text=part,
                    source_url=source.get("url", ""),
                    as_of=as_of,
                )
            )
    nums = [int(s.num) for s in sections if s.num.isdigit()]
    if nums and nums != list(range(1, len(nums) + 1)):
        warnings.append(f"Section numbers are not contiguous: {nums}")
    return chunks, warnings


# ---------------------------------------------------------------------------------------------------
def find_file(raw_dir: Path, filename: str) -> Path | None:
    stem = Path(filename).stem
    corrected = raw_dir / f"{stem}.txt"
    if corrected.exists():
        return corrected
    p = raw_dir / filename
    return p if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--sources", type=Path, default=ROOT / "data" / "sources.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processed" / "chunks.jsonl")
    ap.add_argument("--dump-text", action="store_true", help="write cleaned text to data/processed/text/")
    args = ap.parse_args()

    sources = yaml.safe_load(args.sources.read_text(encoding="utf-8"))["sources"]
    as_of = date.today().isoformat()
    all_chunks: list[Chunk] = []
    missing = 0

    print(f"{'source':28} {'file':34} {'sections':>8} {'chunks':>7}")
    for src in sources:
        if not src.get("enabled", False):
            continue
        path = find_file(args.raw, src["file"])
        if path is None:
            print(f"{src['id']:28} {'MISSING ' + src['file']:34} {'-':>8} {'-':>7}")
            print(f"    download: {src.get('url', '(no url)')}")
            missing += 1
            continue
        text = clean_text(extract_text(path))
        chunks, warnings = build_chunks(src, text, as_of)
        all_chunks += chunks
        n_sections = len({c.section for c in chunks})
        print(f"{src['id']:28} {path.name:34} {n_sections:>8} {len(chunks):>7}")
        for w in warnings:
            print(f"    WARNING: {w}")
        if args.dump_text:
            out_txt = args.out.parent / "text" / f"{src['id']}.txt"
            out_txt.parent.mkdir(parents=True, exist_ok=True)
            out_txt.write_text(text, encoding="utf-8")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
    try:
        shown = args.out.resolve().relative_to(ROOT)
    except ValueError:
        shown = args.out
    print(f"\nWrote {len(all_chunks)} chunks to {shown}")
    if missing:
        print(f"{missing} enabled source file(s) missing. Put them in data/raw/ and re-run.")
    return 0 if all_chunks else 1


if __name__ == "__main__":
    raise SystemExit(main())
