# REVERSING WWISE NUMBERS

*wwiser* can use companion files like `SoundbankInfo.xml`/`(bank).txt`/etc to show names in the bank output and make `.txtp` filenames, but often games don't include them. For games without those files that contain names it's possible to "reverse" (getting original name string) some Wwise numbers with *wwiser* and effort.

Even with those companion files some names may be missing (usually variables), so we may still want to reverse a few.

In short, make a file named `wwnames.txt`, inside write *reversed names* (strings that become Wwise numbers) and put together with the banks. *wwiser* will use this file for names. With some luck, game's data and executable will have a bunch of names somewhere that you can extract with some tools.

This process requires some knowledge of command line though, no GUI at the moment.

Also note that sometimes you can recover (some) names, but others it's just too hard, if devs were too creative with names and files don't have any name references (Wwise can function using only numbers).

## TL;DR
Quick guide to (possibly) get extra names:
- put all files that may contain names inside in some dir, the more the merrier
  - binary files with names are ok too
  - make sure they are decompressed first (like for Unreal Engine use gildor's package decompressor/extractor/etc)
  - binary that *don't* have names are ok too, but the more files the more noise/bad names you may get, try to trim down when possible
    - for example, remove all texture/shader/model files
  - also add the executable (.exe/so/main/xex/eboot/etc) too
  - some executables like main/xex/eboot/exe should be decompressed first (ask in hcs64/discord, or just won't worry)
- zip all files into a single file with the "no compression option"
  - this makes a single, huge file like `files.zip`
  - this file MUST NOT BE COMPRESSED (not an actual zip, but a package; you could use `.tar` or others)
  - doesn't matter if you include folders
- use `strings2.exe` to get a text file with names from `files.zip`
  - get `strings2.exe`: http://split-code.com/files/strings2_x64_v1-2.zip
    - on Linux you may use `strings` too
  - unzip on same dir as `files.zip`
  - call on Windows CLI: `strings2.exe "files.zip" > wwnames.txt`
  - you don't need to change `strings2` default parameters (gets you more names = good)
  - or create a file like `files.bat`, copy the line above + save, double click
  - if zipped files are too big try splitting by max size, repeat steps below, and fuse all `wwnames.txt` created to a final one
  - you may want to also use `sstr.exe` (https://github.com/bnnm/wwiser-utils/raw/master/sstr/sstr.exe) to possible add extra names that `strings2.exe` may get wrong (like `@nbgm_01<`).
  - `sstr.exe "files.zip" >> wwnames.txt`
- the above generates a `wwnames.txt` file with "possible" (not necessarily used) names
  - many "names" will be garbage-looking strings, that is ok and will be ignored by *wwiser*
  - some "names" will be long lines or contain crap like `  "bgm"="name"  `, that is ok too and will be cleaned up automatically (reads `bgm` and `name`)
- now put that file with all `.bnk`, wwiser can use it to get all possible names (may take a while to load if wwnames is big)
  - load all to ensure getting most names (could limit to only music or sfx, but might as well do everything at once while we are at it)
- **HOWEVER** some names may be garbage, preferably do this:
  - put `wwiser.pyz`, `wwnames.db3` and `wwnames.txt` together with *all* banks (even voice/sfx)
    - technically `wwnames.txt` must go near `.bnk`, while `wwnames.db3` goes with `.pyz`
  - open windows CLI and call wwiser like this: `wwiser.pyz *.bnk -sl`
  - this creates a "clean" `wwnames-banks-(date).txt` with actually used names
  - open said file, look for clearly wrong names (like *x8273s* or *aXNuy*) and remove them, or change lower/uppercase in some cases (like `wIN` to `win` and such)
  - now rename `wwnames-bank-(date).txt` to `wwnames.txt` and use wwiser with that instead of the original file, since you just cleaned it up
- you may also add missing names manually (sometimes are easy to guess) or use `fnv.exe`/`words.py` helpers
  - see guide below about tips to squeeze out more names, particularly `words.py` info if you are an advanced user
- be cool and post this list somewhere or include `wwnames.txt` with your rip for everybody to enjoy
- also check if your game is here: https://github.com/bnnm/wwiser-utils/wwnames/


## CONCEPTS

### NUMBER TYPES
There are 2 types of Wwise numbers:
- not reversable: `.wem`, most object IDs (somewhat 'reversable' but the original name is a useless GUID)
- reversable: events, variables (switches/states/etc and their values), bank names, some busses and minor objects

Since games only use events and variables (never `.wem` directly), reversing those gets pretty ok names. *wwiser* internally calls the former, not-reversable names "guidnames" (numbers created by hashing the GUID) and the later "hashnames" (created by hashing the regular name).

Games roughly fall in two categories depending on how they call events/variables:
- by name: somewhere in the original files (exe, scripts, etc) may have event/variable names. More complex games using engines (like *Unity*, *Unreal Engine*) and/or scripting (like `.lua` files) may do this.
- by IDs: no actual names anywhere and just numbers. Simpler games may do this (just constant enum/class with values like NAME_1 = 12345678 used directly in code). Harder, but we may still get a few names.

Even in the second case game files may still contain a few leftover names, so we can still try the usual tricks. Theoretically we can reverse any event/variable, but realistically we may only recover a few, depending on how the game created the names (the longer, more elaborate the less likely). Still, having *some names* is better than *no names*.

Also keep in mind game variables are often in code only (numbers), even if game calls events *by name*.

Knowing all this, we can extract a list of leftover names, plus add some common ones, and make a extra name list for *wwiser* to use.


### EXTERNAL NAMES LIST
In addition to standard companion files like `SoundbankInfo.xml`, or even without them, you can provide a list of "possible" names called `wwnames.txt`. If you know an event is called *play_bgm_01* you can write that in `wwnames.txt` and *wwiser* will use it.

There is also the provided *wwnames.db3* companion file that contains common names (with words like `bgm`) for convenience.

`wwnames.txt` also has some extra behaviors to increase the chance to reverse names:
- valid names: reversable names can only contain numbers, letters, underscore and start with a letter/underscore (plus some exceptions), so it ignores clearly wrong names like `123test`.
- name derivation: if you have `name_1` in the list it'll automatically find names (if used) with a different last letter, like `name_2`, `name_3`, `name_a` and so on, no need to include each variation manually. However it can't derive `name_20` from `name_10` (not last letter).
- case: you can use either `BGM`/`bgm`/`Bgm`, all will be recognized the same.
- splitting: if a line contains something like `type="bgm01"`, it'll read `type` and `bgm01`. This allows to use lines from scripts or XML (though may slightly increase false positives).
- runtime names: some games use names like `bgm_%02i_start` or `game_clear_%d`. That means a number is passed to call `bgm_24_start`, `game_clear_5` and so on. Those cases are detected and multiple numbers are generated (within some limits).

*wwiser* internally calls "name derivation" of last letter "fuzzy matching". You can disable it by adding `#@nofuzzy` to `wwnames.txt` (useful for complete, longer name lists where some odd name is being misused by this fuzzy matching).

Similarly lines are normally split by spaces and non-valid characters, but you can force (some) by adding `= 0` after a name. See *handle bus names* below for more info.


## REVERSING STEPS
The basic flow is this:
- put all `.bnk` and companion files in a dir
- create a big *wwnames.txt* with most possible names for that game (no need to be a clean list)
- call wwiser to read all banks and create a "clean" `wwnames.txt` with actually used names.
- check output and try to refine original (unclean) list to add missing names, or remove false positives.
- use reversing tools to get a few more names
- repeat until we have most names
- save final generated `wwnames.txt` and use that


### BNKS
It's best if you use all possible banks in the game, more banks = more names detected = yay. You can restrict to `bgm.bnk` or whatever only, but might as well try to get most names at once while we are at it.

If the game has `SoundbankInfo.xml`, `(bankname).txt`, `Wwise_IDs.h` and similar files put those together too. Not all names are in each of those files, so you want *all* at once (in otyher words don't delete `(bankname).txt` thinking `SoundbankInfo.xml` is enough).

Another gotcha is that if you only load `bgm.bnk` + `bgm.txt` + `SoundbankInfo.xml`, some names may actually be in `init.bnk` + `init.txt`, so loading every bank ensures you find all at once.


### MAKING WWNAMES.TXT
The idea is to make a rough, non-curated list of names from files that may contain them. The list can contain garbage, *wwiser* will ignore strings that can't be used for names, so no need to get it too detailed. Even big lists (ex. +200MB) are ok, just they are slower to read and need more memory. The bigger the list the more likely it has *false positives* though, try to keep it simpler.

To make the list you usually want to apply a program that extracts text from binary files, (like `strings2.exe` from http://split-code.com/strings2.html on *Windows* or `strings` on Linux), to files that may contain names. For example the game exe, or script/text files: 
```
strings2.exe game.exe > wwnames.txt

strings2.exe config.lua >> wwnames.txt
```

This `wwnames.txt` will contain lots of garbage (no need to clean), but also many possible candidates. A thing to note is that Wwise conversion from names to numbers is fairly simple, meaning multiple names may end up with the same number AKA "false positives".

`strings2.exe` tries to finds names separated by null bytes. This sometimes makes text that contains unwanted letters (like `@nbgm_01<` that would be bytes). To improve those cases you can try `wwiser-utils/sstr/sstr.exe`, that tries to find *sized strings* that games often use and gives much better results on those cases. Note that games may mix both types of strings so you could try both anyway.

So you want to fill the list with many candidates, but not so many that false positives start appearing. Various tricks about making and improving the list are described later.

Put this generated list together with all `.bnk`.


### MAKING A CLEAN LIST
Call *wwiser* with extra `-sl` parameter:
```
wwiser *.bnk -sl
```

This reads all banks, `wwnames.txt` created before, `wwnames.db3` (common names) and companion `.xml`/etc, and saves a file list named *wwnames-banks-(timestamp).txt* with *used* names. You can also set `-g` to create `.txtp` as it's easier to see if names where properly used.

Adding `-sm` it'll also write a list of reversable IDs with missing names, so you can try to figure out those bits. This is most useful when paired with `SoundbankInfo.xml` and similar files, as that file may still miss some names. By default the list has names not in companion files, but you can use `-sc` to add all companion names.

While parsing you may get *alt hashname found, old=..., new=...* in the CLI output. This means it has 2 names that could correspond to one ID. In those cases easiest is taking the correct name and putting it on top of `wwnames.txt` (first name found has priority, you can also remove the incorrect one so that the message doesn't appear). The list contains and marks the new/alt name for easy identification.

**NOTE!** by default `-sl` doesn't generate dump output (`.xml`) but ensures all names are included in the list. Don't use `-d none` unless you are very sure, as that forces generating only names that are *actually used* (so `-d none -g` makes a list from names used in `.txtp` = less names).

Now check the output to see if there are still missing names. With some tricks you can improve the original list (see below), and with the improved list call *wwiser* again and check the output, repeat until satisfied.

In some cases you may get many names, and very few or none in others, but it's still worth trying. Realistically, it's very hard to get *every name* in most cases, but often you get enough to improve `.txtp` filenames a bit for main BGM.



### USING FNV.EXE REVERSING TOOL
Some of the missing IDs (see using `-sm` above) can be reversed using `fnv.exe`:
https://github.com/bnnm/wwiser-utils/raw/master/fnv/bin/fnv.7z
```
fnv.exe 12345678
```
This tool tries combinations of letters/numbers/underscore, plus some speed-up tricks, to find the original name. Since various (wrong) names may be valid for one ID it'll write multiple results, you need to pick one.

Typically this is only useful for smaller names like variables (up to 7-8 chars). Anything bigger will be too slow to reverse, and return too many false positives. It will easily reverse `bgm` or `banana`, but not `play_bgm_001` as it has too many chars.

But you can restrict a bit the search space if you suspect name has a prefix:
```
fnv.exe 123456789 -m 8 -p "play_"
```
That will start from `play_` and search up to 7 letters, making it feasible to find `bgm_001`.

You can also set suffix:
```
fnv.exe 123456789 -m 8 -s "_001"
```

If that fails try disabling some speedups with `-i`. By default it'll only tries combinations that look normal enough (ignores things like `1aaart`), but could skip certain valid names. May need to combine with prefixes for faster and better results:
```
fnv.exe 1492557634 -i -s planet -m 5
#finds "planet_04"
```

If you are desperate it's possible to try higher letter count and leave it running for a (long) while. 9 is borderline usable (fast enough but many false positives, redirect output to file), +10 takes hours but returns too much crap. May use `-l`, `-L` and `-r` to start/end from a certain letter if you suspect a range:
```
fnv.exe 123456789 -m 9 -l s -L z -r > fnv-results.txt
```
A big problem with higher max is that increases false positives. It's hard to judge the "englishness" of a word, so many nonsensical letter combos will match the ID.

You can also try your luck doing the reverse: use `-n` and write names to get possible numbers:
```
fnv.exe -n play_bgm_0 play_bgm_00 play_bgm_001
```
It's faster to add all names you can think of to `wwnames.txt` though.

When you suspect a name doesn't contain letters you can restrict a bit to skip certain ranges of letters (order is `abcdefghijklmnopqrstuvwxyz_0123456789`). Without `-r` it only restricts on base level (used to resume finds from a letter)
```
fnv.exe 1492557634 -l b -L t -r
#finds "planet_04"
```
Alse use `-R` for a quick "ignore all numbers in any level" setting.


Finally, take any reversed names and put them (preferable on top for priority) in `wwnames.txt`.


### USING WORDS.PY REVERSING TOOL
This automates some of the tips explained later. It's mainly useful when we already have a bunch of names, and are missing others that are variations of existing names (since devs use somewhat previsible names):
https://github.com/bnnm/wwiser-utils/blob/master/scripts/words/words.py

The basic theory this tool uses is: if you know a game has `play_bgm_01` but are missing other names, there is a good chance `bgm_01`, `bgm_02` or `play_bgm_01_short` could be valid names. *words.py* basically takes words and generates other words, to test vs missing ID numbers.

By default it reads some expected files (like `wwnames.txt`, or `formats.txt`) to get base names and IDs then tries certain patterns.

With some manual tweaking you can quickly try lots of variations. For example, if you only have a bunch of `bgm_01` you can try prefixing `play_`, `stop_`, ..., and suffixing `_short`. The tool needs some manual fine tuning, as the more words the longer it takes and more false positives appear. Maybe your game needs `playmusic_` or a `_play` suffix instead, or you want to find only `ST_MU_`, so to get most out of it you need to keep tweaking input (can't guess those affixes).

You need to start with a base word list and some imagination to guess how names could be created. The more names and formats you add the longer it takes and the more false positives you get though, so keeping lists reasonable is part of the process, though often you can just throw lots of junk there and see what sticks.


#### Quick guide
Typical use of *words.py*:
- use `wwiser.pyz *.bnk -sl -sm` to generate a base `wwnames-banks-(date).txt` with valid words + missing FNV numbers
- put that file (now base word list + reversable FNV numbers) with *words.py*
  - by default it reads any and all `wwnames*.txt` in dir
- run and check `words_out.txt` for possible matches (this will also create `skips.txt`)
  - *words.py* cuts base list names in various ways, and tries to find missing FNV numbers
  - `skips.txt` is a list of already reversed names that keeps growing, so when retrying same reversed names don't reappear
- copy good matches to the *wwnames* near *words.py* (no need to change `number: name` format)
- create `formats.txt` and add prefixes/suffixes like `play_%s`, `stop_%s`, `play_%s_bgm` and so on
  - observe your current *wwnames* list and try to guess possible patterns
  - example: https://github.com/bnnm/wwiser-utils/blob/master/scripts/words/formats.txt
- run again and save new possible matches
- keep tweaking `formats.txt` and adding/removing words in `wwnames.txt` trying to guess more names
- every now and then update original list, then `wwiser.pyz *.bnk -sl -sm` to see how numbers keep decreasing
- make a `ww.txt` file with extra posible names (together with `wwnames*`), run again
  - you could add it to `wwnames.txt` directly too, but this coexists and it's a bit easier
  - this is best used with many `formats.txt` variations
  - prone to false positives, try disabling "fuzzy matching" with `-zd` or writting `#@nofuzzy` in the file
  - examples of useful texts to try:
    - output of `strings2` (often game has stems in files that aren't used as base wwnames)
    - `english.txt` (extra useful words every now and then): https://github.com/dwyl/english-words/
    - text faqs/guides of the game (possible game-related words)
    - `wwnames.txt` from other games: https://github.com/bnnm/wwiser-utils/tree/master/wwnames
      - Windows batch: `copy *.txt .allnames.txt` to try many at once
- try flags to fine-tune (see below)
- trim word list a bit and try *combinations* (see below)
  - preferably limit FNV numbers to certain banks, as this makes tons of false positives
- trim word list a bit and try *permutations* with another list (see below)
  - for example wwnames + `strings2` results or `english.txt`
- repeat again and again as you get more valid words (new words = new combos = new chances)
- give up at some point, copy names to the original *wwnames.txt*, re-create with `wwiser.pyz *.bnk -sl` and move on

Get *pypy* (https://www.pypy.org/) and use it to run *words.py* for a nice speed up.


#### Basic reversing
Basically make a `wwnames.txt` list of things like `BGM_Vocal_Camp_Off`, include some ID numbers to reverse too, launch `words.py` in the dir and it'll output in `words_out.txt` with reversed names. For example `Vocal_Camp` could be one of them.

You can have an extra `ww.txt` list (only reads words and ignores IDs), and `fnv.txt` (only reads ID numbers) too, or use those two instead of `wwnames.txt`. Include `formats.txt` to fine tune prefixes/suffixes.

FNV ID numbers must be plain `(number)` or `# (number)` (as the later is how it appears in `wwnames.txt`), and will ignore non-numbers and multiple numbers in the same line, or `(number): name` (*words.py* results). Remember missing names can be created with *wwiser* using `-sl -sm`.

Internally *words.py* splits parts (`BGM`, `BGM_Vocal_Camp` `Vocal_Camp_Off`, `Vocal_Camp`, `Vocal`, etc) from lists and combines with formats (see below). It's best to start with all names we have (like `wwnames.txt` or even output straight from `strings2`). You can force generate internally combined words with a flag, but it'll make huge lists.

Key here is quantity over quality. Just make huge lists of possible names and see how it goes. As long as you have free memory big-ish files are ok, but you may want to split giant words lists for easier handling. You can get a bunch of false positives this way, but most should look fake enough.


#### Formats
You can make a `formats.txt` with prefixes/suffixes: `%s` (default if no file is found), `BGM_%s`, `BGM_%s_On`, `BGM_%s_Off`, `BGM_Play_%s`, etc. This will make things that weren't in the original words, like `BGM_Play_Camp`, `BGM_Vocal_Camp_On` and so on (so you can target a certain type of names like missing `BGM_*`).

Because splitting removes `_` (`_Vocal` won't be added), sometimes it's useful to add `_%s` in formats, as some game use names like `_01`. 

A base list with typical formats can be found here: https://github.com/bnnm/wwiser-utils/blob/master/scripts/words/formats.txt


#### Fuzzy feeling
By default last letters are auto-calculated, so a format like `%s_0` may find `BGM_Vocal_A` `BGM_Vocal_B`, but also from `BGM_Vocal` you may get `BGM_Voca2`. It's disabled when using *combinations/permutations* as it tends to get lots of useless matches.

This "fuzzy matching" can be enabled/disabled with flags, or disabled writting `#@nofuzzy` in the word file.


#### Combinations
For the daring you can use the combinator mode. `words.py -c N` takes `words.txt` and tries all combinations of N parts (`formats.txt` are also applied after those combinations). For example from `BGM`, `Vocal`, `Camp` `Desert` in `words.txt`, `-c 3` makes `BGM_Desert_Camp`, `BGM_Vocal_Desert` `Vocal_Camp_BGM` `Desert_BGM_Vocal` and so on. Many will be useless but again, quantity over quality. You can squeeze out a more names this way.

Downside is that many words + high `-c N` = humongous number of results. So `words.txt` here should be restricted to mostly relevant words (remove `Desert` if you aren't trying to find events related to that).  Try `-c 2` and see if some names worked (this is typically most useful), reduce words and try `-c 3` (this gets a few more, but often creates a many valid-looking-enough-but-actually-wrong names, though). `-c 4` is possible but could take many, many hours, `-c 5` and beyond may take ages. Total words and current word is printed every now and then so you can estimate the time it'll take.

In some cases it's better to use fully split stems by using the flag `-fs`. Normally `BGM_Vocal_Camp` splits into `BGM_Vocal`, `Vocal_Camp`, `BGM`, `Vocal`, `Camp`. With the flag, only `BGM`, `Vocal`, `Camp` are used. Combine custom `formats.txt`, this flag and `-c N` to create words like `(prefix)_(combos up to N)_(suffix)`, that can be useful when we have clear prefix/suffixes in `formats.txt`.

#### Permutations
A more specialized version is using `words.py -p`. This takes `words.txt`, that must be divided into "sections", and makes permutations of those sections to create combo words. For example:
```
BGM
Play_BGM

#@section
mission
stage

#@section
01
001
```
With those 3 sections it makes: `BGM_mission_01`, `BGM_stage_01`, `BGM_mission_001`, ..., `Play_BGM_mission_01`, `Play_BGM_stage_001`, an so on. This is similar as making formats (`BGM_%s_01`, `BGM_%s_001`) but simplifies testing more combos. Formats can be used on top of the permutations too.

You can also add `#@section` in `ww.txt` to designate a new section combined with `wwnames.txt` default section.


#### False positives
Because combinations and permutations makes lots of words, and Wwise IDs are very collision-prone (meaning 2 words may match the same ID), it tends to get tons of false positives. Those are easy to check at a glance, but it gets old to wade through lists of weird pseudo-words.

Easiest would be trimming your word list. If you are trying to find states, probably having `play_vo_s01_m10_char10323` isn't going to help much. Or maybe you have a `play_%s` format, remove all `play_*` in your file, or they'll combine too (`play_play_something`).

A trick is to pair related formats you know game uses. For example with `play_%s` and `stop_%s`, only results that have both could be valid (`play_bgm_park` + `stop_bgm_park`, but not a lone `play_flowers_high`). Or `st_%s` and `set_state_%s` may get `st_bgm01_long` + `set_state_bgm01_long` (good) and lone `st_bgm01_burger` (bad).

See modifiers to tweak how words are treated to decrease total results, for example `-mc 50` ignores words bigger than 50 chars. Some games do use huge +80 char names, but if you are targeting some small-ish state it helps a bit.


#### Skips
A special file `skips.txt` contain names that should be ignored in next runs, so output isn't filled with the same results when re-running. This list also doubles as a log.

It's only to decrease output noise, so you can always delete it to start again. Remove it when trying new games, as otherwise good matches that were in other games won't show up.


#### Modifiers
Base tweaks:
- `-zd`: disables "fuzzy matching" in default mode (last letter isn't autocalculated)
- `-ze`: enables "fuzzy matching" in combination/permutation modes

Word modifiers for special cases found in internal files:
- `-js`: joins words that are separated by spaces (`play music` becomes `play_music`)
- `-jb`: joins words by blanks (`Play_Music` becomes `PlayMusic`)
- `-sc`: split by caps (`PlayMusic` becomes `Play_Music`)

Others, mainly useful to control max results for combination/permutations: 
- `-mc N`: limits resulting words to max (to ignore huge, unlikely useful words)
- `-ns`: disables splitting words by `_`
- `-fs`: fully splits stems and don't add any subword containing `_`
- `-sp`: splits words by prefix like `(preffix)_(word_word...)`
- `-ss`: splits words by suffix like `(word_word...)_(suffix)`
- `-sb`: splits words by both prefix/suffix like `(preffix)_(word)_(suffix)`
- `-cl N`: cuts last N chars (for `strings2` garbage like having `bgm_001E` instead of `bgm_001`)


#### Other info
*python* isn't exactly known for speed, so `words.py` can be rather slow. A trick to improve this is using *pypy* (https://www.pypy.org/), a reimplementation of *python.exe* that often results in faster execution (download, unzip, then use `pypy3.exe words.py ...`). While *wwiser* doesn't seem very affected, `words.py` gets a huge boost (specially with `fnv.txt`).

Keep in mind this tool is memory hungry, is it needs to store words, reversed strings and other stuff.


### FINISHING THE LIST
Once you get "enough" names (getting "all" names is not very likely) generate a final clean list. Rename this `wwnames-banks-(timestamp).txt` to `wwnames.txt`. Then clean up as needed, by removing false positives (improbable names like `uTXs`) inside, and maybe rename "NAME" in CAPS to "name" if other vars are lowercase for consistency.

If you are unsure about some names but want to leave them for reference, you can add `#`to any line so the name is excluded (considered a comment).

Finally you could upload somewhere or include in your audio rips so others can benefit.


## WWNAMES CREATION TIPS
The following are a bunch of ideas you can follow to create `wwnames.txt` in steps. For each step the point is to keep adding to the base `wwnames.txt` until you have more and more names.

To recap, basic loop is: name `wwnames.txt` from one step, load all banks + use `-sl` to create a used list, and add those to a final list, keep trying steps and adding to the final list, then do a final cleanup of that.

### use english_words.txt as a base
This is a giant dictionary of English words: https://github.com/dwyl/english-words/. Download and rename to `wwnames.txt` and use *wwiser* to create a base *wwnames-banks-(timestamp).txt* list, then rename that to `wwnames.txt` and remove the word list. This sometimes gives you a bunch of unusual-but-used names for free (like `Adam` and `Eve` in Nier Automata), but also a bunch of false positives.

### add .exe strings
Take the `.exe` and use `strings2.exe` as described before to add to the previous `wwnames.txt`. In multiplatform games, sometimes one version has debug strings in the `.exe` while others don't, so it's useful to add strings from all versions.

Tips for different platforms:
- PC: usually straight .exe can be used. So sometimes it's compressed or protected, and you may need something like load with *IDA PRO* and take the strings inside.
- PS3: decrypt `EBOOT.BIN` to `EBOOT.ELF`, using *TrueAncestor SELF Resigner*
- X360: decrypt `default.xex`, using *XEXTool* (`xextool.exe -e u -c u -o decrypted.xex default.xex`)
- WiiU: decompress rpx/rpl with `rpl2elf`
- Switch: decompress `main`, using *nsnsotool*

### add data strings
For games where names come from scripts and data files you can look around and find those, and extract names with `strings2` then add to `wwnames.txt`.

Sometimes that's too time consuming since there can be many scripts, so here is a shortcut:
- unpack game's archives (may need to use appropriate programs or .bms) and remove useless/big data (like graphic/shaders/textures/audio/movies/models/etc).
- if files are compressed (like *Unity* or *Unreal Engine* files) don't forget to uncompress first
- in rare cases names may be in a SQLite database (.db), use some program like DB Browser to open and extract needed tables (`strings2` may extract names too but this is cleaner).
- put resulting files in some in a folder
- make a zip of that folder with *no compression* set.

This makes a "solid" archive that has everything. Then apply `strings2.exe` to the whole archive to extract all text at once.

### add memory dumps
Similar to the above, you can make a memory dump, apply `strings2.exe` over it and grab some extra names.

On Windows 10 you can make memdumps in the task manager > right click on process > create dump file. Other systems are harder though (emus may have some option like that, while rooted Android can use certain tools to achieve it).

### clean incorrectly extracted strings
Because `strings2.exe` can only guess so much, sometimes it gets names like `fbgm_play` instead of `bgm_play`, so you may want to recheck a bit (try searching `wwnames.txt` for obvious things like `bgm` to see everything looks ok).

You don't need to clean all the garbage strings it creates (names like `$asDFFC`) since it's time consuming and will most likely are ignored. But in some cases you may want to remove names that give false positives.

Sometimes game's files have lines like `C_PlayMusic("bgm_results")`, those are automatically handled by *wwiser* and read `bgm_results` just fine (explained before).

### ignore close numbers
If you have numbers that are the same save the last 2 digits (more or less) that means they share the same root and you only need to reverse one, wwiser automatically fills the rest. For example with 1189781958 and 1189781957 you only need to reverse first (`bgm1`), second (`bgm2`) will be automatically found.

### try other releases/platforms
It can be useful to check the same game in different platforms. The exe may have different strings (see above), but also data itself may be packaged differently and contain extra things. It's worth trying demos (early revisions) or maybe even remasters too.

For example the later PC release of Metal Gear Rising has an extra "debug" folder in one .cpk that graciously contains Wwise companion files/names for all banks, while the X360/PS3 version don't.

### try newer/older games lists' as a base
Sequels sometimes share base Wwise project and names (ex. *Doom Eternal* vs *Doom 2016*), so it's useful to include names from previous names, and also names from newer games in older games works too.

You can even include very different games but it increases the chance of false positives (make sure to clean the final list).

### add game-related strings
Since Wwise thing are generally named using game terms, it's often useful to add names that may not be in the original list but are used by the game (like  `mario` `luigi`). Characters, weapons, items, game modes, stages, environments, the more the merrier. If the list so far has some names but not others, just add a bunch. Conversely if the list doesn't refer to typical terms might not be worth bothering.

These terms are best used with `words.py` step + combinations, described below. Watch out for usage of abbreviations (`Wpn`, `amb`), joint words (`RoomWindow`) and even misspelling (`lazer`).

Sometimes even related media may hold the key. In some developer blog post, Platinum Games kindly provided nice dev screenshots+videos for Nier Automata revealing the elusive `BGM_IntroOff_Cansel`.

### use words.py
As explained before, this automates some of the steps, though only works with existing words lists. Best used before we start adding names manually, since it'll often find a bunch automatically.

A trick for games with few names is combining `formats_common.txt` with `english_words.txt`.

### try similar names + fnv.exe
Files may have `bgm_start` and `bgm_mute` that are properly used, but you are missing other bgm-related names.
It's worth adding some variations of the above that could be used, like `bgm_stop` or `bgm_unmute`.

This is good to test with the `fnv.exe` reversing tool (explained before), as `fnv.exe (number) -p "bgm_"` may reverse some of those variations with some guessing.

When guessing keep in mind name styles the dev uses their games. For example, one dev may often use `bgm_(stage)_001`, other likes `play_mus_(stage)`, other `play_music_(stage)`, etc.

### trim prefixes/suffixes
Sometimes you can find games with "variable-setter" events, for example `Set_State_BGM_Vocal_On`. This often means variable isn't referenced directly (no associated name), but with some luck `BGM_Vocal` will be the missing name. So looking for `Set_(something)` or `(something)_on/off` and removing the prefix/suffix is a good way to try a few extra names. Other suffixes like `_in/out` work, as well as adding the other prefix/suffix (if you have `(something)_on` but not `(something)_off`, or `stop_(something)` but not `play_(something)`).

### check close/related Wwise objects
The way `bnk` saves objects (see `.xml` wwiser generates) actually has some semblance of order. Some parts (like playlist children) are ordered by ID, but events often are saved near related objects, and particularly `init.bnk` may have a `GlobalSettingsChunk` that lists all variables in dev order.

If you have some named variables in that chunk you can narrow the search a lot. For example in Nier Automata: we have 3 variables: `BGM_Shop`, `3758536580`, `BGM_Slow`. Logically `3758536580` must be `BGM_Sh*/BGM_Si*/BGM_Sl*`. `Si*` looks the most likely, so we try `fnv.exe 3758536580 -p BGM_Si`. No results, but just in case again with extra checks disabled (these speed up reversing but also reject some less common names): `fnv.exe 3758536580 -p BGM_Si -i`. Now one of the results is `BGM_Sine_1khz`, which makes sense as the variable is used with channel test events.

For events, follow called IDs (see `tid`) and see what actions they trigger for hints. Events `BGM_Area_CampRoom_Out` and `BGM_Area_CampRoom_In` calls a SetState action that changes variable `4087916061` to value `on/off`. After some reversing that variable happens to be `BGM_Camp_Duck`. If values were `EN/JP`, that variable would have to do with `vocal` or `language`, etc.

### clean incorrectly used strings
Sometimes seemingly correct words are marked as used, like `sheep`. Because how Wwise creates names there is a chance some words can be used in incorrect places. Check that `banks.xml` wwiser creates for suspicious words and see they are not used in incorrect places (wwiser sometimes will do this). Generally only events/states/variables/values/busses and a few other are allowed to have names. If `banks.xml` is too big find strings in a hex editor (much faster).

Unfortunately this also means some events/states/etc may be named incorrectly, and must be checked manually. Most are fairly easy to catch, like  `xgaaks` (non-word), `play_bgm_out_bgm_001_stop` (nonesense mix of words) or `bgm_001_pla5` (mutated `_play`). Some are a bit more subtle, `_IMG_CHAR_WIDTH_1000` (unrelated to bgm) or `play_character1_bgm_loop` (looks ok enough, but no other names use this format, and event could be a stop event). The later isn't very common but be aware when using `words.py`, since it tends to create big those.

### repeat steps
Since the list keeps growing it's useful to repeat some steps so newer names have a chance to contribute. For example, after using `words.py` we later reverse `BGM_Sine_1khz`. Then calling `words.py` again with a bunch of formats variations revealed `BGM_Stop_1khz`, `Ot_1khz`, `BGM_Set_Ot_1khz`, and so on.

### handle bus names
While generally not very interesting, audio buses' names can also be reversed. But annoyingly enough they follow slightly different rules. Reversable (event/variable/etc) names can only contain lowercase letters, numbers, underscore `_` and cannot start with a number, but buses do allow spaces, start with numbers, and some extra symbols like `()-`.

By default *wwiser* ignores bus rules (improves overall output), but you can enable them by adding `= 0` after a name:
```
# will load bus names properly, without = 0 would load "Audio", "Bus" and ignore "01_Bus".
Audio Bus = 0
01_Bus = 0
```
Buses are named like usual (`audio_bus`, `sfx_volume`) too, but if you are missing a few it may be due to this. Also in some (early?) banks some buses take special GUIDs (not reversable).

### give up
Say you have almost every name-number down, save a couple. Just need to try a few more names...! Well, bad news: sometimes it's just too hard. Give up and move on. But you can always come back later, maybe names you need will be in the DLC, sequel or other game, or some extra tricks to get names will be added later.

Remember that you can call wwiser with `-sm` to print all missing numbers in generated `wwnames.txt`.
