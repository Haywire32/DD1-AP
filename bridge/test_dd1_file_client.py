import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_dd1_client import client, ClientPortabilityTests

class FileClientTests(unittest.TestCase):
    def context(self, root):
        ctx=ClientPortabilityTests().make_context(root)
        ctx.state_path=root/'state.json'
        client.atomic_write_json(ctx.state_path,client.empty_bridge_state())
        ctx._apply_unlocks()
        return ctx

    def test_linux_atomic_complete_snapshot_and_update(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','linux'):
            ctx=self.context(Path(d))
            ctx._publish_file_snapshot()
            path=Path(d)/'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm'
            first=path.read_text()
            lines=first.splitlines()
            self.assertEqual(lines[-1],'END|'+lines[0])
            self.assertEqual(int(lines[0].split('|')[-1]),len(lines)-2)
            self.assertIn('APSTATE11|',lines[1])
            self.assertIn('APSHOP',first)
            self.assertFalse(path.with_suffix('.tmp').exists())
            ctx._publish_file_snapshot()
            self.assertEqual(first,path.read_text())
            ctx._file_write_time=-10
            ctx._publish_file_snapshot()
            self.assertEqual(path.read_text().splitlines()[0].split('|')[3],'2')

    def test_windows_no_files(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','win32'):
            ctx=self.context(Path(d))
            ctx._publish_file_snapshot()
            self.assertFalse((Path(d)/'Binaries/Web').exists())

    def test_deathlink_heartbeat_marks_server_disconnect(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','linux'):
            ctx=self.context(Path(d))
            ctx.death_bridge=client.DeathLinkBridge(ctx.unlock_path.parent,ctx._live_seed_identity(),True)
            ctx.server=SimpleNamespace(socket=SimpleNamespace(closed=False))
            ctx._publish_file_snapshot()
            path=Path(d)/'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm'
            line=next(v for v in path.read_text().splitlines() if v.startswith('APDEATH1|'))
            self.assertEqual(line.split('|')[3],'1')
            ctx.server.socket.closed=True; ctx._file_write_time=-10
            ctx._publish_file_snapshot()
            line=next(v for v in path.read_text().splitlines() if v.startswith('APDEATH1|'))
            self.assertEqual(line.split('|')[3],'0')

    def test_ack_requires_current_client_session(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','linux'):
            ctx=self.context(Path(d)); ctx._publish_file_snapshot()
            path=ctx.unlock_path.parent/'UDKDD1ArchipelagoFileStatus.ini'
            prefix='[DD1Archipelago.APFileSnapshotStatus]\nSeedIdentity='+ctx._live_seed_identity()+'\nRevision=3\nSession='
            path.write_text(prefix+'old-session\n')
            ctx._read_file_ack(); self.assertFalse(hasattr(ctx,'_file_ack'))
            path.write_text(prefix+ctx._file_session+'\n')
            ctx._read_file_ack(); self.assertEqual(ctx._file_ack,3)

    def test_malformed_packet_leaves_previous_snapshot_intact(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','linux'):
            ctx=self.context(Path(d)); ctx._publish_file_snapshot()
            path=Path(d)/'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm'
            previous=path.read_bytes(); ctx._file_write_time=-10
            ctx.live_snapshot += '<!--#include file="other"-->\n'
            with self.assertRaises(client.ProtocolError): ctx._publish_file_snapshot()
            self.assertEqual(previous,path.read_bytes())

    def test_failed_replace_keeps_previous_snapshot_and_retries(self):
        with tempfile.TemporaryDirectory() as d, patch.object(client.sys,'platform','linux'):
            ctx=self.context(Path(d)); ctx._publish_file_snapshot()
            path=Path(d)/'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm'
            previous=path.read_bytes(); ctx._file_write_time=-10
            with patch.object(Path,'replace',side_effect=PermissionError):
                with self.assertRaises(PermissionError): ctx._publish_file_snapshot()
            self.assertEqual(previous,path.read_bytes())
            self.assertEqual(ctx._file_sequence,1)
            ctx._publish_file_snapshot(); self.assertEqual(ctx._file_sequence,2)

if __name__=='__main__': unittest.main(defaultTest='FileClientTests')
