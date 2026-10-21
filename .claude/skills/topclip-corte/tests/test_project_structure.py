from __future__ import annotations

import unittest
from pathlib import Path

from scripts.utils import AGENTS_DIR, PROJECT_ROOT
from scripts.validation import _frontmatter

AGENT_NAMES = {
    "context-mapper", "clip-hunter", "clip-builder", "feed-psychologist",
    "blind-reviewer", "clip-deduplicator", "edit-director", "quality-controller",
}


class ProjectStructureTests(unittest.TestCase):
    def test_blind_reviewer_has_only_nonlocal_launch_tool(self) -> None:
        path = AGENTS_DIR / "blind-reviewer.md"
        data, errors = _frontmatter(path)
        self.assertEqual(errors, [])
        self.assertIsNotNone(data)
        self.assertEqual(data.get("tools"), "WebSearch")

        body = path.read_text(encoding="utf-8")
        for forbidden in ("tools: Read", "tools: Bash", "tools: Grep", "tools: Glob", "tools: Write", "tools: Edit", "tools: TodoWrite"):
            self.assertNotIn(forbidden, body)
        self.assertIn("Não a utilize", body)

    def test_package_ships_every_agent(self) -> None:
        found = set()
        for path in AGENTS_DIR.glob("*.md"):
            data, errors = _frontmatter(path)
            self.assertEqual(errors, [], f"frontmatter invalido em {path.name}")
            found.add(str((data or {}).get("name")))
        self.assertEqual(found, AGENT_NAMES)

    def test_skill_is_self_contained(self) -> None:
        """A skill e instalada: nada pode depender de ${CLAUDE_PROJECT_DIR}."""
        skill = (PROJECT_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE_PROJECT_DIR", skill)

    def test_motion_is_out_of_scope(self) -> None:
        """Motion e legenda queimada sao da skill topclip-motion, nao desta."""
        self.assertFalse((PROJECT_ROOT / "scripts" / "composite_motion.py").exists())
        self.assertEqual(list((PROJECT_ROOT / "schemas").glob("motion-*.json")), [])


if __name__ == "__main__":
    unittest.main()
