"""Watch the DD1 Archipelago prototype's Local-only JSON-lines event file."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


DEFAULT_ROOT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\DungeonDefendersDevelopmentKit"
)
EVENT_GLOBS = ("DD1ArchipelagoEvent*json", "DD1ArchipelagoEvents*jsonl")


def candidate_directories(root: Path) -> list[Path]:
    return [
        root / "UDKGame" / "User",
        root / "TotalConversions" / "DD1ArchipelagoCurrent" / "User",
    ]


def event_files(directories: list[Path]) -> list[Path]:
    files = {
        path
        for directory in directories
        if directory.is_dir()
        for pattern in EVENT_GLOBS
        for path in directory.glob(pattern)
        if path.is_file()
    }
    return sorted(files, key=lambda path: (path.stat().st_mtime_ns, path.name))


def validate_event(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or value.get("protocol") != 1:
        return None
    if not isinstance(value.get("sequence"), int):
        return None
    if value.get("event") not in {"session_start", "wave_complete", "level_victory"}:
        return None
    if not isinstance(value.get("map"), str) or not isinstance(value.get("wave"), int):
        return None
    if not isinstance(value.get("detail"), str):
        return None
    return value


def watch(root: Path, poll_seconds: float) -> None:
    directories = candidate_directories(root)
    seen_files: set[Path] = set()

    print("Waiting for a DD1 Archipelago Local event file...", flush=True)
    while True:
        for event_file in event_files(directories):
            if event_file in seen_files:
                continue
            try:
                lines = event_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if not lines:
                    continue
                event = validate_event(json.loads(lines[0])) if len(lines) == 1 else None
            except (OSError, json.JSONDecodeError):
                # The producer closes each file before it becomes valid. Retry
                # files that are still unavailable or incomplete next poll.
                continue
            if event is None:
                seen_files.add(event_file)
                continue

            seen_files.add(event_file)
            print(json.dumps(event, separators=(",", ":")), flush=True)

        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    args = parser.parse_args()
    watch(args.root, max(args.poll_seconds, 0.05))


if __name__ == "__main__":
    main()
