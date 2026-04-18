"""Filesystem walker — discovers toolkit content on disk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolkitPaths:
    root: Path
    skill_md_paths: list[Path]
    agent_md_paths: list[Path]
    playbook_md_paths: list[Path]

    @property
    def total_files(self) -> int:
        return (
            len(self.skill_md_paths)
            + len(self.agent_md_paths)
            + len(self.playbook_md_paths)
        )


def discover(root: Path) -> ToolkitPaths:
    """Walk `root` and return all SKILL.md, agent .md, and playbook .md paths.

    Structure expected:
        {root}/skills/<slug>/SKILL.md
        {root}/agents/*.md
        {root}/playbooks/*.md   (README.md excluded)
    """

    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Toolkit root does not exist: {root}")

    skills_dir = root / "skills"
    agents_dir = root / "agents"
    playbooks_dir = root / "playbooks"

    skill_md_paths: list[Path] = []
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir():
                md = entry / "SKILL.md"
                if md.is_file():
                    skill_md_paths.append(md)

    agent_md_paths: list[Path] = []
    if agents_dir.is_dir():
        for entry in sorted(agents_dir.glob("*.md")):
            if entry.name.lower() == "readme.md":
                continue
            agent_md_paths.append(entry)

    playbook_md_paths: list[Path] = []
    if playbooks_dir.is_dir():
        for entry in sorted(playbooks_dir.glob("*.md")):
            if entry.name.lower() == "readme.md":
                continue
            playbook_md_paths.append(entry)

    return ToolkitPaths(
        root=root,
        skill_md_paths=skill_md_paths,
        agent_md_paths=agent_md_paths,
        playbook_md_paths=playbook_md_paths,
    )
