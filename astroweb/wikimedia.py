"""Resolve an exact Wikipedia title through its linked astronomical catalogue entry."""
from datetime import datetime, timezone
import re
from urllib.parse import quote, unquote, urlsplit

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


def description(store, target):
    """Return short NL/EN introductions only from articles for the verified ID."""
    identity = lookup(store, target)
    if not identity or identity["identifier"] != canonical(target):
        return None
    qid = urlsplit(identity["sources"][0]["url"]).path.rsplit("/", 1)[-1]
    text = {"nl":"", "en":""}
    articles = []
    for source in identity["sources"]:
        url = urlsplit(source["url"])
        if url.hostname not in ("nl.wikipedia.org", "en.wikipedia.org") or not url.path.startswith("/wiki/"):
            continue
        lang = url.hostname[:2]
        try:
            response = external_http.get(f"https://{url.hostname}/w/api.php", headers=CONTACT, timeout=(2,4),
                params={"action":"query","prop":"extracts|pageprops","ppprop":"wikibase_item","exintro":1,
                        "explaintext":1,"exchars":800,"format":"json","formatversion":2,
                        "titles":unquote(url.path.removeprefix("/wiki/"))})
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", [])
            page = next((page for page in pages if page.get("pageprops", {}).get("wikibase_item")==qid), {})
            extract = page.get("extract")
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            continue
        if isinstance(extract, str) and extract.strip():
            text[lang] = " ".join(extract.split())[:800]
            articles.append({**source, "label":source["label"]+" · CC BY-SA 4.0"})
    if not articles:
        return None
    return {"provider":"Wikipedia / Wikidata","title":identity["name"].get("en",target),"text":text,
            "credit":"Wikipedia contributors · CC BY-SA 4.0","url":articles[0]["url"],
            "sources":[*articles,identity["sources"][0]]}


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
