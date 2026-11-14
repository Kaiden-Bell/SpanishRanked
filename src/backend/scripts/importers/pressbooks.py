"""Generic Pressbooks importer: fetch a book through its public REST API and write a content pack.

A content pack is plain files the app reads at startup (see app/curriculum/packs.py):

    <pack>/manifest.json   book metadata, license, attribution, retrieval date
    <pack>/sections.json   one record per section: path, title, kind, module, source URL, license
    <pack>/sections/**.md  the converted text
    <pack>/ATTRIBUTION.md  human-readable credits (generated)

Only text is kept. Images, audio, video and embedded exercises are dropped: their licenses are
often different from the book's, and the app generates its own exercises.

This runs on a developer machine, never during the Docker build, so builds make no network calls.
Book-specific rules (which pages to keep and what kind they are) live in a small per-book module,
e.g. chevere.py, which calls fetch() and build().
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

USER_AGENT = "spanish-study-content-importer"


# --- fetching -------------------------------------------------------------------------------

def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch(base_url: str, raw_dir: Path) -> None:
    """Download metadata, table of contents and every chapter into raw_dir (JSON, as served)."""
    api = base_url.rstrip("/") + "/wp-json/pressbooks/v2"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "metadata.json").write_text(json.dumps(_get_json(f"{api}/metadata")), encoding="utf-8")
    (raw_dir / "toc.json").write_text(json.dumps(_get_json(f"{api}/toc")), encoding="utf-8")
    chapters, page = [], 1
    while True:
        try:
            batch = _get_json(f"{api}/chapters?per_page=100&page={page}")
        except urllib.error.HTTPError as e:  # WordPress answers 400 past the last page
            if e.code == 400:
                break
            raise
        if not isinstance(batch, list) or not batch:
            break
        chapters.extend(batch)
        page += 1
        time.sleep(0.5)
    (raw_dir / "chapters.json").write_text(json.dumps(chapters), encoding="utf-8")


def load_raw(raw_dir: Path) -> tuple[dict, dict, dict[int, dict]]:
    metadata = json.loads((raw_dir / "metadata.json").read_text(encoding="utf-8"))
    toc = json.loads((raw_dir / "toc.json").read_text(encoding="utf-8"))
    files = [raw_dir / "chapters.json"] if (raw_dir / "chapters.json").exists() else sorted(raw_dir.glob("chapters_*.json"))
    chapters: dict[int, dict] = {}
    for f in files:
        for c in json.loads(f.read_text(encoding="utf-8")):
            if isinstance(c, dict):
                chapters[c["id"]] = c
    return metadata, toc, chapters


# --- HTML -> Markdown ------------------------------------------------------------------------

DROP = {"img", "iframe", "video", "audio", "source", "track", "script", "style", "object", "embed",
        "svg", "noscript", "form", "input", "button", "figcaption"}
VOID = {"br", "hr", "img", "input", "source", "track", "embed", "meta", "link", "col", "wbr", "area", "param"}
BLOCK = {"p", "div", "section", "article", "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr",
         "td", "th", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "dl", "dt", "dd", "figure", "pre"}


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)  # Node | str


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        # Tolerate sloppy HTML: close up to the nearest matching open tag, ignore stray end tags.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _classes(node: Node) -> set[str]:
    return set((node.attrs.get("class") or "").split())


def _dropped(node: Node) -> bool:
    if node.tag in DROP:
        return True
    cls = _classes(node)
    # WordPress image captions and H5P/interactive wrappers carry only media. Lumen's per-page
    # "Candela Citations" block mostly credits images; the pack's own attribution replaces it.
    return bool(cls & {"wp-caption-text", "h5p-iframe-wrapper", "h5p-content", "wp-video", "embed-responsive",
                       "citations-section"})


_SHORTCODE = re.compile(r"\[(?:/?h5p|/?caption|/?embed|/?audio|/?video)[^\]]*\]")


def _inline(nodes: list) -> str:
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(_SHORTCODE.sub("", n))
            continue
        if _dropped(n):
            continue
        if n.tag == "br":
            out.append("  \n")
            continue
        inner = _inline(n.children)
        if n.tag in ("strong", "b"):
            out.append(_wrap(inner, "**"))
        elif n.tag in ("em", "i"):
            out.append(_wrap(inner, "*"))
        elif n.tag == "code":
            out.append(_wrap(inner, "`"))
        else:  # a, span, sup, sub, u, mark ... keep the text only
            out.append(inner)
    return "".join(out)


def _wrap(text: str, mark: str) -> str:
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    # Collapse marker nesting such as **  **x** ** produced by redundant markup.
    if core.startswith(mark) and core.endswith(mark) and len(core) > 2 * len(mark):
        return text
    return f"{lead}{mark}{core}{mark}{trail}"


def _clean_inline(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


class _Renderer:
    def __init__(self, heading_offset: int):
        self.heading_offset = heading_offset

    def blocks(self, nodes: list, depth: int = 0) -> list[str]:
        out: list[str] = []
        inline_run: list = []

        def flush():
            if inline_run:
                text = _clean_inline(_inline(inline_run))
                # A paragraph that starts with "* note" or "1. " would turn into a list.
                text = re.sub(r"^([*+-] )", r"\\\1", text)
                text = re.sub(r"^(\d+)\. ", r"\1\\. ", text)
                if text:
                    out.append(text)
                inline_run.clear()

        for n in nodes:
            if isinstance(n, str) or (n.tag not in BLOCK and not _dropped(n)):
                inline_run.append(n)
                continue
            flush()
            if _dropped(n):
                continue
            out.extend(self.block(n, depth))
        flush()
        return out

    def block(self, n: Node, depth: int) -> list[str]:
        t = n.tag
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = min(6, max(2, int(t[1]) + self.heading_offset))
            text = _clean_inline(_inline(n.children)).replace("\n", " ")
            return [f"{'#' * level} {text}"] if text else []
        if t == "hr":
            return ["---"]
        if t in ("ul", "ol"):
            return [self.list_(n, depth)]
        if t == "table":
            table = self.table(n)
            return [table] if table else []
        if t == "blockquote":
            inner = "\n\n".join(self.blocks(n.children, depth))
            return ["\n".join("> " + line if line else ">" for line in inner.split("\n"))] if inner else []
        if t == "pre":
            return ["```\n" + _inline(n.children).strip("\n") + "\n```"]
        return self.blocks(n.children, depth)

    def list_(self, n: Node, depth: int) -> str:
        lines, i = [], 1
        for li in n.children:
            if isinstance(li, str) or li.tag != "li":
                continue
            marker = f"{i}." if n.tag == "ol" else "-"
            i += 1
            inline_parts = [c for c in li.children if isinstance(c, str) or c.tag not in ("ul", "ol", "table")]
            text = " ".join(b.replace("\n", " ") for b in self.blocks(inline_parts, depth + 1))
            pad = "    " * depth  # 4 spaces nests correctly under both "-" and "1." markers
            if text:
                lines.append(f"{pad}{marker} {text}")
            for sub in li.children:
                if isinstance(sub, Node) and sub.tag in ("ul", "ol"):
                    lines.append(self.list_(sub, depth + 1))
                elif isinstance(sub, Node) and sub.tag == "table":
                    # A table can't live inside a Markdown list item: close the list, show the
                    # table, and let the next item continue the numbering (1. ... 2. ... table 3.).
                    table = self.table(sub)
                    if table:
                        lines.append("\n" + table + "\n")
        return "\n".join(lines)

    def table(self, n: Node) -> str:
        rows: list[list[str]] = []

        def walk(node: Node):
            for c in node.children:
                if isinstance(c, str) or _dropped(c):
                    continue
                if c.tag == "tr":
                    cells = []
                    for cell in c.children:
                        if isinstance(cell, Node) and cell.tag in ("td", "th"):
                            text = " ".join(self.blocks(cell.children)).replace("\n", " ").replace("|", "\\|")
                            cells.append(text.strip())
                            span = int(cell.attrs.get("colspan") or 1) if str(cell.attrs.get("colspan") or "1").isdigit() else 1
                            cells.extend([""] * (span - 1))
                    rows.append(cells)
                elif c.tag != "caption":
                    walk(c)

        walk(n)
        rows = [r for r in rows if any(r)]
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)


def html_to_markdown(html: str, heading_offset: int = 0) -> str:
    tb = _TreeBuilder()
    tb.feed(html)
    tb.close()
    md = "\n\n".join(b for b in _Renderer(heading_offset).blocks(tb.root.children) if b.strip())
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


# --- pack writing ------------------------------------------------------------------------------

@dataclass
class Section:
    source_id: int
    path: str            # relative to the pack's sections/ folder, e.g. "m03/gramatica-hora.md"
    title: str
    kind: str            # vocabulary | grammar | context | reading | culture
    module: int
    module_title: str
    source_url: str
    license: dict        # {"code": "CC BY 4.0", "url": ...}
    extra_attribution: list[str] = field(default_factory=list)


def slugify(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70] or "section"


def write_pack(pack_dir: Path, manifest: dict, sections: list[Section], chapters: dict[int, dict],
               render: Callable[[dict], str]) -> None:
    sec_dir = pack_dir / "sections"
    if sec_dir.exists():
        for f in sorted(sec_dir.rglob("*.md")):
            f.unlink()
    for s in sections:
        out = sec_dir / s.path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"# {s.title}\n\n" + render(chapters[s.source_id]), encoding="utf-8")
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "sections.json").write_text(
        json.dumps([s.__dict__ for s in sections], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "ATTRIBUTION.md").write_text(_attribution_md(manifest, sections), encoding="utf-8")


def _attribution_md(manifest: dict, sections: list[Section]) -> str:
    lic = manifest["license"]
    lines = [
        f"# Attribution: {manifest['title']}", "",
        f"This content pack is derived from *{manifest['title']}* by {', '.join(manifest['authors'])}"
        f"{', © ' + manifest['copyright_holder'] if manifest.get('copyright_holder') else ''},"
        f" {manifest['source_url']}, licensed under [{lic['code']}]({lic['url']}).", "",
        f"**Changes:** {manifest['changes']}", "",
        f"Retrieved {manifest['retrieved']}.", "",
    ]
    other = [s for s in sections if s.license["code"] != lic["code"] or s.extra_attribution]
    if other:
        lines += ["## Sections under different or additional terms", ""]
        for s in other:
            credits = "; ".join(s.extra_attribution)
            lines.append(f"- `{s.path}` ({s.title}): [{s.license['code']}]({s.license['url']}). {credits}".rstrip())
        lines.append("")
    return "\n".join(lines)


def today() -> str:
    return date.today().isoformat()
