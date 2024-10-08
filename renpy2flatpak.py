#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import argparse
import json
import os
import pathlib
import textwrap
import typing

import flatpaker

if typing.TYPE_CHECKING:
    class Arguments(flatpaker.SharedArguments, typing.Protocol):
        input: typing.List[pathlib.Path]
        description: flatpaker.Description
        cleanup: bool

def _create_game_sh(use_x11: bool) -> str:
    lines: typing.List[str] = [
        '#!/usr/bin/env sh',
        '',
        'export RENPY_PERFORMANCE_TEST=0',
    ]

    if not use_x11:
        lines.append('export SDL_VIDEODRIVER=wayland')

    lines.extend([
        'cd /app/lib/game',
        'exec sh *.sh',
    ])

    return '\n'.join(lines)


def quote(s: str) -> str:
    return f'"{s}"'


def bd_game(args: Arguments) -> typing.Dict[str, typing.Any]:
    sh = _create_game_sh(args.description.get('workarounds', {}).get('use_x11', True))
    return {
        'buildsystem': 'simple',
        'name': 'game_sh',
        'sources': [],
        'build-commands': [
            'mkdir -p /app/bin',
            f"echo '{sh}' > /app/bin/game.sh",
            'chmod +x /app/bin/game.sh'
        ],
    }


def bd_build_commands(args: Arguments) -> typing.List[str]:
    commands: typing.List[str] = [
        'mkdir -p /app/lib/game',

        # install the main game files
        'mv *.sh *.py renpy game lib /app/lib/game/',

        # Move archives that have not been strippped as they would conflict
        # with the main source archive
        'cp -r */game/* /app/lib/game/game/ || true',
    ]

    # Insert these commands before any rpy and py files are compiled
    for p in args.description.get('sources', {}).get('files', []):
        dest = os.path.join('/app/lib/game', p.get('dest', 'game'))
        commands.extend([
            f'mkdir -p {os.path.dirname(dest)}',
            f'mv {p["path"].name} {dest}',
        ])

    commands.extend([
        # Patch the game to not require sandbox access
        '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py''',

        # Recompile all of the rpy files
        textwrap.dedent('''
            pushd /app/lib/game;
            script="$PWD/$(ls *.sh)";
            dirs="$(find . -type f -name '*.rpy' -printf '%h\\0' | sort -zu | sed -z 's@$@ @')";
            for d in $dirs; do
                bash $script $d compile --keep-orphan-rpyc;
            done;
            popd;
            '''),

        # Recompile all python py files, so we can remove the py files
        # form the final distribution
        #
        # Use -f to force the files mtimes to be updated, otherwise
        # flatpak-builder will delete them as "stale"
        #
        # Use -b for python3 to allow us to delete the .py files
        # I have run into a couple of python2 based ren'py programs that lack
        # the python infrastructure to run with -m, so we'll just open code it to
        # make it more portable
        textwrap.dedent('''
            pushd /app/lib/game;
            if [ -d "lib/py3-linux-x86_64" ]; then
                lib/py3-linux-x86_64/python -m compileall -b -f . || exit 1;
            else
                lib/linux-x86_64/python -c 'import compileall; compileall.main()' -f . || exit 1;
            fi;
            popd;
            ''')
    ])

    return commands


def bd_icon(args: Arguments, appid: str) -> typing.Dict[str, typing.Any]:
    icon_src = '/app/lib/game/game/gui/window_icon.png'
    icon_dst = f'/app/share/icons/hicolor/256x256/apps/{appid}.png'
    # Must at least be before the appdata is generated

    _icon_install_cmd: str
    if args.description.get('workarounds', {}).get('icon_is_webp'):
        _icon_install_cmd = f'dwebp {icon_src} -o {icon_dst}'
    else:
        _icon_install_cmd = f'cp {icon_src} {icon_dst}'

    return {
        'buildsystem': 'simple',
        'name': 'icon',
        'sources': [],
        'build-commands': [
            'mkdir -p /app/share/icons/hicolor/256x256/apps/',
            _icon_install_cmd,
        ],
    }


def dump_json(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:

    sources: typing.List[typing.Dict[str, object]] = []

    if 'sources' in args.description:
        for a in args.description['sources']['archives']:
            sources.append({
                'path': a['path'].as_posix(),
                'sha256': flatpaker.sha256(a['path']),
                'type': 'archive',
                'strip-components': a.get('strip_components', 1),
            })
        for source in args.description['sources'].get('files', []):
            p = source['path']
            sources.append({
                'path': p.as_posix(),
                'sha256': flatpaker.sha256(p),
                'type': 'file',
            })
        for a in args.description['sources'].get('patches', []):
            sources.append({
                'type': 'patch',
                'path': a['path'].as_posix(),
                'strip-components': a.get('strip_components', 1),
            })
    else:
        sources = [{
            'path': i.as_posix(),
            'sha256': flatpaker.sha256(i),
            'type': 'archive',
        } for i in args.input]

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': flatpaker.sanitize_name(args.description['common']['name']),
            'sources': sources,
            'build-commands': bd_build_commands(args),
            'cleanup': [
                '*.exe',
                '*.app',
                '*.rpyc.bak',
                '*.txt',
                '*.rpy',
                '/lib/game/lib/*darwin-*',
                '/lib/game/lib/*windows-*',
                '/lib/game/lib/*-i686',
            ],
        },
        bd_icon(args, appid),
        bd_game(args),
        flatpaker.bd_desktop(desktop_file),
        flatpaker.bd_appdata(appdata_file),
    ]

    if args.description.get('workarounds', {}).get('use_x11', True):
        finish_args = ['--socket=x11']
    else:
        finish_args = ['--socket=wayland', '--socket=fallback-x11']

    struct = {
        'sdk': 'org.freedesktop.Sdk',
        'runtime': 'org.freedesktop.Platform',
        'runtime-version': '23.08',
        'id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            *finish_args,
            '--socket=pulseaudio',
            '--device=dri',
        ],
        'modules': modules,
        'cleanup-commands': [
            "find /app/lib/game/game -name '*.py' -delete",
            "find /app/lib/game/lib -name '*.py' -delete",
            "find /app/lib/game/renpy -name '*.py' -delete",
            'find /app/lib/game -name __pycache__ -print | xargs -n1 rm -vrf',
        ]
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f, indent=4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('description', help="A Toml description file")
    parser.add_argument('input', nargs='*', help='path to the renpy archive, plus archive patches')
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--gpg', action='store', help='A GPG key to sign the output to when writing to a repo')
    parser.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    parser.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    args = typing.cast('Arguments', parser.parse_args())
    args.input = [pathlib.PosixPath(i).absolute() for i in args.input]
    # Don't use type for this because it swallows up the exception
    args.description = flatpaker.load_description(args.description)  # type: ignore

    appid = f"{args.description['common']['reverse_url']}.{flatpaker.sanitize_name(args.description['common']['name'])}"

    with flatpaker.tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.create_desktop(args.description, wd, appid)
        appdata_file = flatpaker.create_appdata(args.description, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        flatpaker.build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()
