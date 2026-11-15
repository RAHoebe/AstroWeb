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


@pytest.mark.parametrize("body,ra,dec,diameter",[
    ("SUN",160.395204384,8.273883003,1901.093),
    ("MOON",28.938347837,16.046291066,1894.095),
    ("MARS",104.601943361,23.302013159,5.071),
    ("JUPITER",136.075371056,17.289956419,31.840),
])
def test_journey_matches_topocentric_horizons(body,ra,dec,diameter):
    # Horizons observer table: coord@399, east 5.38, north 52.15, sea level;
    # 2026-Sep-01 13:54:25.201 UTC. Q1 astrometric ICRF, Q13 angular diameter.
    # Built-in ephemerides and a mean rather than equatorial radius are approximate.
    field=geometry(None,capture(body,ra=0,dec=0))
    from astropy.coordinates import SkyCoord
    assert SkyCoord(*field["center"],unit="deg").separation(SkyCoord(ra,dec,unit="deg")).deg<.04
    assert field["diameter_deg"]*3600==pytest.approx(diameter,rel=.035)
    assert field["utc"].startswith("2026-09-01T13:54:25.201")
    if body=="SUN":assert field["constellation"]=="Leo"


def test_date_only_fits_and_manual_time_override(tmp_path):
    from astropy.io import fits
    from astroweb.observation import read_observation,observation_overrides
    hdu=fits.PrimaryHDU(np.zeros((20,20),dtype=np.uint8));hdu.header["DATE-OBS"]="2026-09-01"
    path=tmp_path/"moon.fits";hdu.writeto(path)
    obs=read_observation(path);r=capture("MOON",**obs)
    assert geometry(None,r)["day_only"] and geometry(None,r)["utc"].startswith("2026-09-01T10:00")
    r["observation"]=observation_overrides(obs,{"date_obs":"2026-09-01T19:00:00+02:00"})
    assert not geometry(None,r)["day_only"]
    assert geometry(None,r)["utc"].startswith("2026-09-01T17:00")


def test_off_centre_solar_disk_lands_on_projected_position():
    import cv2
    from astroweb import journey
    photo=np.zeros((160,200,3),np.uint8);cv2.circle(photo,(62,89),43,(220,220,220),-1)
    anchor,r=journey.disk_in_photo(photo);np.testing.assert_allclose(anchor,[62,89],atol=.5)
    assert r==pytest.approx(43,abs=.6)
    for t in [.66,.75,.9,1]:
        scene=np.zeros((journey.HEIGHT,journey.WIDTH,3),np.uint8)
        target=np.array([580.0,317.0])
        journey.solar_inset(scene,photo,anchor,r,22,target,t)
        y,x=np.nonzero(scene[:,:,0]>50)
        np.testing.assert_allclose([x.mean(),y.mean()],target,atol=1.7)
    _,r=journey.disk_in_photo(photo[:85]);assert r is None
