===============
whipsaw-cd-info
===============

----------------------------------------------------
Retrieve information about the currently inserted CD
----------------------------------------------------

:Author: Louis-Philippe Véronneau
:Date: 2020
:Manual section: 1

Synopsis
========

| whipsaw cd info [**-R** *<RELEASE_ID>*] [**-p**] [**-c** *<COUNTRY>*]
| whipsaw cd info **-h**

Options
=======

| **-h** | **--help**
|     Show this help message and exit

| **-R** *<RELEASE_ID>* | **--release-id** *<RELEASE_ID>*
|     MusicBrainz release id to match to (if there are multiple)

| **-p** | **--prompt**
|     Prompt if there are multiple matching releases

| **-c** *<COUNTRY>* | **--country** *<COUNTRY>*
|     Filter releases by country


See Also
========

whipsaw(1), whipsaw-cd(1), whipsaw-cd-rip(1)
