#!/usr/bin/env python3
"""Screener linter: checks a recruiting screener for routing completeness, quota arithmetic, coverage of the
target profile, and questions or options that reveal what qualifies.

Standard library only, Python 3.9+. No network, no randomness. Rules and sources: references/sources.md.

Usage:
  python3 scripts/screener_writer.py screener.md
  python3 scripts/screener_writer.py screener.json --json
  python3 scripts/screener_writer.py screener.md --strict      # exit 1 when there is an error-level finding
  python3 scripts/screener_writer.py --list-rules

Input: the Markdown layout in references/screener-format.md (or the same content as JSON).

Findings are CANDIDATES from rules. An error means the screener cannot work as written (a question with no
route, a quota that cannot fill); a warning is a likely problem that needs judgment; info is a suggestion.

Exit codes: 0 ran; 1 --strict and at least one error; 2 the file cannot be read or parsed.
"""
import argparse
import json
import math
import re
import statistics
import sys

MIN_DISTRACTORS = 2  # convention of this skill: a screening question needs at least two plausible wrong answers
STANDOUT_LENGTH_RATIO = 2.0  # convention: a qualifying option twice as long as the median distractor stands out
SELECT_ALL_MIN_OPTIONS = 4  # convention: suggest the select-everything check from 4 options up
QUALITATIVE_RE = re.compile(r"\b(?:interviews?|usability|focus[\s-]groups?|diary|co-?design|card[\s-]sort(?:ing)?"
                            r"|moderated|contextual inquiry)\b")
ACTIONS = {"continue", "terminate", "qualify"}
TYPES = {"single", "multi", "open", "numeric"}

RULES = {
    "SC01": ("error", "criterion with no question", "Every profile criterion needs at least one question that screens for it."),
    "SC02": ("error", "unknown criterion", "A question names a criterion that is not in the Criteria list."),
    "SC03": ("error", "option without routing", "Every option needs an action (continue, qualify, terminate, goto Qn)."),
    "SC04": ("error", "bad goto", "A goto must name a later question (no loops, no unknown questions)."),
    "SC05": ("warning", "unreachable question", "No route leads to this question."),
    "SC06": ("error", "nobody can qualify", "Every route ends in a terminate."),
    "SC07": ("warning", "question screens nothing", "Tied to a criterion but no answer terminates or qualifies."),
    "SC08": ("warning", "yes/no screening question", "A yes/no question tells respondents which answer qualifies."),
    "SC09": ("warning", "too few distractors", "The qualifying answer needs plausible wrong answers beside it."),
    "SC10": ("warning", "qualifying option stands out", "Longer or always-first qualifying options are easy to spot."),
    "SC11": ("warning", "reveals the study topic", "The question names what the study is about, so people can tailor answers."),
    "SC12": ("warning", "leading wording", "The wording pushes toward one answer."),
    "SC13": ("warning", "no way out of a multi-select", "A select-all question needs a 'None of these' option."),
    "SC14": ("error", "ranges overlap or leave gaps", "Numeric answer ranges must not overlap and must cover every value."),
    "SC15": ("warning", "no articulation question", "Interviews and usability studies need an open question to check people can express themselves."),
    "SC16": ("info", "select-everything check", "Flag people who select every option (or add a fictitious option that terminates)."),
    "SC17": ("error", "quota arithmetic", "Quota cells must reference real options and be able to sum to the total."),
    "SC18": ("warning", "quota gap", "A qualifying option belongs to no quota cell, or a quota uses a multi-select."),
    "SC19": ("info", "knock-out order", "Questions that terminate should come before open or time-consuming questions."),
    "SC20": ("info", "panel screening", "On Prolific, prefer its built-in filters; custom screening must pay and redirect screen-outs."),
    "SC21": ("warning", "states the criteria", "The text tells respondents what the study is looking for."),
    "SC22": ("error", "criterion skipped on a qualifying route", "Some route reaches the end without passing a question that screens this criterion."),
    "SC23": ("error", "exclusion never terminates", "A criterion marked (exclude) needs a terminate option on a question that screens it."),
    "SC24": ("warning", "one answer for two criteria", "A single-select tied to several criteria lets one answer settle all of them; check each option settles each criterion."),
}

LEADING_PATTERNS = [
    r"\bdon't you\b", r"\bwouldn't you\b", r"\bisn't it\b", r"\baren't you\b", r"\bdo you agree that\b",
    r"\bwould you agree\b", r"\bmost people\b", r"\bas you know\b", r"\bobviously\b", r"\bof course\b",
    r"\b(?:amazing|awesome|fantastic|wonderful|incredible|world-class|revolutionary)\b",
]
STATES_CRITERIA_PATTERNS = [
    r"\bwe(?:'re| are) (?:looking|searching) for (?:[\w-]+ ){0,3}?(?:who|with|that|users? of|owners? of)\b",
    r"\bto qualify\b", r"\bqualif(?:y|ies|ied) (?:you|for)\b",
    r"\bonly (?:people|participants|those) who\b", r"\bthis study is (?:about|on|for)\b", r"\bwe need people\b",
]
YES_NO = {"yes", "no", "y", "n", "true", "false", "not sure", "maybe", "don't know", "i don't know", "unsure"}
NONE_RE = re.compile(r"^(?:none(?: of (?:these|the above))?|neither|no(?:ne)? (?:of these|of the above)|i don'?t use any"
                     r"|nothing|not applicable|n/?a)\b", re.I)
