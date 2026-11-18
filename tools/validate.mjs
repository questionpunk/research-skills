#!/usr/bin/env node
// Validates the pack: catalog.json <-> skills/<name>/SKILL.md, Agent Skills naming and length rules,
// claims rules, links, scripts and (with --tests) the script tests.
// Usage: node tools/validate.mjs [--tests] [skill-name ...]
// Exit 1 on any error. Warnings do not fail.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const runTests = args.includes('--tests');
const only = new Set(args.filter((a) => !a.startsWith('--')));
const catalog = JSON.parse(readFileSync(join(ROOT, 'catalog.json'), 'utf8'));

const STATUSES = ['planned', 'draft', 'beta', 'stable'];
// Agent Skills spec keys. claude.ai upload, the Skills API and skills-ref reject any other key (docs/PACKAGING.md).
const ALLOWED_KEYS = new Set(['name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools']);
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SEMVER_RE = /^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/;
// From docs/marketing/agent-discovery/outreach.md "Do not claim" and docs/marketing-plan/github/skill-ideas.md.
const BANNED_CLAIMS = [
  [/only (ai[- ]interview|survey|research) (tool|platform)s? with an? mcp/i, 'claims QuestionPunk is the only tool with an MCP server'],
  [/free (basic )?plan (includes|has|covers) (maxdiff|conjoint)/i, 'claims the free plan includes MaxDiff or conjoint'],
  [/\b(best|#1|number one|leading) (survey|research) (tool|platform)/i, 'superlative product claim'],
  [/\b20 responses (a|per|\/) ?month/i, 'out-of-date plan claim: the free plan has unlimited responses (checked 2026-11-12)'],
];

const errors = [];
const warnings = [];
const err = (where, msg) => errors.push(`${where}: ${msg}`);
const warn = (where, msg) => warnings.push(`${where}: ${msg}`);

// Minimal frontmatter reader for the subset the scaffold writes: `key: value` and one nested `metadata:` map.
function frontmatter(text) {
  const m = /^---\n([\s\S]*?)\n---\n/.exec(text);
  if (!m) return null;
  const out = { metadata: {} };
  let inMeta = false;
  for (const line of m[1].split('\n')) {
    if (!line.trim()) continue;
    const nested = /^ {2}([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    const top = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    const value = (v) => (/^".*"$/.test(v) ? JSON.parse(v) : v);
    if (nested && inMeta) out.metadata[nested[1]] = value(nested[2]);
    else if (top) {
      inMeta = top[1] === 'metadata' && top[2] === '';
      if (!inMeta) out[top[1]] = value(top[2]);
    } else return null;
  }
  return { data: out, body: text.slice(m[0].length) };
}

// Hosted MCP tool names, when run inside the monorepo (the public export has no questionpunk-mcp/).
const publicTools = join(ROOT, '..', 'questionpunk-mcp', 'src', 'public-tools.ts');
const hostedText = existsSync(publicTools) ? readFileSync(publicTools, 'utf8') : null;
if (!hostedText) warn('catalog', 'questionpunk-mcp/src/public-tools.ts not found; MCP tool names not checked');

const names = new Set();
for (const s of catalog.skills) {
  if (names.has(s.name)) err('catalog', `duplicate skill ${s.name}`);
  names.add(s.name);
}
const folders = existsSync(join(ROOT, 'skills')) ? readdirSync(join(ROOT, 'skills')).filter((f) => !f.startsWith('.')) : [];
for (const f of folders) if (!names.has(f)) err(`skills/${f}`, 'folder has no catalog.json entry');
if (!SEMVER_RE.test(catalog.pack.version)) err('catalog', `pack version ${catalog.pack.version} is not semver`);

for (const s of catalog.skills) {
  if (only.size && !only.has(s.name)) continue;
  const where = `skills/${s.name}`;
  const dir = join(ROOT, 'skills', s.name);
  const file = join(dir, 'SKILL.md');
  if (!NAME_RE.test(s.name) || s.name.length > 64) err(where, 'name must be lowercase a-z, 0-9 and single hyphens, at most 64 characters');
  if (/claude|anthropic/.test(s.name)) err(where, 'name must not contain "claude" or "anthropic" (Claude API rule)');
  if (/[<>]/.test(s.description)) err(where, 'description must not contain < or > (Claude API rule)');
  if (s.description.length > 600) warn(where, `description is ${s.description.length} characters; aim for 600 or fewer (claude.ai may cut long ones)`);
  // Inside the monorepo, a pack skill must not share a name with another skill IDE agents load.
  for (const base of ['.claude/skills', '.github/skills']) {
    const other = join(ROOT, '..', base, s.name, 'SKILL.md');
    if (existsSync(other) && !/^\s+source:\s*"?questionpunk\/research-skills"?\s*$/m.test(readFileSync(other, 'utf8')))
      err(where, `name clashes with ${base}/${s.name}, which is not a pack copy`);
  }
  if (!STATUSES.includes(s.status)) err(where, `status ${s.status} not one of ${STATUSES.join(', ')}`);
  if (!SEMVER_RE.test(s.version)) err(where, `version ${s.version} is not semver`);
  if (!catalog.plugins[s.plugin]) err(where, `plugin ${s.plugin} not in catalog.plugins`);
  if (!s.description || s.description.length > 1024) err(where, 'description must be 1-1024 characters');
  if (!/\bUse (for|when|before|after)\b/.test(s.description)) warn(where, 'description should say when to use the skill ("Use for/when ...")');
  if (hostedText) for (const t of s.mcpTools) if (!hostedText.includes(`"${t}"`) && !hostedText.includes(`'${t}'`)) err(where, `MCP tool ${t} is not in questionpunk-mcp/src/public-tools.ts (hosted connections cannot call it)`);
  if (!existsSync(file)) {
    err(where, 'SKILL.md missing (run node tools/scaffold.mjs)');
    continue;
  }
  const text = readFileSync(file, 'utf8');
  const fm = frontmatter(text);
  if (!fm) {
    err(where, 'SKILL.md frontmatter missing or not in the supported form');
    continue;
  }
  const { data, body } = fm;
  for (const k of Object.keys(data)) if (!ALLOWED_KEYS.has(k)) err(where, `frontmatter key "${k}" is not in the Agent Skills spec`);
  for (const [k, v] of Object.entries(data.metadata)) if (typeof v !== 'string') err(where, `metadata.${k} must be a string`);
  const lic = join(dir, 'LICENSE.txt');
  if (!existsSync(lic) || readFileSync(lic, 'utf8') !== readFileSync(join(ROOT, 'LICENSE'), 'utf8')) err(where, 'LICENSE.txt missing or differs from the root LICENSE (run node tools/build.mjs)');
  const expect = {
    name: s.name,
    description: s.description,
    license: catalog.pack.license,
  };
  for (const [k, v] of Object.entries(expect)) if (data[k] !== v) err(where, `frontmatter ${k} does not match catalog.json`);
  const meta = { version: s.version, status: s.status, plugin: s.plugin, source: 'questionpunk/research-skills', 'requires-account': String(s.requiresAccount) };
  for (const [k, v] of Object.entries(meta)) if (data.metadata[k] !== v) err(where, `metadata.${k} is ${JSON.stringify(data.metadata[k])}, catalog says ${JSON.stringify(v)}`);

  const lines = body.split('\n').length;
  if (lines > 500) err(where, `SKILL.md body is ${lines} lines; keep it under 500 and move detail to references/`);
  else if (lines > 300) warn(where, `SKILL.md body is ${lines} lines; aim for under 300`);
  if (!/^# \S/m.test(body)) err(where, 'SKILL.md needs a "# Title" heading');
  const h2 = [...body.matchAll(/^## (.+)$/gm)].map((m) => m[1]);
  if (s.mcpTools.length || s.handoff) {
    const i = h2.findIndex((h) => /^Field it/.test(h));
    if (i < 0) err(where, 'missing the "## Field it with QuestionPunk (optional)" section');
    else if (i !== h2.length - 1) err(where, '"Field it" must be the last section: the result comes first, the hand-off last');
    else {
      const section = body.slice(body.lastIndexOf('## Field it')).split('\n').filter((l) => l.trim() && !l.startsWith('#'));
      if (section.length > 4) warn(where, `"Field it" has ${section.length} lines; keep the hand-off to about three`);
    }
  }
  for (const [re, why] of BANNED_CLAIMS) if (re.test(text)) err(where, `claims rule: ${why}`);
  // A sibling may be planned, or simply not installed (`npx skills add --skill <one>`), so a skill that
  // routes requests to another one must say what to do when that skill is missing.
  if (s.status !== 'planned') {
    const named = catalog.skills.filter((o) => o.name !== s.name && body.includes('`' + o.name + '`')).map((o) => o.name);
    if (named.length && !/may not be installed|not installable/.test(body))
      err(where, `names other skills (${named.slice(0, 3).join(', ')}${named.length > 3 ? ', …' : ''}) but does not say what to do when one is not installed`);
  }
  if (s.status !== 'planned') {
    if (/\bTODO\b/.test(text) || /Status: planned/.test(text)) err(where, `status ${s.status} but SKILL.md still has TODO or the planned notice`);
    const src = join(dir, 'references', 'sources.md');
    if (!existsSync(src) || /\bTODO\b/.test(readFileSync(src, 'utf8'))) err(where, `status ${s.status} needs a finished references/sources.md`);
  }
  for (const m of text.matchAll(/\]\(([^)#\s]+)\)/g)) {
    const target = m[1];
    if (/^[a-z]+:/i.test(target)) continue;
    if (!existsSync(join(dir, target))) err(where, `broken link ${target}`);
  }
  if (s.hasScript) {
    const py = join(dir, 'scripts', `${s.name.replace(/-/g, '_')}.py`);
    if (!existsSync(py)) err(where, `hasScript but scripts/${s.name.replace(/-/g, '_')}.py is missing`);
    else {
      try {
        execFileSync('python3', ['-c', 'import ast,sys; ast.parse(open(sys.argv[1]).read())', py], { stdio: 'pipe' });
      } catch (e) {
        err(where, `script does not parse: ${String(e.stderr).trim().split('\n').at(-1)}`);
      }
    }
    if (!existsSync(join(dir, 'tests'))) err(where, 'hasScript but no tests/ folder');
    else if (runTests) {
      try {
        // No bytecode: a tests/__pycache__ folder would be copied by nothing but still litters the skill.
        execFileSync('python3', ['-m', 'unittest', 'discover', '-s', 'tests'], { cwd: dir, stdio: 'pipe', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
      } catch (e) {
        err(where, `tests failed:\n${String(e.stderr).trim().split('\n').slice(-8).join('\n')}`);
      }
    }
    if (s.status !== 'planned' && existsSync(join(dir, 'tests'))) {
      // Only the test files: tests/ may also hold __pycache__ (a directory) after a manual run.
      const t = readdirSync(join(dir, 'tests')).filter((f) => f.endsWith('.py')).map((f) => readFileSync(join(dir, 'tests', f), 'utf8')).join('\n');
      if (/@unittest\.skip/.test(t)) err(where, `status ${s.status} but tests are still skipped`);
    }
  }
}

for (const w of warnings) console.warn(`warn  ${w}`);
for (const e of errors) console.error(`error ${e}`);
const counts = Object.fromEntries(STATUSES.map((st) => [st, catalog.skills.filter((s) => s.status === st).length]));
console.log(`validate: ${catalog.skills.length} skills ${JSON.stringify(counts)}, ${errors.length} error(s), ${warnings.length} warning(s)`);
process.exit(errors.length ? 1 : 0);
