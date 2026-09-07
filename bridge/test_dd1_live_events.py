import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dd1_bridge_service as service
from dd1_protocol import ProtocolError, empty_bridge_state, load_bridge_state, write_unlock_ini, switch_hero_profile


class LiveEventTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.seed = service.live_seed_identity("seed", 0, "Haywire")
        service.atomic_write_json(self.path, empty_bridge_state())

    def event(self, event="wave_complete", difficulty="EGD_EASY", wave=1, seed=None):
        return f"DD1EVENT1|{seed or self.seed}|{event}|DD_Lev_02|{wave}|{difficulty}\r\n".encode()

    def test_persists_before_ack_and_retry_after_restart_is_idempotent(self):
        ack, changed = service.receive_live_event(self.event(), self.path, self.seed)
        self.assertTrue(changed)
        state = load_bridge_state(self.path)
        self.assertEqual(len(state["pending_location_ids"]), 1)
        self.assertTrue(ack.startswith(b"DD1ACK1|"))
        again, changed = service.receive_live_event(self.event(), self.path, self.seed)
        self.assertEqual(ack, again)
        self.assertFalse(changed)
        self.assertEqual(state, load_bridge_state(self.path))

    def test_no_ack_on_disk_failure_and_retry_recovers(self):
        with patch.object(service, "atomic_write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                service.receive_live_event(self.event(), self.path, self.seed)
        self.assertFalse(load_bridge_state(self.path)["processed_files"])
        self.assertTrue(service.receive_live_event(self.event(), self.path, self.seed)[1])

    def test_wrong_seed_cannot_change_state(self):
        before = self.path.read_bytes()
        other = service.live_seed_identity("other", 0, "Haywire")
        with self.assertRaises(ProtocolError):
            service.receive_live_event(self.event(seed=other), self.path, self.seed)
        self.assertEqual(before, self.path.read_bytes())

    def test_seed_identity_distinguishes_team_slot_and_filename_collisions(self):
        identities = {
            service.live_seed_identity("seed", 0, "A B"),
            service.live_seed_identity("seed", 0, "A_B"),
            service.live_seed_identity("seed", 1, "A B"),
            service.live_seed_identity("seed2", 0, "A B"),
        }
        self.assertEqual(len(identities), 4)

    def test_rejects_malformed_events_without_changing_state(self):
        before = self.path.read_bytes()
        for line in (b"x" * 513, self.event().replace(b"|1|", b"|-1|"),
                     self.event().replace(b"DD_Lev_02", b"../x"),
                     self.event().replace(b"DD_Lev_02", b"UnknownMap"),
                     self.event().replace(b"EGD_EASY", b"EGD_EASY\nInjected=1"),
                     self.event(event="session_start"), b"\xff", self.event(wave=99)):
            with self.subTest(line=line), self.assertRaises(ProtocolError):
                service.receive_live_event(line, self.path, self.seed)
        self.assertEqual(before, self.path.read_bytes())

    def test_hard_victory_keeps_difficulty_cascade(self):
        service.receive_live_event(self.event("level_victory", "EGD_HARD", 5), self.path, self.seed)
        state = load_bridge_state(self.path)
        self.assertIn("dd1.campaign.CAMPDW.victory.hard", state["victory_history"])
        self.assertEqual(len(state["pending_location_ids"]), 3)

    def test_seed_identity_is_written_to_startup_config(self):
        value = {"protocol": 1, "revision": 1, "slot": "Haywire", "unlocked": {
            "heroes": ["squire"], "defenses": [], "abilities": [], "maps": ["CAMPDW"],
            "max_equipment_quality": 19}}
        path = self.path.with_suffix(".ini")
        write_unlock_ini(path, value, seed_identity=self.seed)
        self.assertIn(f"SeedIdentity={self.seed}", path.read_text())
        with self.assertRaises(ProtocolError):
            write_unlock_ini(path, value, seed_identity="bad\nInjected=1")

    def test_seed_profiles_restore_consumed_rewards_with_the_heroes(self):
        root = Path(self.directory.name)
        tc, profiles = root / "tc", root / "profiles"
        (tc / "Config").mkdir(parents=True)
        rewards = tc / "Config" / "UDKDD1ArchipelagoRewards.ini"
        switch_hero_profile(tc, profiles, "seed A")
        (tc / "DunDefHeroes.dun").write_bytes(b"heroes A")
        rewards.write_text("AppliedXPRewards=3\nAppliedManaRewards=2\n")
        switch_hero_profile(tc, profiles, "seed B")
        self.assertFalse(rewards.exists())
        self.assertFalse((tc / "DunDefHeroes.dun").exists())
        (tc / "DunDefHeroes.dun").write_bytes(b"heroes B")
        rewards.write_text("AppliedXPRewards=1\n")
        switch_hero_profile(tc, profiles, "seed A")
        self.assertEqual((tc / "DunDefHeroes.dun").read_bytes(), b"heroes A")
        self.assertIn("AppliedXPRewards=3", rewards.read_text())


if __name__ == "__main__":
    unittest.main()