ANY_OF_RE = re.compile(r"\b(?:any|none|either) of (?:these|them|those|the above)\b|\bany (?:at all|of it)\b")
NEGATION_RE = re.compile(r"\b(?:no|not|never|none|neither)\b|n't\b")
OTHER_RE = re.compile(r"^(?:other|something else|prefer not to (?:say|answer)|don'?t know)\b", re.I)


class InputError(Exception):
    """The screener cannot be read (exit code 2)."""


# --------------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------------

Q_HEAD_RE = re.compile(r"^#{2,4}\s*(Q\d[\w.-]*)\b\s*(.*)$", re.I)
ACTION_RE = re.compile(r"^(.*?)\s*(?:->|→|=>)\s*(.+?)\s*$")
CELL_RE = re.compile(r'"([^"]+)"\s+(\d+)\s*(?:-|–|to)\s*(\d+)|"([^"]+)"\s+(\d+)\b')


def read_text(path):
    try:
        if path == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as handle:
                data = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a file")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text (byte {exc.start}); save it as UTF-8")


def parse_action(text, where):
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    m = re.match(r"^(?:go ?to|skip to|goto)\s+(q\d[\w.-]*)$", t)
    if m:
        return ("goto", m.group(1).upper())
    if t in ("end", "qualify and end", "end and qualify"):
        raise InputError(f"{where}: {text.strip()!r} is ambiguous: 'qualify' goes on to the next question and "
                         "'terminate' ends the screener; to skip ahead use 'goto Qn'")
    if t in ("qualified", "qualifies"):
        return ("qualify", None)
    if t in ("term", "terminate", "screen out", "screen-out", "disqualify", "reject", "thank and end", "end (terminate)"):
        return ("terminate", None)
    if t in ACTIONS:
        return (t, None)
    if t in ("next", "keep", "ok", "continue (distractor)"):
        return ("continue", None)
    raise InputError(f"{where}: unknown action {text.strip()!r}; use continue, qualify, terminate or goto Qn")


def parse_markdown(text):
    doc = {"title": "", "study": "", "platform": "", "topic_words": [], "intro": "", "criteria": [],
           "quotas": {"total": None, "groups": []}, "questions": []}
    section = None
    q = None
    intro_lines = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        where = f"line {number}"
        m = Q_HEAD_RE.match(stripped)
        if m:
            section = "questions"
            rest = m.group(2)
            qtype = None
            tm = re.search(r"\[(single|multi|open|numeric)\]", rest, re.I)
            if tm:
                qtype = tm.group(1).lower()
            crit = []
            cm = re.search(r"\(([^)]*)\)", rest)
            if cm:
                crit = [c.strip() for c in re.split(r"[,;]", cm.group(1)) if c.strip()]
            q = {"id": m.group(1).upper(), "type": qtype, "text": "", "criteria": crit,
                 "articulation": bool(re.search(r"\barticulation\b", rest, re.I)),
                 "randomize": bool(re.search(r"\brandomi[sz]e\b", rest, re.I)), "options": [], "line": number}
            if not qtype:
                raise InputError(f"{where}: question {q['id']} needs a type: [single], [multi], [open] or [numeric]")
            doc["questions"].append(q)
            continue
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            low = title.lower()
            q = None
            if low.startswith("criteria"):
                section = "criteria"
            elif low.startswith("quota"):
                section = "quotas"
            elif low.startswith("question"):
                section = "questions"
            elif not doc["title"] and (stripped.startswith("# ") or (section is None and re.match(r"^##\s+screener\b", stripped, re.I))):
                doc["title"] = re.sub(r"^screener:\s*", "", title, flags=re.I)
                section = "header"
            else:
                section = "other"
            continue
        kv = re.match(r"^(study|platform|topic words|topic|total|intro)\s*:\s*(.*)$", stripped, re.I)
        if kv and (section in (None, "header", "quotas") or (section == "other" and kv.group(1).lower() != "total")):
            key, value = kv.group(1).lower(), kv.group(2).strip()
            if key in ("topic words", "topic"):
                doc["topic_words"] = [w.strip() for w in re.split(r"[,;]", value) if w.strip()]
            elif key == "total":
                try:
                    doc["quotas"]["total"] = int(value)
                except ValueError:
                    raise InputError(f"{where}: total must be a whole number")
            elif key == "intro":
                intro_lines.append(value)
            else:
                doc[key] = value
            continue
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        if section == "criteria" and bullet:
            cm = re.match(r"^([A-Za-z]\w*)\s*[:.)]\s*(.+)$", bullet.group(1))
            if not cm:
                raise InputError(f"{where}: write criteria as '- C1: description'")
            desc = cm.group(2).strip()
            doc["criteria"].append({"id": cm.group(1), "text": desc,
                                    "exclude": bool(re.search(r"\(exclude\)|\bexclude\b", desc, re.I))})
            continue
        if section == "quotas" and bullet:
            quota_line = re.sub(r"[\u201c\u201d\u201e\u201f\u2033]", '"', bullet.group(1))  # curly quotes
            gm = re.match(r"^(.+?)\s*\((Q\d[\w.-]*)\)\s*:\s*(.+)$", quota_line, re.I)
            if not gm:
                raise InputError(f"{where}: write a quota as '- Name (Q3): \"option\" 4-6; \"option\" 2-4'")
            cells = []
            for part in re.split(r";", gm.group(3)):
                part = part.strip()
                if not part:
                    continue
                cmatch = re.match(r'^((?:"[^"]+"\s*(?:\+|,|or)?\s*)+)\s*(\d+)\s*(?:(?:-|–|to)\s*(\d+))?$', part)
                if not cmatch:
                    raise InputError(f"{where}: quota cell {part!r}: write \"option\" MIN-MAX (or \"a\" + \"b\" MIN-MAX)")
                options = re.findall(r'"([^"]+)"', cmatch.group(1))
                lo = int(cmatch.group(2))
                hi = int(cmatch.group(3)) if cmatch.group(3) else lo
                cells.append({"options": options, "min": lo, "max": hi})
            doc["quotas"]["groups"].append({"name": gm.group(1).strip(), "question": gm.group(2).upper(),
                                            "cells": cells})
            continue
        if section == "questions" and q is not None:
            if bullet:
                am = ACTION_RE.match(bullet.group(1))
                if am:
                    text, act = am.group(1).strip(), parse_action(am.group(2), f"{where} ({q['id']})")
                else:
                    text, act = bullet.group(1).strip(), None
                q["options"].append({"text": text, "action": act[0] if act else None,
                                     "goto": act[1] if act else None, "line": number})
            else:
                if re.match(r"^(?:require|qualify if)\s*:", stripped, re.I):
                    raise InputError(f"{where} ({q['id']}): 'require:' / 'qualify if:' lines are not supported; "
                                     "put the rule in the options' actions (qualify, terminate)")
                q["text"] = (q["text"] + " " + stripped).strip()
            continue
        if section in (None, "header"):
            intro_lines.append(stripped)
    doc["intro"] = " ".join(intro_lines)
    return doc


