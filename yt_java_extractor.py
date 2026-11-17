#!/usr/bin/env python3
"""Extract Java code from YouTube video descriptions (playlist or single video).

Works on messy text: no fixed structure needed. Every line is scored
as code-like or prose, then the code regions are cut out.
Search order: description -> pinned comment -> comments by the uploader.

Usage:
    python yt_java_extractor.py <playlist_or_video_url> [-o DIR] [--range 1-19]
    python yt_java_extractor.py --test description.txt     # test on a local file

Needs:  pip install yt-dlp
Output: DIR/01_title/Main.java (+ description.txt when nothing was found)
"""
import argparse
import re
import sys
from pathlib import Path

# ---------- line classification ----------
TYPES = r"(?:int|long|short|byte|double|float|char|boolean|String|var|Object|[A-Z]\w*(?:<[^>]*>)?)(?:\[\])*"
STRONG = [
    re.compile(r"^\s*(package|import)\s+[\w.*]+;"),
    re.compile(r"^\s*(public|private|protected|static|final|abstract)\b.*[{;(]\s*$"),
    re.compile(r"^\s*(class|interface|enum|record)\s+\w+"),
    re.compile(r"^\s*@\w+"),
    re.compile(r"^\s*(//|/\*|\*/|\*\s)"),
    re.compile(r"^\s*(if|else|for|while|do|switch|try|catch|finally)\b\s*[({]?"),
    re.compile(r"^\s*(case\b.+(:|->)|default\s*(:|->))"),
    re.compile(r"^\s*(return|break|continue|throw)\b.*;"),
    re.compile(r"\bSystem\.(out|in|err)\b"),
    re.compile(r"^\s*(final\s+)?" + TYPES + r"\s+\w+\s*(=|;|\()"),
    re.compile(r"^\s*\w+(\.\w+)*\s*(\+\+|--|[-+*/%&|^]?=)\s*.*;\s*$"),
    re.compile(r"^\s*[\w.]+\(.*\)\s*;\s*$"),
    re.compile(r"^\s*[{}]\s*;?\s*$"),
    re.compile(r".*[;{}]\s*$"),
]
PROSE = [
    re.compile(r"^\s*#\w"),                       # hashtags
    re.compile(r"https?://", re.I),               # links
    re.compile(r"^\s*\d{1,2}:\d{2}"),             # timestamps
    re.compile(r"^\s*(subscribe|follow|like|share|support|bro code|music|socials?)\b", re.I),
]
FENCE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.S)
CLASS_NAME = re.compile(r"public\s+(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+(\w+)")


def is_code(line: str) -> bool:
    if not line.strip():
        return False
    if any(p.search(line) for p in PROSE):
        return False
    s = line.strip()
    # sentence-like prose: many words ending with . ? ! :  (and no code punctuation)
    if re.search(r"[.?!:]$", s) and len(s.split()) > 4 and not re.search(r"[;{}()=]", s):
        return False
    return any(p.search(line) for p in STRONG)


def find_regions(lines: list[str], min_code: int = 2, max_gap: int = 2):
    """Group code-like lines into regions; blank lines (and a few odd lines) allowed inside."""
    regions, cur, gap = [], None, 0
    for i, l in enumerate(lines):
        if is_code(l):
            if cur is None:
                cur = [i, i, 1]
            else:
                cur[1], cur[2] = i, cur[2] + 1
            gap = 0
        elif cur is not None:
            if not l.strip():
                continue                      # blank inside region
            gap += 1
            if gap > max_gap - 1:             # prose line(s) -> close region
                regions.append(cur)
                cur, gap = None, 0
    if cur is not None:
        regions.append(cur)
    return [(a, b) for a, b, n in regions if n >= min_code]


def reindent(code: str) -> str:
    lines = code.split("\n")
    nonblank = [l for l in lines if l.strip()]
    if not nonblank or sum(1 for l in nonblank if l == l.lstrip()) / len(nonblank) < 0.7:
        return code                                   # already indented
    depth, out = 0, []
    for l in lines:
        s = l.strip()
        if not s:
            out.append("")
            continue
        clean = re.sub(r'"(\\.|[^"\\])*"|\'(\\.|[^\'\\])*\'|//.*', "", s)
        lead_close = len(clean) - len(clean.lstrip("}"))
        d = max(depth - lead_close, 0)
        if s.startswith(("case ", "default")) and not s.startswith("default ->") and "->" not in s:
            d = max(d, 0)
        out.append("    " * d + s)
        depth = max(depth + clean.count("{") - clean.count("}"), 0)
    return "\n".join(out)


AUTO_IMPORTS = {"Scanner": "java.util.Scanner", "Random": "java.util.Random",
                "ArrayList": "java.util.ArrayList", "HashMap": "java.util.HashMap",
                "Arrays": "java.util.Arrays", "LocalDate": "java.time.LocalDate",
                "LocalTime": "java.time.LocalTime", "Timer": "java.util.Timer",
                "TimerTask": "java.util.TimerTask"}


def add_missing_imports(code: str) -> str:
    need = [f"import {fq};" for name, fq in AUTO_IMPORTS.items()
            if re.search(rf"\b{name}\b", code) and fq not in code]
    return ("\n".join(need) + "\n" + code) if need else code


