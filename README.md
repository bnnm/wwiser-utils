# WWISER UTILS
Companion utils and stuff for *wwiser*: https://github.com/bnnm/wwiser


## WWNAMES
Examples of `wwnames.txt` files for *wwiser*. Those contain names used in some games, and can be used by renaming to `wwnames.txt` and putting in `.bnk` dir before opening banks with *wwiser*.

Lists are not always complete (almost impossible with Wwise) but gives a bunch of names for free.


## FNV
A simple Wwise FNV hash-to-name reverser.

Run to see help: `fnv.exe`, leave `fnv.lst` together with .exe

Compile with: `gcc -O3 fnv.c -o fnv.exe` or similar tools (no particular dependencies).

See *doc/NAMES.md* and *doc/RIPPING.md* about tips on usage.


## WORDS
A helper to reverse names from existing word lists.

Run `words.py` with a `words.txt` nearby (usually a renamed `wwnames.txt`) to generate `words_out.txt` with variations of the list, that then can be fed to *wwiser*. With some extra commands and tricks it can create variations of names that may used by the game.

See *doc/NAMES.md* and *doc/RIPPING.md* about tips on usage.


## DB3
Sample of `wwnames.db3`, a file *wwiser* can get to write extra names. At the moment it only has default/common names, but may be expanded in the future.

Use *wwiser* to create or fill the .db3, for example: `wwiser.pyz -d none dummy.bnk -nl _default.txt -sd -sa`.


## SCRIPTS
Other helper scripts for Wwise ripping, for see docs for tips on usage.


## CLI EXAMPLES
Examples of (slightly) advanced usage:
```
# dump all bnk to a single xml
wwiser.pyz *.bnk

# create a list of missing name IDs
wwiser.py *.bnk -sl

# generate txtp, moving wem, using alt extensions if neede, unused and using sound dir
wwiser.py -d none *.bnk -g -gm -gae -gu -gw sound
```
