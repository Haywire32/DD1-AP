"""Validate a manually selected DD1 installation."""

from __future__ import annotations

import os
import re
import hashlib
import json
from pathlib import Path
from typing import Callable, Optional


DDDK_DIRECTORY = "DungeonDefendersDevelopmentKit"
DDDK_EXECUTABLE = Path("Binaries") / "Win64" / "DunDefDevelopment.exe"
DDDK_RUNTIME_DLLS = (
    "wxmsw28u_core_vc_custom_64.dll",
    "wxmsw28u_richtext_vc_custom_64.dll",
    "wxmsw28u_vc_custom_64.dll",
    "vorbisenc_64.dll",
)
DDDK_APP_ID = "216840"
TC_DIRECTORY = "DD1ArchipelagoCurrent"
RETAIL_EXECUTABLE = Path("Binaries") / "Win64" / "DunDefGame.exe"
RETAIL_LAUNCH_FLAGS = ("-LANGUAGE=INT", "-windowed")
# The conversion is cooked only in INT. -LANGUAGE takes precedence over the
# native SystemSettings/GameLanguageOverride (including AUTO/OS language).
# Do not rewrite the user's generated INI just to select the cooked language.
REQUIRED_COOKED_FILES = (
    "Core.upk", "Engine.upk", "GameFramework.upk", "UDKGame.upk", "IpDrv.upk",
    "OnlineSubsystemSteamworks.upk", "DunDefEntry.upk", "DunDefTransition.upk",
    "DunDefMiscNoMedia.upk", "EmptyRoom.upk", "Startup_INT.upk",
    "TC_Textures.tfc", "TC_CharTextures.tfc", "GuidCache.upk",
    "GlobalShaderCache-PC-D3D-SM3.bin", "RefShaderCache_TC_-PC-D3D-SM3.upk",
)
STARTUP_URL = {
    "Protocol": "unreal", "Name": "Player", "Map": "DunDefEntry.udk",
    "LocalMap": "DunDefEntry.udk", "TransitionMap": "DunDefTransition.udk",
    "MapExt": "udk", "EXEName": "UDKGame.exe", "DebugEXEName": "DEBUG-UDKGame.exe",
    "SaveExt": "usa", "Port": "7777", "GameName": "Dungeon Defenders",
    "GameNameShort": "DunDef",
}


def read_unreal_ini(path: Path) -> str:
    raw = path.read_bytes()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    return raw.decode(encoding)


def _tc_root(root: Path, tc_directory: str) -> Path:
    if tc_directory not in (TC_DIRECTORY, "DD1ArchipelagoChaos"):
        raise ValueError("Unknown DD1 conversion directory.")
    return root / 'TotalConversions' / tc_directory


def _ini_settings(path: Path) -> dict[tuple[str, str], str]:
    try:
        contents = read_unreal_ini(path)
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Cannot read the DD1 mod configuration {path}. "
                         "Keep a backup; restore this file from the matching package "
                         "if it is a Default INI. Do not delete saves or the Config folder.") from error
    if '\x00' in contents:
        raise ValueError(f"DD1 mod configuration contains invalid NUL bytes: {path}. "
                         "Keep a backup before repairing this file.")
    result = {}
    section = ''
    for raw in contents.splitlines():
        line = raw.strip()
        if not line or line.startswith((';', '#', '//')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip().casefold()
        elif '=' in line:
            key, value = line.split('=', 1)
            result[(section, key.strip().casefold())] = value.strip().strip('"').casefold()
    return result


def verify_conversion_package(root: Path, *, tc_directory: str = TC_DIRECTORY) -> str:
    """Read-only integrity check for new packages; older packages remain supported.

    This is an accidental corruption/mixed-install check, not a security signature.
    The manifest contains immutable cooked files only, never saves or settings.
    """
    tc = _tc_root(root, tc_directory)
    manifest = tc / 'package-manifest.json'
    if not manifest.exists():
        return 'legacy package (no integrity manifest)'
    try:
        if manifest.stat().st_size > 128_000:
            raise ValueError('manifest too large')
        data = json.loads(manifest.read_text(encoding='utf-8-sig'))
        files = data['files']
        if data.get('format') != 1 or not isinstance(files, dict) or not 1 <= len(files) <= 256:
            raise ValueError('invalid manifest format')
        if not {f'CookedPCConsole/{name}' for name in REQUIRED_COOKED_FILES} <= files.keys():
            raise ValueError('manifest omits required cooked files')
        for name, expected in files.items():
            # Never follow manifest-controlled paths outside this exact asset folder.
            if not re.fullmatch(r'CookedPCConsole/[A-Za-z0-9_.-]+\.(?:upk|tfc|bin)', name):
                raise ValueError('invalid manifest path')
            if not isinstance(expected, dict) or type(expected.get('size')) is not int or expected['size'] <= 0:
                raise ValueError('invalid manifest size')
            if not re.fullmatch(r'[0-9a-f]{64}', str(expected.get('sha256', ''))):
                raise ValueError('invalid manifest hash')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError) as error:
        raise ValueError(f"Cannot verify DD1 mod package: {manifest}. "
                         "Re-extract the full matching TotalConversions ZIP; keep saves and settings.") from error
    for name, expected in files.items():
        path = tc / name
        if not path.resolve().is_relative_to(tc.resolve()):
            raise ValueError(f"DD1 mod package points outside the conversion: {path}")
        if not path.is_file() or path.stat().st_size != expected['size']:
            raise ValueError(f"DD1 mod file is missing or incomplete: {path}. "
                             "Re-extract the full matching TotalConversions ZIP and replace packaged files. "
                             "Do not delete saves or the Config folder.")
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected['sha256']:
            raise ValueError(f"DD1 mod file differs from its package (mixed versions or damaged file): {path}. "
                             "Re-extract the full matching TotalConversions ZIP and replace packaged files. "
                             "Do not delete saves or the Config folder.")
    return f'verified {len(files)} cooked files'


