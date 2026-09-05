"""Persist validated DD1 checks for a future Archipelago client connection."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from .dd1_event_watcher import DEFAULT_ROOT, candidate_directories, event_files, validate_event
    from .dd1_protocol import (
        BRIDGE_STATE_VERSION, ProtocolError, atomic_write_json, load_bridge_state, record_locations,
    )
except ImportError:  # Direct execution from the bridge development folder.
    from dd1_event_watcher import DEFAULT_ROOT, candidate_directories, event_files, validate_event
    from dd1_protocol import (
        BRIDGE_STATE_VERSION, ProtocolError, atomic_write_json, load_bridge_state, record_locations,
    )


DEFAULT_STATE = Path(__file__).with_name("runtime") / "bridge_state.json"


def read_closed_event(path: Path) -> dict[str, object] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) != 1:
            return None
        return validate_event(json.loads(lines[0]))
    except (OSError, json.JSONDecodeError):
        return None


def baseline_existing_events(root: Path, state: dict[str, object]) -> int:
    """Mark pre-connection files seen so they cannot leak into a new AP slot."""
    processed = set(state["processed_files"])
    existing = {path.name for path in event_files(candidate_directories(root))}
    unseen = existing - processed
    if unseen:
        state["processed_files"] = sorted(processed | existing)
    return len(unseen)


def process_once(root: Path, state_path: Path) -> tuple[int, int]:
    needs_state_upgrade = not state_path.exists()
    if state_path.exists():
        try:
            stored_state = json.loads(state_path.read_text(encoding="utf-8"))
            needs_state_upgrade = stored_state.get("state_version") != BRIDGE_STATE_VERSION
        except (OSError, json.JSONDecodeError, AttributeError):
            # load_bridge_state below produces the authoritative validation
            # error for malformed state.
            pass
    state = load_bridge_state(state_path)
    processed = set(state["processed_files"])
    files_processed = 0
    locations_added = 0

    for path in event_files(candidate_directories(root)):
        source = path.name
        if source in processed:
            continue
        event = read_closed_event(path)
        if event is None:
            continue

        if event["event"] == "session_start":
            state["processed_files"].append(source)
            state["processed_files"].sort()
        else:
            try:
                recorded = record_locations(state, source, event)
            except ProtocolError as error:
                print(f"Rejected {source}: {error}", flush=True)
                state["processed_files"].append(source)
                state["processed_files"].sort()
            else:
                for key, location_id, was_new in recorded:
                    if was_new:
                        locations_added += 1
                        print(f"Queued {location_id}: {key}", flush=True)
        processed.add(source)
        files_processed += 1

    if files_processed or needs_state_upgrade:
        atomic_write_json(state_path, state)
    return files_processed, locations_added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        processed, added = process_once(args.root, args.state)
        if args.once:
            print(f"Processed {processed} new files; queued {added} new locations.")
            return
        time.sleep(max(args.poll_seconds, 0.05))


if __name__ == "__main__":
    main()
