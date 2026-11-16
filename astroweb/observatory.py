"""Shared read-only explorations for the web viewer and the Google TV client."""
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from flask import Blueprint, abort, jsonify, request, send_file, session, redirect

from . import cosmic, mosaic, planner, solar_compare, stellar_space
from .collection import capture_date, date_order, identity
from .environment import target_galaxy
from .journey import geometry
from .physical import field_scale

MODES = ("mosaic","space","cosmic","planner","solar")
VERSION = 1


def visible(store, private=False):
    return [r for r in store.all("objects") if r["published"] or private]


def availability(store, record, overlap_count=0):
    body,landscape = record.get("body"),record.get("capture_kind")
    field = geometry(store,record)
    aligned = field.get("kind") in {"gaia","wcs"} and not body and not landscape
    return dict(mosaic=aligned and overlap_count>1,space=aligned and len(record["assets"])>=4,
                cosmic=not body and not landscape and bool(record["metadata"].get("redshift") or field_scale(store,record)["distance_ly"] or target_galaxy(record)),
                planner=not body and not landscape and field.get("kind")!="missing",
                solar=body=="SUN")


def index(store, private=False, service=None):
    records = sorted(visible(store,private),key=date_order,reverse=True)
    groups=service.components(records) if service else [[r['id'] for r in g] for g in mosaic.groups(store,records)]
    counts={identifier:len(group) for group in groups for identifier in group}
    return dict(captures=[{**identity(r),"date":capture_date(r),"poster":f"/media/{r['id']}/poster",
                           "features":availability(store,r,counts.get(r['id'],0)),"mosaic_count":counts.get(r['id'],0)} for r in records],
                modes=list(MODES),month=datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%Y-%m"))


class Observatory:
    def __init__(self, store, executor):
        self.store,self.executor = store,executor
        self.lock = threading.RLock()
        self.pending = {}
        self.groups_cache = {}

    def components(self, records):
        fingerprint=hashlib.sha256(json.dumps([{k:r.get(k) for k in ('id','sha256','gaia','fits','body','capture_kind')} for r in records],sort_keys=True).encode()).hexdigest()
        with self.lock:components=self.groups_cache.get(fingerprint)
        if components is None:
            components=[[r['id'] for r in g] for g in mosaic.groups(self.store,records)]
            with self.lock:
                if len(self.groups_cache)>=4:self.groups_cache.clear()
                self.groups_cache[fingerprint]=components
        return components

    def features(self, record, records):
        group=next((g for g in self.components(records) if record['id'] in g),[])
        return availability(self.store,record,len(group))

    def state(self, mode, record, records, month, private=False, retry=False):
        selected = [record]
        if record is None:selected=[]
        if mode=="mosaic":
            ids=next((g for g in self.components(records) if record["id"] in g),[])
            selected=[r for r in records if r["id"] in ids]
            if not selected:
                raise ValueError("observatory_mosaic_missing")
        model_version={'solar':'solar-coordinate-v2','space':'stellar-map-v3','cosmic':'light-flight-v2','planner':'calendar-v2'}.get(mode,mode)
        values = [VERSION,model_version,month if mode=="planner" else None,private if mode=="planner" else False,
                  [{k:r.get(k) for k in ("id","sha256","gaia","fits","observation","metadata","capture_date")} for r in selected]]
        key = hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        with self.lock:
            # A retry must stay pending until the new preparation finishes,
            # rather than redisplaying its previous error or partial result.
            if key in self.pending:
                return dict(status="preparing")
            cached = self.store.get("settings","observatory-v1:"+key)
            if cached and cached.get("token"):
                folder = self.store.path("observatory/"+cached["token"])
                if (folder/"result.json").is_file() and not (retry and mode=="solar"):
                    manifest = json.loads((folder/"result.json").read_text(encoding="utf8"))
                    data = self.media_values(manifest["data"],cached["token"],manifest["files"])
                    if record:data["capture"] = {**identity(record),"date":capture_date(record),"poster":f"/media/{record['id']}/poster"}
                    if mode=='planner':
                        data['events']=[{**identity(r),'date':capture_date(r),'day':capture_date(r)[:10],
                                         'time':(r.get('observation') or {}).get('date_obs') if not (r.get('observation') or {}).get('date_only') else None,
                                         'poster':f"/media/{r['id']}/poster"+('?rotation=90' if r['width']>r['height'] else '')} for r in records if capture_date(r) and capture_date(r).startswith(month)]
                    return dict(status="ready",data=data)
            if cached and cached.get('error'):
                age=time.time()-cached['time'];recoverable=cached['error']=='gaia_depth_unavailable'
                if (not retry and (not recoverable or age<60)) or (retry and age<1):
                    return dict(status='error',error=cached['error'])
            if len(self.pending)>=4:
                return dict(status="busy")
            future = self.executor.submit(self.build,key,mode,record,selected,month,private)
            self.pending[key] = future
            future.add_done_callback(lambda f:self.finished(key))
        return dict(status="preparing")

    def finished(self, key):
        with self.lock:
            self.pending.pop(key,None)

    @staticmethod
    def media_values(value, token, files):
        if isinstance(value,dict):
            return {k:Observatory.media_values(v,token,files) for k,v in value.items()}
        if isinstance(value,list):
            return [Observatory.media_values(v,token,files) for v in value]
        if isinstance(value,str) and value in files:
            return f"/media/observatory/{token}/{value}"
        return value

    def build(self, key, mode, record, selected, month, private):
        token = uuid.uuid4().hex
        folder = self.store.path("observatory/"+token);folder.mkdir(parents=True)
        try:
            if mode=="mosaic":data=mosaic.build(self.store,selected,folder)
            elif mode=="space":data=stellar_space.build(self.store,record,folder)
            elif mode=="cosmic":data=cosmic.build(self.store,record)
            elif mode=="planner":data=planner.build(self.store,record,month,private) if record else planner.collection_calendar(month)
            else:data=solar_compare.build(self.store,record,folder)
            if record:data["capture"] = {**identity(record),"date":capture_date(record),"poster":f"/media/{record['id']}/poster"}
            files = [p.name for p in folder.iterdir() if p.suffix in {".webp",".jpg",".png"}]
            manifest = dict(data=data,files=files,ids=[r["id"] for r in selected],private_site=mode=="planner" and private)
            (folder/"result.json").write_text(json.dumps(manifest,allow_nan=False),encoding="utf8")
            self.store.put("settings","observatory-v1:"+key,dict(token=token,time=time.time()))
        except Exception as exc:
            logging.exception("Observatory %s unavailable for %s",mode,record['id'] if record else 'collection')
            error = str(exc) if str(exc).startswith(("observatory_","gaia_depth_")) else "observatory_failed"
            self.store.put("settings","observatory-v1:"+key,dict(error=error,time=time.time()))
            # Only remove files created by this failed, unique cache job.
            for path in folder.iterdir():
                if path.is_file():path.unlink(missing_ok=True)
            folder.rmdir()


def register(app, store, queue, get_object):
    routes = Blueprint("observatory",__name__)
    service = Observatory(store,queue.executor)
    app.extensions["observatory"] = service

    @routes.get("/observatory")
    def page():
        if request.args.get('embed')=='1':
            record=get_object(request.args.get('capture',''))
            if record['id']!=request.args['capture']:
                args=request.args.to_dict();args['capture']=record['id'];return redirect('/observatory?'+urlencode(args))
        if request.args.get('embed')!='1' and request.args.get('tv')!='1':
            capture=request.args.get('capture')
            mode=request.args.get('mode')
            if not capture or mode=='planner':return redirect('/calendar')
            record=get_object(capture)
            return redirect('/viewer/'+record['id']+'#'+(mode if mode in ('space','cosmic','mosaic','solar') else 'original'))
        return send_file(Path(__file__).parent/"static"/"observatory.html")

    @routes.get('/calendar')
    def calendar_page():
        return send_file(Path(__file__).parent/'static'/'observatory.html')

    @routes.get('/api/calendar')
    def calendar_data():
        month=request.args.get('month') or datetime.now(ZoneInfo('Europe/Amsterdam')).strftime('%Y-%m')
        if not re.fullmatch(r'(?:20\d\d|2100)-(?:0[1-9]|1[0-2])',month):raise ValueError('invalid_parameters')
        return jsonify(service.state('planner',None,visible(store,bool(session.get('admin'))),month,False))

    @routes.get("/api/observatory")
    def catalogue():
        return jsonify(index(store,bool(session.get("admin")),service))

    @routes.get("/api/observatory/<mode>")
    def state(mode):
        if mode not in MODES:
            abort(404)
        record = get_object(request.args.get("capture",""))
        month = request.args.get("month") or datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%Y-%m")
        if not re.fullmatch(r"(?:20\d\d|2100)-(?:0[1-9]|1[0-2])",month):
            raise ValueError("invalid_parameters")
        private = bool(session.get("admin"))
        return jsonify(service.state(mode,record,visible(store,private),month,private,retry=request.args.get("retry")=="1"))

    @routes.get("/media/observatory/<token>/<filename>")
    def media(token, filename):
        if not re.fullmatch(r"[0-9a-f]{32}",token):abort(404)
        folder = store.path("observatory/"+token)
        manifest = folder/"result.json"
        if not manifest.is_file():abort(404)
        value = json.loads(manifest.read_text(encoding="utf8"))
        if value["private_site"] and not session.get("admin"):abort(404)
        for identifier in value["ids"]:get_object(identifier)
        if filename not in value["files"]:abort(404)
        response = send_file(folder/filename,conditional=True,max_age=86400)
        if value["private_site"] or any(not store.get("objects",i)["published"] for i in value["ids"]):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @routes.get("/api/observatory/solar-point/<token>/<int:channel>")
    def solar_point(token, channel):
        if not re.fullmatch(r"[0-9a-f]{32}",token) or channel not in {18,10}:abort(404)
        folder=store.path("observatory/"+token)
        if not (folder/"result.json").is_file():abort(404)
        manifest=json.loads((folder/"result.json").read_text(encoding="utf8"))
        for identifier in manifest["ids"]:get_object(identifier)
        from astropy.io.fits import Header
        if not (folder/f"solar-{channel}.hdr").is_file():abort(404)
        header=Header.fromstring((folder/f"solar-{channel}.hdr").read_text(encoding="ascii"),sep="\n")
        import math
        def number(name,low,high):
            try:value=float(request.args[name])
            except (KeyError,TypeError,ValueError):raise ValueError("invalid_parameters") from None
            if not math.isfinite(value) or not low<=value<=high:raise ValueError("invalid_parameters")
            return value
        if request.args.get("epoch"):
            landmark=dict(epoch=request.args["epoch"],lat=number("lat",-90,90),lon=number("lon",-180,180))
            return jsonify(solar_compare.surface_point(header,landmark=landmark))
        return jsonify(solar_compare.surface_point(header,x=number("x",0,1),y=number("y",0,1)))

    app.register_blueprint(routes)
