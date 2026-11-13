import functools
import gzip
import hmac
import io
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image
from flask import redirect, Flask, abort, jsonify, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from . import __version__
from .jobs import JobQueue
from .media import MAX_FILE, import_object, normalize_id, upload_identity, fits_target, file_prefix, validate_image
from .metadata import refresh_metadata, renamed_metadata, validate_metadata
from .render import Parameters, Scene, ffmpeg_executable, gallery_preview_path, read_rgb, resize_long, save_jpg
from .catalogue import canonical,group_id,belongs
from .solar import BODIES
from .store import Store

ROOT = Path(__file__).resolve().parent


def create_app(data_dir=None, testing=False):
    store = Store(data_dir or os.environ.get("ASTROWEB_DATA", ROOT.parent / "data"))
    app = Flask(__name__, static_folder="static")
    secret = store.path("session.key")
    if not secret.exists():
        try:
            with secret.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_hex(32))
            secret.chmod(0o600)
        except FileExistsError:
            pass
    app.config.update(SECRET_KEY=secret.read_text().strip(), TESTING=testing, MAX_CONTENT_LENGTH=600 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=os.environ.get("ASTROWEB_HTTPS") == "1", PERMANENT_SESSION_LIFETIME=timedelta(hours=12), TRUSTED_HOSTS=[h.strip() for h in os.environ.get("ASTROWEB_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if h.strip()])
    if os.environ.get("ASTROWEB_ADMIN_PASSWORD") and not store.get("settings", "admin"):
        password = os.environ["ASTROWEB_ADMIN_PASSWORD"]
        if len(password) < 11:
            raise ValueError("Admin password must have at least 11 characters")
        store.put("settings", "admin", generate_password_hash(password))
    queue = JobQueue(store, resume=not testing)
    app.extensions.update(store=store, jobs=queue)
    attempts = {}
    attempts_lock = threading.Lock()

    def admin_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin"):
                return jsonify(error="authentication_required"), 401
            return view(*args, **kwargs)
        return wrapped

    def token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    def json_body():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("invalid_parameters")
        return body

    @app.before_request
    def protect_writes():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc.lower() != request.host.lower():
                return jsonify(error="invalid_origin"), 403
            supplied = request.headers.get("X-CSRF-Token", "")
            if not supplied or not hmac.compare_digest(supplied, session.get("csrf", "")):
                return jsonify(error="invalid_csrf"), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if response.is_json and response.status_code == 200 and response.calculate_content_length() >= 16_384:
            response.vary.add("Accept-Encoding")
            if request.accept_encodings["gzip"] > 0:
                response.set_data(gzip.compress(response.get_data(), compresslevel=4))
                response.headers["Content-Encoding"] = "gzip"
        return response

    @app.errorhandler(ValueError)
    def validation(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error="upload_too_large" if exc.code == 413 else f"http_{exc.code}"), exc.code

    @app.errorhandler(Exception)
    def internal_error(exc):
        app.logger.exception("Request failed")
        return jsonify(error="internal_error"), 500

    def get_object(identifier):
        if request.method in ("GET","HEAD"):
            identifier = store.current_id(identifier)
        record = store.get("objects", identifier)
        if not record or (not record["published"] and not session.get("admin")):
            abort(404)
        return record

    def present(record, private=False):
        from .observation import public_observation
        value = {k: record[k] for k in ["id", "width", "height", "metadata", "params", "render", "published", "created_at"]}
        from .collection import capture_date
        value.update(capture_date=capture_date(record),body=record.get("body"),catalog_id=group_id(record),session_name=record.get("session_name",""))
        value.update(poster=f"/media/{record['id']}/poster", video=f"/media/{record['id']}/movie" if record["video"] else None, final=f"/media/{record['id']}/final", observation=record.get("observation") if private else public_observation(record.get("observation", {})), sky_available=all(record.get("observation", {}).get(k) is not None for k in ["ra", "dec", "latitude", "longitude", "date_obs"]))
        if record.get("body"):
            from .solar import displayed_metadata, observing_time
            value["metadata"] = displayed_metadata(record["body"], record["metadata"])
            value["sky_available"] = bool(observing_time(record)[0])
        if Path(record["assets"]["final"]).suffix.lower() in {".tif", ".tiff"}:
            value["original_view"] = f"/media/{record['id']}/original-view"
        if record["video"]:
            film_id = Path(record["video"]).stem
            if record["params"].get("orientation") == "portrait" and record["width"] > record["height"]:
                value["poster"] += "?rotation=90"
                value["width"], value["height"] = record["height"], record["width"]
            value["video"] += f"?v={film_id}"
            value["preview"] = f"/media/{record['id']}/preview?v={film_id}" if gallery_preview_path(store.path(record["video"])).is_file() else value["video"]
        if private:
            value["gaia"] = record.get("gaia") or {}
            value["source_poster"] = f"/media/{record['id']}/poster"
            value["source_width"], value["source_height"] = record["width"], record["height"]
            value["versions"] = [
                {"id": v["id"], "params": Parameters.parse({"orientation": "original", **v["params"]}).__dict__, "created_at": v["created_at"],
                 "selected": v["video"] == record["video"], "render": v["render"],
                 "url": f"/api/admin/objects/{record['id']}/versions/{v['id']}/movie"}
                for v in reversed(record.get("versions", []))]
            value["assets"] = {role: Path(path).name for role, path in record["assets"].items()}
            value["has_fits"] = bool(record.get("fits"))
        return value

    @app.get("/")
    @app.get("/admin")
    def index():
        return send_file(ROOT / "static" / "index.html")

    @app.get("/viewer/<identifier>")
    def viewer(identifier):
        record = get_object(identifier)
        if record["id"] != identifier:
            return redirect(f"/viewer/{record['id']}")
        return send_file(ROOT / "static" / "index.html")

    @app.get("/api/objects/<identifier>")
    def object_detail(identifier):
        from .galaxy import galactic_map
        record = get_object(identifier)
        from .environment import target_galaxy
        from .hubble import eligible as hubble_target
        from .physical import field_scale
        from .collection import capture_groups,date_option,neighbours
        records=store.all("objects")
        catalog=group_id(record)
        groups=capture_groups([r for r in records if r["published"]])
        visible=[g[0] for g in groups.values()]
        primary=groups.get(catalog,[record])[0]
        allowed=records if session.get("admin") else [r for r in records if r["published"]]
        dates=capture_groups([r for r in allowed if group_id(r)==catalog]).get(catalog,[])
        return jsonify({**present(record), "captures":[date_option(r) for r in dates],"neighbours":neighbours(visible,primary["id"]), "physical":field_scale(store,record), "hubble_available":hubble_target(record), "galaxy":galactic_map(record), "environment_available":bool(target_galaxy(record))})

    @app.get("/api/objects/<identifier>/environment")
    def environment(identifier):
        from .environment import neighbourhood
        return jsonify(neighbourhood(store,get_object(identifier)))

    @app.get("/media/<identifier>/allwise")
    def allwise(identifier):
        from .comparison import comparison_image
        record=get_object(identifier)
        try:
            path,scale=comparison_image(store,record)
        except requests.RequestException:
            return jsonify(error="comparison_unavailable"),503
        response=send_file(path,mimetype="image/jpeg",conditional=True,max_age=0)
        response.headers["X-Arcsec-Per-Pixel"]=f"{scale:.3f}"
        return response

    @app.post("/api/admin/objects/<identifier>/autozoom")
    @admin_required
    def autozoom(identifier):
        from .autozoom import propose
        return jsonify(points=propose(store,get_object(identifier),json_body().get("count",4)))

    @app.get("/api/objects/<identifier>/solar-system")
    def solar_destinations(identifier):
        from .solar_detail import options
        fields = options(get_object(identifier).get("body"))
        return jsonify(fields=[f["id"] for f in fields], observations=fields)

    @app.get("/media/<identifier>/solar-system/<name>")
    def solar_detail_movie(identifier, name):
        from .solar_detail import movie
        try:
            path = movie(store, get_object(identifier), name)
        except requests.RequestException:
            return jsonify(error="solarDetailUnavailable"), 503
        return send_file(path, mimetype="video/mp4", conditional=True, max_age=0)

    @app.get("/api/objects/<identifier>/hubble")
    def hubble_fields(identifier):
        from .hubble import fields
        record=get_object(identifier)
        try:
            options=fields(store,record)
        except requests.RequestException:
            return jsonify(error="hubble_unavailable"),503
        return jsonify(fields=[o["id"] for o in options],observations=options)

    @app.get("/media/<identifier>/hubble/<name>")
    def hubble_movie(identifier,name):
        from .hubble import movie
        record=get_object(identifier)
        try:
            path=movie(store,record,name)
        except requests.RequestException:
            return jsonify(error="hubble_unavailable"),503
        return send_file(path,mimetype="video/mp4",conditional=True,max_age=0)

    @app.get("/api/objects/<identifier>/polar")
    def polar_chart(identifier):
        from .polar import chart
        return jsonify(chart(store,get_object(identifier)))

    @app.get("/api/objects/<identifier>/discover")
    def discover_objects(identifier):
        from .discovery import discover
        return jsonify(discover(store, get_object(identifier)))

    @app.get("/api/objects/<identifier>/journey")
    def journey_info(identifier):
        from .journey import geometry
        from .survey import survey_for
        from .galaxy import journey_labels
        record = get_object(identifier)
        field = geometry(store, record)
        return jsonify(solar=bool(record.get("body")),default_site=field.get("default_site"),day_only=field.get("day_only"),labels=journey_labels(record, field), survey=survey_for(field) if not record.get("body") and field["kind"] != "missing" else None, kind=field["kind"], url=f"/media/{identifier}/journey" if field["kind"] != "missing" else None)

    @app.get("/media/<identifier>/journey")
    def journey_movie(identifier):
        from .journey import geometry, movie
        record = get_object(identifier)
        field = geometry(store, record)
        if field["kind"] == "missing":
            abort(404)
        target = movie(store, record, field)
        return send_file(target, mimetype="video/mp4", conditional=True, max_age=0)

    @app.get("/atlas")
    def personal_atlas():
        return send_file(ROOT / "static" / "collection.html")

    @app.get("/api/atlas")
    def personal_atlas_data():
        from .collection import atlas_data
        return jsonify(atlas_data(store, bool(session.get("admin"))))

    @app.get("/guide")
    def guide():
        return send_file(ROOT / "static" / "guide.html")

    @app.get("/api/health")
    def health():
        try:
            ffmpeg_executable()
            encoder = True
        except RuntimeError:
            encoder = False
        return jsonify(ok=True, version=__version__, encoder=encoder)

    @app.get("/api/session")
    def session_info():
        local = request.remote_addr in {"127.0.0.1", "::1"}
        return jsonify(authenticated=bool(session.get("admin")), initialized=bool(store.get("settings", "admin")), can_setup=local, csrf=token())

    @app.post("/api/setup")
    def setup():
        if store.get("settings", "admin"):
            return jsonify(error="already_initialized"), 409
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return jsonify(error="local_setup_required"), 403
        password = json_body().get("password", "")
        if not isinstance(password, str) or not 11 <= len(password) <= 512:
            raise ValueError("weak_password")
        with store.lock:
            if store.get("settings", "admin"):
                return jsonify(error="already_initialized"), 409
            store.put("settings", "admin", generate_password_hash(password))
        session.clear()
        session.update(admin=True, permanent=True)
        return jsonify(ok=True, csrf=token())

    @app.post("/api/login")
    def login():
        address = request.remote_addr or "unknown"
        stamp = time.monotonic()
        with attempts_lock:
            recent = [t for t in attempts.get(address, []) if stamp - t < 300]
            if len(recent) >= 5:
                return jsonify(error="login_rate_limit"), 429
            attempts[address] = recent + [stamp]
        password = json_body().get("password", "")
        hashed = store.get("settings", "admin")
        if not isinstance(password, str) or len(password) > 512 or not hashed or not check_password_hash(hashed, password):
            return jsonify(error="invalid_login"), 401
        with attempts_lock:
            attempts.pop(address, None)
        session.clear()
        session.update(admin=True, permanent=True)
        return jsonify(ok=True, csrf=token())

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True, csrf=token())

    @app.get("/api/objects")
    def objects():
        from .collection import gallery
        return jsonify(objects=[present(record) for record in gallery(r for r in store.all("objects") if r["published"])])

    @app.get("/api/admin/objects")
    @admin_required
    def admin_objects():
        return jsonify(objects=[present(record, True) for record in store.all("objects")], jobs=store.all("jobs", limit=50))

    @app.post("/api/admin/upload-identity")
    @admin_required
    def identify_upload():
        body = json_body()
        names = body.get("names", [])
        if not isinstance(names, list) or len(names) > 4 or not all(isinstance(n,str) for n in names):
            raise ValueError("invalid_filename")
        identifier, source, _ = upload_identity(names, body.get("object"))
        return jsonify(identifier=identifier, source=source)

    @app.post("/api/admin/upload-autozoom")
    @admin_required
    def draft_autozoom():
        import numpy as np
        from PIL import Image
        from .autozoom import propose_image
        upload = request.files.get("preview")
        if not upload:
            raise ValueError("invalid_image")
        data = upload.read(512 * 1024 + 1)
        if len(data) > 512 * 1024:
            raise ValueError("image_too_large")
        try:
            with Image.open(io.BytesIO(data), formats=["JPEG"]) as img:
                if max(img.size) > 640:
                    raise ValueError("image_dimensions")
                image = np.asarray(img.convert("L"))
        except (OSError, Image.DecompressionBombError):
            raise ValueError("invalid_image") from None
        return jsonify(points=propose_image(image, request.form.get("count", type=int)))

    @app.post("/api/admin/upload-poster")
    @admin_required
    def upload_poster():
        image = request.files.get("image")
        if not image:
            raise ValueError("invalid_image")
        with tempfile.TemporaryDirectory(prefix="poster-", dir=store.root) as temp:
            path = Path(temp) / "original"
            image.save(path)
            validate_image(path)
            poster = Path(temp) / "poster.jpg"
            save_jpg(poster, resize_long(read_rgb(path), 1200))
            return send_file(io.BytesIO(poster.read_bytes()), mimetype="image/jpeg")

    @app.post("/api/admin/objects")
    @admin_required
    def upload():
        supplied = request.form.get("identifier", "").strip()
        try:
            raw_params = json.loads(request.form.get("params", "{}"))
        except ValueError:
            raise ValueError("invalid_parameters") from None
        params = Parameters.parse(raw_params)
        files = request.files.getlist("images")
        # A single explicitly selected solar-system body has its own upload mode.
        solar = supplied.upper() in BODIES
        if solar and len(files) != 1:
            raise ValueError("single_image_required")
        if not solar and len(files) != 4:
            raise ValueError("four_images_required")
        with tempfile.TemporaryDirectory(prefix="upload-", dir=store.root) as temp:
            paths = []
            for file in files:
                filename = secure_filename(file.filename or "")
                path = Path(temp) / filename
                if not filename or path in paths:
                    raise ValueError("invalid_filename")
                file.save(path)
                if path.stat().st_size > MAX_FILE:
                    raise ValueError("image_too_large")
                paths.append(path)
            fits = request.files.get("fits")
            observation = None
            fits_path = None
            if fits and fits.filename:
                from .observation import read_observation
                fits_path = Path(temp) / secure_filename(fits.filename)
                if fits_path.suffix.lower() not in {".fit", ".fits", ".fts"}:
                    raise ValueError("invalid_fits")
                fits.save(fits_path)
                observation = read_observation(fits_path)
            source = prefix = None
            if solar:
                identifier = normalize_id(supplied)
                params.method = "kenburns"
            else:
                header = (observation or {}).get("header", {})
                identifier, source, prefix = upload_identity([p.name for p in paths], header.get("OBJECT"), supplied)
                if request.form.get("identifier_override") == "1":
                    identifier = normalize_id(supplied)
                    source = "manual"
                if not identifier:
                    raise ValueError("invalid_identifier")
                if fits_path and not header.get("OBJECT") and file_prefix(fits_path.name) and prefix and not belongs(fits_path.name, prefix):
                    raise ValueError("invalid_filename")
            with queue.lock:
                manual=request.form.get("capture_date","").strip()
                if manual:
                    try:
                        manual=date.fromisoformat(manual).isoformat()
                    except ValueError:
                        raise ValueError("invalid_observation") from None
                record = import_object(store, identifier, paths, request.form.get("session_name",""),
                                       repeat=True,capture_date=manual or None, source_prefix=prefix, allow_export_prefix=source in {"fits", "manual"})
                if fits_path:
                    from .observation import attach_fits
                    record = attach_fits(store, record, fits_path, observation)
                job = queue.submit(record["id"], params.__dict__)
        return jsonify(object=present(record, True), job=job), 202

    @app.post("/api/admin/objects/<identifier>/align")
    @admin_required
    def align(identifier):
        queue.request_alignment(identifier)
        return jsonify(ok=True), 202

    @app.post("/api/admin/jobs/<job_id>/cancel")
    @admin_required
    def cancel_render(job_id):
        return jsonify(job=queue.cancel(job_id))

    @app.post("/api/admin/objects/<identifier>/render")
    @admin_required
    def render(identifier):
        return jsonify(job=queue.submit(identifier, json_body())), 202

    @app.get("/api/admin/objects/<identifier>/versions/<version_id>/movie")
    @admin_required
    def version_movie(identifier, version_id):
        record = get_object(identifier)
        version = next((v for v in record.get("versions", []) if v["id"] == version_id), None)
        if not version or not store.path(version["video"]).is_file():
            abort(404)
        return send_file(store.path(version["video"]), mimetype="video/mp4", conditional=True)

    @app.delete("/api/admin/objects/<identifier>/versions/<version_id>")
    @admin_required
    def delete_version(identifier, version_id):
        pending = queue.delete_version(identifier, version_id)
        return jsonify(ok=True, cleanup_pending=pending)

    @app.put("/api/admin/objects/<identifier>/versions/<version_id>/select")
    @admin_required
    def select_version(identifier, version_id):
        queue.select_version(identifier, version_id)
        return jsonify(ok=True)

    @app.post("/api/admin/objects/<identifier>/preview")
    @admin_required
    def preview(identifier):
        record = get_object(identifier)
        params = Parameters.parse(json_body())
        if record.get("body"):params.method="kenburns"
        count = len(params.zoom_points) or 1
        index = request.args.get("point", default=1, type=int)
        if not 1 <= index <= count:
            raise ValueError("invalid_parameters")
        params.resolution = 720
        scene = Scene.from_paths({role: store.path(path) for role, path in record["assets"].items()}, params)
        # Show the chosen focal point at maximum zoom.
        import cv2
        import numpy as np
        frame = np.rint(scene.frame(index/(count+1)) * 255).astype(np.uint8)
        _, data = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        return send_file(io.BytesIO(data.tobytes()), mimetype="image/jpeg")

    @app.put("/api/admin/objects/<identifier>/identifier")
    @admin_required
    def change_identifier(identifier):
        new = canonical(normalize_id(json_body().get("identifier","")))
        record = get_object(identifier)
        current_catalog = group_id(record)
        if (new in BODIES) != bool(record.get("body")):
            raise ValueError("capture_kind_mismatch")
        if new != current_catalog:
            # Merging into an existing group reuses its editorial metadata.
            known=next((r for r in store.all("objects") if group_id(r)==new),None)
            metadata=known["metadata"] if known else renamed_metadata(new)
            with queue.lock:
                record=store.rename_object(identifier,new,metadata)
                queue.executor.submit(queue.discover_skymap, record["id"])
        return jsonify(object=present(record, True))

    @app.put("/api/admin/objects/<identifier>/metadata")
    @admin_required
    def edit_metadata(identifier):
        record = get_object(identifier)
        raw = json_body()
        value = validate_metadata(raw)
        if "galactic_distance_ly" not in raw and value["target"] == record["metadata"]["target"] and "galactic_distance_ly" in record["metadata"]:
            value["galactic_distance_ly"] = record["metadata"]["galactic_distance_ly"]
        previous = record["metadata"]
        same_target = value["target"].casefold() == previous["target"].casefold()
        value["sources"] = previous.get("sources", []) if same_target else []
        if same_target:
            value["aliases"] = previous.get("aliases", value["aliases"])
            if "external" in previous:
                value["external"] = previous["external"]
        store.update("objects", identifier, metadata=value)
        if not same_target:
            queue.executor.submit(queue.discover_skymap, identifier)
        return jsonify(ok=True)

    @app.post("/api/admin/objects/<identifier>/metadata/refresh")
    @admin_required
    def fetch_metadata(identifier):
        record = get_object(identifier)
        try:
            value = refresh_metadata(record["metadata"], force=False)
        except requests.RequestException:
            return jsonify(error="metadata_unavailable"), 502
        store.update("objects", identifier, metadata=value)
        return jsonify(metadata=value)

    @app.put("/api/admin/objects/<identifier>/observation")
    @admin_required
    def edit_observation(identifier):
        from .observation import observation_overrides
        record = get_object(identifier)
        raw = json_body()
        observation = dict(record.get("observation") or {})
        if record.get("body") and any(k in raw for k in ("latitude","longitude")):
            coords = [raw.get(k) for k in ("latitude","longitude")]
            if coords == [None, None]:
                for k in ("latitude","longitude"):
                    raw.pop(k,None)
                    observation.pop(k,None)
            elif None in coords:
                raise ValueError("invalid_observation")
        value = observation_overrides(observation, raw)
        store.update("objects", identifier, observation=value)
        if any(value.get(k) != (record.get("observation") or {}).get(k) for k in ("ra","dec")):
            queue.request_alignment(identifier)
        return jsonify(ok=True)

    @app.post("/api/admin/objects/<identifier>/fits")
    @admin_required
    def upload_fits(identifier):
        from .observation import attach_fits, read_observation
        record = get_object(identifier)
        file = request.files.get("fits")
        if not file or not file.filename:
            raise ValueError("invalid_filename")
        with tempfile.TemporaryDirectory(prefix="fits-", dir=store.root) as temp:
            path = Path(temp) / secure_filename(file.filename)
            file.save(path)
            observation = read_observation(path)
            if not record.get("body"):
                header_id = fits_target(observation["header"].get("OBJECT"))
                if not belongs(path.name, group_id(record)) and not (
                    header_id and canonical(header_id) == group_id(record)
                ):
                    raise ValueError("invalid_filename")
            record = attach_fits(store, record, path, observation)
            queue.request_alignment(identifier)
        return jsonify(object=present(record, True))

    @app.get("/api/objects/<identifier>/sky")
    def sky(identifier):
        from .sky import build_sky
        record = get_object(identifier)
        return jsonify(build_sky(record))

    @app.get("/media/<identifier>/<kind>")
    def media(identifier, kind):
        record = get_object(identifier)
        if kind == "poster":
            relative = record["poster"]
            if request.args.get("rotation") == "90" and record["width"] > record["height"]:
                output = io.BytesIO()
                with Image.open(store.path(relative)) as image:
                    image.transpose(Image.Transpose.ROTATE_270).save(output, format="JPEG", quality=92)
                output.seek(0)
                return send_file(output, mimetype="image/jpeg", max_age=3600)
        elif kind == "movie":
            relative = record["video"]
        elif kind == "preview" and record["video"]:
            preview = gallery_preview_path(store.path(record["video"]))
            relative = preview if preview.is_file() else record["video"]
        elif kind == "original-view":
            from PIL import Image
            # Browsers do not generally decode TIFF. Display the full-size raster
            # as JPEG while the download route retains the original bytes.
            image = read_rgb(store.path(record["assets"]["final"]))
            import numpy as np
            stream = io.BytesIO()
            Image.fromarray(np.rint(image*255).astype(np.uint8)).save(stream,format="JPEG",quality=96)
            stream.seek(0)
            return send_file(stream,mimetype="image/jpeg",max_age=3600)
        elif kind == "final":
            relative = record["assets"]["final"]
        else:
            abort(404)
        if not relative:
            abort(404)
        response = send_file(store.path(relative), conditional=True, max_age=3600 if kind == "final" else 0, download_name=f"{identifier}{'.mp4' if kind == 'movie' else Path(relative).suffix}", as_attachment=request.args.get("download") == "1")
        return response

    return app
