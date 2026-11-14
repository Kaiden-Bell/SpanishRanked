"""Content packs: textbook text mapped onto the syllabus.

A pack is a folder (written by an importer such as scripts/importers/chevere.py, or by hand):

    manifest.json   {id, title, authors, copyright_holder, source_url, license: {code, url}, changes, ...}
    sections.json   [{path, title, kind, module, module_title, source_url, license, extra_attribution}]
    map.json        {"units": {unit_id: [section path, ...]}}
    sections/**.md  the text

The bundled packs live in src/backend/content/packs and ship in the image. Anyone can add their own
under <data dir>/packs (for example a textbook they own); those are read at startup and never
leave that machine. A pack that fails validation is skipped and reported, never fatal.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .syllabus import Syllabus

log = logging.getLogger(__name__)

BUNDLED_DIR = Path(__file__).resolve().parents[2] / "content" / "packs"
KINDS = ("context", "grammar", "vocabulary", "reading", "culture")
# Reading order inside a lesson: a short text that uses the target, the explicit rule, the words,
# then longer reading. Follows the lesson template in docs/GUIDED_STUDY.md.
KIND_ORDER = {k: i for i, k in enumerate(KINDS)}


@dataclass
class Section:
    path: str
    title: str
    kind: str
    module: int | None
    source_url: str | None
    license: dict
    extra_attribution: list[str]
    file: Path

    def text(self) -> str:
        return self.file.read_text(encoding="utf-8")


@dataclass
class Pack:
    id: str
    title: str
    manifest: dict
    bundled: bool
    sections: dict[str, Section]
    units: dict[str, list[str]]  # unit id -> section paths

    def attribution(self) -> str:
        m = self.manifest
        lic = m["license"]
        authors = ", ".join(m.get("authors") or [])
        holder = f", © {m['copyright_holder']}" if m.get("copyright_holder") else ""
        return f"{m['title']}{' by ' + authors if authors else ''}{holder}. {lic['code']}. {m.get('changes', '')}".strip()


@dataclass
class PackSet:
    packs: list[Pack] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def get(self, pack_id: str) -> Pack | None:
        return next((p for p in self.packs if p.id == pack_id), None)

    def covering(self, unit_id: str) -> list[Pack]:
        return [p for p in self.packs if p.units.get(unit_id)]


class PackError(ValueError):
    pass


def load_pack(folder: Path, syllabus: Syllabus, *, bundled: bool) -> Pack:
    def read(name: str):
        try:
            return json.loads((folder / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise PackError(f"missing {name}")
        except json.JSONDecodeError as exc:
            raise PackError(f"{name} is not valid JSON ({exc})")

    manifest = read("manifest.json")
    for key in ("id", "title"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise PackError(f"manifest.json needs a {key!r}")
    lic = manifest.get("license")
    if not isinstance(lic, dict) or not lic.get("code"):
        # The app shows a license on every lesson; a pack without one can't be displayed honestly.
        raise PackError("manifest.json needs a license {code, url}")

    root = (folder / "sections").resolve()
    sections: dict[str, Section] = {}
    for raw in read("sections.json"):
        path = raw["path"]
        file = (root / path).resolve()
        if root not in file.parents or not file.is_file():
            raise PackError(f"section file not found: {path}")
        kind = raw.get("kind")
        if kind not in KIND_ORDER:
            raise PackError(f"{path}: unknown kind {kind!r} (expected one of {', '.join(KINDS)})")
        sections[path] = Section(
            path=path, title=raw.get("title") or path, kind=kind, module=raw.get("module"),
            source_url=raw.get("source_url"), license=raw.get("license") or lic,
            extra_attribution=list(raw.get("extra_attribution") or []), file=file,
        )

    units = read("map.json").get("units", {})
    for unit_id, paths in units.items():
        if syllabus.get(unit_id) is None:
            raise PackError(f"map.json: unknown unit {unit_id}")
        missing = [p for p in paths if p not in sections]
        if missing:
            raise PackError(f"map.json: {unit_id} lists unknown sections {missing}")
    return Pack(id=manifest["id"], title=manifest["title"], manifest=manifest, bundled=bundled,
                sections=sections, units={k: list(v) for k, v in units.items()})


def load_all(syllabus: Syllabus, extra_dirs: list[Path] = ()) -> PackSet:
    result = PackSet()
    roots = [(BUNDLED_DIR, True)] + [(d, False) for d in extra_dirs]
    for root, bundled in roots:
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            try:
                pack = load_pack(folder, syllabus, bundled=bundled)
            except (PackError, KeyError, TypeError) as exc:
                msg = f"content pack {folder.name}: {exc}"
                result.problems.append(msg)
                log.warning("skipping %s", msg)
                continue
            if result.get(pack.id):
                result.problems.append(f"content pack {folder.name}: duplicate id {pack.id!r}, skipped")
                continue
            result.packs.append(pack)
    return result


def lesson_sections(pack: Pack, unit_id: str) -> list[Section]:
    picked = [pack.sections[p] for p in pack.units.get(unit_id, [])]
    # Stable sort: within a kind, keep the order the map gives.
    return sorted(picked, key=lambda s: KIND_ORDER[s.kind])