def wrap_if_needed(code: str) -> str:
    """Snippet with no class -> make it runnable."""
    if re.search(r"\b(class|interface|enum|record)\s+\w+", code):
        return code
    imports = [l for l in code.split("\n") if re.match(r"\s*(import|package)\s", l)]
    body = [l for l in code.split("\n") if l not in imports]
    has_methods = re.search(r"^\s*(public|private|static)\s.*\)\s*\{?\s*$", "\n".join(body), re.M)
    pad = lambda ls, n: "\n".join(("    " * n + l if l.strip() else "") for l in ls)
    if has_methods:
        inner = pad(body, 1)
    else:
        inner = ("    public static void main(String[] args) {\n"
                 + pad(body, 2) + "\n    }")
    head = "\n".join(imports) + ("\n\n" if imports else "")
    return f"{head}// NOTE: wrapped in a class by the extractor\npublic class Main {{\n{inner}\n}}"


def extract_java(description: str, wrap: bool = True) -> str | None:
    if not description:
        return None
    desc = description.replace("\r\n", "\n")

    blocks = [b.strip("\n") for b in FENCE.findall(desc)]
    if blocks:
        code = "\n\n".join(blocks)
    else:
        lines = desc.split("\n")
        regions = find_regions(lines)
        if not regions:
            return None
        parts = ["\n".join(lines[a:b + 1]).strip("\n") for a, b in regions]
        code = "\n\n".join(parts)

    code = reindent(code)
    if wrap:
        code = wrap_if_needed(add_missing_imports(code))
    return code.rstrip() + "\n"


# ---------- helpers ----------
def safe(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s-]+", "_", text)[:60] or "video"


def parse_range(r: str | None, total: int) -> range:
    if not r:
        return range(1, total + 1)
    a, _, b = r.partition("-")
    return range(int(a), int(b or a) + 1)


def code_from_comments(ydl_comments, url: str, wrap: bool):
    """Fetch comments and look for code: pinned first, then uploader comments."""
    v = ydl_comments.extract_info(url, download=False)
    comments = v.get("comments") or []
    pinned = [c for c in comments if c.get("is_pinned")]
    uploader = [c for c in comments if c.get("author_is_uploader") and not c.get("is_pinned")]
    for label, group in (("pinned comment", pinned), ("uploader comment", uploader)):
        for c in group:
            code = extract_java(c.get("text", ""), wrap=wrap)
            if code:
                return code, label, c.get("text", "")
    return None, None, "\n\n---\n\n".join(c.get("text", "") for c in (pinned + uploader))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("-o", "--output", default="java_from_videos")
    ap.add_argument("--range", help="playlist positions, e.g. 1-19 or 5")
    ap.add_argument("--no-wrap", action="store_true", help="do not wrap snippets in a class")
    ap.add_argument("--no-comments", action="store_true", help="do not look in comments")
    ap.add_argument("--save-description", action="store_true", help="always save description.txt")
    ap.add_argument("--test", metavar="FILE", help="run extraction on a local text file and print result")
    args = ap.parse_args()

    if args.test:
        text = Path(args.test).read_text(encoding="utf-8")
        print(extract_java(text, wrap=not args.no_wrap) or "NO CODE FOUND")
        return
    if not args.url:
        ap.error("give a URL or use --test FILE")

    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp missing. Run: pip install yt-dlp")

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": "in_playlist", "skip_download": True}) as ydl:
        info = ydl.extract_info(args.url, download=False)
    entries = info.get("entries") or [info]
    missing = []

    c_opts = {"quiet": True, "skip_download": True, "noplaylist": True, "getcomments": True,
              "extractor_args": {"youtube": {"max_comments": ["15", "15", "0", "0"],
                                             "comment_sort": ["top"]}}}
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl, \
            yt_dlp.YoutubeDL(c_opts) as ydl_c:
        for pos in parse_range(args.range, len(entries)):
            if pos > len(entries) or not entries[pos - 1]:
                continue
            e = entries[pos - 1]
            url = e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={e['id']}"
            try:
                v = ydl.extract_info(url, download=False)
            except Exception as ex:
                print(f"[{pos:02d}] FAILED: {ex}")
                missing.append(pos)
                continue

            title, desc = v.get("title", f"video_{pos}"), v.get("description", "")
            folder = out / f"{pos:02d}_{safe(title)}"
            code = extract_java(desc, wrap=not args.no_wrap)
            source, extra = "description", ""

            if code is None and not args.no_comments:
                try:
                    code, source, extra = code_from_comments(ydl_c, url, not args.no_wrap)
                except Exception as ex:
                    print(f"[{pos:02d}] comments failed: {ex}")

            if code is None or args.save_description:
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "description.txt").write_text(desc, encoding="utf-8")
                if extra:
                    (folder / "comments.txt").write_text(extra, encoding="utf-8")
            if code is None:
                print(f"[{pos:02d}] NO CODE: {title}  (description/comments saved)")
                missing.append(pos)
                continue

            folder.mkdir(parents=True, exist_ok=True)
            m = CLASS_NAME.search(code)
            name = (m.group(1) if m else "Main") + ".java"
            (folder / name).write_text(code, encoding="utf-8")
            print(f"[{pos:02d}] saved {folder.name}/{name}  (from {source})")

    print(f"\nDone. Output: {out.resolve()}")
    if missing:
        print("Check these positions by hand:", ", ".join(map(str, missing)))


if __name__ == "__main__":
    main()
