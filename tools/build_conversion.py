"""Package known-good cooked assets, current defaults and an integrity manifest.

No recooking: a caller must explicitly supply the verified baseline ZIP. This
avoids silently replacing working retail content with development-kit assets.
Optional freshly compiled/cooked script and texture output can be supplied
explicitly; all other verified baseline assets remain byte-for-byte intact.
The two shipped defaults are replaced. Never package generated UDK INIs,
hero saves, per-seed state or scripts/executables from a local game install.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
from dd1_install import REQUIRED_COOKED_FILES, STARTUP_URL, _ini_settings

PREFIX = 'TotalConversions/DD1ArchipelagoCurrent/'


def build(root: Path, baseline: Path, output: Path, cooked: Path | None = None) -> Path:
    overrides = {} if cooked is None else {
        PREFIX+'CookedPCConsole/'+name: cooked/name
        for name in ('Startup_INT.upk', 'TC_Textures.tfc')}
    for path in overrides.values():
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Missing newly cooked asset: {path.name}')
    settings = _ini_settings(root / 'release/Config/DefaultEngine.ini')
    for key, value in STARTUP_URL.items():
        if settings.get(('url', key.casefold())) != value.casefold():
            raise ValueError(f'Incomplete packaged startup defaults: {key}')
    if settings.get(('systemsettings', 'gamelanguageoverride')) != 'int':
        raise ValueError('Native startup language must be INT')
    with ZipFile(baseline) as base:
        names = base.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate baseline ZIP entries')
        assets = sorted(n for n in names if n.startswith(PREFIX+'CookedPCConsole/') and not n.endswith('/'))
        if not {PREFIX+'CookedPCConsole/'+n for n in REQUIRED_COOKED_FILES} <= set(assets):
            raise ValueError('Baseline lacks required cooked files')
        if not set(overrides) <= set(assets):
            raise ValueError('Cooked overrides must replace existing baseline assets')
        # Build only from the narrow allowlist of packaged content locations.
        import re
        if any(not re.fullmatch(re.escape(PREFIX)+r'CookedPCConsole/[A-Za-z0-9_.-]+\.(?:upk|tfc|bin)', n) for n in assets):
            raise ValueError('Unexpected asset path in baseline')
        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, 'x', ZIP_DEFLATED, compresslevel=6) as out:
            files = {}
            for name in assets:
                digest = hashlib.sha256()
                size = 0
                source = overrides[name].open('rb') if name in overrides else base.open(name)
                with source as src, out.open(name, 'w', force_zip64=True) as dst:
                    while chunk := src.read(1024*1024):
                        digest.update(chunk)
                        size += len(chunk)
                        dst.write(chunk)
                files[name.removeprefix(PREFIX)] = dict(size=size, sha256=digest.hexdigest())
            for name in ('DefaultEngine.ini', 'DefaultGame.ini'):
                out.write(root / 'release/Config' / name, PREFIX+'Config/'+name)
            out.writestr(PREFIX+'package-manifest.json', json.dumps(dict(format=1, files=files), indent=2)+'\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cooked', type=Path, help='Explicit freshly verified cooked script/texture directory')
    args = parser.parse_args()
    print(build(ROOT, args.baseline, args.output, args.cooked))
