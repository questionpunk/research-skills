#!/usr/bin/env node
// Creates the folder of every catalog skill that has no SKILL.md yet. Never overwrites a file.
// Usage: node tools/scaffold.mjs [skill-name ...]   (default: every skill in catalog.json)

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const catalog = JSON.parse(readFileSync(join(ROOT, 'catalog.json'), 'utf8'));
const only = new Set(process.argv.slice(2));

const snake = (name) => name.replace(/-/g, '_');
const writeNew = (path, text) => {
  if (existsSync(path)) return false;
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
  return true;
};
// YAML double-quoted scalar: JSON string syntax is valid YAML.
const yamlString = (s) => JSON.stringify(s);

function skillMd(s) {
  const handoff = catalog.handoffs[s.handoff] ?? s.handoff;
  const whenToUse = s.description.includes('Use ') ? s.description.slice(s.description.indexOf('Use ')) : 'TODO';
  const tools = s.mcpTools.length ? s.mcpTools.map((t) => `\`${t}\``).join(', ') : 'none';
  const script = s.hasScript
    ? `\nThe calculation lives in [\`scripts/${snake(s.name)}.py\`](scripts/${snake(s.name)}.py) (Python 3.9+, standard library only). Run it; do not redo the math in the conversation.\n`
    : '';
  return `---
name: ${s.name}
description: ${yamlString(s.description)}
license: MIT
metadata:
  version: "${s.version}"
  status: "${s.status}"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "${s.requiresAccount}"
  plugin: "${s.plugin}"
---

# ${s.title}

> **Status: planned.** Scaffold only. Build it as described in \`docs/DEVELOPMENT.md\` before using it.

## When to use

${whenToUse}

TODO: list the user requests that should trigger this skill, and the ones that should not (and which skill
handles them instead).

## What to ask for

- TODO: the inputs this skill needs (file, pasted text, decision, audience), with a sensible default for each.

## Steps

1. TODO
${script}
## Output

TODO: the exact shape of the answer (table, file, sections), so results are comparable between runs.

## Checks before answering

- TODO: the mistakes this method invites (see \`references/sources.md\`, "Pitfalls"), each as a yes/no check.

## Field it with QuestionPunk (optional)

The result above is complete on its own. ${handoff}

Hosted MCP tools this step may use: ${tools}. Ask before creating, changing or publishing anything.
`;
}

function sourcesMd(s) {
  return `# ${s.title}: method sources

TODO: formulas, thresholds and authoritative sources (with links) the skill and its script rely on. Every
number in SKILL.md and in the script must trace to an entry here.

## Formulas and thresholds

- TODO

## Sources

- TODO

## Pitfalls

- TODO
`;
}

function scriptPy(s) {
  return `#!/usr/bin/env python3
"""${s.title}: ${s.description.split('. Use ')[0].replace(/"/g, "'")}.

Standard library only, Python 3.9+. Status: planned (not implemented).
Usage: python3 scripts/${snake(s.name)}.py INPUT [options]
"""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="TODO: input file (CSV, JSON or Markdown)")
    parser.parse_args(argv)
    sys.exit("${s.name}: not implemented yet, see docs/DEVELOPMENT.md")


if __name__ == "__main__":
    main()
`;
}

function testPy(s) {
  return `"""Tests for scripts/${snake(s.name)}.py. Run from the skill folder: python3 -m unittest discover -s tests"""
import pathlib
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "${snake(s.name)}.py"


class ${snake(s.name).replace(/(^|_)(\w)/g, (_, __, c) => c.toUpperCase())}Test(unittest.TestCase):
    @unittest.skip("planned: add fixtures with hand-checked expected results first (docs/DEVELOPMENT.md)")
    def test_fixture_matches_expected(self):
        self.fail("write me")


if __name__ == "__main__":
    unittest.main()
`;
}

const fixturesMd = (s) => `# Fixtures for ${s.name}

Small, anonymised inputs with expected outputs worked out independently of the script (by hand, in a
spreadsheet, or with a published example). Name pairs \`<case>.input.*\` and \`<case>.expected.*\`, and say
in this file where each expected value comes from.
`;

let created = 0;
for (const s of catalog.skills) {
  if (only.size && !only.has(s.name)) continue;
  const dir = join(ROOT, 'skills', s.name);
  created += writeNew(join(dir, 'SKILL.md'), skillMd(s));
  created += writeNew(join(dir, 'references', 'sources.md'), sourcesMd(s));
  if (s.hasScript) {
    created += writeNew(join(dir, 'scripts', `${snake(s.name)}.py`), scriptPy(s));
    created += writeNew(join(dir, 'tests', `test_${snake(s.name)}.py`), testPy(s));
    created += writeNew(join(dir, 'fixtures', 'README.md'), fixturesMd(s));
  }
}
console.log(`scaffold: ${created} file(s) created`);
