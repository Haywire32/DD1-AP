"""Dungeon Defenders world and launcher components."""
from .world import DungeonDefendersWorld
from .options import DungeonDefendersOptions
from worlds.LauncherComponents import Component, Type, components
from worlds.LauncherComponents import launch as launch_component
from .public_yaml import install_template_export
from .runtime_profile import CLIENT_TITLE

install_template_export()


def launch_client(*args):
    from .Client import launch
    launch_component(launch, name=CLIENT_TITLE, args=args)


def launch_yaml_template(*args):
    from .public_yaml import launch
    launch_component(launch, name='Dungeon Defenders YAML', args=args)


components.append(Component(CLIENT_TITLE, func=launch_client,
    component_type=Type.CLIENT, game_name='Dungeon Defenders', supports_uri=True,
    description='Local-only Dungeon Defenders Total Conversion.'))
components.append(Component('Dungeon Defenders YAML', func=launch_yaml_template,
    component_type=Type.TOOL, description="Save the author's Dungeon Defenders YAML."))
