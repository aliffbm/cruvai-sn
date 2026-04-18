"""Parsers for toolkit markdown files.

Handles YAML frontmatter via `python-frontmatter` and builds typed records
for skills, agents, and playbooks. Playbook table extraction uses
`markdown-it-py` to walk the AST.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import frontmatter  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - dependency declared in pyproject
    frontmatter = None  # type: ignore[assignment]

try:
    from markdown_it import MarkdownIt  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    MarkdownIt = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Typed records
# ---------------------------------------------------------------------------


@dataclass
class ParsedSkill:
    slug: str  # directory name
    name: str
    description: str | None
    body: str
    frontmatter: dict[str, Any]
    source_uri: str
    content_hash: str
    license_type: str | None = None
    license_text: str | None = None
    asset_paths: list[Path] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def requires_rewrite(self) -> bool:
        return self.license_type is not None


@dataclass
class ParsedAgent:
    slug: str
    name: str
    description: str | None
    body: str
    frontmatter: dict[str, Any]
    source_uri: str
    content_hash: str
    tools: list[str] = field(default_factory=list)
    model: str | None = None


@dataclass
class ParsedPlaybook:
    slug: str
    name: str
    description: str | None
    body: str
    source_uri: str
    content_hash: str
    stack_manifest: list[dict[str, str]] = field(default_factory=list)
    agent_routing_rows: list[dict[str, str]] = field(default_factory=list)
    load_bearing_skills: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_sections(body: str) -> dict[str, str]:
    """Return a {h2_heading: section_body} map for diff UI targeting."""
    sections: dict[str, str] = {}
    matches = list(_H2_RE.finditer(body))
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[heading] = body[start:end].strip()
    return sections


def _coerce_tools(raw: Any) -> list[str]:
    """Normalize agent frontmatter `tools` into a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, str):
        # Typical format: "Read, Write, Edit, Bash, Glob, Grep"
        return [part.strip() for part in re.split(r"[,\s]+", raw) if part.strip()]
    return []


def _require_deps() -> None:
    if frontmatter is None:
        raise RuntimeError(
            "python-frontmatter is required. Install with `pip install python-frontmatter`."
        )
    if MarkdownIt is None:
        raise RuntimeError(
            "markdown-it-py is required. Install with `pip install markdown-it-py`."
        )


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


LICENSE_FILE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "license", "license.txt", "license.md")


def detect_license(skill_dir: Path, fm_license: Any) -> tuple[str | None, str | None]:
    """Return (license_type, license_text) if licensed, else (None, None)."""
    if fm_license:
        # Frontmatter license field — may be just a reference string
        for name in LICENSE_FILE_NAMES:
            p = skill_dir / name
            if p.is_file():
                return ("anthropic-ai-toolkit-license", p.read_text(encoding="utf-8", errors="replace"))
        # Frontmatter-only license: store the reference text
        return ("frontmatter-declared", str(fm_license))

    for name in LICENSE_FILE_NAMES:
        p = skill_dir / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            return ("anthropic-ai-toolkit-license", text)
    return (None, None)


def parse_skill(skill_md_path: Path, toolkit_root: Path) -> ParsedSkill:
    """Parse a single SKILL.md file along with its auxiliary assets."""
    _require_deps()
    raw = skill_md_path.read_text(encoding="utf-8", errors="replace")
    post = frontmatter.loads(raw)
    fm = dict(post.metadata or {})
    body = post.content or ""
    slug = skill_md_path.parent.name
    name = str(fm.get("name") or slug)
    description = fm.get("description")
    if description is not None:
        description = str(description).strip()

    license_type, license_text = detect_license(skill_md_path.parent, fm.get("license"))

    # Asset walk — everything in the skill dir except the SKILL.md itself and LICENSE files
    asset_paths: list[Path] = []
    for path in skill_md_path.parent.rglob("*"):
        if not path.is_file():
            continue
        if path == skill_md_path:
            continue
        if path.name in LICENSE_FILE_NAMES:
            continue
        asset_paths.append(path)

    return ParsedSkill(
        slug=slug,
        name=name,
        description=description,
        body=body,
        frontmatter=fm,
        source_uri=str(skill_md_path.relative_to(toolkit_root)),
        content_hash=_sha256(body),
        license_type=license_type,
        license_text=license_text,
        asset_paths=asset_paths,
        sections=_extract_sections(body),
    )


