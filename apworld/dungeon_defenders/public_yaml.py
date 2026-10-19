"""Export the author's YAML using Archipelago's normal launcher and save dialog.

The build copies release/Dungeon Defenders.yaml into this package. Both the DD1
export button and normal Generate Template Options return that authored file.
The latter uses a narrow post-generation wrapper; other games are unchanged.
"""

from __future__ import annotations

import argparse
from importlib import resources
import logging
from pathlib import Path
from functools import wraps


TEMPLATE_NAME = "Dungeon Defenders.yaml"


def template_bytes() -> bytes:
    """Read the bundled file unchanged, including its comments and line endings."""
    return resources.files(__package__).joinpath(TEMPLATE_NAME).read_bytes()


def install_template_export() -> None:
    """Replace only DD1's just-generated default template, never user YAMLs.

    AP 0.6.7 has no per-world authored-file hook. Preserve its complete generator
    and replace DD1's output only after it has successfully generated that file.
    Importing the APWorld alone performs no file operations. Presets and every
    other world's template keep the native generator's output.
    """
    import Options

    original = Options.generate_yaml_templates
    if getattr(original, '_dd1_authored_template', False):
        return

    @wraps(original)
    def generate(target_folder, *args, **kwargs):
        result = original(target_folder, *args, **kwargs)
        destination = Path(target_folder) / TEMPLATE_NAME
        if destination.is_file():
            destination.write_bytes(template_bytes())
        return result

    generate._dd1_authored_template = True
    Options.generate_yaml_templates = generate


def export_template(destination: str | Path, *, overwrite: bool = False) -> Path:
    destination = Path(destination)
    if destination.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Choose a filename ending in .yaml or .yml.")
    content = template_bytes()
    # CLI/test exports must never overwrite someone's edited options implicitly.
    # The interactive Save As dialog asks before replacing a selected file.
    with destination.open("wb" if overwrite else "xb") as output:
        output.write(content)
    return destination


def launch(*args: str) -> None:
    from Utils import messagebox, save_filename

    parser = argparse.ArgumentParser(description="Save the public Dungeon Defenders YAML.")
    parser.add_argument("--output", type=Path, help="Save to this new YAML file without a dialog.")
    options = parser.parse_args(args)
    try:
        destination = options.output
        if destination is None:
            destination = save_filename(
                "Save Dungeon Defenders YAML", (("YAML", (".yaml", ".yml")),), TEMPLATE_NAME,
            )
            if not destination:
                logging.info(
                    "No YAML saved. You can also use Dungeon Defenders.yaml from the public release download."
                )
                return
        result = export_template(destination, overwrite=options.output is None)
    except Exception as error:
        message = (
            f"Could not save the Dungeon Defenders YAML: {error}\n\n"
            "You can use Dungeon Defenders.yaml from the public release download instead."
        )
        if options.output is not None:
            raise RuntimeError(message) from error
        messagebox("Dungeon Defenders YAML", message, error=True)
        return
    if options.output is None:
        messagebox("Dungeon Defenders YAML", f"Saved:\n{result}\n\nEdit the name setting to your slot name.")
    else:
        logging.info("Saved Dungeon Defenders YAML: %s", result)
