"""Group captures by unambiguous catalogue identifiers, independently of their file IDs."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOG=Path(__file__).with_name("catalog")
IDENTIFIER = re.compile(r"[A-Z][A-Z0-9]{0,14}_[0-9]{1,8}[A-Z]?")


def notation(value):
    compact=re.sub(r"[\s_-]+","",str(value).strip().upper())
    compact=re.sub(r"^CALDWELL(?=\d)","C",compact)
    compact=re.sub(r"^MESSIER(?=\d)","M",compact)
    compact=re.sub(r"^CL(?=MELOTTE\d)","",compact)
    match=re.fullmatch(r"([A-Z]+)0*(\d+)([A-Z]?)",compact)
    if not match:
        return str(value).strip().upper()
    return f"{match[1]}_{int(match[2])}{match[3]}"


@lru_cache(maxsize=1)
def object_catalogue():
    primary = json.loads((CATALOG/"galactic-objects.json").read_text(encoding="utf8"))
    atlas = json.loads((CATALOG/"atlas-landmarks.json").read_text(encoding="utf8"))
    return primary + [{**row,"source":row.get("source",atlas["sources"][row["src"]])} for row in atlas["objects"]]


@lru_cache(maxsize=1)
def cross_ids():
    pairs={alias:{target} for alias,target in json.loads((CATALOG/"caldwell-ids.json").read_text()).items()}
    for row in object_catalogue():
        target=notation(row["id"])
        for alias in (*row.get("aliases",[]),*row.get("match_names",[])):
            name=notation(alias)
            if not re.fullmatch(r"(?:NGC|IC|M|C|MELOTTE|COLLINDER)_\d+[A-Z]?",name):
                continue
            # Eastern Veil/C33 includes multiple separately catalogued filaments.
            if name=="C_33":continue
            pairs.setdefault(name,set()).add(target)
    return {alias:next(iter(ids)) for alias,ids in pairs.items() if len(ids)==1}


def name_key(value):
    return "".join(ch for ch in unicodedata.normalize("NFKD",str(value)).casefold() if ch.isalnum())


@lru_cache(maxsize=1)
def named_ids():
    names = {}
    for row in object_catalogue():
        ident = notation(row["id"])
        if not IDENTIFIER.fullmatch(ident):
            continue
        ident = cross_ids().get(ident,ident)
        for name in (row.get("nl"),row.get("en"),*row.get("aliases",[]),*row.get("match_names",[])):
            if name and not IDENTIFIER.fullmatch(notation(name)):
                names.setdefault(name_key(name),set()).add(ident)
    return {name:next(iter(matches)) for name,matches in names.items() if len(matches)==1}


def canonical(value):
    name=notation(value)
    if IDENTIFIER.fullmatch(name):
        return cross_ids().get(name,name)
    return named_ids().get(name_key(value),name)


@lru_cache(maxsize=1)
def catalogue_labels():
    labels = {}
    for row in object_catalogue():
        labels.setdefault(canonical(row["id"]),row)
    return labels


@lru_cache(maxsize=1)
def field_positions():
    from .galaxy import expanded_catalog
    return {notation(identifier): (ra, dec) for identifier, ra, dec, _ in expanded_catalog()["field_objects"]}


def catalogue_position(name):
    identifier = canonical(name)
    entry = catalogue_labels().get(identifier)
    if entry and "ra" in entry and "dec" in entry:
        return entry["ra"], entry["dec"]
    return field_positions().get(identifier)


def group_id(record):
    return canonical(record.get("catalog_id") or record["id"])


def belongs(filename, identifier):
    # Preserve the original bytes and filenames, accepting e.g. C20_* for NGC_7000.
    for match in re.finditer("_",filename):
        if canonical(filename[:match.start()])==canonical(identifier):
            return True
    return False

