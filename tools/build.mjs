#!/usr/bin/env node
// Writes the generated files from catalog.json and LICENSE:
//   skills/<name>/LICENSE.txt         copy of the root LICENSE, so a single copied skill keeps its notice
//   .claude-plugin/marketplace.json   Claude Code / Copilot CLI / Codex (legacy path) / npx skills discovery
//   README.md skills table            between the skills-table markers
// Usage: node tools/build.mjs [--check]   (--check exits 1 if any generated file is out of date)
// Format notes and sources: docs/PACKAGING.md.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const check = process.argv.includes('--check');
const catalog = JSON.parse(readFileSync(join(ROOT, 'catalog.json'), 'utf8'));
const license = readFileSync(join(ROOT, 'LICENSE'), 'utf8');

// Only skills someone can use go into the marketplace; planned scaffolds stay out.
const listed = catalog.skills.filter((s) => s.status !== 'planned');

const outputs = new Map();
for (const s of catalog.skills) outputs.set(join(ROOT, 'skills', s.name, 'LICENSE.txt'), license);

const methodPlugins = Object.entries(catalog.plugins)
  .map(([name, description]) => ({
    name,
    source: './',
    strict: false,
    description,
    category: 'research',
    skills: listed.filter((s) => s.plugin === name).map((s) => `./skills/${s.name}`),
  }))
  .filter((p) => p.skills.length);
const marketplace = {
  name: catalog.pack.name,
  description: `${catalog.pack.displayName}: survey design, pricing research, feedback analysis and interview method skills.`,
  owner: { name: catalog.pack.author, url: catalog.pack.homepage },
  // No $schema (the URL once written here returned 404; the field is ignored at load) and one description only:
  // `description` and `metadata.description` are alternate locations (docs/PACKAGING.md).
  metadata: { version: catalog.pack.version },
  plugins: [
    ...(listed.length
      ? [
          {
            name: catalog.pack.name,
            source: './',
            strict: false,
            description: 'Every skill in the pack.',
            category: 'research',
            skills: listed.map((s) => `./skills/${s.name}`),
          },
        ]
      : []),
    ...methodPlugins,
    {
      // The official QuestionPunk plugin (MCP server + account skills), kept in its own repo.
      name: 'questionpunk',
      source: { source: 'github', repo: 'questionpunk/claude-plugin' },
      description: 'Optional: connect the QuestionPunk MCP server to field studies and read results.',
      category: 'research',
    },
  ],
};
outputs.set(join(ROOT, '.claude-plugin', 'marketplace.json'), `${JSON.stringify(marketplace, null, 2)}\n`);

const readmePath = join(ROOT, 'README.md');
const readme = readFileSync(readmePath, 'utf8');
const start = readme.indexOf('<!-- skills-table:start');
const end = readme.indexOf('<!-- skills-table:end -->');
if (start < 0 || end < 0) throw new Error('README.md is missing the skills-table markers');
const startLineEnd = readme.indexOf('\n', start) + 1;
const rows = [...catalog.skills]
  .sort((a, b) => a.plugin.localeCompare(b.plugin) || a.priority.localeCompare(b.priority) || a.name.localeCompare(b.name))
  .map((s) => `| [\`${s.name}\`](skills/${s.name}/SKILL.md) | ${s.plugin} | ${s.version} | ${s.description.split('. Use ')[0].replace(/\|/g, '\\|')}. |`);
const table = ['| Skill | Plugin | Version | What it does |', '|---|---|---|---|', ...rows].join('\n');
outputs.set(readmePath, `${readme.slice(0, startLineEnd)}${table}\n${readme.slice(end)}`);

let stale = 0;
for (const [path, text] of outputs) {
  const current = existsSync(path) ? readFileSync(path, 'utf8') : null;
  if (current === text) continue;
  stale++;
  if (check) console.error(`build: ${relative(ROOT, path)} is out of date`);
  else {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, text);
  }
}
if (check && stale) {
  console.error('Run: node tools/build.mjs');
  process.exit(1);
}
console.log(`build: ${outputs.size} generated file(s), ${stale} ${check ? 'out of date' : 'written'}; ${listed.length} skill(s) in the marketplace`);
