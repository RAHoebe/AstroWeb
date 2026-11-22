"""Rebuild the offline factual catalogue from OpenNGC, UNGC and NASA indexes."""
import csv
import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
REVISION = "be3cd6c5498806a2fbb2f7e0452ef802dbb02be0"
VIZIER = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"
NASA = "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/"
OUT = ROOT / "astroweb/catalog/object-facts.json"


def fetch(url, **kwargs):
    response = requests.get(url, timeout=(5,30), headers={"User-Agent":"AstroWeb (https://github.com/RAHoebe/AstroWeb)"}, **kwargs)
    response.raise_for_status()
    return response.content.decode("utf-8-sig")


def number(value):
    return float(value) if value.strip() else None


def coord(value):
    a,b,c = map(float,value.lstrip("+-").split(":"))
    return round((a+b/60+c/3600)*(-1 if value.startswith("-") else 1),7)


def designation(value):
    match = re.fullmatch(r"(NGC|IC|M|UGC)\s*0*(\d+)([A-Z]?)",value.strip(),re.I)
    return f"{match[1].upper()}_{int(match[2])}{match[3].upper()}" if match else None


def wiki_facts(objects, messier, caldwell):
    """Match Wikipedia redirects to Wikidata claims before taking CC0 labels and descriptions."""
    candidates = set(messier.values()) | set(caldwell.values())
    candidates.update(key for key, row in objects.items() if row[7])
    codes = sorted(candidates.intersection(objects))
    ids = {}
    for start in range(0,len(codes),40):
        batch = codes[start:start+40]
        params = dict(action="query", format="json", formatversion=2, redirects=1, prop="pageprops",
                      ppprop="wikibase_item", titles="|".join(code.replace("_"," ") for code in batch))
        query = json.loads(fetch("https://en.wikipedia.org/w/api.php",params=params))["query"]
        redirects = {r["from"]:r["to"] for r in query.get("normalized",[])+query.get("redirects",[])}
        pages = {p["title"]:p.get("pageprops",{}).get("wikibase_item") for p in query["pages"]}
        for code in batch:
            title = code.replace("_"," ")
            visited = set()
            while title in redirects and title not in visited:
                visited.add(title)
                title = redirects[title]
            if qid := pages.get(title):
                ids.setdefault(qid,set()).add(code)
    qids = sorted(q for q, matches in ids.items() if len(matches)==1)
    result = {}
    for start in range(0,len(qids),16):
        params = dict(action="wbgetentities",format="json",ids="|".join(qids[start:start+16]),
                      props="labels|descriptions|claims|sitelinks",languages="nl|en",sitefilter="nlwiki|enwiki")
        entities = json.loads(fetch("https://www.wikidata.org/w/api.php",params=params))["entities"]
        for qid,entity in entities.items():
            claims = entity.get("claims",{})
            def values(prop):
                return [c.get("mainsnak",{}).get("datavalue",{}).get("value")
                        for c in claims.get(prop,[]) if c.get("rank")!="deprecated"]
            simbad = [v for v in values("P3083") if isinstance(v,str)]
            aliases = {designation(v) for v in simbad+values("P528") if isinstance(v,str)}
            code = next(iter(ids[qid]))
            if not simbad or code not in {messier.get(v,v) for v in aliases}:
                continue
            entry = {"qid":qid}
            for lang in ("nl","en"):
                label = entity.get("labels",{}).get(lang,{}).get("value","")
                title = entity.get("sitelinks",{}).get(lang+"wiki",{}).get("title","")
                if not label or designation(label):
                    label = title or label
                entry[lang] = [label,entity.get("descriptions",{}).get(lang,{}).get("value","")]
            result[code] = entry
    if len(result)<100:
        raise ValueError("Incomplete verified Wikidata snapshot")
    return result


def main():
    objects, messier, duplicates = {}, {}, {}
    for filename in ("NGC.csv","addendum.csv"):
        url=f"https://raw.githubusercontent.com/mattiaverga/OpenNGC/{REVISION}/database_files/{filename}"
        for row in csv.DictReader(io.StringIO(fetch(url)),delimiter=";"):
            key=designation(row["Name"])
            if not key:
                continue
            if row["Type"]=="Dup":
                parents=[designation(prefix+row[prefix]) for prefix in ("NGC","IC") if row[prefix]]
                if len(parents)==1 and parents[0]:
                    duplicates[key]=parents[0]
                continue
            if row["Type"]=="NonEx" or not row["RA"] or not row["Dec"]:
                continue
            objects[key]=[row["Type"],row["Const"],round(coord(row["RA"])*15,7),coord(row["Dec"]),
                          number(row["MajAx"]),number(row["MinAx"]),number(row["V-Mag"]),
                          [n.strip() for n in row["Common names"].split(",") if n.strip()]]
            if row["M"].isdigit():
                messier["M_"+str(int(row["M"]))]=key

    for endpoint in (VIZIER, "https://vizier.cds.unistra.fr/viz-bin/asu-tsv", "https://vizier.idia.ac.za/viz-bin/asu-tsv"):
        try:
            result=fetch(endpoint,params={"-source":"J/AJ/145/101/catalog","-out.max":"unlimited","-out":"Name,Dist,f_Dist"})
        except requests.RequestException:
            continue
        lines=[line for line in result.splitlines() if line.strip() and not line.startswith("#")]
        if len(lines)>800 and lines[0].split("\t")==["Name","Dist","f_Dist"]:
            break
    else:
        raise ValueError("Incomplete Updated Nearby Galaxy Catalog response")
    distances={}
    for row in csv.reader(lines[3:],delimiter="\t"):
        key=designation(row[0])
        if key in objects and row[1].strip() and number(row[1])>0:
            distances[key]=[number(row[1]),row[2].strip()]

    nasa={}
    for series,prefix in (("messier","M"),("caldwell","C")):
        url=NASA+f"hubble-{series}-catalog/"
        links=set(re.findall(r'href="([^"]+)"',fetch(url)))
        for link in sorted(links):
            full=urljoin(url,link)
            path=urlsplit(full)
            match=re.fullmatch(rf".*/hubble-{series}-catalog/{series}-(\d+)(?:-[\w-]+)?/",path.path)
            if match and path.hostname=="science.nasa.gov":
                nasa[f"{prefix}_{int(match[1])}"]=full
    if len(objects)<12500 or len(nasa)<165 or len(distances)<50:
        raise ValueError("Incomplete catalogue snapshot")
    from astropy.coordinates import funcs
    iau = Path(funcs.__file__).parent / "data/constellation_names.dat"
    constellations = dict(line.split(None,1) for line in iau.read_text(encoding="utf8").splitlines()
                          if line.strip() and not line.startswith("#"))
    data=dict(revision=REVISION,constellations=constellations,objects=objects,messier=messier,duplicates=duplicates,distances=distances,nasa=nasa)
    data["wikidata"] = wiki_facts(objects,messier,json.loads((OUT.parent/"caldwell-ids.json").read_text()))
    print("Verified Wikidata records:",len(data["wikidata"]))
    OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\n",encoding="utf-8")
    print(f"{len(objects)} entries, {len(duplicates)} duplicate designations, {len(distances)} galaxy distances, {len(nasa)} NASA pages")


if __name__=="__main__":
    main()
