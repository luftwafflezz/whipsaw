=======
whipsaw
=======

----------------------------------------------------
A CD ripping utility focusing on accuracy over speed
----------------------------------------------------

:Author: Louis-Philippe Véronneau
:Date: 2020
:Manual section: 1

Synopsis
========

| whipsaw [**subcommand**]
| whipsaw [**-R**] [**-v**] [**-h**] [**-e** *{never failure success always}*]

Description
===========

| **whipsaw** is a CD ripping utility focusing on accuracy over speed that
| supports multiple features. As such, **whipsaw**:

|

| * Detects correct read offset (in samples)
| * Detects whether ripped media is a CD-R
| * Has ability to defeat cache of drives
| * Performs Test & Copy rips
| * Verifies rip accuracy using the AccurateRip database
| * Uses MusicBrainz for metadata lookup
| * Supports reading the pre-emphasis flag embedded into some CDs (and
|   correctly tags the resulting rip)
| * Detects and rips non digitally silent Hidden Track One Audio (HTOA)
| * Provides batch ripping capabilities
| * Provides templates for file and directory naming
| * Supports lossless encoding of ripped audio tracks (FLAC)
| * Allows extensibility through external logger plugins

Options
=======

| **-h** | **--help**
|     Show this help message and exit

| **-e** | **--eject**  *never failure success always*
|     When to eject disc (default: success)

| **-c** | **--drive-auto-close** *True False*
|     Whether to auto close the drive's tray before reading a CD
|     (default: True)

| **-R** | **--record**
|     Record API requests for playback

| **-v** | **--version**
|     Show version information

Subcommands
===========

**whipsaw** gives you a tree of subcommands to work with, namely:

|

| * accurip
| * cd
| * drive
| * image
| * mblookup
| * offset

| For more details on these subcommands, see their respective man pages.

Bugs
====

| Bugs can be reported to your distribution's bug tracker or upstream
| at https://github.com/luftwafflezz/whipsaw/issues.

See Also
========

whipsaw-accurip(1), whipsaw-cd(1), whipsaw-drive(1), whipsaw-image(1),
whipsaw-mblookup(1), whipsaw-offset(1)
