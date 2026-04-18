"""Tests for the toolkit markdown parsers."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

pytest.importorskip("frontmatter")
pytest.importorskip("markdown_it")

from app.ingestion.toolkit_ingest import parsers  # noqa: E402


def _write(dir_path: Path, name: str, text: str) -> Path:
    p = dir_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_parse_skill_extracts_frontmatter_and_sections(tmp_path: Path):
    root = tmp_path
    skill_dir = root / "skills" / "tdd"
    _write(
        skill_dir,
        "SKILL.md",
        """\
        ---
        name: tdd
        description: "Use before implementing any feature"
        ---
        # Test-Driven Development

        ## When to use

        Before writing implementation code.

        ## Steps

        1. Write a failing test.
        2. Make it pass.
        """,
    )
    skill = parsers.parse_skill(skill_dir / "SKILL.md", root)
    assert skill.slug == "tdd"
    assert skill.name == "tdd"
    assert "When to use" in skill.sections
    assert "implement" in skill.body.lower()
    assert skill.license_type is None
    assert not skill.requires_rewrite


def test_parse_skill_detects_license_file(tmp_path: Path):
    root = tmp_path
    skill_dir = root / "skills" / "claude-api"
    _write(
        skill_dir,
        "SKILL.md",
        """\
        ---
        name: claude-api
        description: "Build apps with Claude"
        license: "LICENSE.txt"
        ---
        # Claude API
        body here
        """,
    )
    _write(skill_dir, "LICENSE.txt", "Anthropic toolkit license terms")
    skill = parsers.parse_skill(skill_dir / "SKILL.md", root)
    assert skill.requires_rewrite is True
    assert skill.license_type is not None
    assert "Anthropic" in (skill.license_text or "")


def test_parse_skill_detects_license_without_frontmatter_hint(tmp_path: Path):
    root = tmp_path
    skill_dir = root / "skills" / "bare"
    _write(
        skill_dir,
        "SKILL.md",
        """\
        ---
        name: bare
        description: "test"
        ---
        body
        """,
    )
    _write(skill_dir, "LICENSE", "license text")
    skill = parsers.parse_skill(skill_dir / "SKILL.md", root)
    assert skill.requires_rewrite is True


def test_parse_agent_coerces_string_tools(tmp_path: Path):
    root = tmp_path
    agents_dir = root / "agents"
    _write(
        agents_dir,
        "react-specialist.md",
        """\
        ---
        name: react-specialist
        description: "Advanced React work"
        tools: Read, Write, Edit, Bash, Glob, Grep
        model: opus
        ---
        # React specialist

        System prompt body.
        """,
    )
    agent = parsers.parse_agent(agents_dir / "react-specialist.md", root)
    assert agent.slug == "react-specialist"
    assert agent.tools == ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    assert agent.model == "opus"


def test_parse_playbook_extracts_tables(tmp_path: Path):
    root = tmp_path
    pb_dir = root / "playbooks"
    _write(
        pb_dir,
        "sample.md",
        """\
        # Sample playbook

        ## Context

        Multi-tenant SaaS with Postgres.

        ## Stack

        | Layer | Tech |
        |---|---|
        | Frontend | Next.js |
        | Backend | FastAPI |

        ## Agent routing

        | Task | Primary agent | Supporting |
        |---|---|---|
        | Build API | `backend-developer` | `security-auditor` |

        ## Load-bearing skills

        - `test-driven-development`
        - `systematic-debugging`
        """,
    )
    pb = parsers.parse_playbook(pb_dir / "sample.md", root)
    assert pb.slug == "sample"
    assert pb.stack_manifest, "expected stack rows"
    assert pb.agent_routing_rows, "expected routing rows"
    assert "test-driven-development" in pb.load_bearing_skills
    assert "systematic-debugging" in pb.load_bearing_skills
