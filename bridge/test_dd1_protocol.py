from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dd1_protocol import (
    PROTOTYPE_LOCATION_ID_BASE,
    ProtocolError,
    acknowledge_locations,
    atomic_write_json,
    bind_slot_identity,
    canonicalize_event,
    canonicalize_event_locations,
    empty_bridge_state,
    load_bridge_state,
    record_location,
    record_received_items,
    recover_observed_victories,
    summit_is_unlocked,
    switch_hero_profile,
    validate_unlock_state,
    write_unlock_ini,
)
from dd1_bridge_service import baseline_existing_events, process_once
from dd1_ap_adapter import ingest_received_packet, normalize_received_packet, reconcile_locations


WAVE_EVENT = {
    "protocol": 1,
    "sequence": 1,
    "event": "wave_complete",
    "map": "DD_Entryway_03",
    "wave": 2,
    "detail": "EGD_MEDIUM",
}
VICTORY_EVENT = {
    "protocol": 1,
    "sequence": 2,
    "event": "level_victory",
    "map": "DD_Entryway_03",
    "wave": 6,
    "detail": "EGD_MEDIUM",
}


class ProtocolTests(unittest.TestCase):
    def test_level_six_config_is_seed_specific_and_filters_invalid_heroes(self):
        value = {'protocol': 1, 'revision': 1, 'slot': 'Haywire', 'unlocked': {
            'heroes': ['squire'], 'defenses': [], 'abilities': [], 'maps': [],
            'max_equipment_quality': 19}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unlocks.ini'
            write_unlock_ini(path, value, level_six_heroes=['squire', 'monk', 'squire', 'bad\nInjected=1'])
            text = path.read_text()
            self.assertEqual(text.count('LevelSixHeroes='), 2)
            self.assertNotIn('Injected', text)
            write_unlock_ini(path, value)
            self.assertNotIn('LevelSixHeroes=', path.read_text())

    def test_new_slot_can_baseline_old_event_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_dir = root / "UDKGame" / "User"
            event_dir.mkdir(parents=True)
            (event_dir / "DD1ArchipelagoEvent-old.json").write_text(
                '{"protocol":1,"sequence":1,"event":"level_victory",'
                '"map":"FoundriesAndForges","wave":5,"detail":"victory"}\n',
                encoding="utf-8",
            )
            state = empty_bridge_state()

            self.assertEqual(baseline_existing_events(root, state), 1)
            state_path = root / "state.json"
            atomic_write_json(state_path, state)
            self.assertEqual(process_once(root, state_path), (0, 0))

    def test_received_items_packet_is_normalized_and_journaled(self) -> None:
        state = empty_bridge_state()
        packet = {
            "index": 0,
            "items": [
                {"item": 101, "location": -2, "player": 1},
                {"item": 102, "location": 202, "player": 2},
            ],
        }
        self.assertEqual(
            normalize_received_packet(packet),
            [
                {"index": 0, "item_id": 101, "location_id": -2, "player": 1},
                {"index": 1, "item_id": 102, "location_id": 202, "player": 2},
            ],
        )
        self.assertEqual(ingest_received_packet(state, packet), 2)
        self.assertEqual(ingest_received_packet(state, packet), 0)

    def test_pending_checks_are_only_sent_when_slot_declares_them(self) -> None:
        state = empty_bridge_state()
        state["pending_location_ids"] = [10, 20, 30]
        safe, unknown = reconcile_locations(
            state,
            server_locations={10, 20},
            checked_locations={10},
        )
        self.assertEqual(safe, [20])
        self.assertEqual(unknown, [30])
        self.assertEqual(state["acknowledged_location_ids"], [10])
        self.assertEqual(state["pending_location_ids"], [20, 30])

    def test_canonical_keys_and_prototype_ids_are_stable(self) -> None:
        wave_key, wave_id = canonicalize_event(WAVE_EVENT)
        victory_key, victory_id = canonicalize_event(VICTORY_EVENT)
        self.assertEqual(wave_key, "dd1.campaign.CAMPFF.wave.1")
        self.assertEqual(victory_key, "dd1.campaign.CAMPFF.victory.medium")
        self.assertEqual(wave_id, PROTOTYPE_LOCATION_ID_BASE + 10_001)
        self.assertEqual(victory_id, PROTOTYPE_LOCATION_ID_BASE + 11_900)

    def test_higher_difficulty_cascades_and_final_wave_is_not_double_counted(self) -> None:
        event = {
            **WAVE_EVENT,
            "event": "level_victory",
            "wave": 6,
            "detail": "EGD_INSANE",
        }
        expanded = canonicalize_event_locations(event)
        self.assertEqual(
            [key for key, _ in expanded],
            [
                "dd1.campaign.CAMPFF.victory.easy",
                "dd1.campaign.CAMPFF.victory.medium",
                "dd1.campaign.CAMPFF.victory.hard",
            ],
        )
        state = empty_bridge_state()
        _, current_id, was_new = record_location(state, "final-wave.json", event)
        self.assertTrue(was_new)
        self.assertEqual(current_id, PROTOTYPE_LOCATION_ID_BASE + 12_900)
        self.assertEqual(len(state["pending_location_ids"]), 3)

    def test_nightmare_and_ruthless_reuse_the_hard_location_tier(self) -> None:
        for difficulty in ("EGD_NIGHTMARE", "EGD_RUTHLESS"):
            event = {
                **WAVE_EVENT,
                "event": "level_victory",
                "wave": 6,
                "detail": difficulty,
            }
            self.assertEqual(
                [key for key, _ in canonicalize_event_locations(event)],
                [
                    "dd1.campaign.CAMPFF.victory.easy",
                    "dd1.campaign.CAMPFF.victory.medium",
                    "dd1.campaign.CAMPFF.victory.hard",
                ],
            )

            wave_event = {**WAVE_EVENT, "detail": difficulty}
            self.assertEqual(
                canonicalize_event_locations(wave_event)[0][0],
                "dd1.campaign.CAMPFF.wave.1",
            )

    def test_easy_awards_wave_and_easy_victory_checks(self) -> None:
        self.assertEqual(
            canonicalize_event_locations({**WAVE_EVENT, "detail": "EGD_EASY"})[0][0],
            "dd1.campaign.CAMPFF.wave.1",
        )
        self.assertEqual(
            canonicalize_event_locations({**VICTORY_EVENT, "detail": "EGD_EASY"})[0][0],
            "dd1.campaign.CAMPFF.victory.easy",
        )

    def test_foundries_displayed_waves_map_to_four_ordinal_checks(self) -> None:
        mapped = []
        for displayed_wave in range(2, 6):
            event = {**WAVE_EVENT, "wave": displayed_wave}
            mapped.append(canonicalize_event(event))
        self.assertEqual(
            [key for key, _ in mapped],
            [f"dd1.campaign.CAMPFF.wave.{wave}" for wave in range(1, 5)],
        )
        self.assertEqual(
            [location_id for _, location_id in mapped],
            [PROTOTYPE_LOCATION_ID_BASE + 10_000 + wave for wave in range(1, 5)],
        )

    def test_final_wave_event_waits_for_separate_victory_event(self) -> None:
        event = {**WAVE_EVENT, "wave": 6}
        self.assertEqual(canonicalize_event_locations(event), [])

    def test_summit_hard_is_goal_and_cascades_to_easy_and_medium_checks(self) -> None:
        event = {
            "protocol": 1,
            "sequence": 9,
            "event": "level_victory",
            "map": "DD_Finale",
            "wave": 9,
            "detail": "EGD_HARD",
        }
        state = empty_bridge_state()
        recorded = record_location(state, "summit-hard.json", event)
        self.assertTrue(state["goal_complete"])
        self.assertEqual(recorded[0], "dd1.campaign.CAMPTS.victory.medium")
        self.assertEqual(len(state["pending_location_ids"]), 2)

    def test_summit_nightmare_and_ruthless_also_complete_the_goal(self) -> None:
        for difficulty in ("EGD_NIGHTMARE", "EGD_RUTHLESS"):
            event = {
                "protocol": 1,
                "sequence": 9,
                "event": "level_victory",
                "map": "DD_Finale",
                "wave": 9,
                "detail": difficulty,
            }
            state = empty_bridge_state()
            recorded = record_location(state, f"summit-{difficulty}.json", event)
            self.assertTrue(state["goal_complete"])
            self.assertEqual(recorded[0], "dd1.campaign.CAMPTS.victory.medium")
            self.assertEqual(len(state["pending_location_ids"]), 2)

    def test_summit_requires_victory_on_all_other_eleven_maps(self) -> None:
        tags = [
            "CAMPDW", "CAMPFF", "CAMPMQ", "CAMPAL", "CAMPSQ", "CAMPCA",
            "CAMPHC", "CAMPTR", "CAMPRG", "CAMPRP", "CAMPES",
        ]
        victories = {
            f"dd1.campaign.{tag}.victory.medium": {} for tag in tags
        }
        self.assertTrue(summit_is_unlocked(victories))
        easy_victories = {
            f"dd1.campaign.{tag}.victory.easy": {} for tag in tags
        }
        self.assertFalse(summit_is_unlocked(easy_victories))
        victories.pop("dd1.campaign.CAMPES.victory.medium")
        victories["dd1.campaign.CAMPES.wave.4"] = {}
        self.assertFalse(summit_is_unlocked(victories))

    def test_server_checks_recover_summit_history_without_resubmission(self) -> None:
        state = empty_bridge_state()
        checked = {
            PROTOTYPE_LOCATION_ID_BASE + map_index * 10_000 + 1_900
            for map_index in range(11)
        }
        self.assertEqual(recover_observed_victories(state, checked), 11)
        self.assertTrue(summit_is_unlocked(state["observed_locations"]))
        self.assertEqual(state["pending_location_ids"], [])
        self.assertEqual(recover_observed_victories(state, checked), 0)

        with self.assertRaises(ProtocolError):
            recover_observed_victories(state, {"not-an-id"})

    def test_locations_are_deduplicated_and_acknowledged(self) -> None:
        state = empty_bridge_state()
        _, location_id, was_new = record_location(state, "event-1.json", WAVE_EVENT)
        self.assertTrue(was_new)
        _, duplicate_id, was_new = record_location(state, "event-duplicate.json", WAVE_EVENT)
        self.assertFalse(was_new)
        self.assertEqual(location_id, duplicate_id)
        self.assertEqual(state["pending_location_ids"], [location_id])
        acknowledge_locations(state, [location_id])
        self.assertEqual(state["pending_location_ids"], [])
        self.assertEqual(state["acknowledged_location_ids"], [location_id])

    def test_state_is_atomically_round_tripped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge_state.json"
            expected = empty_bridge_state()
            atomic_write_json(path, expected)
            self.assertEqual(load_bridge_state(path), expected)

    def test_corrupt_state_recovers_from_last_atomic_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge_state.json"
            original = empty_bridge_state()
            original["goal_complete"] = True
            atomic_write_json(path, original)

            newer = empty_bridge_state()
            atomic_write_json(path, newer)
            path.write_text("{interrupted", encoding="utf-8")

            self.assertEqual(load_bridge_state(path), original)

    def test_hero_saves_are_isolated_and_restored_per_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tc = root / "tc"
            profiles = root / "profiles"
            tc.mkdir()
            (tc / "DunDefHeroes.dun").write_bytes(b"legacy")

            key_a = switch_hero_profile(tc, profiles, "SeedA|0|Simon")
            self.assertFalse((tc / "DunDefHeroes.dun").exists())
            self.assertEqual((profiles / "legacy-shared.dun").read_bytes(), b"legacy")
            (tc / "DunDefHeroes.dun").write_bytes(b"seed-a")

            key_b = switch_hero_profile(tc, profiles, "SeedB|0|Simon")
            self.assertNotEqual(key_a, key_b)
            self.assertFalse((tc / "DunDefHeroes.dun").exists())
            (tc / "DunDefHeroes.dun").write_bytes(b"seed-b")

            self.assertEqual(switch_hero_profile(tc, profiles, "SeedA|0|Simon"), key_a)
            self.assertEqual((tc / "DunDefHeroes.dun").read_bytes(), b"seed-a")
            self.assertEqual((profiles / f"{key_b}.dun").read_bytes(), b"seed-b")

    def test_legacy_state_is_migrated_without_losing_checks(self) -> None:
        legacy = {
            "protocol": 1,
            "processed_files": ["event.json"],
            "observed_locations": {"a": {"prototype_location_id": 1}},
            "pending_location_ids": [1],
            "acknowledged_location_ids": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge_state.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            migrated = load_bridge_state(path)
            self.assertEqual(migrated["processed_files"], ["event.json"])
            self.assertEqual(migrated["last_received_index"], -1)
            self.assertEqual(migrated["received_items"], [])

    def test_slot_identity_cannot_be_silently_rebound(self) -> None:
        state = empty_bridge_state()
        bind_slot_identity(state, seed_name="SeedA", slot="Simon", team=0, slot_data_version=1)
        bind_slot_identity(state, seed_name="SeedA", slot="Simon", team=0, slot_data_version=1)
        with self.assertRaises(ProtocolError):
            bind_slot_identity(state, seed_name="SeedB", slot="Simon", team=0, slot_data_version=1)

    def test_received_items_are_reconnect_safe_and_gap_checked(self) -> None:
        state = empty_bridge_state()
        first = {"index": 0, "item_id": 100, "location_id": 200, "player": 1}
        second = {"index": 1, "item_id": 101, "location_id": 201, "player": 2}
        self.assertEqual(record_received_items(state, [first, second]), 2)
        self.assertEqual(record_received_items(state, [first, second]), 0)
        self.assertEqual(state["last_received_index"], 1)
        with self.assertRaises(ProtocolError):
            record_received_items(
                state,
                [{"index": 3, "item_id": 103, "location_id": 203, "player": 1}],
            )

    def test_unlock_state_is_validated_and_normalized(self) -> None:
        value = {
            "protocol": 1,
            "revision": 3,
            "slot": "Simon",
            "unlocked": {
                "heroes": ["squire", "squire"],
                "defenses": ["squire.spike_blockade"],
                "abilities": [],
                "maps": ["CAMPFF"],
                "max_equipment_quality": 2,
            },
        }
        validated = validate_unlock_state(value)
        self.assertEqual(validated["unlocked"]["heroes"], ["squire"])
        value["unlocked"]["max_equipment_quality"] = 20
        with self.assertRaises(ProtocolError):
            validate_unlock_state(value)

    def test_service_replay_does_not_duplicate_a_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "UDKGame" / "User"
            events.mkdir(parents=True)
            event_path = events / "DD1ArchipelagoEvent-2-testjson"
            event_path.write_text(json.dumps(VICTORY_EVENT) + "\n", encoding="utf-8")
            state_path = root / "state.json"

            self.assertEqual(process_once(root, state_path), (1, 2))
            self.assertEqual(process_once(root, state_path), (0, 0))
            state = load_bridge_state(state_path)
            self.assertEqual(len(state["pending_location_ids"]), 2)

    def test_service_persists_legacy_migration_without_new_events(self) -> None:
        legacy = {
            "protocol": 1,
            "processed_files": [],
            "observed_locations": {},
            "pending_location_ids": [],
            "acknowledged_location_ids": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / "state.json"
            state_path.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertEqual(process_once(root, state_path), (0, 0))
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["state_version"], 3)

    def test_unlock_ini_is_atomically_generated(self) -> None:
        value = {
            "protocol": 1,
            "revision": 4,
            "slot": "Simon",
            "unlocked": {
                "heroes": ["squire"],
                "defenses": ["squire.spike_blockade"],
                "abilities": [],
                "maps": ["CAMPDW"],
                "max_equipment_quality": 1,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DD1ArchipelagoUnlocks.ini"
            write_unlock_ini(path, value)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Revision=4", text)
            self.assertIn("UnlockedDefenses=squire.spike_blockade", text)


if __name__ == "__main__":
    unittest.main()
