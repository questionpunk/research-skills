#!/usr/bin/env python3
"""QSF convert: survey Markdown -> Qualtrics import file (.qsf or Advanced Format TXT), and a .qsf ->
Markdown or a codebook, plus a structural check of a .qsf.

Standard library only, Python 3.9+. No network. Deterministic: the same input gives the same bytes.

    python3 scripts/qsf_convert.py to-qualtrics survey.md -o survey.qsf   # picks TXT or QSF, says why
    python3 scripts/qsf_convert.py to-qsf survey.md -o survey.qsf
    python3 scripts/qsf_convert.py to-md export.qsf -o survey.md
    python3 scripts/qsf_convert.py codebook export.qsf -o codebook.csv
    python3 scripts/qsf_convert.py validate survey.qsf

The Markdown format is defined in references/markdown-format.md. The QSF shapes written here are
copied from real Qualtrics exports (references/sources.md); Qualtrics publishes no schema. Import into a test
survey first.

Exit codes: 0 done, 1 bad input or (validate) structural errors, 2 internal error.
"""
import argparse
import hashlib
import html
import json
import re
import sys

# Markdown type tag -> (QuestionType, Selector, SubSelector). Every triple was seen in real exports
# (references/sources.md, "Question types").
TYPES = {
    "single": ("MC", "SAVR", "TX"),
    "multi": ("MC", "MAVR", "TX"),
    "dropdown": ("MC", "DL", None),
    "nps": ("MC", "NPS", None),
    "text": ("TE", "SL", None),
    "text-long": ("TE", "ML", None),
    "essay": ("TE", "ESTB", None),
    "form": ("TE", "FORM", None),
    "info": ("DB", "TB", None),
    "matrix": ("Matrix", "Likert", "SingleAnswer"),
    "matrix-multi": ("Matrix", "Likert", "MultipleAnswer"),
    "matrix-text": ("Matrix", "TE", "Short"),
    "slider": ("Slider", "HSLIDER", None),
    "rank": ("RO", "DND", "TX"),
    "sum": ("CS", "VRTL", "TX"),
}
# Other multiple-choice layouts read as the vertical type, with a warning.
MC_LAYOUTS = {"SAHR": "single", "SACOL": "single", "SB": "single", "MAHR": "multi", "MACOL": "multi", "MSB": "multi"}
LOGIC_SOURCES = ("single", "multi", "dropdown")  # choices addressed as q://QIDn/SelectableChoice/k
OPTION_TYPES = ("single", "multi", "dropdown", "rank", "slider", "form", "sum")
MATRIX_TYPES = ("matrix", "matrix-multi", "matrix-text")
CODE_TYPES = ("single", "multi", "dropdown")  # {code:n} on options; on a Likert matrix it goes on the columns
RANDOM_TYPES = ("single", "multi", "matrix", "matrix-multi", "sum")  # Randomization "All" seen on these in exports
SINGLE_EXPORT_TYPES = ("nps", "rank", "sum")  # shape seen in one real export only
RANDOMIZE_ALL = {"Advanced": None, "TotalRandSubset": "", "Type": "All"}
FIELD_RE = r"[A-Za-z0-9_][A-Za-z0-9_ .-]*"
# Advanced Format TXT question tags (Qualtrics support page, see references/sources.md).
TXT_TAGS = {
    "single": "MC:SingleAnswer:Vertical", "multi": "MC:MultipleAnswer:Vertical", "dropdown": "MC:DropDown",
    "text": "TE:SingleLine", "essay": "TE:Essay", "form": "TE:Form", "info": "DB",
    "matrix": "Matrix:SingleAnswer", "matrix-multi": "Matrix:MultipleAnswer", "rank": "RO", "sum": "CS",
}
NPS_LABELS = ["Not at all likely", "Extremely likely"]
NPS_POINTS = [str(i) for i in range(11)]  # 0 to 10
SLIDER_RANGE = (0, 100)
SLIDER_MAX_GRID_LINES = 10
DESCRIPTION_LIMIT = 99  # SecondaryAttribute holds the first 99 characters of the question text
ID_LENGTH = 15  # SV_, RS_, UR_ ids carry 15 base-62 characters in every sampled export
SHAPES_AS_OF = "2026-11-12"  # the day the shapes written here were last compared with real exports
FIXED_DATE = "2026-01-01 00:00:00"
NO_DATE = "0000-00-00 00:00:00"
TRASH_NAME = "Trash / Unused Questions"
KEPT_TAGS = ("strong", "b", "em", "i", "u")  # plain emphasis stays as inline HTML in the Markdown
TAG_RE = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
ENTRY_KEYS = [
    "SurveyID", "SurveyName", "SurveyDescription", "SurveyOwnerID", "SurveyBrandID", "DivisionID",
    "SurveyLanguage", "SurveyActiveResponseSet", "SurveyStatus", "SurveyStartDate", "SurveyExpirationDate",
    "SurveyCreationDate", "CreatorID", "LastModified", "LastAccessed", "LastActivated", "Deleted",
]
USUAL_ELEMENTS = ["SO", "SCO", "STAT", "QC", "RS"]  # in every sampled export, next to BL and FL
# Payload keys to-md reads or that carry nothing a respondent sees.
KNOWN_KEYS = {
    "QuestionText", "QuestionText_Unsafe", "DataExportTag", "QuestionType", "Selector", "SubSelector",
    "Configuration", "QuestionDescription", "Choices", "ChoiceOrder", "Answers", "AnswerOrder", "Validation",
    "Language", "NextChoiceId", "NextAnswerId", "QuestionID", "DataVisibility", "DefaultChoices", "GradingData",
    "SearchSource", "Labels", "ColumnLabels", "AnalyzeChoices", "DisplayLogic", "RecodeValues", "Randomization",
    "ChoiceDataExportTags", "ClarifyingSymbolType", "NumberOfQuestions", "AdditionalQuestions",
}


class ConvertError(Exception):
    """Bad input: reported to the user, exit code 1."""


# --------------------------------------------------------------------------- text <-> HTML


def md_to_html(text):
    """Markdown text of a question or option -> the HTML Qualtrics stores."""
    out = re.sub(r"&(?!#?\w+;)", "&amp;", text)
    out = re.sub(r"<(?![A-Za-z/!])", "&lt;", out)
    return out.replace("\n", "<br>")


def html_to_md(source, keep_html=False):
    """Qualtrics HTML -> (Markdown text, names of the tags that were dropped)."""
    out = source if isinstance(source, str) else ""
    out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"<br\s*/?>", "\n", out, flags=re.I)
    out = re.sub(r"</(p|div)>", "\n\n", out, flags=re.I)
    out = re.sub(r"<(p|div)>", "", out, flags=re.I)
    dropped = []
    if not keep_html:
        other = r"<(?!/?(?:%s)>)/?([A-Za-z][A-Za-z0-9]*)\b[^>]*>" % "|".join(KEPT_TAGS)
        dropped = sorted({m.lower() for m in re.findall(other, out, flags=re.I)})
        out = re.sub(other, "", out, flags=re.I)
    # Decode entities, except the two that would turn back into markup on the way to QSF.
    out = re.sub(r"&lt;(?=[A-Za-z/!])", "\x01", out)
    out = re.sub(r"&amp;(?=#?\w+;)", "\x02", out)
    out = html.unescape(out).replace("\xa0", " ")
    out = out.replace("\x01", "&lt;").replace("\x02", "&amp;")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in out.split("\n")]
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out, dropped


def plain(source):
    """HTML -> one line of plain text."""
    out = re.sub(r"<[^>]+>", " ", source if isinstance(source, str) else "")
    out = re.sub(r"\s+", " ", html.unescape(out).replace("\xa0", " ")).strip()
    return re.sub(r" ([,.;:?!])", r"\1", out)


def shorten(text, limit=DESCRIPTION_LIMIT):
    return text if len(text) <= limit else text[: limit - 3] + "..."


def quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquote(text):
    return re.sub(r"\\(.)", r"\1", text)


QUOTED = r'"((?:[^"\\]|\\.)*)"'

# --------------------------------------------------------------------------- Markdown -> model


def strip_comments(text):
    out = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    if "<!--" in out:
        line = out[: out.index("<!--")].count("\n") + 1
        raise ConvertError(f"line {line}: comment opened with <!-- is never closed")
    return out


def parse_skip(value, line):
    m = re.fullmatch(rf"if\s+(not\s+)?{QUOTED}\s*->\s*(end of block|end of survey|{TAG_RE})", value)
    if not m:
        raise ConvertError(
            f'line {line}: cannot read skip rule. Write: > skip: if "Option text" -> end of block '
            "(or end of survey, or the tag of a later question in the same block); "
            'add "not" before the option for "is not selected"'
        )
    return {"negate": bool(m.group(1)), "choice": unquote(m.group(2)), "dest": m.group(3), "line": line}


def parse_show(value, line):
    cond = rf"({TAG_RE})\s+is\s+(not\s+)?{QUOTED}"
    if not re.fullmatch(rf"{cond}(\s+(and|or)\s+{cond})*", value):
        raise ConvertError(
            f'line {line}: cannot read display rule. Write: > show if: tag is "Option text" '
            '(join several with "and" or with "or"; "is not" for not selected)'
        )
    conds = [{"tag": m.group(1), "negate": bool(m.group(2)), "choice": unquote(m.group(3))} for m in re.finditer(cond, value)]
    joins = set(re.findall(rf'"\s+(and|or)\s+(?={TAG_RE}\s+is\s)', value))
    if len(joins) > 1:
        raise ConvertError(f'line {line}: a display rule may use "and" or "or", not both (no export evidences the grouping)')
    return {"conds": conds, "join": (joins.pop() if joins else "and"), "line": line}


