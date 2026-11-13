import argparse
import getpass
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AstroWeb · lokaal / local · NAS")
    parser.add_argument("command", nargs="?", choices=["serve", "import", "admin"], default="serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--source", type=Path, default=Path("AstroPhotos"))
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.command == "serve":
        from .app import create_app
        from waitress import serve
        app = create_app()
        print(f"AstroWeb: http://{args.host}:{args.port}", flush=True)
        try:
            serve(app, host=args.host, port=args.port, threads=6, max_request_body_size=600 * 1024 * 1024)
        finally:
            app.extensions["jobs"].shutdown()
        return
    from .store import Store
    store = Store(os.environ.get("ASTROWEB_DATA", Path.cwd() / "data"))
    if args.command == "admin":
        from werkzeug.security import generate_password_hash
        password = getpass.getpass("Nieuw wachtwoord / new password (11+): ")
        if len(password) < 11 or password != getpass.getpass("Herhaal / repeat: "):
            parser.error("Wachtwoorden komen niet overeen / passwords do not match (11+)")
        store.put("settings", "admin", generate_password_hash(password))
        print("Wachtwoord opgeslagen / password saved")
        return
    from .jobs import JobQueue
    from .media import EXTENSIONS, import_object
    from .observation import attach_fits
    queue = JobQueue(store)
    submitted = []
    try:
        for folder in sorted(args.source.iterdir()):
            if not folder.is_dir():
                continue
            existing = store.get("objects", store.current_id(folder.name.upper()))
            if existing:
                record = existing
            else:
                record = import_object(store, folder.name, [p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS])
                print(f"Import: {record['id']}", flush=True)
            previous_fits = bool(record.get("fits"))
            fits = list(folder.glob("*.fits")) + list(folder.glob("*.fit"))
            if fits and not record.get("fits"):
                record = attach_fits(store, record, fits[0])
                print(f"FITS: {record['id']}", flush=True)
            if (not existing or (fits and not previous_fits)) and not (args.render and not record.get("video")):
                queue.request_alignment(record["id"])
            if args.render and not record.get("video"):
                job = queue.submit(record["id"])
                submitted.append(job["id"])
                print(f"Render: {record['id']} ({job['id']})", flush=True)
    finally:
        queue.shutdown()
    results = [store.get("jobs", job_id) for job_id in submitted]
    failed = [job for job in results if job["status"] == "failed"]
    if failed:
        raise SystemExit("Mislukte renders / failed renders: " + ", ".join(job["object_id"] for job in failed))


if __name__ == "__main__":
    main()