def parse_agent(agent_md_path: Path, toolkit_root: Path) -> ParsedAgent:
    """Parse a single agent definition file."""
    _require_deps()
    raw = agent_md_path.read_text(encoding="utf-8", errors="replace")
    post = frontmatter.loads(raw)
    fm = dict(post.metadata or {})
    body = post.content or ""
    slug = str(fm.get("name") or agent_md_path.stem).strip()
    name = slug.replace("-", " ").title()
    description = fm.get("description")
    if description is not None:
        description = str(description).strip()
    tools = _coerce_tools(fm.get("tools"))
    model = fm.get("model")
    if model is not None:
        model = str(model).strip() or None

    return ParsedAgent(
        slug=slug,
        name=name,
        description=description,
        body=body,
        frontmatter=fm,
        source_uri=str(agent_md_path.relative_to(toolkit_root)),
        content_hash=_sha256(body),
        tools=tools,
        model=model,
    )


# Playbook-specific parsing --------------------------------------------------


def _parse_markdown_tables(md_text: str) -> list[list[list[str]]]:
    """Return list of tables, each a list of rows (rows are lists of cells)."""
    _require_deps()
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(md_text)
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    current_row: list[str] = []
    in_table = False
    for tok in tokens:
        if tok.type == "table_open":
            in_table = True
            current = []
        elif tok.type == "table_close":
            if current:
                tables.append(current)
            current = []
            in_table = False
        elif tok.type == "tr_open" and in_table:
            current_row = []
        elif tok.type == "tr_close" and in_table:
            current.append(current_row)
        elif tok.type == "inline" and in_table:
            current_row.append(tok.content.strip())
    return tables


def _extract_stack_manifest(tables: list[list[list[str]]]) -> list[dict[str, str]]:
    """First table with header (Layer, Tech, …) = stack manifest."""
    for table in tables:
        if not table:
            continue
        header = [c.lower() for c in table[0]]
        if any(h in {"layer", "component", "tech"} for h in header):
            rows: list[dict[str, str]] = []
            keys = table[0]
            for row in table[1:]:
                rows.append({keys[i]: row[i] for i in range(min(len(keys), len(row)))})
            return rows
    return []


def _extract_routing_rows(tables: list[list[list[str]]]) -> list[dict[str, str]]:
    """Tables whose header includes 'primary agent' are routing tables."""
    rows_out: list[dict[str, str]] = []
    for table in tables:
        if not table:
            continue
        header = [c.lower() for c in table[0]]
        if any("primary" in h and "agent" in h for h in header):
            keys = table[0]
            for row in table[1:]:
                rows_out.append(
                    {keys[i]: row[i] for i in range(min(len(keys), len(row)))}
                )
    return rows_out


_SKILL_LIST_RE = re.compile(r"`([a-z][a-z0-9-]+)`")


def _extract_load_bearing_skills(body: str) -> list[str]:
    """Best-effort: grab backtick-quoted slugs under a 'load-bearing skills' heading."""
    lowered = body.lower()
    idx = lowered.find("load-bearing skills")
    if idx < 0:
        idx = lowered.find("load bearing skills")
    if idx < 0:
        return []
    # Take the next ~2000 chars after the heading
    region = body[idx : idx + 2000]
    return sorted(set(_SKILL_LIST_RE.findall(region)))


def parse_playbook(playbook_md_path: Path, toolkit_root: Path) -> ParsedPlaybook:
    _require_deps()
    raw = playbook_md_path.read_text(encoding="utf-8", errors="replace")
    # Playbooks have no YAML frontmatter — treat whole file as body.
    body = raw
    # First H1 is the title
    title_match = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    name = title_match.group(1).strip() if title_match else playbook_md_path.stem
    slug = playbook_md_path.stem
    # First paragraph under any "When this applies" / "Context" = description
    desc_match = re.search(r"(?:^##\s+When this applies.*?\n+|^##\s+Context.*?\n+)(.+?)(?=\n#|\Z)", body, re.DOTALL | re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else None

    tables = _parse_markdown_tables(body)
    return ParsedPlaybook(
        slug=slug,
        name=name,
        description=description,
        body=body,
        source_uri=str(playbook_md_path.relative_to(toolkit_root)),
        content_hash=_sha256(body),
        stack_manifest=_extract_stack_manifest(tables),
        agent_routing_rows=_extract_routing_rows(tables),
        load_bearing_skills=_extract_load_bearing_skills(body),
    )