def validate_retail_install(root: Path, *, tc_directory: str = TC_DIRECTORY) -> None:
    """Read-only preflight for the cooked, Local-only regular-DD1 conversion."""
    tc = _tc_root(root, tc_directory)
    required = [root / RETAIL_EXECUTABLE]
    required += [tc / "CookedPCConsole" / name for name in REQUIRED_COOKED_FILES]
    for path in required:
        if not path.is_file() or not path.stat().st_size:
            raise FileNotFoundError(f"Regular DD1 mod installation is incomplete: {path}. "
                                    "Use the full retail-conversion package, not the older DDDK release.")
    for suffix in ("Engine", "Game"):
        for prefix in ("Default", "UDK"):
            path = tc / "Config" / f"{prefix}{suffix}.ini"
            # Retail creates generated settings on first launch. If present,
            # they must not override the mod with the ordinary game classes.
            if prefix == "UDK" and not path.exists():
                continue
            settings = _ini_settings(path)
            expected = ({
                ("engine.engine", "gameviewportclientclassname"): "dd1archipelago.apviewportclient",
                ("onlinesubsystemsteamworks.onlinesubsystemsteamworks", "busevac"): "false",
            } if suffix == "Engine" else {
                ("engine.gameinfo", "defaultgame"): "dd1archipelago.apgameinfo",
                ("engine.gameinfo", "defaultservergame"): "dd1archipelago.apgameinfo",
            })
            for key, value in expected.items():
                if settings.get(key) != value:
                    raise ValueError(f"Local-only DD1 mod configuration is not enabled in {path} ({key[1]}). "
                                     "Replace the mod configuration from the matching release before launching.")
            if suffix == 'Engine':
                # Default INIs are deltas with inheritance. Generated UDKEngine
                # is a complete cache: missing URL fields there reproduce the
                # broken configuration in the BearKat report. Do not treat it
                # as another delta, and do not silently erase user preferences.
                keys = ('Map', 'LocalMap') if prefix == 'Default' else (
                    'Protocol', 'Map', 'LocalMap', 'TransitionMap', 'MapExt', 'Port')
                bad = [key for key in keys if not settings.get(('url', key.casefold()))]
                for key in ('Map', 'LocalMap'):
                    value = settings.get(('url', key.casefold()), '')
                    if value and value not in ('dundefentry', 'dundefentry.udk'):
                        bad.append(key)
                if bad:
                    action = ("Install the corrected DefaultEngine.ini from the new package."
                              if prefix == 'Default' else
                              "Back up this file, then restore its [URL] startup entries from the "
                              "package's DefaultEngine.ini. Do not replace the entire file if you "
                              "want to keep your graphics settings.")
                    raise ValueError(f"DD1 startup settings are missing or invalid in {path}: "
                                     + ', '.join(bad) + '. ' + action +
                                     " No files were changed. Do not delete saves or the Config folder.")


def find_retail_root(explicit: Optional[Path] = None, *,
                     tc_directory: str = TC_DIRECTORY) -> Path:
    """Validate only the folder supplied by the player."""
    if explicit is None:
        raise ValueError("Select your Dungeon Defenders game folder.")
    root = Path(explicit).expanduser().resolve()
    validate_retail_install(root, tc_directory=tc_directory)
    return root


