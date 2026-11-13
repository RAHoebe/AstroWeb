import numpy as np
import pytest

from astroweb import solar
from astroweb.galaxy import SUN, galactic_map
from astroweb.journey import geometry
from astroweb.sky import build_sky
from astroweb.solar_detail import options


def capture(body="SUN", **obs):
    return {"id":body,"body":body,"metadata":solar.body_metadata(body),
            "observation":{"date_obs":"2026-09-01T13:54:25.201000+00:00", **obs}}


def test_sun_uses_daylight_and_identifies_default_site():
    rec=capture(ra=0,dec=0)
    sky=build_sky(rec)
    assert sky["default_site"] and sky["location"]=={"latitude":52.15,"longitude":5.38}
    observed=next(row for row in sky["samples"] if row["time"]==sky["observed_at"])
    assert observed["altitude"]==pytest.approx(38,abs=.2)
    assert observed["azimuth"]==pytest.approx(225,abs=1)
    assert sky["samples"][-1]["time"]-sky["samples"][0]["time"]==86400
    assert geometry(None,rec)["center"]==pytest.approx([160.4,8.27],abs=.1)
    assert galactic_map(rec)["xy"]==list(SUN)


def test_moon_moves_and_private_site_takes_precedence():
    first=capture("MOON",latitude=0.,longitude=0.)
    result=build_sky(first)
    assert not result["default_site"] and result["location"] is None
    first_position=geometry(None,first)["center"]
    other=capture("MOON",latitude=0.,longitude=0.,date_obs="2026-09-02T13:54:25+00:00")
    assert np.linalg.norm(np.subtract(first_position,geometry(None,other)["center"]))>5
    assert geometry(None,capture("MOON"))["center"]!=first_position


def test_only_date_uses_local_noon_and_undated_capture_keeps_detail_routes():
    rec=capture("JUPITER")
    rec["observation"]={}
    assert geometry(None,rec)=={"kind":"missing"}
    with pytest.raises(ValueError,match="solarDateMissing"):
        build_sky(rec)
    rec["capture_date"]="2026-09-01"
    stamp,estimated=solar.observing_time(rec)
    assert estimated and stamp=="2026-09-01T12:00:00+02:00"
    assert geometry(None,rec)["day_only"]
    assert all(options(body) for body in solar.BODIES)
    assert len(options("MOON"))>=4


def test_existing_sun_gets_bilingual_facts_and_retains_personal_text():
    old={"description":{"nl":"Zon in ons zonnestelsel.","en":"My own observing notes."},
         "summary":{"nl":"Eigen opname van Zon.","en":"A capture of Sun."}}
    value=solar.displayed_metadata("SUN",old)
    assert "fotosfeer" in value["description"]["nl"]
    assert value["description"]["en"]=="My own observing notes."
    assert value["sources"][0]["url"]=="https://science.nasa.gov/sun/facts/"
    assert old["description"]["nl"]=="Zon in ons zonnestelsel."
