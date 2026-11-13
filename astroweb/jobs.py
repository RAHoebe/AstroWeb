"""One CPU worker, durable states and atomic publish after successful encoding."""
import logging
import os
import threading
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .render import Parameters, build_gallery_preview, gallery_preview_path, render_video
from .store import now


class JobQueue:
    def __init__(self, store, resume=True):
        self.store = store
        self.worker_lock = store.path("worker.lock").open("a+b")
        if self.worker_lock.tell() == 0:
            self.worker_lock.write(b"0")
            self.worker_lock.flush()
        self.worker_lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.worker_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.worker_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.worker_lock.close()
            raise RuntimeError("AstroWeb gebruikt deze datamap al / this data directory already has a running AstroWeb worker") from None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="astro-render")
        self.lock = threading.RLock()
        self.futures = {}
        self.file_lock = threading.Lock()
        self.restore_versions()
        for record in store.all("objects"):
            if record.get("pending_movie_cleanup"):
                self.clean_deleted_movies(record["id"])
        if resume:
            for job in reversed(store.all("jobs")):
                if job["status"] == "running":
                    store.update("jobs", job["id"], status="failed", error="render_interrupted", finished_at=now())
                elif job["status"] == "queued":
                    self.futures[job["id"]] = self.executor.submit(self.run, job["id"])

            for record in store.all("objects"):
                if (record.get("gaia") or {}).get("status") in (None, "pending", "running"):
                    self.executor.submit(self.align, record["id"])
                if record.get("video"):
                    self.executor.submit(self.ensure_preview, record["video"])

    def restore_versions(self):
        jobs = self.store.all("jobs")
        for record in self.store.all("objects"):
            if "versions" in record:
                continue
            versions = []
            for job in reversed(jobs):
                if job["object_id"] != record["id"] or job["status"] != "completed":
                    continue
                movie = f"objects/{record.get('storage_id', record['id'])}/movies/{job['id']}.mp4"
                if self.store.path(movie).is_file():
                    versions.append({"id": job["id"], "video": movie, "params": job["params"],
                                     "created_at": job["finished_at"], "render": record["render"] if movie == record["video"] else None})
            if record["video"] and not any(v["video"] == record["video"] for v in versions):
                versions.append({"id": Path(record["video"]).stem, "video": record["video"], "params": record["params"],
                                 "created_at": record["created_at"], "render": record["render"]})
            self.store.update("objects", record["id"], versions=versions)

    def ensure_preview(self, relative):
        try:
            with self.file_lock:
                movie = self.store.path(relative)
                if movie.is_file():
                    build_gallery_preview(movie)
        except Exception:
            logging.warning("Gallery preview unavailable for %s", relative, exc_info=True)

    def select_version(self, identifier, version_id):
        with self.store.lock:
            record = self.store.get("objects", identifier)
            version = next((v for v in (record or {}).get("versions", []) if v["id"] == version_id), None)
            if not version or not self.store.path(version["video"]).is_file():
                raise ValueError("version_missing")
            self.store.update("objects", identifier, video=version["video"], params=version["params"],
                              render=version["render"], published=True)
        self.executor.submit(self.ensure_preview, version["video"])

    def delete_version(self, identifier, version_id):
        with self.store.lock:
            record = self.store.get("objects", identifier)
            version = next((v for v in (record or {}).get("versions", []) if v["id"] == version_id), None)
            if not version:
                raise ValueError("version_missing")
            if record["video"] == version["video"]:
                raise ValueError("version_published")
            # Save the cleanup request with the catalog change, so a restart or
            # a Windows reader holding the MP4 open cannot lose the cleanup.
            record["versions"].remove(version)
            record.setdefault("pending_movie_cleanup", []).append(version["video"])
            self.store.put("objects", identifier, record)
        return self.clean_deleted_movies(identifier)

    def clean_deleted_movies(self, identifier):
        with self.file_lock, self.store.lock:
            record = self.store.get("objects", identifier)
            pending = []
            for relative in record.get("pending_movie_cleanup", []):
                movie = self.store.path(relative)
                if movie.parent != self.store.path(f"objects/{record.get('storage_id',identifier)}/movies") or movie.suffix != ".mp4":
                    raise ValueError("invalid_path")
                try:
                    movie.unlink(missing_ok=True)
                    gallery_preview_path(movie).unlink(missing_ok=True)
                except OSError:
                    pending.append(relative)
                    logging.warning("Movie cleanup pending for %s", relative)
            self.store.update("objects", identifier, pending_movie_cleanup=pending)
            return bool(pending)

    def request_alignment(self, identifier):
        with self.store.lock:
            record = self.store.get("objects", identifier)
            if not record:
                raise ValueError("object_not_found")
            if (record.get("gaia") or {}).get("status") == "solved":
                return
            self.store.update("objects", identifier, gaia={"status":"pending", "request":uuid.uuid4().hex})
            self.executor.submit(self.align, identifier)

    def align(self, identifier):
        with self.store.lock:
            record = self.store.get("objects", identifier)
            if not record:
                return
            previous = record.get("gaia") or {}
            if previous.get("status") not in (None, "pending", "running"):
                return
            token = previous.get("request") or uuid.uuid4().hex
            self.store.update("objects", identifier, gaia={"status":"running", "request":token})
        try:
            from .gaia import solve
            result = solve(self.store, record)
        except Exception:
            logging.exception("Gaia alignment failed for %s", identifier)
            result = {"status":"unavailable"}
        with self.store.lock:
            latest = self.store.get("objects", identifier)
            if latest["gaia"].get("request") == token:
                self.store.update("objects", identifier, gaia=result)

    def submit(self, identifier, raw_params=None):
        params = Parameters.parse(raw_params)
        with self.lock:
            if not self.store.get("objects", identifier):
                raise ValueError("object_not_found")
            jobs = self.store.all("jobs")
            if any(job["object_id"] == identifier and job["status"] in {"queued", "running"} for job in jobs):
                raise ValueError("render_active")
            if sum(job["status"] in {"queued", "running"} for job in jobs) >= 8:
                raise ValueError("queue_full")
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "object_id": identifier, "status": "queued", "progress": 0, "params": params.__dict__, "created_at": now(), "error": None}
            self.store.put("jobs", job_id, job)
            self.futures[job_id] = self.executor.submit(self.run, job_id)
            return job

    def run(self, job_id):
        job = self.store.update("jobs", job_id, status="running", started_at=now(), progress=2)
        try:
            record = self.store.get("objects", job["object_id"])
            if record["metadata"].get("translation") == "pending" and not record["metadata"].get("external"):
                # New, uncurated targets are enriched automatically; offline failures never block a movie.
                from .metadata import refresh_metadata
                try:
                    metadata = refresh_metadata(record["metadata"])
                    external = metadata.get("external", {})
                    for language, text in external.get("text", {}).items():
                        if text:
                            metadata["description"][language] = text
                            metadata["summary"][language] = text.split(". ", 1)[0][:300]
                    metadata["translation"] = external.get("translation", "partial") if external.get("text", {}).get("nl") else "partial"
                    current = self.store.get("objects", record["id"])
                    if current["metadata"].get("updated_at") == record["metadata"].get("updated_at"):
                        self.store.update("objects", record["id"], metadata=metadata)
                except Exception:
                    logging.info("Object metadata unavailable for %s; keeping local descriptions", record["id"])
            self.align(record["id"])
            relative = f"objects/{record.get('storage_id', record['id'])}/movies/{job_id}.mp4"
            params = Parameters.parse(job["params"])
            stats = render_video({key: self.store.path(value) for key, value in record["assets"].items()}, self.store.path(relative), params, progress=lambda p: self.store.update("jobs", job_id, progress=p))
            self.ensure_preview(relative)
            with self.store.lock:
                record = self.store.get("objects", record["id"])
                finished = now()
                version = {"id": job_id, "video": relative, "params": params.__dict__, "render": stats, "created_at": finished}
                record.setdefault("versions", []).append(version)
                if not record["video"]:
                    record.update(video=relative, params=params.__dict__, render=stats, published=True)
                job.update(status="completed", progress=100, error=None, finished_at=finished)
                self.store.finish_render(record, job)
        except Exception as exc:
            logging.exception("Render failed: %s", job_id)
            known = str(exc) if str(exc) in {"ffmpeg_missing", "encode_failed", "invalid_image"} else "render_failed"
            self.store.update("jobs", job_id, status="failed", error=known, finished_at=now())

    def shutdown(self):
        self.executor.shutdown(wait=True)
        self.worker_lock.close()
