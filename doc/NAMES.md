# REVERSING WWISE NUMBERS

*wwiser* can use companion files like `SoundbankInfo.xml`/`(bank).txt`/etc to show names in the bank output and make `.txtp` filenames, but often games don't include them. For games without those files that contain names it's possible to "reverse" (getting original name string) some Wwise numbers with *wwiser* and effort.

Even with those companion files some names may be missing (usually variables), so we may still want to reverse a few.

This process requires some knowledge of command line though, no GUI at the moment.

## TL;DR
Quick guide to (possibly) get extra names:
- put all files that may contain names inside in some dir, the more the merrier
  - binary files with names are ok too (make sure they are decompressed first, like for Unreal Engine use gildor's package decompressor/extractor/etc)
  - binary that *don't* have names are ok too, but the more files the more noise/bad names you may get, try to trim down when possible
  - also add the .exe too (may work better if decompressed + strings are extracted with IDA PRO though)
- zip all files into a single fule with the "no compression option"
  - this makes a single, huge file like `files.zip`
- use strings2.exe to get a text file with names from `files.zip`
  - get strings2.exe: http://split-code.com/files/strings2_x64_v1-2.zip
  - unzip on same dir as `files.zip`
  - call on Windows CLI: `strings2.exe "files.zip" > wwnames.txt`
  - or create a file like `files.bat`, copy the line above + save, double click
- this generates a `wwnames.txt` file with "possible" (not necessarily used) names
  - some "names" will be long lines or contain crap like `  "bgm"="name"  `,  that is fine and will be cleaned up automatically (reads `bgm` and `name`)
- now put that file with all `.bnk`, wwiser can use it to get all possible names (may take a while to load if wwnames is big)
- **HOWEVER** some names may be garbage, preferably do this:
  - put `wwiser.pyz`, `wwnames.db3` and `wwnames.txt` together with *all* banks (even voice/sfx)
  - open windows CLI and call wwiser like this: `wwiser.pyz *.bnk -sl -sc`
  - this creates a "clean" `wwnames-banks-(date).txt` with actually used names
  - open said file, look for clearly wrong names (like *x8273s* or *aXNuy*) and remove them, or change lower/uppercase in some cases (like `wIN` to `win` and such)
  - now rename `wwnames-bank-(date).txt` to `wwnames.txt` and use wwiser with that instead of the original file, since you just cleaned it up
- you may also add missing names (sometimes are easy to guess) or use `fnv.exe` to reverse a few numbers
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

If the game has `SoundbankInfo.xml`, `(bankname).txt`, `Wwise_IDs.h` and similar files put those together too. Not all names are in each of those files, so you want *all* at once (IOW don't delete `(bankname).txt` thinking `SoundbankInfo.xml` is enough).

Another gotcha is that if you only load `bgm.bnk` + `bgm.txt` + `SoundbankInfo.xml`, some names may actually be in `init.bnk` + `init.txt`, so loading every bank ensures you find all at once.


### MAKING WWNAMES.TXT
The idea is to make a rough, non-curated list of names from files that may contain them. The list can contain garbage, *wwiser* will ignore strings that can't be used for names, so no need to get it too detailed. Even big lists (ex. +200MB) are ok, just they are slower to read and need more memory. The bigger the list the more likely it has *false positives* though, try to keep it simpler.

To make the list you usually want to apply a program that extracts text from binary files, (like `strings2.exe` from http://split-code.com/strings2.html on *Windows* or `strings` on Linux), to files that may contain names. For example the game exe, or script/text files: 
```
strings2.exe game.exe > wwnames.txt

strings2.exe config.lua >> wwnames.txt
```

This `wwnames.txt` will contain lots of garbage (no need to clean), but also many possible candidates. A thing to note is that Wwise conversion from names to numbers is fairly simple, meaning multiple names may end up with the same number AKA "false positives".

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



### USING REVERSING TOOLS
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

You can also set suffix, but it's slower than prefixing:
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


Finally, take any reversed names and put them (preferable on top for priority) in `wwnames.txt`.


### FINISHING THE LIST
Once you get "enough" names (getting "all" names is not very likely) generate a final clean list. Rename this `wwnames-banks-(timestamp).txt` to `wwnames.txt`. Then clean up as needed, by removing false positives (improbable names like `uTXs`) inside, and maybe rename "NAME" in CAPS to "name" if other vars are lowercase for consistency.

If you are unsure about some names but want to leave them for reference, you can add `#`to any line so the name is excluded (considered a comment).

Finally you could upload somewhere or include in your audio rips so others can benefit.


## WWNAMES CREATION TIPS
The following are a bunch of ideas you can follow to create `wwnames.txt` in steps. For each step the point is to keep adding to the base `wwnames.txt` until you have more and more names.

To recap, basic loop is: name `wwnames.txt` from one step, load all banks + use `-sl` to create a used list, and add those to a final list, keep trying steps and adding to the final list, then do a final cleanup of that.

### use words.txt as a base
This is a giant dictionary of English words: https://github.com/dwyl/english-words/. Download and rename to `wwnames.txt` and use *wwiser* to create a base *wwnames-banks-(timestamp).txt* list, then rename that to `wwnames.txt` and remove the word list. This sometimes gives you a bunch of unusual-but-used names for free (like `Adam` and `Eve` in Nier Automata), but also a bunch of false positives.

### add .exe strings
Take the `.exe` and use `strings2.exe` as described before to add to the previous `wwnames.txt`. In multiplatform games, sometimes one version has debug strings in the `.exe` while others don't, so it's useful to add strings from all versions.

Tips for different platforms:
- PC/Switch: usually straight .exe (or `main` file in Switch) can be used. So sometimes it's compressed and you may need something like load with *IDA PRO* (plus appropriate loaders) and take the strings inside.
- PS3: first decrypt EBOOT.BIN to EBOOT.ELF, using *TrueAncestor SELF Resigner*
- X360: first decrypt default.xex, using XEXTool (`xextool.exe -e u -c u -o decrypted.xex default.xex`)

### add data strings
For games where names come from scripts and data files you can look around and find those, and extract names with `strings2` then add to `wwnames.txt`.

Sometimes that's too time consuming since there can be many scripts, so here is a shortcut:
- unpack game's archives (may need to use appropriate programs or .bms) and remove useless/big data (like graphic/shaders/textures/audio/movies/models/etc).
- if files are compressed (like *Unity* or *Unreal Engine* files) don't forget to uncompress first
- in rare cases names may be in a SQLite database (.db), use some program like DB Browser to open and extract needed tables (`strings2` may extract names too but this is cleaner).
- put resulting files in some in a folder
- make a zip of that folder with *no compression* set.

This makes a "solid" archive that has everything. Then apply `strings2.exe` to the whole archive to extract all text at once.

### clean incorrectly extracted strings
Because `strings2.exe` can only guess so much, sometimes it gets names like `fbgm_play` instead of `bgm_play`, so you may want to recheck a bit (try searching `wwnames.txt` for obvious things like `bgm` to see everything looks ok).

You don't need to clean all the garbage strings it creates (names like `$asDFFC`) since it's time consuming and will most likely are ignored. But in some cases you may want to remove names that give false positives.

Sometimes game's files have lines like `C_PlayMusic("bgm_results")`, those are automatically handled by *wwiser* and read `bgm_results` just fine (explained before).

### ignore close numbers
If you have numbers that are the same save the last 2 digits (more or less) that means they share the same root and you only need to reverse one, wwiser automatically fills the rest. For example with 1189781958 and 1189781957 you only need to reverse first (`bgm1`), second (`bgm2`) will be automatically found.

### try newer/older games lists' as a base
Sequels sometimes share base Wwise project and names (ex. *Doom Eternal* vs *Doom 2016*), so it's useful to include names from previous names, and also names from newer games in older games works too.

You can even include very different games but it increases the chance of false positives (make sure to clean the final list).

### try similar names
Files may have `bgm_start` and `bgm_mute` that are properly used, but you are missing other bgm-related names.
It's worth adding some variations of the above that could be used, like `bgm_stop` or `bgm_unmute`.

This is good to test with the `fnv.exe` reversing tool (explained before), as `fnv.exe (number) -p "bgm_"` may reverse some of those variations with some guessing.

When guessing keep in mind name styles the dev uses their games. For example, one dev may often use "bgm_(stage)_001", other likes "play_mus_(stage)", other "play_music_(stage)", etc.

### trim prefixes/suffixes
Sometimes you can find games with "variable-setter" events, for example `Set_State_BGM_Vocal_On`. This often means variable isn't referenced directly (no associated name), but with some luck `BGM_Vocal` will be the missing name. So looking for `Set_(something)` or `(something)_on/off` and removing the prefix/suffix is a good way to try a few extra names. Other suffixes like `_in/out` work, as well as adding the other prefix/suffix (if you have `(something)_on` but not `(something)_off`, or `stop_(something)` but not `play_(something)`).

## check close/related Wwise objects
The way `bnk` saves objects (see `.xml` wwiser generates) actually has some semblance of order. Some parts (like playlist children) are ordered by ID, but events often are saved near related objects, and particularly `init.bnk` may have a `GlobalSettingsChunk` that lists all variables in dev order.

If you have some named variables in that chunk you can narrow the search a lot. For example in Nier Automata: we have 3 variables: `BGM_Shop`, `3758536580`, `BGM_Slow`. Logically `3758536580` must be `BGM_Sh*/BGM_Si*/BGM_Sl*`. `Si*` looks the most likely, so we try `fnv.exe 3758536580 -p BGM_Si`. No results, but just in case again with extra checks disabled (these speed up reversing but also reject some less common names): `fnv.exe 3758536580 -p BGM_Si -i`. Now one of the results is `BGM_Sine_1khz`, which makes sense as the variable is used with channel test events.

For events, follow called IDs (see `tid`) and see what actions they trigger for hints. Events `BGM_Area_CampRoom_Out` and `BGM_Area_CampRoom_In` calls a SetState action that changes variable `4087916061` to value `on/off`. After some reversing that variable happens to be `BGM_Camp_Duck`. If values were `EN/JP`, that variable would have to do with `vocal` or `language`, etc.

### use words.py
To help testing you can use this script: https://github.com/bnnm/wwiser-utils/blob/master/scripts/words.py (for advanced users). It automates some of the above tips. This is mainly useful when we already have a bunch of names (names are somewhat previsible) but are missing some others.

Basically make a `words.txt` list of things like `BGM_Vocal_Camp_Off`, launch `words.py` in the dir and it'll generate in `words_out.txt` a list of split parts (`BGM`, `BGM_Vocal_Camp` `Vocal_Camp_Off`, `Vocal_Camp`, `Vocal`, etc) from those words. This is useful because `Vocal` or `Vocal_Camp` are likely to be used as variable/values. It's best to start with all names we have, copy `wwnames.txt` and rename to `words.txt`.

You can make `formats.txt` and add prefixes/suffixes: `%s`, `BGM_%s`, `BGM_%s_On`, `BGM_%s_Off`, `BGM_Play_%s`, etc. This will also make things that weren't in the original words, like `BGM_Play_Camp`, `BGM_Vocal_Camp_On` and so on (so you can target a certain type of names like missing `BGM_*`). Also remember last letter are auto-calculated, so a format like `%s_0` may find `BGM_Vocal_A` `BGM_Vocal_B`.

Key here is we want quantity over quality. Just generate huge lists of possible names, rename `words_out.txtp` to `wwnames.txt` and let *wwiser* decide which names are good enough, as long as you have free memory big-ish files (ex. +300MB) are ok. You can get a bunch of false positives this way, but most should be obviously fake like `BGM_Voca4` (a few may need to be checked how are they used in the `.xml`).

If there is a `fnv.txt` present with some ID numbers, instead of writing all generated words it'll only write words that match one of those IDs. Remember missing names can be created with *wwiser* using `-sl -sm`.

For the daring you can use the combinator feature. `words.py -c N` takes `words.txt` and tries all combinations of N parts (`formats.txt` are also applied after those combinations). For example from `BGM`, `Vocal`, `Camp` `Desert` in `words.txt`, `-c 3` makes `BGM_Desert_Camp`, `BGM_Vocal_Desert` `Vocal_Camp_BGM` `Desert_BGM_Vocal` and so on. Many will be useless but again, quantity over quality. You can squeeze out a few names this way.

Downside is that many words + high `-c N` = humongous number of results. So `words.txt` here should be restricted to mostly relevant words (remove `Desert` if you aren't trying to find events related to that). Best is to combine with `fnv.txt` to reverse only, since generated `.txt` can be +GBs big otherwise. Try `-c 2` and see if some names worked, reduce words and try `-c 3`. `-c 4` is possible but could take a few hours, `-c 5` and beyond may take ages. Add `-S` to disable the *split words by _* feature to fine tune your word count too.

### clean incorrectly used strings
Sometimes seemingly correct words are marked as used, like `sheep`. Because how Wwise creates names there is a chance some words can be used in incorrect places. Check that `banks.xml` wwiser creates for suspicious words and see they are not used in incorrect places (wwiser sometimes will do this). Generally only events/states/variables/values/busses and a few other are allowed to have names. If `banks.xml` is too big find strings in a hex editor (much faster).

### repeat steps
Since the list keeps growing it's useful to repeat some steps so newer names have a chance to contribute. For example, after using `words.py` we later reverse `BGM_Sine_1khz`. Then calling `words.py` again with a bunch of formats variations revealed `BGM_Stop_1khz`, `Ot_1khz`, `BGM_Set_Ot_1khz`, and so on.

### give up
Say you have almost every name-number down, save a couple. Just need to try a few more names...! Well, bad news: sometimes it's just too hard. Give up and move on. But you can always come back later, maybe names you need will be in the sequel or other game, or some extra tricks to get names will be added later.

Remember that you can call wwiser with `-sm` to print all missing numbers in generated `wwnames.txt`.
