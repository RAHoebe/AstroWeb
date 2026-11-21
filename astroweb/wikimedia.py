"""Resolve an exact Wikipedia title through its linked astronomical catalogue entry."""
from datetime import datetime, timezone
import re
from urllib.parse import quote

import requests

from . import external_http
from .catalogue import canonical, notation

API = "https://www.wikidata.org/w/api.php"
CONTACT = {"User-Agent":"AstroWeb (https://github.com/RAHoebe/AstroWeb)"}
SUPPORTED = re.compile(r"(M|NGC|IC|HIP|HD|MELOTTE|COLLINDER)_[0-9]{1,8}[A-Z]?")


def values(entity, property_id):
    result = []
    for statement in entity.get("claims",{}).get(property_id,[]):
        if statement.get("rank")=="deprecated":
            continue
        value = statement.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(value,str) and value.strip():
            result.append(value)
    return result


def read_identity(entity):
    qid = entity.get("id","")
    simbad = values(entity,"P3083")
    if not re.fullmatch(r"Q[1-9][0-9]*",qid) or not simbad:
        return None
    codes = [canonical(code) for value in simbad+values(entity,"P528")
             if SUPPORTED.fullmatch(code:=notation(value))]
    for catalogue in ("M","NGC","IC","HIP","HD","MELOTTE","COLLINDER"):
        matches = {code for code in codes if code.startswith(catalogue+"_")}
        if matches:
            if len(matches)!=1:
                return None
            identifier = next(iter(matches))
            break
    else:
        return None
    sources = [{"label":"Wikidata · "+qid,"url":"https://www.wikidata.org/wiki/"+qid}]
    names = {}
    for lang in ("nl","en"):
        title = entity.get("sitelinks",{}).get(lang+"wiki",{}).get("title")
        label = entity.get("labels",{}).get(lang,{}).get("value") or title
        if isinstance(label,str) and label.isprintable() and 1<=len(label)<=100:
            names[lang] = label
        if isinstance(title,str) and title.isprintable() and 1<=len(title)<=120:
            sources.append({"label":"Wikipedia · "+title,
                            "url":f"https://{lang}.wikipedia.org/wiki/"+quote(title.replace(" ","_"),safe="")})
    return {"identifier":identifier,"name":names,"sources":sources}


def lookup(store, value):
    if not isinstance(value,str) or len(value)>72:
        return None
    title = " ".join(value.replace("_"," ").split())
    if not re.fullmatch(r"[\w .’'()\-]{2,64}",title) or not any(c.isalpha() for c in title):
        return None
    key = "wikipedia-object-v1:"+title
    current = datetime.now(timezone.utc).timestamp()
    saved = store.get("settings",key)
    if saved and saved["until"]>current:
        return saved["identity"]
    for site in ("nlwiki","enwiki"):
        try:
            reply = external_http.get(API,params={"action":"wbgetentities","sites":site,"titles":title,
                                      "redirects":"yes","props":"labels|claims|sitelinks","sitefilter":"nlwiki|enwiki",
                                      "languages":"nl|en","format":"json"},headers=CONTACT,timeout=(2,3))
            reply.raise_for_status()
            data = reply.json()
            if data.get("success")!=1:
                return None
            matches = [m for entity in data.get("entities",{}).values() if (m:=read_identity(entity))]
        except (requests.RequestException,TypeError,ValueError,AttributeError):
            return None  # An outage should not be cached as an unidentified object.
        if len(matches)==1:
            store.put("settings",key,{"until":current+30*86400,"identity":matches[0]})
            return matches[0]
        if len(matches)>1:
            return None
    store.put("settings",key,{"until":current+86400,"identity":None})
    return None


def add_metadata(store, metadata, value):
    identity = lookup(store,value)
    if not identity or canonical(metadata["target"])!=identity["identifier"]:
        return metadata
    names = dict(metadata["name"])
    if metadata.get("translation")=="pending":
        names.update(identity["name"])
    sources = list({s["url"]:s for s in metadata.get("sources",[])+identity["sources"]}.values())
    aliases = list(dict.fromkeys([*metadata.get("aliases",[]),value.strip(),*identity["name"].values()]))
    return {**metadata,"name":names,"sources":sources,"aliases":aliases}