def _field(obj, key, where, kind=None):
    if not isinstance(obj, dict):
        raise InputError(f"{where} must be an object")
    if key not in obj or obj[key] is None or (isinstance(obj[key], str) and not obj[key].strip()):
        raise InputError(f"{where} needs {key!r}")
    value = obj[key]
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
            raise InputError(f"{where}: {key!r} must be a whole number")
        return int(value)
    if kind is list and not isinstance(value, list):
        raise InputError(f"{where}: {key!r} must be a list")
    return value


def _list(data, key, where):
    value = data.get(key) or []
    if not isinstance(value, list):
        raise InputError(f"{where}: {key!r} must be a list")
    return value


def parse_json(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise InputError("the JSON must be an object with criteria, quotas and questions")
    doc = {"title": str(data.get("title") or ""), "study": str(data.get("study") or ""),
           "platform": str(data.get("platform") or ""),
           "topic_words": [str(w) for w in _list(data, "topic_words", "the screener")],
           "intro": str(data.get("intro") or ""),
           "criteria": [], "quotas": {"total": None, "groups": []}, "questions": []}
    for i, c in enumerate(_list(data, "criteria", "the screener"), start=1):
        where = f"criteria[{i}]"
        doc["criteria"].append({"id": str(_field(c, "id", where)), "text": str(c.get("text", "")),
                                "exclude": bool(c.get("exclude"))})
    quotas = data.get("quotas") or {}
    if not isinstance(quotas, dict):
        raise InputError("quotas must be an object with total and groups")
    if quotas.get("total") is not None:
        doc["quotas"]["total"] = _field(quotas, "total", "quotas", int)
    for gi, g in enumerate(_list(quotas, "groups", "quotas"), start=1):
        where = f"quota group {gi}"
        cells = []
        for ci, c in enumerate(_field(g, "cells", where, list), start=1):
            cw = f"{where}, cell {ci}"
            lo = _field(c, "min", cw, int)
            hi = _field(c, "max", cw, int) if c.get("max") is not None else lo
            cells.append({"options": [str(o) for o in _field(c, "options", cw, list)], "min": lo, "max": hi})
        doc["quotas"]["groups"].append({"name": str(g.get("name", "")),
                                        "question": str(_field(g, "question", where)).upper(), "cells": cells})
    for i, qd in enumerate(_list(data, "questions", "the screener"), start=1):
        where = f"questions[{i}]"
        qid = str(_field(qd, "id", where)).upper()
        qtype = str(qd.get("type", "")).lower()
        q = {"id": qid, "type": qtype, "text": str(qd.get("text", "")),
             "criteria": [str(c) for c in _list(qd, "criteria", qid)], "articulation": bool(qd.get("articulation")),
             "randomize": bool(qd.get("randomize")), "options": [], "line": None}
        for j, o in enumerate(_list(qd, "options", qid), start=1):
            text = _field(o, "text", f"{qid} option {j}")
            act = o.get("action")
            parsed = parse_action(str(act), f"question {qid}") if act else None
            q["options"].append({"text": str(text), "action": parsed[0] if parsed else None,
                                 "goto": parsed[1] if parsed else None, "line": None})
        doc["questions"].append(q)
    return doc


def load(path):
    text = read_text(path)
    doc = parse_json(text) if text.lstrip().startswith("{") else parse_markdown(text)
    if not doc["questions"]:
        raise InputError("no questions found. Question headings look like '### Q1 [single] (C1)'; see "
                         "references/screener-format.md")
    ids = [q["id"] for q in doc["questions"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise InputError(f"question id used twice: {', '.join(dup)}")
    for q in doc["questions"]:
        if q["type"] not in TYPES:
            raise InputError(f"{q['id']}: type must be single, multi, open or numeric")
    return doc


# --------------------------------------------------------------------------------------------------
# Ranges (numeric options), simplified from the pack's survey-bias-check
# --------------------------------------------------------------------------------------------------

NUM = r"(\d[\d,]*(?:\.\d+)?)(?:\s*(k|m)(?![a-z]))?"  # "10k", not the m of "months"


def _num(text, suffix):
    v = float(text.replace(",", ""))
    return v * {"k": 1e3, "m": 1e6}.get((suffix or "").lower(), 1)


def parse_range(label):
    low = re.sub(r"[$€£]", "", label.lower().replace("−", "-")).strip()
    low = re.sub(r"\s+", " ", low)
    inf = math.inf
    tail = r"(?:\s*[a-z%][a-z %/]*)?$"
    m = re.match(r"^(?:under|below|less than|fewer than|<)\s*" + NUM, low)
    if m:  # whole numbers: "under 5" ends at 4
        return (-inf, math.ceil(_num(m.group(1), m.group(2))) - 1)
    m = re.match(r"^(?:up to|at most|<=)\s*" + NUM, low) or re.match(r"^" + NUM + r".{0,15}\bor (?:less|fewer)\b", low)
    if m:
        return (-inf, _num(m.group(1), m.group(2)))
    m = re.match(r"^(?:over|above|more than|greater than|>)\s*" + NUM, low)
    if m:  # whole numbers: "over 5" starts at 6
        return (math.floor(_num(m.group(1), m.group(2))) + 1, inf)
    m = (re.match(r"^(?:at least|>=)\s*" + NUM, low) or re.match(r"^" + NUM + r"\s*\+", low)
         or re.match(r"^" + NUM + r".{0,15}\b(?:or|and) (?:more|over|above|older)\b", low))
    if m:
        return (_num(m.group(1), m.group(2)), inf)
    m = re.match(r"^" + NUM + r"\s*(?:-|–|—|to)\s*" + NUM + tail, low)
    if m:
        return (_num(m.group(1), m.group(2)), _num(m.group(3), m.group(4)))
    m = re.match(r"^" + NUM + tail, low)
    if m and re.search(r"\d", low):
        v = _num(m.group(1), m.group(2))
        return (v, v)
    return None


def range_problems(labels):
    """Overlaps and integer gaps between ranges (whole-number answers assumed)."""
    parsed = []
    for label in labels:
        r = parse_range(label)
        if r is None:
            return None
        parsed.append((r[0], r[1], label))
    if len(parsed) < 2:
        return []
    out = [f"reversed: {label} (the first number is larger than the second)" for lo, hi, label in parsed if lo > hi]
    parsed = [r for r in parsed if r[0] <= r[1]]
    parsed.sort(key=lambda r: (r[0], r[1]))
    furthest = None
    for lo, hi, label in parsed:
        if furthest is not None:
            f_hi, f_label = furthest
            if lo <= f_hi:
                out.append(f"overlap: {f_label} / {label}")
            elif not (math.isinf(f_hi) or math.isinf(lo)) and math.floor(f_hi) + 1 < math.ceil(lo):
                out.append(f"gap: {f_label} / {label} (nothing covers {math.floor(f_hi) + 1:g} to "
                           f"{math.ceil(lo) - 1:g})")
        if furthest is None or hi > furthest[0]:
            furthest = (hi, label)
    return out


# --------------------------------------------------------------------------------------------------
# Linting
# --------------------------------------------------------------------------------------------------


def straight(text):
    return text.replace("\u2019", "'").replace("\u2018", "'")


def norm(text):
    return re.sub(r"\s+", " ", straight(text).strip().lower())


def is_none(option_text):
    t = option_text.strip().lower().replace("\u2019", "'").replace("\u2018", "'")
    return bool(NONE_RE.match(t) or (ANY_OF_RE.search(t) and NEGATION_RE.search(t)))


def is_special(option_text):
    t = option_text.strip().replace("\u2019", "'")
    return bool(is_none(t) or OTHER_RE.match(t))


def screens_something(q):
    return q["type"] != "open" and any(o["action"] in ("qualify", "terminate") for o in q["options"])


def route_moves(qs, index):
    """For each question, the moves a person can make: (destination index, option label, passes).

    `passes` says the move passes the question's screen. Single-select and numeric: the chosen option's action
    applies; when the question has qualify options only those pass, so a distractor routed to continue lets a
    non-target through. Multi-select: any selected terminate option screens out, and when the question has
    qualify options at least one must be selected; when several selected options goto, the earliest target
    applies. The end of the screener is index len(qs)."""
    out = []
    for i, q in enumerate(qs):
        nxt = i + 1
        opts = q["options"]
        moves = []
        if q["type"] == "open" or not opts:
            moves.append((nxt, None, True))
        else:
            has_qual = any(o["action"] == "qualify" for o in opts)
            for o in opts:
                act = o["action"]
                if act == "terminate":
                    continue
                if act == "goto":
                    if o["goto"] not in index or index[o["goto"]] <= i:
                        continue
                    dest = index[o["goto"]]
                else:
                    dest = nxt
                if q["type"] == "multi":
                    if act == "goto" or not has_qual or act == "qualify":
                        moves.append((dest, o["text"], True))
                else:
                    moves.append((dest, o["text"], act == "qualify" or not has_qual))
        out.append(moves)
    return out


def route_missing(qs, moves, screens):
    """A route from the first question to the end that never passes one of `screens`, or None."""
    end_node = len(qs)
    parent = {0: None}
    frontier = [0] if qs else []
    while frontier:
        i = frontier.pop(0)
        if i == end_node:
            steps, node = [], end_node
            while parent[node] is not None:
                prev, label = parent[node]
                q = qs[prev]
                if label is None or q["type"] == "open":
                    steps.append(q["id"])
                else:
                    short = label if len(label) <= 45 else label[:42] + "..."
                    steps.append(f"{q['id']} '{short}'")
                node = prev
            return " -> ".join(reversed(steps)) + " -> end"
        for dest, label, passes in moves[i]:
            if i in screens and passes:
                continue
            if dest not in parent:
                parent[dest] = (i, label)
                frontier.append(dest)
    return None


def lint(doc):
    findings = []

    def add(rule, where, detail, fix):
        sev, name, _ = RULES[rule]
        findings.append({"rule": rule, "severity": sev, "name": name, "where": where, "detail": detail,
                         "fix": fix})

    qs = doc["questions"]
    index = {q["id"]: i for i, q in enumerate(qs)}
    crit_ids = {c["id"] for c in doc["criteria"]}

    # Coverage of the profile.
    covered = set()
    for q in qs:
        for c in q["criteria"]:
            if c not in crit_ids:
                add("SC02", q["id"], f"names criterion {c!r}, which is not in the Criteria list",
                    "Add the criterion or correct the id.")
            covered.add(c)
    for c in doc["criteria"]:
        if c["id"] not in covered:
            add("SC01", c["id"], f"no question screens for: {c['text']}",
                "Add a behavioural question for it, or drop the criterion if it does not matter.")
    if not doc["criteria"]:
        add("SC01", "Criteria", "the screener lists no target criteria, so coverage cannot be checked",
            "List each criterion of the target profile as '- C1: ...'.")

    # Routing.
    for q in qs:
        if q["type"] in ("single", "multi", "numeric") and not q["options"]:
            add("SC03", q["id"], "closed question without options", "List the options with their actions.")
        for o in q["options"]:
            if o["action"] is None:
                add("SC03", q["id"], f"option {o['text']!r} has no action",
                    "End it with '-> continue', '-> qualify', '-> terminate' or '-> goto Qn'.")
            elif o["action"] == "goto":
                target = o["goto"]
                if target not in index:
                    add("SC04", q["id"], f"option {o['text']!r} goes to {target}, which does not exist",
                        "Point it at a real later question.")
                elif index[target] <= index[q["id"]]:
                    add("SC04", q["id"], f"option {o['text']!r} goes back to {target}: a loop",
                        "Route only forward.")
        acts = [o["action"] for o in q["options"]]
        if q["options"] and acts and all(a == "terminate" for a in acts):
            add("SC06", q["id"], "every option terminates", "At least one answer must continue or qualify.")

    # Routes: every move a person can make, forward only (backward gotos are SC04 errors and are not followed).
    moves = route_moves(qs, index)
    end_node = len(qs)
    reachable, frontier = set(), [0] if qs else []
    while frontier:
        i = frontier.pop()
        if i in reachable or i == end_node:
            continue
        reachable.add(i)
        frontier.extend(dest for dest, _, _ in moves[i])
    can_finish = any(dest == end_node for i in reachable for dest, _, _ in moves[i])
    for i, q in enumerate(qs):
        if i not in reachable:
            add("SC05", q["id"], "no route reaches this question", "Fix the goto targets above it.")
    if qs and not can_finish:
        add("SC06", "screener", "no route reaches the end without a terminate",
            "Check the terminate actions: at least one complete path must qualify.")

    # Every route that qualifies must pass a screening question for every criterion.
    for c in doc["criteria"]:
        named = [i for i, q in enumerate(qs) if c["id"] in q["criteria"]]
        closed = [i for i in named if qs[i]["type"] != "open"]
        screens = {i for i in closed if screens_something(qs[i])}
        if named and not closed:
            add("SC07", c["id"], f"{c['id']} is screened only by an open answer",
                "Read those answers before inviting, or add a closed question that terminates or qualifies.")
            continue
        if not closed:
            continue
        if c["exclude"] and not any(o["action"] == "terminate" for i in closed for o in qs[i]["options"]):
            add("SC23", c["id"], f"exclusion '{c['text']}' has no terminate option on "
                                 f"{', '.join(qs[i]['id'] for i in closed)}",
                "Route the excluded answers to '-> terminate'.")
        path = route_missing(qs, moves, screens)
        if path is not None:
            add("SC22", c["id"], f"a person can qualify without passing {c['id']} ({c['text']}): {path}",
                "Route non-target answers on its question to '-> terminate', or remove the goto that skips it.")
    for q in qs:
        distinct = list(dict.fromkeys(q["criteria"]))
        if q["type"] != "open" and len(distinct) >= 2:
            add("SC24", q["id"], f"one answer settles {', '.join(distinct)}"
                                 + (" (a multi-select passes on any one qualify option: OR, not AND)"
                                    if q["type"] == "multi" else ""),
                "Split it into one question per criterion, unless every option settles each criterion "
                "(a part-time worker in an excluded industry must still terminate).")

    # Per-question screening quality.
    first_positions, qualifying_questions = [], 0
    quota_questions = {g["question"] for g in doc["quotas"]["groups"]}
    topic = [w.lower() for w in doc["topic_words"] if w.strip()]
    for q in qs:
        text_low = straight(q["text"]).lower()
        opts = q["options"]
        quals = [o for o in opts if o["action"] == "qualify"]
        terms = [o for o in opts if o["action"] == "terminate"]
        if q["criteria"] and q["type"] != "open" and not quals and not terms:
            add("SC07", q["id"], f"tied to {', '.join(q['criteria'])} but no answer qualifies or terminates",
                "Mark the qualifying answer(s) '-> qualify' or the excluded ones '-> terminate'.")
        elif q["criteria"] and q["type"] != "open" and not terms and opts and all(o["action"] == "qualify" for o in opts):
            add("SC07", q["id"], f"tied to {', '.join(q['criteria'])} but every answer qualifies",
                "Route the answers that fail the criterion to '-> terminate'.")
        labels = {norm(o["text"]) for o in opts}
        if opts and labels <= YES_NO and len(labels) >= 2 and (quals or terms):
            add("SC08", q["id"], f"'{q['text'][:70]}' is answered yes/no",
                "Ask which of several plausible behaviours applies, with the qualifying one among distractors, "
                "or ask an open question (Whitenton 2019).")
        excluded = any(c["exclude"] for c in doc["criteria"] if c["id"] in q["criteria"])
        if (not quals and terms and q["type"] == "single" and q["criteria"] and not excluded
                and q["id"] not in quota_questions
                and not all(parse_range(o["text"]) for o in opts if not is_special(o["text"]))):
            # continue/terminate screening question: the continuing answers are the targets
            quals = [o for o in opts if o["action"] in ("continue", "goto") and not is_special(o["text"])]
        if quals and q["type"] in ("single", "multi") and not labels <= YES_NO and q["id"] not in quota_questions:
            distractors = [o for o in opts if o not in quals and not is_special(o["text"])]
            if len(distractors) < MIN_DISTRACTORS:
                add("SC09", q["id"], f"{len(quals)} qualifying option(s) and {len(distractors)} plausible "
                                     "distractor(s)",
                    f"Add at least {MIN_DISTRACTORS} realistic wrong answers a company might also research.")
            other = [len(o["text"]) for o in opts if o not in quals and not is_special(o["text"])]
            if other:
                median = statistics.median(other)
                for o in quals:
                    if median and len(o["text"]) >= STANDOUT_LENGTH_RATIO * median and len(o["text"]) > 20:
                        add("SC10", q["id"], f"qualifying option {o['text']!r} is {len(o['text'])} characters; "
                                             f"the distractors' median is {median:g}",
                            "Write distractors as specific as the qualifying answer, or shorten it.")
            if not q["randomize"]:
                qualifying_questions += 1
                first_positions.append(opts.index(quals[0]) == 0)
        for w in topic:
            if re.search(r"\b" + re.escape(w) + r"\b", text_low):
                add("SC11", q["id"], f"the question text names {w!r}",
                    "Ask about the broader behaviour and put the topic among distractors in the options.")
        for pat in LEADING_PATTERNS:
            m = re.search(pat, text_low)
            if m:
                add("SC12", q["id"], f"'{m.group(0)}'", "Use neutral wording.")
        for pat in STATES_CRITERIA_PATTERNS:
            m = re.search(pat, text_low)
            if m:
                add("SC21", q["id"], f"'{m.group(0)}'", "Do not say what qualifies.")
        if q["type"] == "multi":
            if not any(is_none(o["text"]) for o in opts):
                add("SC13", q["id"], "no 'None of these' option", "Add an exclusive 'None of these' option.")
            trap = any(o["action"] == "terminate" and not is_special(o["text"]) for o in opts)
            if not trap and len([o for o in opts if not is_special(o["text"])]) >= SELECT_ALL_MIN_OPTIONS:
                add("SC16", q["id"], "a respondent could tick every option",
                    "Terminate or flag anyone who selects every option (Whitenton 2019).")
        ranged = [o["text"] for o in opts if not is_special(o["text"])]
        if q["type"] == "numeric" or (len(ranged) >= 2 and all(parse_range(t) for t in ranged)):
            probs = range_problems([o["text"] for o in opts if not is_special(o["text"])])
            if probs:
                for p in probs:
                    add("SC14", q["id"], p, "Make ranges mutually exclusive and cover every value.")
            elif probs is None and q["type"] == "numeric":
                add("SC14", q["id"], "the numeric options could not be read as ranges",
                    "Write them as '0-4', '5-9', '10 or more'.")
    if qualifying_questions >= 2 and all(first_positions):
        add("SC10", "screener", "the qualifying option is listed first in every question that is not randomized",
            "Randomize option order, or vary where the qualifying option sits.")

    for where, text in (("title", doc["title"]), ("intro", doc["intro"])):
        low = straight(text).lower()
        for w in topic:
            if re.search(r"\b" + re.escape(w) + r"\b", low):
                add("SC11", where, f"the {where} names {w!r}", "Describe the study in general terms.")
        for pat in STATES_CRITERIA_PATTERNS:
            m = re.search(pat, low)
            if m:
                add("SC21", where, f"'{m.group(0)}'", "Do not say what qualifies.")

    study = doc["study"].strip().lower()
    if QUALITATIVE_RE.search(study) and not re.search(r"\bunmoderated\b", study) and not any(q["articulation"] and q["type"] == "open" and q["text"].strip()
                                                for q in qs):
        add("SC15", "screener", f"study type {doc['study']!r} but no question is marked articulation",
            "Add an open question about a recent experience ('Tell us about the last time ...') and read the "
            "answers before inviting.")
    first_open = next((index[q["id"]] for q in qs if q["type"] == "open"), None)
    if first_open is not None:
        late = [q["id"] for q in qs[first_open + 1:] if any(o["action"] == "terminate" for o in q["options"])]
        if late:
            add("SC19", ", ".join(late), "terminating questions come after an open question",
                "Move knock-out questions before open ones so people screened out spend less time.")
    if "prolific" in doc["platform"].lower():
        add("SC20", "screener", "fielding on Prolific",
            "Use Prolific's own screeners for anything they cover; custom screening must redirect screen-outs "
            "with the screen-out code and pays them a fixed reward.")

    quota_summary = check_quotas(doc, qs, index, add, reachable, moves)
    return findings, quota_summary


def check_quotas(doc, qs, index, add, reachable, moves):
    """Cell bounds [min_i, max_i] can sum to the total exactly when sum(min) <= total <= sum(max). A cell counts
    only when one of its options lies on a route that qualifies; a cell that cannot fill has a real maximum of 0.
    Each group is checked on its own: crossed quotas (two groups) need their combinations checked by hand."""
    quotas = doc["quotas"]
    end_node = len(qs)
    reach_end = {end_node: True}
    for i in range(len(qs) - 1, -1, -1):
        reach_end[i] = any(reach_end.get(dest, False) for dest, _, _ in moves[i])
    total = quotas["total"]
    summary = []
    if quotas["groups"] and total is None:
        add("SC17", "Quotas", "quota groups but no total", "Add 'total: N' (participants to recruit).")
    if total is not None and total <= 0:
        add("SC17", "Quotas", f"total is {total}", "The total must be a positive number.")
    for g in quotas["groups"]:
        where = f"quota {g['name']}"
        qid = g["question"]
        if qid not in index:
            add("SC17", where, f"refers to {qid}, which does not exist", "Point it at the question it splits.")
            continue
        q = qs[index[qid]]
        if q["type"] == "multi":
            add("SC18", where, f"{qid} is multi-select, so one person can fall in several cells",
                "Base quotas on a single-select question.")
        by_text = {norm(o["text"]): o for o in q["options"]}
        qi = index[qid]
        live_opts = set()
        for o in q["options"]:
            if o["action"] == "terminate" or qi not in reachable:
                continue
            dest = index.get(o["goto"], end_node + 1) if o["action"] == "goto" else qi + 1
            if reach_end.get(dest, False):
                live_opts.add(norm(o["text"]))
        used = {}
        mins = maxs = 0
        broken = False
        for cell in g["cells"]:
            if cell["min"] < 0 or cell["max"] < cell["min"]:
                add("SC17", where, f"cell {cell['options']} has min {cell['min']} and max {cell['max']}",
                    "Use 0 <= min <= max.")
                broken = True
            live = any(norm(opt) in live_opts for opt in cell["options"])
            mins += cell["min"]
            maxs += cell["max"] if live else 0
            if not live and cell["min"] > 0:
                broken = True
                if all(norm(opt) in by_text and by_text[norm(opt)]["action"] != "terminate"
                       for opt in cell["options"]):
                    add("SC17", where, f"cell {cell['options']} needs {cell['min']} but no route through it qualifies",
                        "Fix the routing after that option, or drop the cell.")
            for opt in cell["options"]:
                o = by_text.get(norm(opt))
                if o is None:
                    add("SC17", where, f"option {opt!r} is not an option of {qid}", "Copy the option text exactly.")
                    broken = True
                    continue
                if o["action"] == "terminate":
                    add("SC17", where, f"option {opt!r} terminates, so its cell can never fill",
                        "Remove the cell or stop terminating that option.")
                    broken = True
                if norm(opt) in used:
                    add("SC17", where, f"option {opt!r} is in two cells", "Put each option in one cell.")
                    broken = True
                used[norm(opt)] = True
        if total is not None:
            if mins > total:
                add("SC17", where, f"cell minimums add to {mins}, more than the total {total}",
                    "Lower the minimums or raise the total.")
            if maxs < total:
                add("SC17", where, f"maximums of the cells that can fill add to {maxs}, less than the total {total}",
                    "Raise the maximums or lower the total: the study cannot fill.")
        uncovered = [o["text"] for o in q["options"] if o["action"] != "terminate" and norm(o["text"]) not in used
                     and not is_special(o["text"])]
        if uncovered:
            add("SC18", where, "options that do not terminate but belong to no cell: " + ", ".join(uncovered),
                "Add them to a cell, or terminate them.")
        summary.append({"name": g["name"], "question": qid, "total": total, "sum_min": mins, "sum_max": maxs,
                        "feasible": not broken and total is not None and total > 0 and mins <= total <= maxs})
    if not quotas["groups"] and total is not None:
        # A total with no quota groups is still the recruiting target: report it rather than an empty list.
        summary.append({"name": "Total (no quota groups)", "question": None, "total": total, "sum_min": None,
                        "sum_max": None, "feasible": total > 0})
    return summary


def routing_table(doc):
    rows = []
    for q in doc["questions"]:
        acts = {}
        for o in q["options"]:
            key = o["action"] if o["action"] != "goto" else f"goto {o['goto']}"
            acts.setdefault(key or "(none)", []).append(o["text"])
        row = {"id": q["id"], "type": q["type"], "criteria": q["criteria"], "articulation": q["articulation"],
               "routes": acts}
        if q["type"] == "multi" and "qualify" in acts and "continue" in acts:
            # route_moves: on a multi-select with qualify options, at least one must be picked to pass.
            row["note"] = ("continue options pass only together with a qualify option (" + ", ".join(acts["qualify"]) +
                           "); picked alone they screen out")
        rows.append(row)
    return rows


def render(doc, findings, quotas):
    out = [f"Screener: {doc['title'] or '(untitled)'}; study {doc['study'] or 'not stated'}; "
           f"{len(doc['questions'])} questions, {len(doc['criteria'])} criteria."]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warning", "info")}
    out.append(f"Findings: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info.")
    out.append("")
    for sev in ("error", "warning", "info"):
        for f in findings:
            if f["severity"] == sev:
                out.append(f"[{sev}] {f['rule']} {f['name']} at {f['where']}: {f['detail']}")
                out.append(f"        fix: {f['fix']}")
    out.append("")
    out.append("Routing:")
    for r in routing_table(doc):
        names = {"continue": "continue if a qualify option is also picked"} if r.get("note") else {}
        routes = "; ".join(f"{names.get(k, k)}: {', '.join(v)}" for k, v in r["routes"].items()) or "open answer, continue"
        tag = " [articulation]" if r["articulation"] else ""
        out.append(f"  {r['id']} ({r['type']}{', ' + ', '.join(r['criteria']) if r['criteria'] else ''}){tag}: {routes}")
        if r.get("note"):
            out.append(f"      note: {r['note']}")
    if quotas:
        out.append("Quotas:")
        for qd in quotas:
            if qd["question"] is None:
                out.append(f"  Total {qd['total']} participants; no quota groups" +
                           ("" if qd["feasible"] else " (the total must be positive)"))
                continue
            verdict = ("cell sums fit the total" if qd["feasible"]
                       else "cannot fill (see the SC17 findings)")
            out.append(f"  {qd['name']} ({qd['question']}): minimums {qd['sum_min']}, maximums of cells that can "
                       f"fill {qd['sum_max']}, total {qd['total']}: {verdict}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Lint a recruiting screener: routing, quotas, coverage, leakage.")
    p.add_argument("input", nargs="?", help="screener .md or .json ('-' for stdin)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true", help="exit 1 when there is an error-level finding")
    p.add_argument("--list-rules", action="store_true")
    args = p.parse_args(argv)
    if args.list_rules:
        for rid, (sev, name, why) in RULES.items():
            print(f"{rid} [{sev}] {name}: {why}")
        return 0
    if not args.input:
        p.error("give a screener file")
    try:
        doc = load(args.input)
    except InputError as exc:
        print(f"screener-writer: {exc}", file=sys.stderr)
        return 2
    findings, quotas = lint(doc)
    if args.json:
        print(json.dumps({"title": doc["title"], "study": doc["study"], "questions": len(doc["questions"]),
                          "criteria": [c["id"] for c in doc["criteria"]], "findings": findings,
                          "routing": routing_table(doc), "quotas": quotas}, indent=2))
    else:
        print(render(doc, findings, quotas))
    if args.strict and any(f["severity"] == "error" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
