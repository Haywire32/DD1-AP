"""Pure protocol adapter between CommonClient packets and DD1 durable state.

This module deliberately does not import Archipelago's bundled CommonClient.
It can therefore be regression-tested with the project Python runtime and then
used unchanged by a future launcher component inside Archipelago.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

try:
    from .dd1_protocol import acknowledge_locations, record_received_items
except ImportError:  # Direct execution from the bridge development folder.
    from dd1_protocol import acknowledge_locations, record_received_items


def _network_item_field(item: object, field: str) -> int:
    if isinstance(item, Mapping):
        value = item.get(field)
    else:
        value = getattr(item, field, None)
    # AP uses negative location sentinels for precollected/start-inventory
    # items. Item IDs and player IDs remain non-negative.
    if not isinstance(value, int) or (field != "location" and value < 0):
        qualifier = "an integer" if field == "location" else "a non-negative integer"
        raise ValueError(f"ReceivedItems {field} must be {qualifier}")
    return value


def normalize_received_packet(args: Mapping[str, Any]) -> list[dict[str, int]]:
    """Convert one CommonClient ReceivedItems payload to indexed journal rows."""
    base = args.get("index", 0)
    items = args.get("items", [])
    if not isinstance(base, int) or base < 0:
        raise ValueError("ReceivedItems index must be a non-negative integer")
    if not isinstance(items, (list, tuple)):
        raise ValueError("ReceivedItems items must be a list")

    return [
        {
            "index": base + offset,
            "item_id": _network_item_field(item, "item"),
            "location_id": _network_item_field(item, "location"),
            "player": _network_item_field(item, "player"),
        }
        for offset, item in enumerate(items)
    ]


def ingest_received_packet(state: dict[str, Any], args: Mapping[str, Any]) -> int:
    return record_received_items(state, normalize_received_packet(args))


def reconcile_locations(
    state: dict[str, Any],
    *,
    server_locations: Iterable[int],
    checked_locations: Iterable[int],
) -> tuple[list[int], list[int]]:
    """Return (safe_to_send, unknown_to_this_slot) and persist server acks.

    Prototype IDs are never sent merely because they are locally pending. The
    future CommonContext wrapper must first prove that the connected slot's
    server location set contains them, preventing a mismatched table from
    disconnecting or corrupting another seed.
    """
    server_set = set(server_locations)
    checked_set = set(checked_locations)
    acknowledge_locations(
        state,
        [value for value in state["pending_location_ids"] if value in checked_set],
    )
    pending = set(state["pending_location_ids"])
    safe_to_send = sorted(pending & server_set - checked_set)
    unknown = sorted(pending - server_set)
    return safe_to_send, unknown
