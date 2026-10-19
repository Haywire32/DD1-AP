"""Session-bound DeathLink file bridge, also usable by a native Linux client."""
import configparser
import os
import secrets
import time
from pathlib import Path


class DeathLinkBridge:
    def __init__(self, config: Path, seed: str, enabled: bool, mode: str = 'hero_death'):
        if mode not in ('hero_death', 'crystal_destruction'):
            raise ValueError('Unknown DeathLink mode.')
        self.config = config
        self.seed = seed
        self.enabled = enabled
        self.mode = mode
        self.session = secrets.token_hex(16)
        self.incoming = 0
        self.outgoing = 0
        self.pulse = 0
        self.last_write = 0.0
        self.live_status = None
        self.live_status_time = 0.0

    def snapshot(self, connected=True):
        return (f'APDEATH1|{self.seed}|{self.session}|{int(self.enabled and connected)}|'
                f'{int(self.mode == "crystal_destruction")}|{self.incoming}|{self.outgoing}\r\n').encode('ascii')

    def accept_status(self, line):
        parts = line.strip().split('|')
        if len(parts) != 7 or parts[0] != 'DD1DEATH1' or parts[1:3] != [self.seed, self.session]:
            return False
        try:
            count, sequence = int(parts[4]), int(parts[5])
        except ValueError:
            return False
        if parts[3] not in ('0', '1') or min(count, sequence) < 0:
            return False
        parser = configparser.ConfigParser()
        parser['state'] = {'bReady': str(parts[3] == '1'), 'LocalDeaths': str(count),
                           'SeenSequence': str(sequence), 'Reason': parts[6]}
        self.live_status = parser['state']
        self.live_status_time = time.monotonic()
        return True

    def write(self, connected: bool, force=False):
        now = time.monotonic()
        if not force and now - self.last_write < 1.0:
            return
        self.pulse += 1
        path = self.config / 'UDKDD1ArchipelagoDeathLinkInput.ini'
        content = ('[DD1Archipelago.APDeathLinkInput]\n'
                   f'SeedIdentity={self.seed}\nSession={self.session}\n'
                   f'bEnabled={str(self.enabled and connected).lower()}\n'
                   f'bCrystalDestruction={str(self.mode == "crystal_destruction").lower()}\n'
                   f'Sequence={self.incoming}\nPulse={self.pulse}\n')
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        self.last_write = now

    def status(self):
        if self.live_status is not None:
            return self.live_status if time.monotonic() - self.live_status_time < 5 else None
        path = self.config / 'UDKDD1ArchipelagoDeathLinkOutput.ini'
        parser = configparser.ConfigParser(strict=False)
        try:
            parser.read_string(path.read_text(encoding='utf-8-sig'))
            state = parser['DD1Archipelago.APDeathLinkState']
            if state.get('Session') != self.session or state.get('SeedIdentity') != self.seed:
                return None
            return state
        except (OSError, UnicodeError, configparser.Error, KeyError):
            return None

    def receive(self, live_connected=False):
        state = self.status()
        if not self.enabled or (not live_connected and state is None):
            return False
        # A live status is only a heartbeat, not permission to kill. Readiness
        # may have changed since that report (respawn, map load, hero swap).
        # The engine checks the current world/pause/target at delivery time.
        # Keep the legacy file-only safety check; it has no live delivery path.
        if not live_connected and self.live_status is None and not state.getboolean('bReady', fallback=False):
            return False
        self.incoming += 1
        if not live_connected and self.live_status is None:
            self.write(True, force=True)
        return True

    def poll_death(self):
        state = self.status()
        if state is None:
            return False
        count = state.getint('LocalDeaths', fallback=0)
        if count <= self.outgoing:
            return False
        self.outgoing = count
        return self.enabled
