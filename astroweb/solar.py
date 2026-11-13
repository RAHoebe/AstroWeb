"""Supported Solar System capture identifiers and bilingual catalogue metadata."""
BODIES = {
    "SUN":("Zon","Sun","Ster","Star"), "MOON":("Maan","Moon","Natuurlijke satelliet","Natural satellite"),
    "MERCURY":("Mercurius","Mercury","Planeet","Planet"), "VENUS":("Venus","Venus","Planeet","Planet"),
    "MARS":("Mars","Mars","Planeet","Planet"), "JUPITER":("Jupiter","Jupiter","Planeet","Planet"),
    "SATURN":("Saturnus","Saturn","Planeet","Planet"), "URANUS":("Uranus","Uranus","Planeet","Planet"),
    "NEPTUNE":("Neptunus","Neptune","Planeet","Planet"),
}
ALIASES = {alias.upper():key for key,(nl,en,_,_) in BODIES.items() for alias in (key,nl,en)}


def body_metadata(key):
    nl,en,kind_nl,kind_en=BODIES[key]
    return {"target":en,"name":{"nl":nl,"en":en},"type":{"nl":kind_nl,"en":kind_en},
            "constellation":{"nl":"","en":""},"summary":{"nl":f"Eigen opname van {nl}.","en":f"A capture of {en}."},
            "description":{"nl":f"{nl} in ons zonnestelsel.","en":f"{en} in our Solar System."},
            "aliases":[en],"sources":[{"label":"NASA · "+en,"url":"https://science.nasa.gov/"+en.lower()+"/"}],
            "translation":"curated"}