def select_retail_root(explicit: Optional[Path], settings_path: Path,
                       choose_folder: Callable[[], Optional[str]], *,
                       force_select: bool = False,
                       tc_directory: str = TC_DIRECTORY) -> Optional[Path]:
    """Remember a validated manual choice; cancellation changes nothing."""
    if explicit is None and not force_select:
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            saved = data.get("game_root") if isinstance(data, dict) and data.get("version") == 1 else None
            if isinstance(saved, str) and saved and Path(saved).is_absolute():
                return find_retail_root(Path(saved), tc_directory=tc_directory)
        except (OSError, ValueError, UnicodeError):
            pass
    if explicit is None:
        selected = choose_folder()
        if not selected:
            return None
        explicit = Path(selected)
    root = find_retail_root(explicit, tc_directory=tc_directory)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings_path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps({"version": 1, "game_root": str(root)}) + "\n",
                             encoding="utf-8")
        os.replace(temporary, settings_path)
    finally:
        temporary.unlink(missing_ok=True)
    return root


def validate_dddk_install(root: Path) -> None:
    """Check the installed mod without creating directories or changing files."""
    required_files = (
        DDDK_EXECUTABLE,
        Path("TotalConversions") / TC_DIRECTORY / "Script" / "DD1Archipelago.u",
        Path("TotalConversions") / TC_DIRECTORY / "Script" / "UDKGame.u",
        Path("TotalConversions") / TC_DIRECTORY / "Script" / "Core.u",
        Path("TotalConversions") / TC_DIRECTORY / "Script" / "Engine.u",
    )
    for relative in required_files:
        target = root / relative
        if not target.is_file() or target.stat().st_size == 0:
            if relative == DDDK_EXECUTABLE:
                raise FileNotFoundError(
                    f"Development Kit executable is missing or empty: {target}. "
                    "Check that Steam has finished installing Dungeon Defenders Development Kit "
                    "and that the selected folder is the Development Kit folder."
                )
            raise FileNotFoundError(
                f"DD1 mod installation is incomplete: missing or empty {target}. "
                "Merge DD1ArchipelagoCurrent from the full updated release into this "
                "Development Kit's TotalConversions folder and replace matching files. "
                "Do not delete the existing folder or its saves."
            )

    for filename in DDDK_RUNTIME_DLLS:
        target = root / DDDK_EXECUTABLE.parent / filename
        if not target.is_file() or target.stat().st_size == 0:
            raise FileNotFoundError(
                f"Development Kit runtime file is missing or empty: {target}. "
                "In Steam, install/update both Dungeon Defenders and its Development Kit. "
                "Then copy the contents of your normal Dungeon Defenders installation "
                "into the Development Kit folder, replacing matching files as described "
                "in the installation guide. Do not download individual DLL files from websites."
            )

    checks = {
        "DefaultEngine.ini": (("Engine.Engine", "GameViewportClientClassName", "DD1Archipelago.APViewportClient"),),
        "UDKEngine.ini": (("Engine.Engine", "GameViewportClientClassName", "DD1Archipelago.APViewportClient"),),
        "DefaultGame.ini": (
            ("Engine.GameInfo", "DefaultGame", "DD1Archipelago.APGameInfo"),
            ("Engine.GameInfo", "DefaultServerGame", "DD1Archipelago.APGameInfo"),
        ),
        "UDKGame.ini": (
            ("Engine.GameInfo", "DefaultGame", "DD1Archipelago.APGameInfo"),
            ("Engine.GameInfo", "DefaultServerGame", "DD1Archipelago.APGameInfo"),
        ),
    }
    for filename, expected_settings in checks.items():
        path = root / "TotalConversions" / TC_DIRECTORY / "Config" / filename
        try:
            contents = read_unreal_ini(path)
        except (OSError, UnicodeError) as error:
            raise ValueError(
                f"Cannot read the DD1 mod configuration {path}: {error}. "
                "Merge DD1ArchipelagoCurrent from the latest release into the Development Kit's "
                "TotalConversions folder and replace matching files. Do not delete the existing folder."
            ) from error
        # Unreal INIs allow repeated keys/sections, which ConfigParser rejects.
        # Read the final scalar value, matching the activation entries we ship.
        settings: dict[tuple[str, str], str] = {}
        section = ""
        for raw_line in contents.splitlines():
            line = raw_line.strip()
            if not line or line.startswith((";", "#", "//")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().casefold()
            elif "=" in line:
                key, value = line.split("=", 1)
                settings[(section, key.strip().casefold())] = value.strip().casefold()
        for section, key, expected in expected_settings:
            if settings.get((section.casefold(), key.casefold())) != expected.casefold():
                raise ValueError(
                    f"The DD1 mod is not enabled in {path} ({key}). "
                    "Merge DD1ArchipelagoCurrent from the latest release into the Development Kit's "
                    "TotalConversions folder and replace matching files. Do not delete the existing folder."
                )


def find_dddk_root(explicit: Optional[Path] = None) -> Path:
    """Validate an explicitly selected legacy Development Kit folder."""
    if explicit is None:
        raise ValueError("Select the Development Kit folder with --dddk-root.")
    root = Path(explicit).expanduser().resolve()
    validate_dddk_install(root)
    return root
