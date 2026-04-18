"""Schema brittleness guard — parses the actual toolkit content at ~/.claude.

Skipped if TOOLKIT_ROOT is not present. When present, asserts we can read
all skills/agents/playbooks without raising. This is the CI guard mentioned
in the plan's risk section (playbook table parsing brittleness).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("frontmatter")
pytest.importorskip("markdown_it")

from app.ingestion.toolkit_ingest import parsers, walker  # noqa: E402


def _toolkit_root() -> Path | None:
    candidate = os.environ.get("TOOLKIT_ROOT") or str(Path.home() / ".claude")
    path = Path(candidate).expanduser()
    return path if path.is_dir() else None


def test_can_discover_toolkit():
    root = _toolkit_root()
    if root is None:
        pytest.skip("Toolkit root not present on this host")
    paths = walker.discover(root)
    # Smoke: we found something
    assert paths.total_files > 0


def test_can_parse_all_skills():
    root = _toolkit_root()
    if root is None:
        pytest.skip("Toolkit root not present on this host")
    paths = walker.discover(root)
    for skill_md in paths.skill_md_paths:
        skill = parsers.parse_skill(skill_md, root)
        assert skill.slug, f"Empty slug for {skill_md}"
        assert skill.body, f"Empty body for {skill_md}"


def test_can_parse_all_agents():
    root = _toolkit_root()
    if root is None:
        pytest.skip("Toolkit root not present on this host")
    paths = walker.discover(root)
    for agent_md in paths.agent_md_paths:
        agent = parsers.parse_agent(agent_md, root)
        assert agent.slug, f"Empty slug for {agent_md}"


def test_can_parse_all_playbooks():
    root = _toolkit_root()
    if root is None:
        pytest.skip("Toolkit root not present on this host")
    paths = walker.discover(root)
    for pb_md in paths.playbook_md_paths:
        pb = parsers.parse_playbook(pb_md, root)
        assert pb.slug, f"Empty slug for {pb_md}"
        # Stack + routing tables are nice-to-have but must not raise