def parse_markdown(text):
    """Survey Markdown -> {"title", "blocks": [{"name", "items": [question | {"kind": "break"}]}]}."""
    survey = {"title": None, "blocks": [], "embedded": []}
    block = None
    q = None
    section = None
    for no, raw in enumerate(strip_comments(text).splitlines(), 1):
        line = raw.strip()
        if not line:
            if q and section == "text" and q["text_lines"]:
                q["text_lines"].append("")
            continue
        if line.startswith("### "):
            m = re.fullmatch(rf"###\s+({TAG_RE})\s+\[([a-z-]+)\](?:\s+(required|request))?", line)
            if not m:
                raise ConvertError(
                    f"line {no}: cannot read question heading. Write: ### tag [type] with an optional "
                    f"'required' or 'request'; types: {', '.join(TYPES)}"
                )
            if m.group(2) not in TYPES:
                raise ConvertError(f"line {no}: unknown question type [{m.group(2)}]; use one of: {', '.join(TYPES)}")
            if block is None:
                raise ConvertError(f"line {no}: question before any block; add a '## Block name' heading first")
            q = {
                "kind": "question", "tag": m.group(1), "type": m.group(2), "force": m.group(3), "line": no,
                "text_lines": [], "options": [], "rows": [], "columns": [], "skips": [], "show": None,
                "range": None, "labels": None, "randomize": False, "total": None,
            }
            block["items"].append(q)
            section = "text"
        elif line.startswith("## "):
            block = {"name": line[3:].strip(), "items": [], "line": no}
            if not block["name"]:
                raise ConvertError(f"line {no}: block heading has no name")
            survey["blocks"].append(block)
            q = None
        elif line.startswith("# "):
            if survey["title"] is not None or survey["blocks"]:
                raise ConvertError(f"line {no}: the survey title (# ...) must come once, before the first block")
            survey["title"] = line[2:].strip()
        elif re.fullmatch(r"-{3,}", line):
            if block is None:
                raise ConvertError(f"line {no}: page break before any block")
            block["items"].append({"kind": "break", "line": no})
            q = None
        elif block is None and line.startswith(">"):
            m = re.fullmatch(rf">\s*embedded\s*:\s*({FIELD_RE}?)\s*(?:=\s*(.*))?", line)
            if not m:
                raise ConvertError(
                    f"line {no}: before the first block only '> embedded: field' or '> embedded: field = value' is allowed"
                )
            if m.group(1) in [e["field"] for e in survey["embedded"]]:
                raise ConvertError(f"line {no}: embedded data field {m.group(1)!r} is declared twice")
            survey["embedded"].append({"field": m.group(1), "value": m.group(2)})
        elif q is None:
            raise ConvertError(
                f"line {no}: text outside a question: {line[:40]!r}. Put it under a '### tag [info]' heading, "
                "or in an HTML comment"
            )
        elif line.startswith("- "):
            body = line[2:].strip()
            m = re.search(rf"(?:\s*\{{(?:text|exclusive|code:-?\d+|var:{TAG_RE})\}})+$", body)
            attrs = dict(re.findall(r"\{(\w+):?([^}]*)\}", m.group(0))) if m else {}
            label = body[: m.start()].strip() if m else body
            if not label:
                raise ConvertError(f"line {no}: option has no text")
            option = {
                "text": label, "text_entry": "text" in attrs, "exclusive": "exclusive" in attrs,
                "code": attrs.get("code"), "var": attrs.get("var"), "line": no,
            }
            if q["type"] in MATRIX_TYPES:
                if section not in ("rows", "columns"):
                    raise ConvertError(f"line {no}: a matrix lists its statements under 'Rows:' and its scale under 'Columns:'")
                q[section].append(option)
            else:
                if section not in ("text", "options"):
                    raise ConvertError(f"line {no}: options must come before the '>' rules of question {q['tag']}")
                section = "options"
                q["options"].append(option)
        elif line in ("Rows:", "Columns:"):
            if q["type"] not in MATRIX_TYPES:
                raise ConvertError(f"line {no}: '{line}' is only for [matrix] and [matrix-multi] questions")
            section = line[:-1].lower()
        elif line.startswith(">"):
            m = re.fullmatch(r">\s*(skip|show if|range|labels|randomize|total)\s*:\s*(.+)", line)
            if not m:
                raise ConvertError(
                    f"line {no}: unknown rule. Known rules: > skip:, > show if:, > range:, > labels:, > randomize:, > total:"
                )
            key, value = m.group(1), m.group(2).strip()
            section = "rules"
            if key == "skip":
                q["skips"].append(parse_skip(value, no))
            elif key == "show if":
                if q["show"]:
                    raise ConvertError(f"line {no}: question {q['tag']} already has a display rule; join conditions in one line")
                q["show"] = parse_show(value, no)
            elif key == "range":
                m2 = re.fullmatch(r"(-?\d+)\s+to\s+(-?\d+)", value)
                if not m2 or int(m2.group(1)) >= int(m2.group(2)):
                    raise ConvertError(f"line {no}: write the range as whole numbers, low to high: > range: 0 to 100")
                q["range"] = (int(m2.group(1)), int(m2.group(2)))
            elif key == "randomize":
                wanted = "rows" if q["type"] in MATRIX_TYPES else "options"
                if value != wanted or q["type"] not in RANDOM_TYPES:
                    raise ConvertError(
                        f"line {no}: write '> randomize: options' (on {', '.join(t for t in RANDOM_TYPES if t not in MATRIX_TYPES)}) "
                        "or '> randomize: rows' (on matrix and matrix-multi)"
                    )
                q["randomize"] = True
            elif key == "total":
                if q["type"] != "sum" or not re.fullmatch(r"\d+", value) or int(value) == 0:
                    raise ConvertError(f"line {no}: '> total:' takes a whole number above 0 and only applies to [sum]")
                q["total"] = int(value)
            else:
                q["labels"] = [part.strip() for part in value.split("|")]
                if not all(q["labels"]):
                    raise ConvertError(f"line {no}: empty label; write: > labels: Low | High")
        else:
            if section != "text":
                raise ConvertError(
                    f"line {no}: unexpected text after the options or rules of question {q['tag']}: {line[:40]!r}. "
                    "Question text goes directly under the heading"
                )
            q["text_lines"].append(line[1:] if line.startswith("\\") else line)
    check_model(survey)
    return survey


def questions_of(survey):
    return [item for block in survey["blocks"] for item in block["items"] if item["kind"] == "question"]


def find_choice(q, label, line, what):
    hits = [i for i, option in enumerate(q["options"]) if option["text"] == label]
    if len(hits) != 1:
        problem = "has no option" if not hits else "has more than one option"
        raise ConvertError(f"line {line}: {what}: question {q['tag']} {problem} with the exact text {label!r}")
    return hits[0] + 1


def check_model(survey):
    if not survey["title"]:
        raise ConvertError("the survey needs a title: start the file with '# Survey name'")
    if not survey["blocks"]:
        raise ConvertError("the survey has no block: add '## Block name' and at least one question")
    by_tag = {}
    for q in questions_of(survey):
        where = f"line {q['line']}: question {q['tag']}"
        if q["tag"] in by_tag:
            raise ConvertError(f"{where}: tag already used on line {by_tag[q['tag']]['line']}; tags must be unique")
        by_tag[q["tag"]] = q
        lines = q.pop("text_lines")
        q["text"] = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        kind = q["type"]
        if not q["text"]:
            raise ConvertError(f"{where}: no question text under the heading")
        if kind in OPTION_TYPES and not q["options"]:
            raise ConvertError(f"{where}: a [{kind}] question needs at least one '- option' line")
        if kind not in OPTION_TYPES and q["options"]:
            raise ConvertError(f"{where}: a [{kind}] question takes no '- option' lines")
        if kind in MATRIX_TYPES and not (q["rows"] and q["columns"]):
            raise ConvertError(f"{where}: a matrix needs 'Rows:' and 'Columns:', each with at least one '- ' line")
        coded = q["columns"] if kind in ("matrix", "matrix-multi") else q["options"] if kind in CODE_TYPES else []
        for option in q["options"] + q["rows"] + q["columns"]:
            if option["code"] is not None and not any(option is o for o in coded):
                raise ConvertError(
                    f"line {option['line']}: {{code:n}} applies to the options of {', '.join(CODE_TYPES)} "
                    "and to the columns of matrix and matrix-multi"
                )
            if option["var"] is not None and not (kind in MATRIX_TYPES and any(option is o for o in q["rows"])):
                raise ConvertError(f"line {option['line']}: {{var:name}} only applies to matrix rows")
        for group, key, what in ((coded, "code", "{code:n}"), (q["rows"], "var", "{var:name}")):
            given = [o[key] for o in group if o[key] is not None]
            if given and (len(given) != len(group) or len(set(given)) != len(given)):
                raise ConvertError(f"{where}: give {what} to every {'row' if key == 'var' else 'option or column'}, each one different, or to none")
        if q["force"] and kind == "sum":
            raise ConvertError(f"{where}: a [sum] question cannot be '{q['force']}' (no export evidences that shape); use '> total:'")
        for option in q["options"] + q["rows"] + q["columns"]:
            if option["exclusive"] and kind != "multi":
                raise ConvertError(f"line {option['line']}: {{exclusive}} only applies to [multi] options")
            if option["text_entry"] and kind not in ("single", "multi"):
                raise ConvertError(f"line {option['line']}: {{text}} only applies to [single] and [multi] options")
        if q["force"] and kind == "info":
            raise ConvertError(f"{where}: an [info] screen cannot be '{q['force']}'")
        if q["range"] and kind != "slider":
            raise ConvertError(f"{where}: '> range:' only applies to [slider]")
        if q["labels"] and kind not in ("slider", "nps"):
            raise ConvertError(f"{where}: '> labels:' only applies to [slider] and [nps]")
        if q["labels"] and kind == "nps" and len(q["labels"]) != 2:
            raise ConvertError(f"{where}: an [nps] question takes exactly two labels: > labels: Low end | High end")
        if q["skips"] and kind not in LOGIC_SOURCES:
            raise ConvertError(f"{where}: '> skip:' is only supported on {', '.join(LOGIC_SOURCES)} questions")
    for block in survey["blocks"]:
        seen = []
        for item in block["items"]:
            if item["kind"] != "question":
                continue
            seen.append(item["tag"])
        for position, item in enumerate(i for i in block["items"] if i["kind"] == "question"):
            for skip in item["skips"]:
                skip["key"] = find_choice(item, skip["choice"], skip["line"], "skip rule")
                if skip["dest"] in ("end of block", "end of survey"):
                    continue
                if skip["dest"] not in seen[position + 1 :]:
                    raise ConvertError(
                        f"line {skip['line']}: skip target {skip['dest']!r} must be a later question in the same block "
                        "(Qualtrics skip logic only moves forward inside a block); otherwise use 'end of block'"
                    )
    for q in questions_of(survey):
        for cond in q["show"]["conds"] if q["show"] else []:
            line = q["show"]["line"]
            source = by_tag.get(cond["tag"])
            if source is None:
                raise ConvertError(f"line {line}: display rule names question {cond['tag']!r}, which does not exist")
            if source is q:
                raise ConvertError(f"line {line}: a display rule cannot depend on its own question")
            if source["type"] not in LOGIC_SOURCES:
                raise ConvertError(f"line {line}: display rules can only test {', '.join(LOGIC_SOURCES)} questions, not [{source['type']}]")
            cond["key"] = find_choice(source, cond["choice"], line, "display rule")


# --------------------------------------------------------------------------- model -> QSF


def make_id(prefix, seed, name):
    digest = int(hashlib.sha256(f"{seed}:{name}".encode("utf-8")).hexdigest(), 16)
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    chars = []
    for _ in range(ID_LENGTH):
        digest, index = divmod(digest, len(alphabet))
        chars.append(alphabet[index])
    return prefix + "".join(chars)


def choices_payload(options):
    choices = {}
    for key, option in enumerate(options, 1):
        choice = {"Display": md_to_html(option["text"])}
        if option["text_entry"]:
            choice["TextEntry"] = "true"
        if option["exclusive"]:
            choice["ExclusiveAnswer"] = True
        choices[str(key)] = choice
    return choices


