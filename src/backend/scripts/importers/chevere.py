"""Build the bundled ¡Chévere! content pack from the Lumen Learning Pressbooks edition.

    python src/backend/scripts/importers/chevere.py fetch  RAW_DIR
    python src/backend/scripts/importers/chevere.py build  RAW_DIR [PACK_DIR]

"Introductory Spanish I" on Lumen (SUNY Oneonta) is the upstream original of ¡Chévere! I and II:
modules 1-23 in one book, CC BY 4.0, © Lumen Learning (checked 2026-11-13 via /wp-json/pressbooks/v2/metadata).

Kept: Vocabulario, Gramática, En contexto, Voces and Cultura pages, as text.
Dropped: exercises and activities (H5P; the app makes its own), discussions, assignments, intros,
and every image, audio clip and video (third-party licenses vary page by page).

License exceptions were found by reading every page's `_candela_citation` metadata. Almost all
non-CC-BY entries are photos, which are dropped anyway. The pages below also adapt *text* from
CC BY-SA sources, so those sections are marked CC BY-SA 4.0 with the extra credit. They stay in
their own files and are never merged into CC BY text.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pressbooks as pb  # noqa: E402

BASE_URL = "https://courses.lumenlearning.com/suny-oneonta-spanish1-2-print-sp2021"
PACK_DIR = Path(__file__).resolve().parents[2] / "content" / "packs" / "chevere"

CC_BY = {"code": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}
CC_BY_SA = {"code": "CC BY-SA 4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0/"}

_WIKIBOOKS = "Wikibooks contributors, *Spanish* (https://en.wikibooks.org/wiki/Spanish), CC BY-SA"
SHARE_ALIKE_TEXT = {
    53: "Section cited by its authors as CC BY-SA (Gramática: Artículos indefinidos y definidos / Hay)",
    71: "Some content on pronouns adapted from " + _WIKIBOOKS + ", Lesson 3",
    94: "Explanation of verb conjugations adapted from " + _WIKIBOOKS + ", Lesson 3",
    101: "Notes on telling time adapted from " + _WIKIBOOKS + ", Lesson 7",
    229: "Wikipedia contributors, *Romance copula* (https://en.wikipedia.org/wiki/Romance_copula), CC BY-SA, adapted by Lumen Learning; "
         "Wiktionary, *Appendix:English words by Latin antecedents*, CC BY-SA",
    237: "Some content adapted from Athabasca University, *Beginner Spanish* OER (https://ocw.lms.athabascau.ca/mod/page/view.php?id=3157), CC BY-SA",
}
# Pages whose text cites NonCommercial or all-rights-reserved sources. None of them would be kept by
# the rules below, but they are excluded by id so a rule change can't let them in.
EXCLUDE = {78}

SKIP_PREFIXES = ("Ejercicios", "Actividades", "Actvidades", "Discussion", "Assignment", "Why It Matters",
                 "Putting It Together", "Repaso", "Review Module")
_NUMBERED = re.compile(r"^\d+\.\d+:?\s")


def classify(title: str, previous_kind: str | None) -> str | None:
    """Kind of section for a page title, or None to skip it."""
    t = title.strip()
    if t.startswith(SKIP_PREFIXES):
        return None
    numbered = bool(_NUMBERED.match(t))
    body = _NUMBERED.sub("", t)
    if body.startswith("Voces"):
        return "reading"
    if numbered:
        return "culture-intro" if body.startswith("Cultura") else None
    if t.startswith("Vocabulario"):
        return "vocabulary"
    if t.startswith("En contexto"):
        return "context"
    if t.startswith("Gramática"):
        return "grammar"
    if t.startswith("Cultura"):
        return "culture"
    # Volume II drops the "Gramática:" prefix; the explanation always follows its "En contexto" page.
    if previous_kind == "context":
        return "grammar"
    return None


def _clean_title(title: str) -> str:
    import html
    return html.unescape(re.sub(r"\s+", " ", title)).strip()


def select_sections(toc: dict, chapters: dict[int, dict]) -> list[pb.Section]:
    sections: list[pb.Section] = []
    for part in toc["parts"]:
        m = re.match(r"^(\d+)\.\s*(.+)$", _clean_title(part["title"]))
        if not m:
            continue  # resource and review parts
        module, module_title = int(m.group(1)), m.group(2)
        previous, picked = None, []
        for entry in part["chapters"]:
            title = _clean_title(entry["title"])
            kind = classify(title, previous)
            previous = kind or ("intro" if _NUMBERED.match(title) else previous)
            if kind is None or entry["id"] in EXCLUDE or entry["id"] not in chapters:
                continue
            picked.append((entry["id"], title, kind))
        has_culture_page = any(k == "culture" for _, _, k in picked)
        for cid, title, kind in picked:
            if kind == "culture-intro":
                if has_culture_page:
                    continue  # just a header page for the real Cultura page
                kind = "culture"
            shown = _NUMBERED.sub("", title)
            sa = SHARE_ALIKE_TEXT.get(cid)
            sections.append(pb.Section(
                source_id=cid,
                path=f"m{module:02d}/{pb.slugify(shown)}.md",
                title=shown,
                kind=kind,
                module=module,
                module_title=module_title,
                source_url=chapters[cid]["link"],
                license=CC_BY_SA if sa else CC_BY,
                extra_attribution=[sa] if sa else [],
            ))
    seen: dict[str, int] = {}
    for s in sections:  # keep paths unique within a module
        n = seen.get(s.path, 0)
        seen[s.path] = n + 1
        if n:
            s.path = s.path[:-3] + f"-{n + 1}.md"
    return sections


def manifest(metadata: dict) -> dict:
    lic = metadata.get("license") or {}
    if lic.get("url") != CC_BY["url"]:
        raise SystemExit(f"Upstream license changed to {lic!r}; review before rebuilding the pack.")
    return {
        "id": "chevere",
        "title": "¡Chévere! Introductory Spanish I & II",
        "upstream_title": metadata.get("name"),
        "language": "es",
        "authors": [a["name"] for a in metadata.get("author", [])],
        "copyright_holder": (metadata.get("copyrightHolder") or {}).get("name"),
        "source_url": BASE_URL + "/",
        "license": CC_BY,
        "changes": "Converted from HTML to Markdown; excerpted to vocabulary, grammar, reading and culture pages; "
                   "images, audio, video and interactive exercises removed; headings reformatted.",
        "retrieved": pb.today(),
        "format": 1,
    }


def render(chapter: dict) -> str:
    return pb.html_to_markdown(chapter["content"]["rendered"], heading_offset=-1)


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[0] not in ("fetch", "build"):
        raise SystemExit(__doc__)
    raw = Path(argv[1])
    if argv[0] == "fetch":
        pb.fetch(BASE_URL, raw)
        return
    out = Path(argv[2]) if len(argv) > 2 else PACK_DIR
    metadata, toc, chapters = pb.load_raw(raw)
    sections = select_sections(toc, chapters)
    pb.write_pack(out, manifest(metadata), sections, chapters, render)
    kinds = {}
    for s in sections:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    print(f"wrote {len(sections)} sections to {out}: {kinds}")


if __name__ == "__main__":
    main(sys.argv[1:])
