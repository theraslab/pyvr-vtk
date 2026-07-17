"""
One-off helper: filter vtk_openxr_actions.json's default_bindings list down
to only the profiles WiVRn/Quest 3 actually support, dropping the ones that
crash on unsupported extensions (hand_interaction, hp_mixed_reality, etc).

Usage:
    python3 trim_actions.py /path/to/source_dir /path/to/dest_dir
"""
import json
import shutil
import sys
from pathlib import Path

KEEP_SUBSTRINGS = ("khr_simple_controller", "oculus_touch_controller")

def main():
    src_dir = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])
    dest_dir.mkdir(parents=True, exist_ok=True)

    actions_path = src_dir / "vtk_openxr_actions.json"
    with open(actions_path) as f:
        manifest = json.load(f)

    if "default_bindings" not in manifest:
        print("No 'default_bindings' key found -- inspect the file manually:")
        print(json.dumps(manifest, indent=2)[:2000])
        return

    original_count = len(manifest["default_bindings"])
    manifest["default_bindings"] = [
        entry for entry in manifest["default_bindings"]
        if any(keep in json.dumps(entry) for keep in KEEP_SUBSTRINGS)
    ]
    kept_count = len(manifest["default_bindings"])
    print(f"Kept {kept_count} of {original_count} default_bindings entries.")

    # Write trimmed manifest
    with open(dest_dir / "vtk_openxr_actions.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Copy only the binding files we're keeping
    for entry in manifest["default_bindings"]:
        entry_str = json.dumps(entry)
        for f_name in src_dir.glob("*.json"):
            if f_name.name in entry_str:
                shutil.copy(f_name, dest_dir / f_name.name)
                print(f"Copied {f_name.name}")

    print(f"\nTrimmed manifest written to: {dest_dir}")
    print("Point SetActionManifestDirectory at this directory (with trailing slash).")

if __name__ == "__main__":
    main()