def question_payload(q, qid, qids, by_tag):
    qtype, selector, sub = TYPES[q["type"]]
    kind = q["type"]
    text_html = md_to_html(q["text"])
    payload = {"QuestionText": text_html, "DataExportTag": q["tag"], "QuestionType": qtype, "Selector": selector}
    if sub:
        payload["SubSelector"] = sub
    config = {"QuestionDescriptionOption": "UseText"}
    payload["Configuration"] = config
    payload["QuestionDescription"] = shorten(plain(text_html))
    next_choice, next_answer = 4, 1  # the counters a fresh text question carries in the sampled exports
    if kind in OPTION_TYPES:
        payload["Choices"] = choices_payload(q["options"])
        payload["ChoiceOrder"] = [str(i) for i in range(1, len(q["options"]) + 1)]
        next_choice = len(q["options"]) + 1
        if q["options"][0]["code"] is not None:
            payload["RecodeValues"] = {str(i): o["code"] for i, o in enumerate(q["options"], 1)}
    if kind in MATRIX_TYPES:
        payload["Choices"] = choices_payload(q["rows"])
        payload["ChoiceOrder"] = [str(i) for i in range(1, len(q["rows"]) + 1)]
        payload["Answers"] = choices_payload(q["columns"])
        payload["AnswerOrder"] = [str(i) for i in range(1, len(q["columns"]) + 1)]
        payload["ChoiceDataExportTags"] = False
        if q["rows"][0]["var"] is not None:
            payload["ChoiceDataExportTags"] = {str(i): o["var"] for i, o in enumerate(q["rows"], 1)}
        if q["columns"][0]["code"] is not None:
            payload["RecodeValues"] = {str(i): o["code"] for i, o in enumerate(q["columns"], 1)}
        config.update({"TextPosition": "inline", "ChoiceColumnWidth": 25, "RepeatHeaders": "none", "MobileFirst": True})
        if kind != "matrix-text":
            config["WhiteSpace"] = "OFF"
        next_choice, next_answer = len(q["rows"]) + 1, len(q["columns"]) + 1
    if kind == "nps":
        labels = q["labels"] or NPS_LABELS
        payload["Choices"] = [{"Display": point} for point in NPS_POINTS]
        payload["ChoiceOrder"] = list(NPS_POINTS)
        payload["ColumnLabels"] = [{"Display": md_to_html(label), "IsLabelDefault": labels == NPS_LABELS} for label in labels]
        next_choice = len(NPS_POINTS)
    if kind == "slider":
        low, high = q["range"] or SLIDER_RANGE
        config.update({
            "CSSliderMin": low, "CSSliderMax": high, "GridLines": min(high - low, SLIDER_MAX_GRID_LINES),
            "SnapToGrid": False, "NumDecimals": "0", "ShowValue": True, "CustomStart": False,
            "NotApplicable": False, "MobileFirst": True,
        })
        payload["Labels"] = {str(i): {"Display": md_to_html(label)} for i, label in enumerate(q["labels"], 1)} if q["labels"] else []
    if q["randomize"]:
        payload["Randomization"] = dict(RANDOMIZE_ALL)
    if kind == "sum":
        payload["Labels"] = []
        payload["ClarifyingSymbolType"] = "None"
    if kind == "info":
        payload["ChoiceOrder"] = []
        payload["Validation"] = {"Settings": {"Type": "None"}}
    elif kind == "sum" and q["total"]:
        payload["Validation"] = {"Settings": {"EnforceRange": "OFF", "Type": "ChoicesTotal", "ChoiceTotal": str(q["total"])}}
    else:
        force = {"required": "ON", "request": "RequestResponse", None: "OFF"}[q["force"]]
        force_type = "RequestResponse" if force == "RequestResponse" else "ON"
        payload["Validation"] = {"Settings": {"ForceResponse": force, "ForceResponseType": force_type, "Type": "None"}}
    payload.update({
        "DefaultChoices": False, "GradingData": [], "Language": [], "NextChoiceId": next_choice,
        "NextAnswerId": next_answer, "DataVisibility": {"Private": False, "Hidden": False}, "QuestionID": qid,
    })
    if q["show"]:
        expressions = {}
        for index, cond in enumerate(q["show"]["conds"]):
            source = by_tag[cond["tag"]]
            source_id = qids[cond["tag"]]
            locator = f"q://{source_id}/SelectableChoice/{cond['key']}"
            join = "If" if index == 0 else q["show"]["join"].capitalize()
            verb = "Is Not Selected" if cond["negate"] else "Is Selected"
            expression = {
                "LogicType": "Question", "QuestionID": source_id, "QuestionIsInLoop": "no", "ChoiceLocator": locator,
                "Operator": "NotSelected" if cond["negate"] else "Selected", "QuestionIDFromLocator": source_id,
                "LeftOperand": locator, "Type": "Expression",
                "Description": (
                    f'<span class="ConjDesc">{join}</span> <span class="QuestionDesc">{html.escape(plain(md_to_html(source["text"])))}</span> '
                    f'<span class="LeftOpDesc">{html.escape(plain(md_to_html(cond["choice"])))}</span> <span class="OpDesc">{verb}</span> '
                ),
            }
            if index:
                expression["Conjuction"] = join  # Qualtrics' own spelling
            expressions[str(index)] = expression
        expressions["Type"] = "If"
        payload["DisplayLogic"] = {"0": expressions, "Type": "BooleanExpression", "inPage": False}
    return payload


def skip_payload(q, qid, qids, by_tag, counter):
    out = []
    for skip in q["skips"]:
        locator = f"q://{qid}/SelectableChoice/{skip['key']}"
        choice = html.escape(plain(md_to_html(skip["choice"])))
        verb = "Not Selected" if skip["negate"] else "Selected"
        if skip["dest"] == "end of block":
            dest, dest_name = "ENDOFBLOCK", "End of Block"
        elif skip["dest"] == "end of survey":
            dest, dest_name = "ENDOFSURVEY", "End of Survey"
        else:
            dest = qids[skip["dest"]]
            dest_name = html.escape(shorten(plain(md_to_html(by_tag[skip["dest"]]["text"]))))
        counter[0] += 1
        out.append({
            "SkipLogicID": counter[0], "ChoiceLocator": locator, "Condition": "NotSelected" if skip["negate"] else "Selected",
            "SkipToDestination": dest, "Locator": locator,
            "SkipToDescription": f"{html.escape(shorten(plain(md_to_html(q['text']))))} <strong>{choice}</strong> Is <strong>{verb}</strong>",
            "Description": f'If <strong title="{choice}">{choice}</strong> Is <strong>{verb}</strong>, Then Skip To <strong>{dest_name}</strong>',
            "QuestionID": qid,
        })
    return out


def build_qsf(survey, source_text):
    """Model -> (QSF dict, warnings)."""
    warnings = []
    seed = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    survey_id = make_id("SV_", seed, "survey")
    owner = make_id("UR_", seed, "owner")
    response_set = make_id("RS_", seed, "responses")
    questions = questions_of(survey)
    by_tag = {q["tag"]: q for q in questions}
    qids = {q["tag"]: f"QID{n}" for n, q in enumerate(questions, 1)}
    order = list(qids)
    for q in questions:
        if q["type"] in SINGLE_EXPORT_TYPES:
            warnings.append(f"{q['tag']}: the [{q['type']}] shape was seen in one real export only; check this question after import")
        for cond in q["show"]["conds"] if q["show"] else []:
            if order.index(cond["tag"]) > order.index(q["tag"]):
                warnings.append(f"{q['tag']}: its display rule tests {cond['tag']}, which comes later in the survey, so it can never be true")

    def element(code, primary, secondary, tertiary, payload):
        return {
            "SurveyID": survey_id, "Element": code, "PrimaryAttribute": primary, "SecondaryAttribute": secondary,
            "TertiaryAttribute": tertiary, "Payload": payload,
        }

    blocks, flow, counter = [], [], [0]
    if survey["embedded"]:
        fields = []
        for item in survey["embedded"]:
            field = {"Description": item["field"], "Type": "Recipient" if item["value"] is None else "Custom", "Field": item["field"],
                     "VariableType": "String", "DataVisibility": [], "AnalyzeText": False}
            if item["value"] is not None:
                field["Value"] = item["value"]
            fields.append(field)
        flow.append({"Type": "EmbeddedData", "FlowID": "FL_2", "EmbeddedData": fields})
    for index, block in enumerate(survey["blocks"]):
        block_id = make_id("BL_", seed, f"block{index}")
        elements = []
        for item in block["items"]:
            if item["kind"] == "break":
                elements.append({"Type": "Page Break"})
                continue
            entry = {"Type": "Question", "QuestionID": qids[item["tag"]]}
            if item["skips"]:
                entry["SkipLogic"] = skip_payload(item, qids[item["tag"]], qids, by_tag, counter)
            elements.append(entry)
        if not elements:
            warnings.append(f"block {block['name']!r} has no questions")
        if index == 0:
            blocks.append({"Type": "Default", "Description": block["name"], "ID": block_id, "BlockElements": elements})
            blocks.append({"Type": "Trash", "Description": TRASH_NAME, "ID": make_id("BL_", seed, "trash"), "BlockElements": []})
        else:
            blocks.append({"Type": "Standard", "SubType": "", "Description": block["name"], "ID": block_id, "BlockElements": elements})
        flow.append({"Type": "Block" if index == 0 else "Standard", "ID": block_id, "FlowID": f"FL_{len(flow) + 2}", "Autofill": []})
    options = {
        "BackButton": "false", "SaveAndContinue": "true", "SurveyProtection": "PublicSurvey",
        "BallotBoxStuffingPrevention": "false", "NoIndex": "Yes", "SecureResponseFiles": "true", "SurveyExpiration": "None",
        "SurveyTermination": "DefaultMessage", "Header": "", "Footer": "", "ProgressBarDisplay": "None",
        "PartialData": "+1 week", "ValidationMessage": "", "PreviousButton": " \u2190 ", "NextButton": " \u2192 ",
        "SkinLibrary": "", "SkinType": "templated", "Skin": {"brandingId": None, "templateId": "*base", "overrides": None},
        "NewScoring": 1,
    }
    scoring = {
        "ScoringCategories": [], "ScoringCategoryGroups": [], "ScoringSummaryCategory": None,
        "ScoringSummaryAfterQuestions": 0, "ScoringSummaryAfterSurvey": 0, "DefaultScoringCategory": None,
        "AutoScoringCategory": None,
    }
    elements = [
        element("BL", "Survey Blocks", None, None, blocks),
        element("FL", "Survey Flow", None, None, {"Type": "Root", "FlowID": "FL_1", "Flow": flow, "Properties": {"Count": len(flow) + 1}}),
        element("SO", "Survey Options", None, None, options),
        element("SCO", "Scoring", None, None, scoring),
        element("PROJ", "CORE", None, "1.1.0", {"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"}),
        element("STAT", "Survey Statistics", None, None, {"MobileCompatible": True, "ID": "Survey Statistics"}),
        element("QC", "Survey Question Count", str(len(questions)), None, None),
        element("RS", response_set, "Default Response Set", None, None),
    ]
    for q in questions:
        payload = question_payload(q, qids[q["tag"]], qids, by_tag)
        elements.append(element("SQ", qids[q["tag"]], payload["QuestionDescription"], None, payload))
    entry = {
        "SurveyID": survey_id, "SurveyName": survey["title"], "SurveyDescription": None, "SurveyOwnerID": owner,
        "SurveyBrandID": "", "DivisionID": None, "SurveyLanguage": "EN", "SurveyActiveResponseSet": response_set,
        "SurveyStatus": "Inactive", "SurveyStartDate": NO_DATE, "SurveyExpirationDate": NO_DATE,
        "SurveyCreationDate": FIXED_DATE, "CreatorID": owner, "LastModified": FIXED_DATE, "LastAccessed": NO_DATE,
        "LastActivated": NO_DATE, "Deleted": None,
    }
    return {"SurveyEntry": entry, "SurveyElements": elements}, warnings


# --------------------------------------------------------------------------- QSF -> model pieces


