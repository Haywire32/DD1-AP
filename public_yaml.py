"""Export the author's YAML using Archipelago's normal launcher and save dialog.

The build copies release/Dungeon Defenders.yaml into this package. Archipelago's
generic template generator has no per-world custom-file hook, so this component
offers the exact short public template without modifying Archipelago itself.
"""

from __future__ import annotations

import argparse
from importlib import resources
import logging
from pathlib import Path


TEMPLATE_NAME = "Dungeon Defenders.yaml"


def template_bytes() -> bytes:
    """Read the bundled file unchanged, including its comments and line endings."""
    return resources.files(__package__).joinpath(TEMPLATE_NAME).read_bytes()


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
        messagebox("Dungeon Defenders YAML", f"Saved:\n{result}\n\nEdit PlayerName to your slot name.")
    else:
        logging.info("Saved Dungeon Defenders YAML: %s", result)
