"""Group captures by unambiguous catalogue identifiers, independently of their file IDs."""
import json
import re
from functools import lru_cache
from pathlib import Path

CATALOG=Path(__file__).with_name("catalog")


def notation(value):
    compact=re.sub(r"[\s_-]+","",str(value).strip().upper())
    compact=re.sub(r"^CALDWELL(?=\d)","C",compact)
    compact=re.sub(r"^MESSIER(?=\d)","M",compact)
    match=re.fullmatch(r"([A-Z]+)0*(\d+)([A-Z]?)",compact)
    if not match:
        return str(value).strip().upper()
    return f"{match[1]}_{int(match[2])}{match[3]}"


@lru_cache(maxsize=1)
def cross_ids():
    records=json.loads((CATALOG/"galactic-objects.json").read_text(encoding="utf8"))
    records+=json.loads((CATALOG/"atlas-landmarks.json").read_text(encoding="utf8"))["objects"]
    pairs={alias:{target} for alias,target in json.loads((CATALOG/"caldwell-ids.json").read_text()).items()}
    for row in records:
        target=notation(row["id"])
        for alias in row.get("aliases",[]):
            name=notation(alias)
            if not re.fullmatch(r"(?:NGC|IC|M|C)_\d+[A-Z]?",name):
                continue
            # Eastern Veil/C33 includes multiple separately catalogued filaments.
            if name=="C_33":continue
            pairs.setdefault(name,set()).add(target)
    return {alias:next(iter(ids)) for alias,ids in pairs.items() if len(ids)==1}


def canonical(value):
    name=notation(value)
    return cross_ids().get(name,name)


def group_id(record):
    return canonical(record.get("catalog_id") or record["id"])


def belongs(filename, identifier):
    # Preserve the original bytes and filenames, accepting e.g. C20_* for NGC_7000.
    for match in re.finditer("_",filename):
        if canonical(filename[:match.start()])==canonical(identifier):
            return True
    return False

