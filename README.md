# whipsaw

A CD ripper for Linux that puts accuracy first. It rips securely with cdparanoia, checks every track against the [AccurateRip](http://www.accuraterip.com/) database, and looks up metadata and cover art on [MusicBrainz](https://musicbrainz.org/), falling back to other sources when that comes up empty. Tracks are encoded with ffmpeg (FLAC by default).

whipsaw is an unofficial fork of [whipper](https://github.com/whipper-team/whipper), not affiliated with or endorsed by its authors. It is GPLv3, and [NOTICE](NOTICE) lists what changed. It is meant to replace whipper, not run alongside it: the command, config file and environment variables are all renamed.

## Features

- Secure ripping with cdparanoia: test and copy passes, drive offset detection, audio-cache detection, hidden track one audio (HTOA)
- Every track verified against AccurateRip, computed from the raw audio, so the result is the same whichever format you encode to
- Metadata from MusicBrainz, then FreeDB, then Discogs (with `--search`), then the disc's own CD-Text
- Cover art from the Cover Art Archive (release, then release-group), then iTunes, then fanart.tv, Discogs or Last.fm (those three need keys); embedded pictures are re-read from disk to confirm they were written
- Output via ffmpeg as FLAC (default), WAV, ALAC, MP3, Opus, Vorbis or AAC, tagged correctly for each container
- A rip log recording the AccurateRip results and which metadata and cover art sources were used

## Install

You need Python 3.9+, a C compiler and the libsndfile headers (they build the AccurateRip extension), plus:

- programs: `cd-paranoia` (libcdio-paranoia), `cdrdao`, `ffmpeg`, `sox` (with `soxi`) and `eject`
- libraries: libsndfile and libdiscid
- Python packages: musicbrainzngs, mutagen, pycdio, discid, ruamel.yaml and packaging
- optional: Pillow and requests (cover art and Discogs; skipped with a warning if missing) and coloredlogs

**Arch Linux:** install [whipsaw from the AUR](https://aur.archlinux.org/packages/whipsaw) with your AUR helper. It conflicts with the `whipper` package, so remove that first.

```bash
yay -S whipsaw
```

The same PKGBUILD is in [packaging/arch](packaging/arch) if you'd rather build it yourself with `makepkg -si`.

**From source**, in a virtualenv:

```bash
git clone https://github.com/luftwafflezz/whipsaw.git && cd whipsaw
pip install ".[cover_art]"
```

pycdio's PyPI release can fail to build on newer Pythons (it does on 3.14). If it does, install your distro's `python-pycdio` and create the virtualenv with `--system-site-packages`.

## Usage

```bash
whipsaw drive list            # find your drive
whipsaw drive analyze         # does it cache audio?
whipsaw offset find -o 6      # confirm the drive's read offset (saved to the config)
whipsaw cd rip                # rip the disc in the drive
```

Look up your drive's offset in [AccurateRip's list](http://www.accuraterip.com/driveoffsets.htm). A rip won't start until an offset is known, via `offset find` or `-o` on the rip command.

Options belong to the command they follow: `whipsaw cd -d /dev/sr0 rip`, not `whipsaw cd rip -d /dev/sr0`.

Useful `cd rip` options:

| Option | Effect |
| --- | --- |
| `-C`, `--cover-art file\|embed\|complete` | Save cover art as a file, embed it in the tracks, or both (off by default) |
| `-U`, `--unknown` | Rip a disc that no metadata source recognizes |
| `--search "artist - album"` | Hint for the Discogs fallback |
| `-R`, `--release-id ID` | Use a specific MusicBrainz release |
| `-O`, `--output-directory DIR` | Where to put the rip |
| `--track-template`, `--disc-template` | File and directory naming |

Common examples:

```bash
whipsaw cd info                                # what MusicBrainz, FreeDB and AccurateRip know about the disc
whipsaw cd rip -C complete                     # rip with cover art, saved as a file and embedded
whipsaw cd rip -O ~/Music/rips                 # rip into a specific directory
whipsaw cd rip -p                              # choose the release when several match
whipsaw cd rip --search "artist - album"       # no MusicBrainz match: let Discogs try
whipsaw cd rip -U                              # rip a disc nothing recognizes
whipsaw cd rip -k                              # keep going if a track can't be ripped
whipsaw cd rip --cdr                           # rip a CD-R (refused by default)
whipsaw -e never cd rip                        # don't eject when finished
whipsaw cd -d /dev/sr1 rip                     # use a second drive
whipsaw image verify Album.cue                 # re-check an existing rip against AccurateRip
whipsaw mblookup KnpGsLhvH.lPrNc1PBL21lb9Bg4-  # look up a MusicBrainz disc or release ID
```

## Configuration

The config file is `~/.config/whipsaw/whipsaw.conf` (or under `$XDG_CONFIG_HOME`). It is separate from whipper's, and nothing is migrated. Every setting has a default, so add only what you want to change:

```ini
[encoding]
format = flac                ; flac, wav, alac, mp3, opus, vorbis or aac
flac_compression_level = 8
mp3_quality = 0              ; VBR quality, 0 (best) to 9
opus_bitrate = 320k
aac_bitrate = 320k

[cover_art]
chain = caa_release, caa_release_group, itunes, fanarttv, discogs, lastfm
max_dimension = 1200         ; downscale to fit
format = jpeg

[art:fanarttv]
api_key =                    ; keyed providers stay off until a key is set
[art:discogs]
token =
[art:lastfm]
enabled = false              ; needs enabled = true and an api_key
api_key =

[metadata]
cdtext_fallback = true
[metadata:discogs]
token =                      ; only used with --search

[whipsaw.cd.rip]             ; defaults for `whipsaw cd rip` options
output_directory = ~/Music/rips
```

## Troubleshooting and development

To debug a failing command, run it with `WHIPSAW_DEBUG=DEBUG WHIPSAW_LOGFILE=whipsaw.log` set and attach the log to a report on the [issue tracker](https://github.com/luftwafflezz/whipsaw/issues).

```bash
pip install -e ".[cover_art,test]"
python -m unittest discover
```

The man pages are built with `make -C man` (needs docutils).

## License and credits

GPLv3 or later; see [LICENSE](LICENSE). whipsaw builds on whipper, by Thomas Vander Stichele (who started it as morituri) and The Whipper Team: Joe Lametta, Samantha Baldwin, Merlijn Wajer, Frederik "Freso" S. Olesen and its other contributors. It is maintained by [Ian Vidricksen](https://github.com/luftwafflezz).
