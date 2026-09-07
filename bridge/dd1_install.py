"""Locate regular Steam DD1 without scanning disks; retain legacy DDDK checks."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional


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


def validate_retail_install(root: Path) -> None:
    """Read-only preflight for the cooked, Local-only regular-DD1 conversion."""
    tc = root / "TotalConversions" / TC_DIRECTORY
    required = [root / RETAIL_EXECUTABLE]
    required += [tc / "CookedPCConsole" / name for name in (
        "Startup_INT.upk", "TC_Textures.tfc", "TC_CharTextures.tfc",
        "RefShaderCache_TC_-PC-D3D-SM3.upk",
    )]
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
            settings = {}
            section = ""
            for raw in path.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if not line or line.startswith((";", "#", "//")):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].casefold()
                elif "=" in line:
                    key, value = line.split("=", 1)
                    settings[(section, key.strip().casefold())] = value.strip().casefold()
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


def find_retail_root(explicit: Optional[Path] = None, *,
                     steam_install_roots: Optional[Iterable[Path]] = None) -> Path:
    """Use Steam's registered libraries or the user's explicit folder, never a disk scan."""
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        validate_retail_install(root)
        return root
    roots = list(steam_install_roots) if steam_install_roots is not None else _registered_steam_roots()
    candidates = []
    active = set()
    for steam in _unique_paths(roots):
        for library in _library_roots(steam):
            installed = _manifest_install(library, "65800")
            if installed is not None:
                active.add(installed.resolve())
                candidates.append(installed)
            candidates.append(library / "steamapps" / "common" / "Dungeon Defenders")
    valid, errors = [], []
    for candidate in _unique_paths(candidates):
        if not (candidate / RETAIL_EXECUTABLE).is_file():
            continue
        try:
            validate_retail_install(candidate)
        except (OSError, ValueError) as error:
            errors.append(str(error))
        else:
            valid.append(candidate.resolve())
    preferred = [path for path in valid if path in active] or valid
    if len(preferred) == 1:
        return preferred[0]
    if len(preferred) > 1:
        raise ValueError("More than one regular DD1 mod installation was found. Select one with --game-root.")
    if errors:
        raise ValueError("No usable regular DD1 mod installation. " + " ".join(errors))
    raise FileNotFoundError("Regular Dungeon Defenders with the AP conversion was not found in Steam's libraries. "
                            "Install the conversion or select its game folder with --game-root.")


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
            contents = path.read_text(encoding="utf-8-sig")
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


def _manifest_install(library_root: Path, app_id: str = DDDK_APP_ID) -> Optional[Path]:
    """Return Steam's installed copy, if its app manifest marks it installed."""
    manifest = library_root / "steamapps" / f"appmanifest_{app_id}.acf"
    try:
        contents = manifest.read_text(encoding="utf-8-sig")
        fields = dict(re.findall(r'"([^"\\]+)"\s*"([^"\\]*)"', contents))
        if fields.get("appid") != app_id or not int(fields.get("StateFlags", "0")) & 4:
            return None
        directory = fields.get("installdir", "")
        if not directory or directory in {".", ".."} or "/" in directory or "\\" in directory:
            return None
        return library_root / "steamapps" / "common" / directory
    except (OSError, UnicodeError, ValueError):
        return None


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(os.fspath(path)))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _registered_steam_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        import winreg

        registry_locations = (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        )
        for hive, key_name, value_name in registry_locations:
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                if isinstance(value, str) and value:
                    roots.append(Path(value))
            except OSError:
                pass
    except ImportError:
        pass

    for environment_name in ("ProgramFiles(x86)", "ProgramFiles"):
        program_files = os.environ.get(environment_name)
        if program_files:
            roots.append(Path(program_files) / "Steam")
    roots.append(Path(r"C:\Program Files (x86)\Steam"))
    return _unique_paths(roots)


def _library_roots(steam_root: Path) -> list[Path]:
    roots = [steam_root]
    library_file = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        contents = library_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return roots

    for match in re.finditer(r'"path"\s*"((?:\\.|[^"\\])*)"', contents):
        value = match.group(1).replace(r"\\", "\\")
        if value:
            roots.append(Path(value))
    return _unique_paths(roots)


def _is_dddk_root(path: Path) -> bool:
    return (path / DDDK_EXECUTABLE).is_file()


def find_dddk_root(
    explicit: Optional[Path] = None,
    *,
    steam_install_roots: Optional[Iterable[Path]] = None,
) -> Path:
    """Return the installed DDDK root or raise one concise error."""

    if explicit is not None:
        root = Path(explicit).expanduser()
        validate_dddk_install(root)
        return root.resolve()

    steam_roots = (
        list(steam_install_roots)
        if steam_install_roots is not None
        else _registered_steam_roots()
    )
    candidates: list[Path] = []
    active_installs: set[Path] = set()
    for steam_root in _unique_paths(Path(root) for root in steam_roots):
        for library_root in _library_roots(steam_root):
            active = _manifest_install(library_root)
            if active is not None:
                active_installs.add(active.resolve())
                candidates.append(active)
            candidates.append(
                library_root / "steamapps" / "common" / DDDK_DIRECTORY
            )
    valid: list[Path] = []
    invalid: list[str] = []
    for candidate in _unique_paths(candidates):
        if _is_dddk_root(candidate):
            try:
                validate_dddk_install(candidate)
            except (OSError, ValueError) as error:
                invalid.append(str(error))
            else:
                valid.append(candidate.resolve())
    preferred = [candidate for candidate in valid if candidate in active_installs] or valid
    if len(preferred) == 1:
        return preferred[0]
    if len(preferred) > 1:
        raise ValueError(
            "More than one Development Kit has the DD1 mod installed: "
            + "; ".join(str(path) for path in preferred)
            + ". Select one by launching this client with --dddk-root followed by its folder."
        )
    if invalid:
        raise ValueError("No usable DD1 mod installation was found. " + " ".join(invalid))

    raise FileNotFoundError(
        "Dungeon Defenders Development Kit was not found in any Steam library. "
        "Install it in Steam, or launch this client with --dddk-root followed by its folder."
    )
