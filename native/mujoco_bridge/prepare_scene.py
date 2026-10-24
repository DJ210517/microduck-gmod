"""Prepare the original MicroDuck MJCF for the embedded MuJoCo bridge.

No game access. This deliberately leaves terrain empty unless a fragment is
supplied. Proxies are compiled with collision masks, parked out of the world;
the native bridge disables them after compilation to retain collision BVHs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENE = ROOT / 'upstream/microduck_rl/src/mjlab_microduck/robot/microduck/scene.xml'
ASSET_MARKER = 'MICRODUCK_WORLD_ASSETS'
WORLD_MARKER = 'MICRODUCK_WORLD_GEOMS'


def read_flat(path: Path, stack: tuple[Path, ...] = ()) -> ET.Element:
    """Expand includes and resolve asset files in their declaring XML directory."""
    path = path.resolve()
    if path in stack:
        raise ValueError(f'Recursive MJCF include: {path}')
    root = ET.parse(path).getroot()
    compiler = root.find('compiler')
    meshdir = compiler.get('meshdir', '') if compiler is not None else ''
    texturedir = compiler.get('texturedir', '') if compiler is not None else ''
    assetdir = compiler.get('assetdir', '') if compiler is not None else ''
    for node in root.iter():
        if node.tag in ('mesh', 'texture', 'hfield', 'skin') and node.get('file'):
            directory = meshdir if node.tag == 'mesh' else texturedir if node.tag == 'texture' else ''
            file = Path(node.get('file'))
            if not file.is_absolute():
                file = path.parent / (directory or assetdir) / file
            node.set('file', file.resolve().as_posix())
            # Explicit names survive staging paths / custom filename extensions.
            if node.tag == 'mesh' and not node.get('name'):
                node.set('name', file.stem)
    if compiler is not None:
        for key in ('meshdir', 'texturedir', 'assetdir'):
            compiler.attrib.pop(key, None)
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag == 'include':
                included = read_flat(path.parent / child.attrib['file'], (*stack, path))
                index = list(parent).index(child)
                parent.remove(child)
                for offset, element in enumerate(list(included)):
                    parent.insert(index + offset, element)
    return root


def section(root: ET.Element, tag: str) -> ET.Element:
    """Merge repeatable top-level sections while preserving element order."""
    nodes = root.findall(tag)
    if not nodes:
        return ET.SubElement(root, tag)
    result = nodes[0]
    for extra in nodes[1:]:
        result.extend(list(extra))
        root.remove(extra)
    return result


def add_terrain(root: ET.Element, path: Path) -> None:
    fragment = read_flat(path)
    if fragment.tag == 'worldbody':
        section(root, 'worldbody').extend(list(fragment))
    elif fragment.tag in ('mujoco', 'mujocoinclude'):
        for node in fragment:
            if node.tag not in ('worldbody', 'asset'):
                raise ValueError(f'Terrain fragment may contain only asset/worldbody, got {node.tag}')
            section(root, node.tag).extend(list(node))
    else:
        raise ValueError('Terrain must have a mujoco, mujocoinclude, or worldbody root')
    # Terrain may only be static world geometry; robot/proxy body IDs stay fixed.
    world = section(root, 'worldbody')
    for body in list(world):
        if body.tag == 'body' and body.get('name') != 'trunk_base':
            raise ValueError('Terrain fragments must use world geoms, not bodies')


def prepare_scene(source: Path = DEFAULT_SCENE, *, remove_floor: bool = True,
                  proxy_count: int = 32, terrain: Path | None = None,
                  timestep: float = .005) -> ET.Element:
    if not 0 <= proxy_count <= 32:
        raise ValueError('proxy_count must be between 0 and 32')
    if timestep <= 0:
        raise ValueError('timestep must be positive')
    root = read_flat(source)
    root.set('model', 'microduck_gmod')
    world = section(root, 'worldbody')
    assets = section(root, 'asset')
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag in ('visual', 'camera', 'light', 'texture', 'material'):
                parent.remove(child)
            elif child.tag == 'geom' and child.get('class') == 'visual':
                parent.remove(child)
            elif remove_floor and parent is world and child.tag == 'geom' and child.get('name') == 'floor':
                parent.remove(child)
        parent.attrib.pop('material', None)
    used_meshes = {node.get('mesh') for node in root.iter('geom') if node.get('mesh')}
    for node in list(assets):
        if node.tag == 'mesh' and node.get('name') not in used_meshes:
            assets.remove(node)
    option = section(root, 'option')
    option.set('timestep', format(timestep, '.12g'))
    if terrain:
        add_terrain(root, terrain)
    assets.append(ET.Comment(ASSET_MARKER))
    world.append(ET.Comment(WORLD_MARKER))
    for i in range(1, proxy_count + 1):
        body = ET.SubElement(world, 'body', name=f'md_proxy_{i}', mocap='true', pos=f'{i} 0 -1000')
        ET.SubElement(body, 'geom', name=f'md_proxy_geom_{i}', type='box', size='.05 .05 .05',
                      contype='1', conaffinity='1', friction='1 .005 .0001', group='5')
    return root


def write_scene(root: ET.Element, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SCENE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--terrain', type=Path)
    parser.add_argument('--keep-floor', action='store_true')
    parser.add_argument('--proxies', type=int, default=32)
    parser.add_argument('--timestep', type=float, default=.005)
    args = parser.parse_args()
    root = prepare_scene(args.source, remove_floor=not args.keep_floor,
                         proxy_count=args.proxies, terrain=args.terrain, timestep=args.timestep)
    write_scene(root, args.output)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
