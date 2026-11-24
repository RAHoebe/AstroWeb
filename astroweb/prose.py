"""Choose complete sentences for sourced object descriptions and short captions."""

import re

END = re.compile(r"""[.!?](?:["”’»)]+)?(?=\s|$)""")
ABBREVIATION = re.compile(
    r"(?:\b(?:dr|prof|mr|mrs|ms|st|nr|no|bijv|ca|e\.g|i\.e)|\b[A-Z])\.$", re.I
)
CUT = re.compile(r"(?:…|\.{3}|\[\.\.\.\])\s*$")


def excerpt(value, limit, *, first=False, clipped=False):
    text = "\n\n".join(
        " ".join(p.split())
        for p in re.split(r"\n\s*\n", (value or "").strip())
        if p.strip()
    )
    partial = clipped or bool(CUT.search(text))
    if len(text) <= limit and not first and not partial:
        return text
    text = CUT.sub("", text)
    ends = []
    for match in END.finditer(text[: limit + 1]):
        end = match.end()
        if end > limit or (end < len(text) and not text[end].isspace()):
            continue
        if end < len(text) and ABBREVIATION.search(text[:end]):
            continue
        ends.append(end)
        if first:
            break
    if ends:
        return text[: ends[-1]]
    if not partial and len(text) <= limit:
        return text
    return ""


def summary_for(text, fallback):
    return excerpt(text, 300, first=True) or fallback
