"""Validate a downloaded AstroWeb kit. Pass --create to assemble a new Resolve project."""
import argparse
import json
import os
from pathlib import Path
import sys

def resolve_connection():
    api = os.environ.get("RESOLVE_SCRIPT_API")
    if not api and sys.platform == "win32":
        api = str(Path(os.environ["PROGRAMDATA"]) / "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting")
    if api:
        sys.path.insert(0, str(Path(api) / "Modules"))
    import DaVinciResolveScript
    instance = DaVinciResolveScript.scriptapp("Resolve")
    if not instance:
        raise SystemExit("Open Resolve Studio and enable local external scripting, then retry.")
    return instance

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="Create a new project without editing an existing timeline")
    parser.add_argument("--kit", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.kit.resolve()
    edit = json.loads((root / "edit.json").read_text(encoding="utf-8"))
    footage = root / "Footage"
    for item in edit:
        path = footage / item["file"]
        if path.parent != footage or not path.is_file():
            raise SystemExit(f"Missing footage: {item['file']}")
    resolve = resolve_connection()
    print(resolve.GetProductName(), resolve.GetVersionString(), f"— {len(edit)} chapters ready at 24 fps")
    if not args.create:
        return
    manager = resolve.GetProjectManager()
    name = "AstroWeb — Web 1.4.1 and TV 0.6.0"
    if name in (manager.GetProjectListInCurrentFolder() or []):
        raise SystemExit("A project with this name already exists. Rename it first if a second assembly is wanted.")
    project = manager.CreateProject(name)
    if not project:
        raise SystemExit("Resolve could not create the project.")
    for key,value in [("timelineFrameRate","24"),("timelineResolutionWidth","1920"),("timelineResolutionHeight","1080")]:
        if not project.SetSetting(key,value):
            raise SystemExit(f"Could not set {key} to {value}.")
    pool = project.GetMediaPool()
    sources = pool.ImportMedia([str(path) for path in sorted(footage.glob("*.mp4"))])
    if not sources:
        raise SystemExit("Resolve could not import the editing copies.")
    by_name = {Path(item.GetClipProperty("File Path")).name:item for item in sources}
    timeline = pool.CreateEmptyTimeline("English overview")
    if not timeline:
        raise SystemExit("Could not create the timeline.")
    timeline.SetStartTimecode("00:00:00:00")
    for item in edit:
        clip = by_name[item["file"]]
        count = item["seconds"] * 24
        added = pool.AppendToTimeline([{"mediaPoolItem":clip,"startFrame":0,"endFrame":count-1}])
        if not added:
            raise SystemExit(f"Could not append {item['file']}.")
        timeline.AddMarker(item["timelineFrame"],"Rose",item["title"],"",1,"")
    if not manager.SaveProject():
        raise SystemExit("Could not save the new project.")
    print("English overview created. Import the SRT on a subtitle track and record the narration when ready.")

if __name__=="__main__":
    main()
