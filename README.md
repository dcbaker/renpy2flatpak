# renpy2flatpak

Script to mostly automate creating flatpaks from published renpy projects

## What is it?

It's a script that automatically handles much of the task of generating a
flatpak for pre-built renpy projects, including adding patches or mods. You
write a small, simple toml file, fetch the sources, and get a ready to publish
flatpak.

It currently automatically does the following automatically:

- Generates an appstream xml file
- Generates a .desktop file
- Extracts an icon from the game source, and installs it
- patches the game to honor $XDG_DATA_HOME for storing game data inside the sandbox (instead of needing $HOME access)
- sets up the sandbox to allow audio and display, but nothing else
- recompiles the program when mods are applied
- strips .rpy files to save space (keeping the rpyc files)
- strips windows and macos specific files
- allows local install or publishing to a repo

## Why?

I like playing renpy games sometimes. I also don't always trust random
pre-compiled binaries from the internet. Flatpak provides a nice, convenient
way to sandbox applications. But generating flatpaks by hand is a lot of work,
especially when most of the process will be exactly the same for every renpy
project.

## How do I use it?

1. Download the compressed project
2. Download any mods or addons (optional)
3. Write a toml description
4. run the program

### Toml Format

```toml
[common]
  name = 'Game or VN'
  reverse_url = 'com.example.JDoe'  # name will be appended
  # "Game" is added automatically
  # used freedesktop menu categories. see: https://specifications.freedesktop.org/menu-spec/latest/apas02.html
  categories = ['Simulation']

[appdata]
  summary = "A short summary, one setence or so."
  description = """
    A longer description.

    probably on multiple \
    lines
    """

  # This is an optional value for the license of the renpy project itself.
  # If unset it defaults to LicenseRef-Proprietary.
  # if you have specific terms which are not an Open Source license, you can use the form:
  # LicenseRef-Proprietary=https://www.example.com/my-license
  # See: https://spdx.org/specifications for more information
  license = "SPDX identifier"

[appdata.content_rating]
    # optional
    # Uses OARS specifications. See: https://hughsie.github.io/oars/
    # keys should be ids, and the values are must be a rating (as a string):
    # none, mild, moderate, or intense
    language-profanity = "mild"

[appdata.releases]
  # optional
  # in the form "version = date"
  1.0.0 = "2023-01-01"

# Optional, alternatively may be passed on teh command line
[[sources.archives]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, defaults to 1. How many directory levels to remove from this component
  strip_comonents = 2

# Optional, cannot be set from command line
[[sources.patches]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, defaults to 1. How many directory levels to remove from this component
  strip_comonents = 2

# Optional, cannot be set from command line
[[sources.files]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, if set the file will be installed to this name
  # Does not have to be set for .rpy files that go in the game root directory
  dest = "where to install"
```

## What is required?

- python 3.11 or a modern version of python3 with tomli
- flatpak-builder