def load_qsf(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConvertError(f"not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}") from None
    if not isinstance(data, dict) or not isinstance(data.get("SurveyEntry"), dict) or not isinstance(data.get("SurveyElements"), list):
        raise ConvertError("not a QSF file: expected a JSON object with 'SurveyEntry' (object) and 'SurveyElements' (list)")
    return data


def as_list(payload):
    """A BL payload is a list in some exports and an object keyed "0", "1", ... in others."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload[key] for key in sorted(payload, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0, str(k)))]
    return []


def ordered(mapping, order):
    """Choices or Answers as [(key, entry)] in display order. NPS stores Choices as a list."""
    if isinstance(mapping, list):
        mapping = {str(index): entry for index, entry in enumerate(mapping)}
    if not isinstance(mapping, dict):
        return [], 0
    keys = [str(key) for key in order] if isinstance(order, list) and order else list(mapping)
    shown = [(key, mapping[key]) for key in keys if key in mapping]
    return shown, len(mapping) - len(shown)


def classify(payload):
    """Payload -> (Markdown type or None, layout note or None)."""
    qtype, selector, sub = payload.get("QuestionType"), payload.get("Selector"), payload.get("SubSelector")
    if qtype == "MC":
        if selector in MC_LAYOUTS:
            return MC_LAYOUTS[selector], f"layout {selector} becomes a vertical list"
        for name in ("single", "multi", "dropdown", "nps"):
            if TYPES[name][1] == selector:
                return name, None
        return None, None
    if qtype == "Matrix":
        if not isinstance(payload.get("Answers"), dict):
            return None, None
        if selector == "Likert" and sub in ("SingleAnswer", "MultipleAnswer"):
            return ("matrix" if sub == "SingleAnswer" else "matrix-multi"), None
        if selector == "Likert" and isinstance(sub, str):
            return "matrix", f"matrix layout {sub} becomes a table with one answer per row"
        if (selector, sub) == ("TE", "Short"):
            return "matrix-text", None
        return None, None
    for name, (t, s, _) in TYPES.items():
        if (t, s) == (qtype, selector) and t not in ("MC", "Matrix"):
            return name, None
    return None, None


def logic_text(logic):
    """Qualtrics logic as one readable line, from the Description each expression carries."""
    parts = []
    for key, group in (logic.items() if isinstance(logic, dict) else []):
        if not isinstance(group, dict):
            continue
        for sub, expr in group.items():
            if isinstance(expr, dict):
                text = plain(expr.get("Description")) or " ".join(
                    str(expr[k]) for k in ("Conjuction", "LeftOperand", "Operator", "RightOperand") if expr.get(k) not in (None, "")
                )
                parts.append(text)
    return " ".join(part for part in parts if part) or "a condition the export does not spell out"


def comment(text):
    return "<!-- " + re.sub(r"-{2,}", "-", re.sub(r"\s+", " ", text)).replace(">", "&gt;").strip() + " -->"


class Reader:
    """One .qsf -> Markdown lines and the list of everything Markdown could not hold."""

    def __init__(self, data, keep_html=False):
        self.data = data
        self.keep_html = keep_html
        self.warnings = []
        elements = [e for e in data["SurveyElements"] if isinstance(e, dict)]
        self.elements = elements
        self.questions = {}
        for e in elements:
            if e.get("Element") == "SQ" and isinstance(e.get("Payload"), dict):
                qid = e["Payload"].get("QuestionID") or e.get("PrimaryAttribute")
                self.questions[str(qid)] = e["Payload"]
        block_elements = [e for e in elements if e.get("Element") == "BL"]
        if not block_elements:
            raise ConvertError("the file has no 'BL' (Survey Blocks) element, so the order of its questions is unknown")
        self.blocks = [b for b in as_list(block_elements[0].get("Payload")) if isinstance(b, dict) and b.get("ID")]
        flows = [e for e in elements if e.get("Element") == "FL" and isinstance(e.get("Payload"), dict)]
        self.flow = flows[0]["Payload"] if flows else None
        self.split = {}  # side-by-side QID -> the QIDs of the one-column questions it is read as
        for qid, payload in list(self.questions.items()):
            columns = payload.get("AdditionalQuestions")
            if payload.get("QuestionType") != "SBS" or not isinstance(columns, dict):
                continue
            parts = []
            for key in sorted(columns, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0)):
                if not isinstance(columns[key], dict):
                    continue
                part = dict(columns[key])
                part.update({
                    "QuestionID": f"{qid}#{key}", "DataExportTag": f"{payload.get('DataExportTag')}_{key}",
                    "QuestionText": f"{payload.get('QuestionText') or ''}<br>{part.get('QuestionText') or ''}",
                    "Choices": payload.get("Choices"), "ChoiceOrder": payload.get("ChoiceOrder"),
                })
                self.questions[part["QuestionID"]] = part
                parts.append(part["QuestionID"])
            if parts:
                self.split[qid] = parts
        self.types = {qid: classify(p) for qid, p in self.questions.items()}
        self.embedded = []
        self.changes = {}  # QID -> warnings about a question that was written
        self.lost = {}  # QID -> why the question was not written
        self.report = None
        self.tags = {}
        self.options = {}

    def warn(self, text):
        self.warnings.append(text)
        m = re.match(r"QID\d+", text)
        if m:
            self.changes.setdefault(m.group(0), []).append(text)

    def lose(self, qid, text, reason):
        """A question (or one column of a side-by-side question) that is not written."""
        if "#" in qid:
            self.warn(text)
        else:
            self.warnings.append(text)
            self.lost[qid] = reason

    def entries(self, block):
        """A block's elements, with each side-by-side question replaced by its columns."""
        out = []
        for element in block.get("BlockElements") or []:
            if not isinstance(element, dict):
                continue
            parts = self.split.get(str(element.get("QuestionID"))) if element.get("Type") == "Question" else None
            if parts:
                out += [{"Type": "Question", "QuestionID": part} for part in parts]
            else:
                out.append(element)
        return out

    @staticmethod
    def simple_embedded(node):
        """The fields of an embedded-data element as [(field, value or None)], or None if Markdown cannot hold them."""
        if not isinstance(node, dict) or node.get("Type") != "EmbeddedData" or not node.get("EmbeddedData"):
            return None
        out = []
        for field in node["EmbeddedData"]:
            if not isinstance(field, dict) or not re.fullmatch(FIELD_RE, str(field.get("Field"))) or field.get("VariableType") not in (None, "String"):
                return None
            value = field.get("Value")
            if field.get("Type") == "Recipient" and value in (None, ""):
                out.append((field["Field"], None))
            elif field.get("Type") == "Custom" and isinstance(value, str) and value == value.strip() and "\n" not in value:
                out.append((field["Field"], value))
            else:
                return None
        return out if len({f for f, _ in out}) == len(out) else None

    def text(self, source, where, what="text"):
        out, dropped = html_to_md(source, self.keep_html)
        if dropped:
            self.warn(f"{where}: HTML formatting removed from the {what} ({', '.join('<' + tag + '>' for tag in dropped)}); use --keep-html to keep it")
        return out

    def one_line(self, source, where, what):
        out = self.text(source, where, what)
        if "\n" in out:
            self.warn(f"{where}: line breaks inside the {what} became spaces")
            out = re.sub(r"\s*\n\s*", " ", out)
        return out

    # ---- planning: which blocks and questions reach the Markdown, in which order

    def plan(self):
        by_id = {b["ID"]: b for b in self.blocks}
        sequence = []  # ("block", block) | ("note", text)
        used = []

        first = (self.flow.get("Flow") or [None])[0] if self.flow else None
        self.embedded = self.simple_embedded(first) or []

        def walk(node, depth):
            kind = node.get("Type")
            if node is first and self.embedded:
                return
            if kind in ("Block", "Standard"):
                block = by_id.get(node.get("ID"))
                if block is None:
                    self.warn(f"flow: names block {node.get('ID')}, which the file does not define")
                elif block.get("Type") == "Trash":
                    pass
                elif block["ID"] in used:
                    self.warn(f"flow: block {block.get('Description')!r} appears more than once; kept once")
                    sequence.append(("note", f"flow: block {block.get('Description')!r} is shown again here"))
                else:
                    used.append(block["ID"])
                    sequence.append(("block", block))
                return
            if kind == "Branch":
                rule = logic_text(node.get("BranchLogic"))
                self.warn(f"flow: branch not represented (condition: {rule}); the blocks inside it are listed as if everyone saw them")
                sequence.append(("note", f"unsupported flow: branch starts, only when: {rule}"))
            elif kind in ("BlockRandomizer", "Randomizer"):
                self.warn(f"flow: randomizer not represented (shows {node.get('SubSet')} of {len(node.get('Flow') or [])} elements)")
                sequence.append(("note", f"unsupported flow: randomizer starts, shows {node.get('SubSet')} of {len(node.get('Flow') or [])} elements"))
            elif kind == "Group":
                sequence.append(("note", f"flow: group {node.get('Description')!r} starts"))
                self.warn(f"flow: group {node.get('Description')!r} not represented; its blocks are kept in order")
            elif kind == "EmbeddedData":
                fields = ", ".join(str(f.get("Field")) for f in node.get("EmbeddedData") or [] if isinstance(f, dict))
                self.warn(f"flow: embedded data not represented ({fields})")
                sequence.append(("note", f"unsupported flow: embedded data ({fields})"))
            elif kind == "EndSurvey":
                self.warn("flow: an 'end of survey' element is not represented" + (" (it sits inside a branch or group)" if depth else ""))
                sequence.append(("note", "unsupported flow: end of survey"))
            elif kind != "Root":
                self.warn(f"flow: element of type {kind} not represented")
                sequence.append(("note", f"unsupported flow: {kind}"))
            for child in node.get("Flow") or []:
                if isinstance(child, dict):
                    walk(child, depth + (kind != "Root"))
            if kind in ("Branch", "BlockRandomizer", "Randomizer", "Group"):
                sequence.append(("note", f"flow: {kind} ends"))

        if self.flow is None:
            self.warn("the file has no 'FL' (Survey Flow) element; blocks are listed in file order")
            for block in self.blocks:
                if block.get("Type") != "Trash":
                    used.append(block["ID"])
                    sequence.append(("block", block))
        else:
            walk(self.flow, 0)
        for block in self.blocks:
            ids = [str(e.get("QuestionID")) for e in block.get("BlockElements") or [] if isinstance(e, dict) and e.get("Type") == "Question"]
            count = len(ids)
            if block.get("Type") == "Trash" or block["ID"] not in used:
                for qid in ids:
                    self.lost.setdefault(qid, "it is in the Trash block" if block.get("Type") == "Trash" else "its block is not in the survey flow")
            if block.get("Type") == "Trash":
                if count:
                    self.warn(f"trash: {count} question(s) in the Trash block were left out")
            elif block["ID"] not in used:
                self.warn(f"block {block.get('Description')!r} ({count} question(s)) is not in the survey flow and was left out")
        return sequence

    def assign_tags(self, sequence):
        taken = set()
        for kind, block in sequence:
            if kind != "block":
                continue
            for entry in self.entries(block):
                qid = str(entry.get("QuestionID")) if entry.get("Type") == "Question" else None
                payload = self.questions.get(qid)
                if payload is None or self.types[qid][0] is None or qid in self.tags:
                    continue
                tag = payload.get("DataExportTag")
                if not isinstance(tag, str) or not re.fullmatch(TAG_RE, tag) or tag in taken:
                    new = "q" + re.sub(r"\D+", "_", qid).strip("_")
                    while new in taken:
                        new += "_"
                    self.warn(f"{qid}: export tag {tag!r} is empty, repeated or not a plain name; written as {new}")
                    tag = new
                taken.add(tag)
                self.tags[qid] = tag

    def choice_label(self, qid, key):
        """The Markdown text of one choice, if a rule can name it without ambiguity."""
        if qid not in self.tags or self.types[qid][0] not in LOGIC_SOURCES:
            return None
        labels = self.options.get(qid)
        if labels is None:
            shown, _ = ordered(self.questions[qid].get("Choices"), self.questions[qid].get("ChoiceOrder"))
            labels = {k: re.sub(r"\s*\n\s*", " ", html_to_md(c.get("Display") if isinstance(c, dict) else "", self.keep_html)[0]) for k, c in shown}
            self.options[qid] = labels
        label = labels.get(str(key))
        if not label or list(labels.values()).count(label) != 1:
            return None
        return label

    # ---- rules

    def show_rule(self, qid, logic):
        """DisplayLogic -> '> show if:' line, or None when the shape is outside the supported subset."""
        if not isinstance(logic, dict) or logic.get("inPage") or [k for k in logic if k not in ("0", "Type", "inPage")]:
            return None
        group = logic.get("0")
        if not isinstance(group, dict) or group.get("Type") != "If":
            return None
        keys = sorted((k for k in group if k != "Type"), key=lambda k: int(k) if k.isdigit() else -1)
        parts, joins = [], set()
        for index, key in enumerate(keys):
            expr = group[key]
            if not key.isdigit() or not isinstance(expr, dict) or expr.get("LogicType") != "Question":
                return None
            if expr.get("Operator") not in ("Selected", "NotSelected"):
                return None
            m = re.fullmatch(r"q://(QID\d+)/SelectableChoice/(\w+)", str(expr.get("LeftOperand")))
            if not m or m.group(1) == qid:
                return None
            label = self.choice_label(m.group(1), m.group(2))
            if label is None:
                return None
            if index:
                if expr.get("Conjuction") not in ("And", "Or"):
                    return None
                joins.add(expr["Conjuction"].lower())
            parts.append(f"{self.tags[m.group(1)]} is {'not ' if expr['Operator'] == 'NotSelected' else ''}{quote(label)}")
        if not parts or len(joins) > 1:
            return None
        return "> show if: " + f" {joins.pop() if joins else 'and'} ".join(parts)

    def skip_rule(self, qid, skip, later):
        if not isinstance(skip, dict) or skip.get("Condition") not in ("Selected", "NotSelected"):
            return None
        m = re.fullmatch(r"q://(QID\d+)/SelectableChoice/(\w+)", str(skip.get("Locator") or skip.get("ChoiceLocator")))
        if not m or m.group(1) != qid:
            return None
        label = self.choice_label(qid, m.group(2))
        dest = skip.get("SkipToDestination")
        if dest == "ENDOFBLOCK":
            target = "end of block"
        elif dest == "ENDOFSURVEY":
            target = "end of survey"
        elif dest in later:
            target = self.tags[dest]
        else:
            return None
        if label is None:
            return None
        return f"> skip: if {'not ' if skip['Condition'] == 'NotSelected' else ''}{quote(label)} -> {target}"

    # ---- one question

    def codes(self, payload, shown, where, what):
        """Export values of the shown choices (or columns) as {key: code}, or None when they are 1..n in order."""
        recode = payload.get("RecodeValues") if isinstance(payload.get("RecodeValues"), dict) else {}
        values = [str(recode.get(key, key)) for key, _ in shown]
        if values == [str(i) for i in range(1, len(shown) + 1)]:
            return None
        if all(re.fullmatch(r"-?\d+", value) for value in values) and len(set(values)) == len(values):
            return dict(zip((key for key, _ in shown), values))
        self.warn(f"{where}: {what} codes repeat or are not whole numbers, so they are not represented; a rebuilt survey codes them 1, 2, 3 in the order shown")
        return None

    def option_lines(self, entries, where, what, attrs, codes=None, names=None):
        lines = []
        extra = set()
        for key, choice in entries:
            choice = choice if isinstance(choice, dict) else {}
            label = self.one_line(choice.get("Display"), where, what)
            if not label:
                label = "(blank)"
                self.warn(f"{where}: {what} {key} has no text; written as (blank)")
            line = "- " + label
            if str(choice.get("TextEntry")).lower() in ("true", "on", "1"):
                if "text" in attrs:
                    line += " {text}"
                else:
                    extra.add("TextEntry")
            if choice.get("ExclusiveAnswer") in (True, "true"):
                if "exclusive" in attrs:
                    line += " {exclusive}"
                else:
                    extra.add("ExclusiveAnswer")
            extra.update(k for k, v in choice.items() if k not in ("Display", "TextEntry", "ExclusiveAnswer") and v not in (None, "", [], {}, False))
            if codes:
                line += f" {{code:{codes[key]}}}"
            if names:
                line += f" {{var:{names[key]}}}"
            lines.append(line)
        if extra:
            self.warn(f"{where}: {what} settings not represented: {', '.join(sorted(extra))}")
        return lines

    def question(self, qid, entry, later):
        payload = self.questions[qid]
        kind, layout = self.types[qid]
        tag = self.tags[qid]
        where = f"{qid} ({tag})"
        settings = (payload.get("Validation") or {}).get("Settings") if isinstance(payload.get("Validation"), dict) else None
        settings = settings if isinstance(settings, dict) else {}
        force = {"ON": " required", "RequestResponse": " request"}.get(settings.get("ForceResponse"), "")
        if kind == "info":
            force = ""
        if kind == "sum" and force:
            self.warn(f"{where}: forced response on a constant sum is not represented")
            force = ""
        lines = [f"### {tag} [{kind}]{force}"]
        text = self.text(payload.get("QuestionText"), where, "question text")
        if not text:
            text = "(no text)"
            self.warn(f"{where}: the question has no text (an image or script only?); written as (no text)")
        for line in text.split("\n"):
            lines.append("\\" + line if re.match(r"(#|- |>|\\|-{3,}$|Rows:$|Columns:$)", line) else line)
        if layout:
            self.warn(f"{where}: {layout}")
        total = str(settings.get("ChoiceTotal") or "")
        has_total = kind == "sum" and settings.get("Type") == "ChoicesTotal" and re.fullmatch(r"\d+", total) and int(total) > 0
        if settings.get("Type") not in (None, "", "None") and not has_total:
            self.warn(f"{where}: validation rule not represented (Type {settings.get('Type')})")
        config = payload.get("Configuration") if isinstance(payload.get("Configuration"), dict) else {}
        rules = []
        coded = False
        if kind in OPTION_TYPES:
            shown, hidden = ordered(payload.get("Choices"), payload.get("ChoiceOrder"))
            if hidden:
                self.warn(f"{where}: {hidden} choice(s) missing from ChoiceOrder were left out")
            codes = self.codes(payload, shown, where, "choice") if kind in CODE_TYPES and shown else None
            coded = kind in CODE_TYPES
            options = self.option_lines(shown, where, "choice", ("text", "exclusive") if kind == "multi" else ("text",) if kind == "single" else (), codes)
            if not options:
                options = ["- (blank)"]
                self.warn(f"{where}: no choices in the export; written with one (blank) option")
            lines += [""] + options
        if kind in MATRIX_TYPES:
            rows, hidden_rows = ordered(payload.get("Choices"), payload.get("ChoiceOrder"))
            columns, hidden_columns = ordered(payload.get("Answers"), payload.get("AnswerOrder"))
            if hidden_rows or hidden_columns:
                self.warn(f"{where}: {hidden_rows} row(s) and {hidden_columns} column(s) missing from the order lists were left out")
            codes = None
            recode = payload.get("RecodeValues")
            if kind != "matrix-text" and columns:
                if not isinstance(recode, dict) or {str(k) for k in recode} <= {key for key, _ in columns}:
                    codes = self.codes(payload if isinstance(recode, dict) else {}, columns, where, "column")
                    coded = True
            names = payload.get("ChoiceDataExportTags")
            if isinstance(names, dict) and names:
                wanted = [str(names.get(key) or "") for key, _ in rows]
                if all(re.fullmatch(TAG_RE, name) for name in wanted) and len(set(wanted)) == len(wanted):
                    names = dict(zip((key for key, _ in rows), wanted))
                else:
                    self.warn(f"{where}: row export tags are incomplete, repeated or not plain names, so they are not represented")
                    names = None
            else:
                names = None
                if [key for key, _ in rows] != [str(i) for i in range(1, len(rows) + 1)] and sorted(key for key, _ in rows) != [str(i) for i in range(1, len(rows) + 1)]:
                    self.warn(f"{where}: row ids are not 1..n in the export; a rebuilt survey renumbers them, which changes exported column names")
            lines += ["", "Rows:"] + (self.option_lines(rows, where, "row", (), None, names) or ["- (blank)"])
            lines += ["", "Columns:"] + (self.option_lines(columns, where, "column", (), codes) or ["- (blank)"])
        if kind == "nps":
            shown, _ = ordered(payload.get("Choices"), payload.get("ChoiceOrder"))
            if [plain(c.get("Display")) if isinstance(c, dict) else "" for _, c in shown] != NPS_POINTS:
                self.warn(f"{where}: the NPS scale is not the usual 0 to 10; Markdown always writes 0 to 10")
            labels = payload.get("ColumnLabels") if isinstance(payload.get("ColumnLabels"), list) else []
            texts = [self.one_line(l.get("Display"), where, "label").replace("|", "/") for l in labels if isinstance(l, dict)]
            if len(texts) == 2 and texts != NPS_LABELS:
                rules.append("> labels: " + " | ".join(texts))
            elif texts and len(texts) != 2:
                self.warn(f"{where}: {len(texts)} NPS labels not represented (Markdown takes two)")
        if kind == "slider":
            low, high = config.get("CSSliderMin"), config.get("CSSliderMax")
            if isinstance(low, int) and isinstance(high, int) and not isinstance(low, bool) and low < high:
                if (low, high) != SLIDER_RANGE:
                    rules.append(f"> range: {low} to {high}")
            else:
                self.warn(f"{where}: slider range {low!r} to {high!r} is not two whole numbers; the default 0 to 100 applies")
            labels, _ = ordered(payload.get("Labels"), None)
            texts = [self.one_line(l.get("Display"), where, "label").replace("|", "/") for _, l in labels if isinstance(l, dict)]
            texts = [t for t in texts if t]
            if texts:
                rules.append("> labels: " + " | ".join(texts))
            odd = [k for k, v in (("NotApplicable", False), ("SnapToGrid", False), ("NumDecimals", "0")) if config.get(k, v) != v]
            if odd:
                self.warn(f"{where}: slider settings not represented: {', '.join(odd)}")
        if has_total:
            rules.append(f"> total: {int(total)}")
        randomization = payload.get("Randomization")
        mode = randomization.get("Type") if isinstance(randomization, dict) else randomization
        if mode == "All" and kind in RANDOM_TYPES and isinstance(randomization, dict) and not randomization.get("Advanced") and not randomization.get("TotalRandSubset"):
            rules.append("> randomize: " + ("rows" if kind in MATRIX_TYPES else "options"))
        elif mode not in (None, "", "None", False):
            self.warn(f"{where}: choice randomization not represented ({mode})")
        for skip in entry.get("SkipLogic") or []:
            rule = self.skip_rule(qid, skip, later)
            if rule:
                rules.append(rule)
            else:
                detail = plain(skip.get("Description")) if isinstance(skip, dict) else ""
                rules.append(comment(f"unsupported skip logic on {tag}: {detail or 'see the export'}"))
                self.warn(f"{where}: skip logic not represented: {detail or 'see the export'}")
        if payload.get("DisplayLogic"):
            rule = self.show_rule(qid, payload["DisplayLogic"])
            if rule:
                rules.append(rule)
            else:
                detail = logic_text(payload["DisplayLogic"])
                rules.append(comment(f"unsupported display logic on {tag}: {detail}"))
                self.warn(f"{where}: display logic not represented: {detail}")
        self.other_settings(payload, where, config, coded, kind)
        if rules:
            lines += [""] + rules
        return lines

    def other_settings(self, payload, where, config, coded, kind):
        recode = payload.get("RecodeValues")
        if coded:
            pass  # carried as {code:n}, or already reported by codes()
        elif isinstance(recode, dict) and any(str(k) != str(v) for k, v in recode.items()):
            self.warn(f"{where}: recode values not represented; a rebuilt survey codes choices 1, 2, 3 in the order shown")
        elif kind not in MATRIX_TYPES and isinstance(payload.get("Choices"), dict) and list(payload["Choices"]) != [str(i) for i in range(1, len(payload["Choices"]) + 1)]:
            self.warn(f"{where}: choice codes are not 1..n in the export; a rebuilt survey renumbers them, which changes the exported values")
        if isinstance(payload.get("Language"), dict) and payload["Language"]:
            self.warn(f"{where}: translations not represented ({', '.join(sorted(payload['Language']))})")
        if config.get("QuestionDescriptionOption") == "SpecifyLabel":
            self.warn(f"{where}: custom question label not represented ({payload.get('QuestionDescription')!r})")
        visibility = payload.get("DataVisibility") if isinstance(payload.get("DataVisibility"), dict) else {}
        if visibility.get("Private") or visibility.get("Hidden"):
            self.warn(f"{where}: data visibility setting (private or hidden) not represented")
        if payload.get("DefaultChoices"):
            self.warn(f"{where}: default (pre-selected) answers not represented")
        if payload.get("GradingData"):
            self.warn(f"{where}: scoring not represented")
        text = json.dumps([payload.get("QuestionText"), payload.get("Choices"), payload.get("Answers")])
        if "${" in text:
            self.warn(f"{where}: piped text (${{...}}) is kept as written; question IDs are renumbered on to-qsf and embedded data is not carried, so check it after import")
        extra = sorted(k for k, v in payload.items() if k not in KNOWN_KEYS and v not in (None, "", [], {}, False))
        if extra:
            self.warn(f"{where}: settings not represented: {', '.join(extra)}")

    # ---- whole file

    def markdown(self):
        entry = self.data["SurveyEntry"]
        title = re.sub(r"\s+", " ", str(entry.get("SurveyName") or "")).strip() or "Untitled survey"
        sequence = self.plan()
        self.assign_tags(sequence)
        if str(entry.get("SurveyLanguage") or "EN") != "EN":
            self.warn(f"survey language {entry.get('SurveyLanguage')} not represented; to-qsf writes EN")
        out = [f"# {title}"]
        if self.embedded:
            out += [""] + [f"> embedded: {field}" + ("" if value is None else f" = {value}".rstrip()) for field, value in self.embedded]
        counts = {"blocks": 0, "questions": 0, "unsupported_questions": 0, "page_breaks": 0}
        done = set()
        for kind, item in sequence:
            if kind == "note":
                out += ["", comment(item)]
                continue
            block = item
            counts["blocks"] += 1
            name = re.sub(r"\s+", " ", str(block.get("Description") or block["ID"])).strip()
            out += ["", f"## {name}"]
            options = block.get("Options") if isinstance(block.get("Options"), dict) else {}
            if options.get("RandomizeQuestions") not in (None, "", "false", False):
                self.warn(f"block {name!r}: question randomization not represented ({options.get('RandomizeQuestions')})")
            if options.get("Looping") not in (None, "", "None", False):
                self.warn(f"block {name!r}: loop and merge not represented")
            entries = self.entries(block)
            for element in block.get("BlockElements") or []:
                parts = self.split.get(str(element.get("QuestionID"))) if isinstance(element, dict) else None
                if parts and str(element.get("QuestionID")) not in done:
                    whole = self.questions[str(element["QuestionID"])]
                    done.add(str(element["QuestionID"]))
                    self.warn(f"{element['QuestionID']} ({whole.get('DataExportTag')}): side-by-side question written as {len(parts)} separate question(s), one per column")
                    if element.get("SkipLogic") or whole.get("DisplayLogic"):
                        self.warn(f"{element['QuestionID']} ({whole.get('DataExportTag')}): skip or display logic on the side-by-side question is not represented")
            for index, element in enumerate(entries):
                if element.get("Type") == "Page Break":
                    out += ["", "---"]
                    counts["page_breaks"] += 1
                    continue
                qid = str(element.get("QuestionID"))
                if element.get("Type") != "Question":
                    self.warn(f"block {name!r}: element of type {element.get('Type')} not represented")
                    continue
                payload = self.questions.get(qid)
                if payload is None:
                    self.warn(f"block {name!r}: names question {qid}, which the file does not define")
                    continue
                if qid not in self.tags:
                    counts["unsupported_questions"] += 1
                    triple = "/".join(str(payload.get(k)) for k in ("QuestionType", "Selector", "SubSelector") if payload.get(k))
                    reason = f"type {triple} is outside the supported set"
                    summary = shorten(plain(payload.get("QuestionText")), 80)
                    out += ["", comment(f"unsupported question {qid} ({payload.get('DataExportTag')}): {reason}: {summary}")]
                    self.lose(qid, f"{qid} ({payload.get('DataExportTag')}): question left out, {reason}: {summary!r}", reason)
                    if element.get("SkipLogic") or payload.get("DisplayLogic"):
                        self.warnings.append(f"{qid} ({payload.get('DataExportTag')}): its skip or display logic was left out with it")
                        if qid in self.lost:
                            self.lost[qid] += "; its skip or display logic was left out with it"
                    continue
                later = [str(e.get("QuestionID")) for e in entries[index + 1 :] if e.get("Type") == "Question" and str(e.get("QuestionID")) in self.tags]
                if qid in done:
                    self.warn(f"{qid}: placed in the survey more than once; kept once")
                    continue
                done.add(qid)
                out += [""] + self.question(qid, element, later)
                counts["questions"] += 1
        placed = {str(e.get("QuestionID")) for b in self.blocks for e in b.get("BlockElements") or [] if isinstance(e, dict)}
        orphans = [qid for qid in self.questions if qid not in placed and "#" not in qid]
        for qid in orphans:
            self.lost.setdefault(qid, "it sits in no block")
        if orphans:
            self.warn(f"{len(orphans)} question(s) are defined but sit in no block and were left out: {', '.join(orphans[:10])}")
        extra = sorted({str(e.get("Element")) for e in self.elements} - {"BL", "FL", "SQ", "SO", "SCO", "PROJ", "STAT", "QC", "RS", "PL"})
        if extra:
            self.warn(f"survey-level elements not represented: {', '.join(extra)} (notes, quotas and similar)")
        self.warn("survey options (back button, progress bar, look and feel, end-of-survey message) are not represented; to-qsf writes defaults")
        written = {qid.split("#")[0] for qid in done if qid.split("#")[0] not in self.lost}
        real = [qid for qid in self.questions if "#" not in qid]
        label = lambda qid: self.tags.get(qid) or self.questions[qid].get("DataExportTag")  # noqa: E731
        self.report = {
            "questions_in_file": len(real),
            "converted": [qid for qid in real if qid in written and qid not in self.changes],
            "converted_with_changes": [
                {"id": qid, "tag": label(qid), "changes": [re.sub(r"^QID\d+(#\d+)?( \([^)]*\))?: ", "", c) for c in self.changes[qid]]}
                for qid in real if qid in written and qid in self.changes
            ],
            "not_converted": [
                {"id": qid, "tag": label(qid), "reason": self.lost.get(qid) or "it is not placed in a block the survey shows"}
                for qid in real if qid not in written
            ],
            "survey_level": [w for w in self.warnings if not re.match(r"QID\d+", w)],
            "imported_into_qualtrics": False,
        }
        return "\n".join(out) + "\n", counts


# --------------------------------------------------------------------------- validate


def validate_qsf(data):
    """Structural self-check. Returns (errors, warnings). It cannot tell whether Qualtrics will accept the file."""
    errors, warnings = [], []
    entry = data["SurveyEntry"]
    for key in ("SurveyID", "SurveyName"):
        if not entry.get(key):
            errors.append(f"SurveyEntry.{key} is missing or empty")
    missing = [key for key in ENTRY_KEYS if key not in entry]
    if missing:
        warnings.append(f"SurveyEntry lacks keys every sampled export has: {', '.join(missing)}")
    elements = data["SurveyElements"]
    by_code = {}
    for index, element in enumerate(elements):
        if not isinstance(element, dict) or "Element" not in element or "Payload" not in element or "PrimaryAttribute" not in element:
            errors.append(f"SurveyElements[{index}] lacks Element, PrimaryAttribute or Payload")
            continue
        by_code.setdefault(element["Element"], []).append(element)
        if element.get("SurveyID") != entry.get("SurveyID"):
            warnings.append(f"SurveyElements[{index}] ({element['Element']}) has a SurveyID that differs from SurveyEntry.SurveyID")
    for code in ("BL", "FL"):
        if len(by_code.get(code, [])) != 1:
            errors.append(f"expected exactly one {code} element, found {len(by_code.get(code, []))}")
    for code in USUAL_ELEMENTS:
        if code not in by_code:
            warnings.append(f"no {code} element; every sampled export has one")
    questions = {}
    for element in by_code.get("SQ", []):
        payload = element["Payload"]
        if not isinstance(payload, dict):
            errors.append(f"SQ {element.get('PrimaryAttribute')}: Payload is not an object")
            continue
        qid = payload.get("QuestionID")
        if qid != element.get("PrimaryAttribute"):
            errors.append(f"SQ {element.get('PrimaryAttribute')}: PrimaryAttribute differs from Payload.QuestionID ({qid!r})")
        if qid in questions:
            errors.append(f"question ID {qid} is defined twice")
        questions[qid] = payload
        for key in ("QuestionType", "Selector", "QuestionText", "DataExportTag", "QuestionID"):
            if key not in payload:
                errors.append(f"SQ {qid}: Payload.{key} is missing")
        for mapping, order in (("Choices", "ChoiceOrder"), ("Answers", "AnswerOrder")):
            entries = payload.get(mapping)
            keys = {str(i) for i in range(len(entries))} if isinstance(entries, list) else {str(k) for k in entries} if isinstance(entries, dict) else set()
            stray = [str(k) for k in payload.get(order) or [] if str(k) not in keys] if isinstance(payload.get(order), list) else []
            if stray:
                warnings.append(f"SQ {qid}: {order} names {mapping} keys that do not exist: {', '.join(stray)}")
        logic = payload.get("DisplayLogic")
        for group in logic.values() if isinstance(logic, dict) else []:
            for key, expr in group.items() if isinstance(group, dict) else []:
                if not isinstance(expr, dict):
                    continue
                if "Conjunction" in expr:
                    errors.append(f"SQ {qid}: display logic uses the key 'Conjunction'; Qualtrics spells it 'Conjuction'")
                if expr.get("LogicType") == "Question" and expr.get("QuestionID") not in questions and expr.get("QuestionID") not in {
                    e["Payload"].get("QuestionID") for e in by_code.get("SQ", []) if isinstance(e["Payload"], dict)
                }:
                    warnings.append(f"SQ {qid}: display logic names question {expr.get('QuestionID')}, which the file does not define")
    def check_locator(owner, locator, what):
        m = re.fullmatch(r"q://(QID\d+)/SelectableChoice/(\w+)", str(locator))
        if not m:
            return
        if m.group(1) not in questions:
            if what == "skip logic":
                warnings.append(f"{what} on {owner} names question {m.group(1)}, which the file does not define")
            return
        entries = questions[m.group(1)].get("Choices")
        if isinstance(entries, dict) and m.group(2) not in {str(k) for k in entries}:
            warnings.append(f"{what} on {owner} names choice {m.group(2)} of {m.group(1)}, which does not exist")

    for qid, payload in questions.items():
        logic = payload.get("DisplayLogic")
        for group in logic.values() if isinstance(logic, dict) else []:
            for key, expr in group.items() if isinstance(group, dict) else []:
                if not isinstance(expr, dict):
                    continue
                if expr.get("LogicType") == "Question":
                    check_locator(qid, expr.get("LeftOperand"), "display logic")
                if str(key).isdigit() and str(key) != "0" and "Conjuction" not in expr and "Conjunction" not in expr:
                    warnings.append(f"SQ {qid}: display logic condition {key} has no 'Conjuction' (And/Or) key")
    tags = [p.get("DataExportTag") for p in questions.values()]
    repeated = sorted({t for t in tags if t and tags.count(t) > 1})
    if repeated:
        warnings.append(f"export tags used more than once: {', '.join(repeated)}")
    blocks, placed = {}, {}
    if len(by_code.get("BL", [])) == 1:
        for block in as_list(by_code["BL"][0]["Payload"]):
            if not isinstance(block, dict) or not block.get("ID") or not block.get("Type"):
                errors.append("a block lacks ID or Type")
                continue
            if block["ID"] in blocks:
                errors.append(f"block ID {block['ID']} is used twice")
            blocks[block["ID"]] = block
            entries = [e for e in block.get("BlockElements") or [] if isinstance(e, dict)]
            for position, element in enumerate(entries):
                if element.get("Type") != "Question":
                    continue
                qid = element.get("QuestionID")
                if qid not in questions:
                    warnings.append(f"block {block.get('Description')!r} lists question {qid}, which has no SQ element")
                elif qid in placed:
                    warnings.append(f"question {qid} is listed in two blocks ({placed[qid]!r} and {block.get('Description')!r})")
                placed[qid] = block.get("Description")
                for skip in element.get("SkipLogic") or []:
                    if not isinstance(skip, dict):
                        continue
                    check_locator(qid, skip.get("Locator") or skip.get("ChoiceLocator"), "skip logic")
                    if skip.get("QuestionID") != qid or f"q://{qid}/" not in str(skip.get("ChoiceLocator")):
                        warnings.append(f"skip logic on {qid} points at another question's choice ({skip.get('ChoiceLocator')})")
                    dest = skip.get("SkipToDestination")
                    later = [e.get("QuestionID") for e in entries[position + 1 :]]
                    if dest not in ("ENDOFBLOCK", "ENDOFSURVEY") and dest not in later:
                        warnings.append(
                            f"skip logic on {qid} goes to {dest}, which is not a later question in the same block"
                        )
        for qid in questions:
            if qid not in placed:
                warnings.append(f"question {qid} is in no block, so the survey would not show it")
    if len(by_code.get("FL", [])) == 1 and isinstance(by_code["FL"][0]["Payload"], dict):
        root = by_code["FL"][0]["Payload"]
        used, flow_ids = set(), []

        def walk(node):
            flow_ids.append(node.get("FlowID"))
            if node.get("Type") in ("Block", "Standard"):
                if node.get("ID") not in blocks:
                    warnings.append(f"flow names block {node.get('ID')}, which the BL element does not define")
                used.add(node.get("ID"))
            for child in node.get("Flow") or []:
                if isinstance(child, dict):
                    walk(child)

        walk(root)
        if root.get("Type") != "Root" or not isinstance(root.get("Flow"), list):
            errors.append("the FL payload must be {Type: 'Root', Flow: [...]}")
        for block_id, block in blocks.items():
            if block.get("Type") != "Trash" and block_id not in used:
                warnings.append(f"block {block.get('Description')!r} is not in the flow, so the survey would not show it")
        numbered = [fid for fid in flow_ids if fid]
        if len(numbered) != len(set(numbered)):
            warnings.append("flow IDs repeat")
        numbers = [int(m.group(1)) for m in (re.fullmatch(r"FL_(\d+)", str(fid)) for fid in numbered) if m]
        count = (root.get("Properties") or {}).get("Count") if isinstance(root.get("Properties"), dict) else None
        if isinstance(count, int) and numbers and count < max(numbers):
            warnings.append(f"flow Properties.Count ({count}) is below the highest flow ID ({max(numbers)})")
    elif len(by_code.get("FL", [])) == 1:
        errors.append("the FL payload is not an object")
    if "QC" in by_code:
        count = by_code["QC"][0].get("SecondaryAttribute")
        if not re.fullmatch(r"\d+", str(count)):
            errors.append(f"QC SecondaryAttribute should be a whole number written as text, found {count!r}")
        elif int(count) < len(questions):
            warnings.append(f"QC says {count} but the file defines {len(questions)} questions (in exports QC is at least the number of questions)")
    if "RS" in by_code and entry.get("SurveyActiveResponseSet") not in [e.get("PrimaryAttribute") for e in by_code["RS"]]:
        warnings.append("SurveyEntry.SurveyActiveResponseSet does not match the RS element")
    return errors, warnings


# --------------------------------------------------------------------------- model -> Advanced Format TXT


def txt_limits(survey):
    """What Qualtrics' Advanced Format TXT cannot hold for this survey: [{"tag", "what", "fatal"}]."""
    out = []

    def add(tag, what, fatal=False):
        out.append({"tag": tag, "what": what, "fatal": fatal})

    for item in survey["embedded"]:
        if item["value"] and (":" in item["value"] or "]]" in item["value"]):
            add(None, f"the value of embedded data field {item['field']!r} (it contains ':' or ']]')")
    for q in questions_of(survey):
        if q["type"] not in TXT_TAGS:
            add(q["tag"], f"question type [{q['type']}] (no TXT tag for it)", True)
        if q["force"]:
            add(q["tag"], f"'{q['force']}' (TXT has no validation tags)")
        if q["skips"]:
            add(q["tag"], "skip logic")
        if q["show"]:
            add(q["tag"], "display logic")
        if q["randomize"]:
            add(q["tag"], "randomization")
        if q["total"]:
            add(q["tag"], "the required total")
        options = q["options"] + q["rows"] + q["columns"]
        for key, what in (("text_entry", "write-in box {text}"), ("exclusive", "exclusive option {exclusive}")):
            if any(o[key] for o in options):
                add(q["tag"], what)
        if any(o["var"] for o in options):
            add(q["tag"], "row export tags {var:name}")
    return out


def build_txt(survey):
    """Model -> (Advanced Format TXT, warnings). Refuses question types that have no TXT tag."""
    limits = txt_limits(survey)
    fatal = [limit for limit in limits if limit["fatal"]]
    if fatal:
        raise ConvertError(
            "Advanced Format TXT cannot hold: " + "; ".join(f"{l['tag']}: {l['what']}" for l in fatal) + ". Use --format qsf or --format auto"
        )
    warnings = [f"{l['tag'] or 'survey'}: not carried into the TXT file: {l['what']}" for l in limits]
    out = ["[[AdvancedFormat]]"]

    def listing(options, plain_tag, advanced_tag, item_tag):
        if options and options[0]["code"] is not None:
            out.append(f"[[{advanced_tag}]]")
            for option in options:
                out.extend([f"[[{item_tag}:{option['code']}]]", md_to_html(option["text"])])
        else:
            out.append(f"[[{plain_tag}]]")
            out.extend(md_to_html(option["text"]) for option in options)

    if survey["embedded"]:
        out.append("")
        for item in survey["embedded"]:
            carried = item["value"] and ":" not in item["value"] and "]]" not in item["value"]
            out.append(f"[[ED:{item['field']}:{item['value']}]]" if carried else f"[[ED:{item['field']}]]")
    for block in survey["blocks"]:
        out += ["", f"[[Block:{block['name'].replace(']]', '')}]]"]
        for item in block["items"]:
            out.append("")
            if item["kind"] == "break":
                out.append("[[PageBreak]]")
                continue
            out += [f"[[Question:{TXT_TAGS[item['type']]}]]", f"[[ID:{item['tag']}]]", md_to_html(item["text"])]
            if item["type"] in MATRIX_TYPES:
                listing(item["rows"], "Choices", "AdvancedChoices", "Choice")
                listing(item["columns"], "Answers", "AdvancedAnswers", "Answer")
            elif item["options"]:
                listing(item["options"], "Choices", "AdvancedChoices", "Choice")
    return "\n".join(out) + "\n", warnings


# --------------------------------------------------------------------------- codebook

CODEBOOK_COLUMNS = ["variable", "question_id", "block", "type", "label", "values", "note"]
NAMING_NOTE = (
    "Variables with a suffix (tag_1, tag_1_TEXT) follow the usual Qualtrics export naming; row export tags set "
    "in the survey are used where the file has them. Check the names against a real data export before relying on them."
)


def codebook_rows(data):
    """An export -> one row per variable a data export would carry, in survey order (Trash left out)."""
    reader = Reader(data)
    rows = []

    def values(shown, recode):
        recode = recode if isinstance(recode, dict) else {}
        return "; ".join(f"{recode.get(key, key)}={plain(c.get('Display') if isinstance(c, dict) else '')}" for key, c in shown)

    for kind, block in reader.plan():
        if kind != "block":
            continue
        for element in block.get("BlockElements") or []:
            payload = reader.questions.get(str(element.get("QuestionID"))) if isinstance(element, dict) else None
            if payload is None or payload.get("QuestionType") == "DB":
                continue
            qtype, selector, sub = payload.get("QuestionType"), payload.get("Selector"), payload.get("SubSelector")
            tag = payload.get("DataExportTag") or payload.get("QuestionID")
            label = plain(payload.get("QuestionText"))
            recode = payload.get("RecodeValues") if isinstance(payload.get("RecodeValues"), dict) else {}
            shown, _ = ordered(payload.get("Choices"), payload.get("ChoiceOrder"))
            answers, _ = ordered(payload.get("Answers"), payload.get("AnswerOrder"))
            names = payload.get("ChoiceDataExportTags") if isinstance(payload.get("ChoiceDataExportTags"), dict) else {}

            def row(variable, text, value_text, note=""):
                rows.append({
                    "variable": variable, "question_id": payload.get("QuestionID"), "block": block.get("Description") or block["ID"],
                    "type": "/".join(str(part) for part in (qtype, selector, sub) if part), "label": text, "values": value_text, "note": note,
                })

            def text_boxes():
                for key, choice in shown:
                    if isinstance(choice, dict) and str(choice.get("TextEntry")).lower() in ("true", "on", "1"):
                        row(f"{tag}_{recode.get(key, key)}_TEXT", f"{label} - {plain(choice.get('Display'))} - text", "(open text)")

            if qtype == "MC" and selector in ("MAVR", "MAHR", "MACOL", "MSB"):
                for key, choice in shown:
                    row(f"{tag}_{recode.get(key, key)}", f"{label} - {plain(choice.get('Display') if isinstance(choice, dict) else '')}", "1=selected")
                text_boxes()
            elif qtype == "MC":
                row(tag, label, values(shown, recode))
                text_boxes()
            elif qtype == "TE" and selector == "FORM":
                for key, choice in shown:
                    row(f"{tag}_{key}", f"{label} - {plain(choice.get('Display') if isinstance(choice, dict) else '')}", "(open text)")
            elif qtype == "TE":
                row(tag, label, "(open text)")
            elif qtype == "Matrix" and answers:
                note = {"MultipleAnswer": "several answers per row: one column per value, named <variable>_<value>"}.get(sub, "")
                if selector == "TE":
                    note = "text boxes: one column per row and column, named <variable>_<column>"
                for key, choice in shown:
                    row(str(names.get(key) or f"{tag}_{key}"), f"{label} - {plain(choice.get('Display') if isinstance(choice, dict) else '')}", values(answers, recode), note)
            elif qtype in ("Slider", "RO", "CS"):
                kind_note = {"Slider": "(number)", "RO": f"(rank 1 to {len(shown)})", "CS": "(number)"}[qtype]
                for key, choice in shown:
                    row(f"{tag}_{key}", f"{label} - {plain(choice.get('Display') if isinstance(choice, dict) else '')}", kind_note)
            elif qtype == "SBS" and isinstance(payload.get("AdditionalQuestions"), dict):
                for key in sorted(payload["AdditionalQuestions"], key=str):
                    column = payload["AdditionalQuestions"][key]
                    if isinstance(column, dict):
                        column_answers, _ = ordered(column.get("Answers"), column.get("AnswerOrder"))
                        row(str(column.get("DataExportTag") or f"{tag}#{key}"), f"{label} - {plain(column.get('QuestionText'))}",
                            values(column_answers, column.get("RecodeValues")), f"side by side: one column per row ({len(shown)} rows)")
            else:
                row(tag, label, "", "variables of this question type are not listed")
    return rows


def codebook_text(rows, fmt):
    if fmt == "md":
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")  # noqa: E731
        lines = ["| " + " | ".join(CODEBOOK_COLUMNS) + " |", "|" + "---|" * len(CODEBOOK_COLUMNS)]
        lines += ["| " + " | ".join(clean(r[c]) for c in CODEBOOK_COLUMNS) + " |" for r in rows]
        return "\n".join(lines) + "\n"
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CODEBOOK_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


# --------------------------------------------------------------------------- command line

NOT_TESTED = "Import into a new test survey first and preview it."


def read_file(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return handle.read()
    except OSError as error:
        raise ConvertError(f"cannot read {path}: {error.strerror}") from None
    except UnicodeDecodeError:
        raise ConvertError(f"{path} is not UTF-8 text; re-save it as UTF-8") from None


def write_out(path, text, source):
    if path is None:
        sys.stdout.write(text)
        return
    if path == source:
        raise ConvertError("the output path is the input file; choose another name")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def report_lines(report):
    """The fixed three-part conversion report as text."""
    converted = report["converted"]
    lines = [
        f"conversion report: {converted if isinstance(converted, int) else len(converted)} converted, "
        f"{len(report['converted_with_changes'])} converted with changes, {len(report['not_converted'])} not converted "
        f"(of {report['questions_in_file']} question(s))"
    ]
    lines.append("converted with changes:" + ("" if report["converted_with_changes"] else " none"))
    for item in report["converted_with_changes"]:
        lines.append(f"- {item['id']} ({item['tag']}): " + "; ".join(item["changes"]) if "id" in item else f"- {item['tag']}: " + "; ".join(item["changes"]))
    lines.append("not converted:" + ("" if report["not_converted"] else " none"))
    for item in report["not_converted"]:
        lines.append(f"- {item['id']} ({item['tag']}): {item['reason']}")
    lines.append("survey level, not represented:" + ("" if report["survey_level"] else " none"))
    lines += [f"- {text}" for text in report["survey_level"]]
    return lines


def emit(args, result, output, lines):
    """Write the converted file, then print the readable report (stderr when the file goes to stdout) or JSON."""
    path = result.get("output_file")
    if output is not None and path is not None:
        write_out(path, output, args.input)
    if args.json:
        if output is not None and path is None:
            result["output"] = output
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return
    if output is not None and path is None:
        write_out(None, output, args.input)
    stream = sys.stderr if output is not None and path is None else sys.stdout
    for line in lines:
        print(line, file=stream)


def cmd_to_qualtrics(args):
    source = read_file(args.input)
    survey = parse_markdown(source)
    questions = questions_of(survey)
    limits = txt_limits(survey)
    if args.format == "auto":
        chosen = "qsf" if limits else "txt"
        seen = []
        for limit in limits:
            what = re.sub(r" \(.*", "", limit["what"])
            if what not in seen:
                seen.append(what)
        reason = (
            "Qualtrics' documented Advanced Format holds everything in this survey"
            if chosen == "txt"
            else "the survey uses what Advanced Format TXT cannot hold: " + "; ".join(seen)
        )
    else:
        chosen, reason = args.format, "requested with --format"
    path = args.output
    if path and args.format == "auto" and re.search(r"\.(qsf|txt)$", path, flags=re.I) and not path.lower().endswith("." + chosen):
        path = path[:-3] + chosen
    if chosen == "txt":
        text, warnings = build_txt(survey)
    else:
        qsf, warnings = build_qsf(survey, source)
        errors, check_warnings = validate_qsf(qsf)
        if errors or check_warnings:
            raise RuntimeError("generated file fails its own check: " + "; ".join(errors + check_warnings))
        text = json.dumps(qsf, indent=2 if args.pretty else None, separators=None if args.pretty else (",", ":")) + "\n"
    kinds = {}
    for q in questions:
        kinds[q["type"]] = kinds.get(q["type"], 0) + 1
    summary = {
        "blocks": len(survey["blocks"]), "questions": len(questions), "types": kinds,
        "page_breaks": sum(1 for b in survey["blocks"] for i in b["items"] if i["kind"] == "break"),
        "skip_rules": sum(len(q["skips"]) for q in questions), "display_rules": sum(1 for q in questions if q["show"]),
        "embedded_fields": len(survey["embedded"]),
    }
    changed = {}
    for warning in warnings:
        tag, _, rest = warning.partition(": ")
        changed.setdefault(tag, []).append(rest)
    tags = [q["tag"] for q in questions]
    report = {
        "questions_in_file": len(questions),
        "converted": [tag for tag in tags if tag not in changed],
        "converted_with_changes": [{"tag": tag, "changes": changed[tag]} for tag in tags if tag in changed],
        "not_converted": [],
        "survey_level": [w for w in warnings if w.partition(": ")[0] not in tags],
        "imported_into_qualtrics": False,
    }
    result = {
        "direction": "to-" + chosen, "format": chosen, "format_reason": reason, "input": args.input, "output_file": path,
        "summary": summary, "report": report, "warnings": warnings, "imported_into_qualtrics": False,
        "shapes_as_of": SHAPES_AS_OF,
    }
    lines = [
        f"format: {chosen.upper()} ({reason})",
        f"to-{chosen}: {summary['blocks']} block(s), {summary['questions']} question(s) "
        f"({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))}), {summary['page_breaks']} page break(s), "
        f"{summary['skip_rules']} skip rule(s), {summary['display_rules']} display rule(s), {summary['embedded_fields']} embedded field(s)",
    ]
    if path:
        lines.append(f"written: {path}")
    if chosen == "qsf":
        lines.append("structural check: passed. " + NOT_TESTED)
    else:
        lines.append(
            "Advanced Format TXT follows the tag list Qualtrics documents. " + NOT_TESTED
            + " A TXT import ADDS to the survey that is open, so start from a new empty survey."
        )
    emit(args, result, text, lines + report_lines(report))
    return 0


def cmd_to_md(args):
    data = load_qsf(read_file(args.input))
    reader = Reader(data, keep_html=args.keep_html)
    text, counts = reader.markdown()
    parse_markdown(text)  # the Markdown written must read back; a failure here is a bug, not bad input
    result = {
        "direction": "to-md", "input": args.input, "output_file": args.output, "summary": counts,
        "report": reader.report, "warnings": reader.warnings,
    }
    lines = [
        f"to-md: {counts['blocks']} block(s), {counts['questions']} question(s) written, "
        f"{counts['unsupported_questions']} left out as comments, {counts['page_breaks']} page break(s)",
    ]
    emit(args, result, text, lines + report_lines(reader.report))
    return 0


def cmd_codebook(args):
    data = load_qsf(read_file(args.input))
    rows = codebook_rows(data)
    text = codebook_text(rows, args.format)
    result = {
        "direction": "codebook", "input": args.input, "output_file": args.output, "format": args.format,
        "variables": len(rows), "naming_note": NAMING_NOTE, "rows": rows,
    }
    if args.json:
        if args.output:
            write_out(args.output, text, args.input)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    emit(args, result, text, [f"codebook: {len(rows)} variable(s); descriptive text and Trash questions are left out", NAMING_NOTE])
    return 0


def cmd_validate(args):
    data = load_qsf(read_file(args.input))
    errors, warnings = validate_qsf(data)
    result = {
        "direction": "validate", "input": args.input, "ok": not errors and not (args.strict and warnings), "errors": errors,
        "warnings": warnings,
        "questions": sum(1 for e in data["SurveyElements"] if isinstance(e, dict) and e.get("Element") == "SQ"),
        "imported_into_qualtrics": False,
    }
    lines = [f"error: {error}" for error in errors] + [f"warning: {warning}" for warning in warnings]
    lines.append(
        f"validate: {'passed' if result['ok'] else 'FAILED'} ({len(errors)} error(s), {len(warnings)} warning(s), {result['questions']} question(s)). "
        "This checks structure only; it cannot tell whether Qualtrics accepts the file."
    )
    emit(args, result, None, lines)
    return 1 if errors or (args.strict and warnings) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert survey Markdown to a Qualtrics import file (.qsf or Advanced Format TXT), read a .qsf as "
        "Markdown or as a codebook, or check a .qsf's structure.",
        epilog="Format: references/markdown-format.md. Import generated files into a test survey first.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, default, text in (
        ("to-qualtrics", "auto", "survey Markdown -> Qualtrics import file; picks TXT when the survey has nothing TXT cannot hold"),
        ("to-qsf", "qsf", "survey Markdown -> .qsf (same as to-qualtrics --format qsf)"),
    ):
        build = sub.add_parser(name, help=text)
        build.add_argument("input", help="Markdown file in the format of references/markdown-format.md")
        build.add_argument("-o", "--output", help="write the file here (default: stdout); with --format auto the extension follows the format chosen")
        build.add_argument("--format", choices=("qsf", "txt", "auto"), default=default, help=f"output format (default: {default})")
        build.add_argument("--pretty", action="store_true", help="indent the .qsf JSON (exports are one line)")
        build.add_argument("--json", action="store_true", help="print a JSON report (with the file, if no -o)")
        build.set_defaults(run=cmd_to_qualtrics)
    to_md = sub.add_parser("to-md", help=".qsf -> survey Markdown, with a report of what Markdown cannot hold")
    to_md.add_argument("input", help="a .qsf exported from Qualtrics")
    to_md.add_argument("-o", "--output", help="write the Markdown here (default: stdout)")
    to_md.add_argument("--keep-html", action="store_true", help="keep HTML tags in texts instead of removing them")
    to_md.add_argument("--json", action="store_true", help="print a JSON report (with the Markdown, if no -o)")
    to_md.set_defaults(run=cmd_to_md)
    book = sub.add_parser("codebook", help=".qsf -> codebook (variable, label, values) as CSV or a Markdown table")
    book.add_argument("input", help="a .qsf exported from Qualtrics")
    book.add_argument("-o", "--output", help="write the codebook here (default: stdout)")
    book.add_argument("--format", choices=("csv", "md"), default="csv", help="csv (default) or md")
    book.add_argument("--json", action="store_true", help="print the rows as JSON")
    book.set_defaults(run=cmd_codebook)
    check = sub.add_parser("validate", help="structural check of a .qsf (exit 1 on errors)")
    check.add_argument("input", help="a .qsf file")
    check.add_argument("--strict", action="store_true", help="also exit 1 on warnings (use for generated files)")
    check.add_argument("--json", action="store_true", help="print a JSON report")
    check.set_defaults(run=cmd_validate)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except ConvertError as error:
        print(f"qsf-convert: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0
    except Exception as error:  # a defect in this script, not in the input
        print(f"qsf-convert: internal error ({type(error).__name__}: {error}); please report it with the input file", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
