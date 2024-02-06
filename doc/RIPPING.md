# RIPPING WWISE GAMES


## TL;DR:
Quick guide to get decent Wwise audio rips
- get latest wwiser: https://github.com/bnnm/wwiser/releases
- find the *base dir* where .bnk and .wem reside (it's fine if they are in subdirs)
  - .bnk/wem may be in other bigfiles like .pck, extract first with this Quickbms script:
     https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise_pck_extractor.bms
- if you see SoundbankInfo.xml/(bankname).txt/(bankname).json/Wwise_IDs.h/etc in files leave them
  - those files contain names = good
- if you don't have those xml/txt it's possible to add names making a `wwnames.txt` file
  - check if they are here and rename to `wwnames.txt`:
    https://github.com/bnnm/wwiser-utils/tree/master/wwnames 
  - often you can find *several* names manually in game files, see
    https://github.com/bnnm/wwiser-utils/blob/master/doc/NAMES.md
  - you may still want `wwnames.txt` together with other files as SoundbankInfo.xml/etc may not have every name
- open (double click) *wwiser.pyz*, the GUI should load
  - make sure you have a recent version of python 3
- press *Load dirs...* and choose the *base dir*, this will load every bnk
  - if you have *tons* of banks it may be cleaner to select unwanted wem + press *Unload banks* (less `.txtp`)
    - or just load BGM `.bnk` manually
  - make sure `init.bnk` (or `1355168291.bnk`) is loaded as well for more accurate output
- press *Generate TXTP* to get a bunch of `.txtp` in `(base dir)/txtp/*.txtp`
  - stuff like `.wem` should be found automatically
  - pay attention to log window just in case
- test `.txtp` with vgmstream
- you may want to tweak some options to improve output, notably:
  - *Filter* box may be used to limit `.txtp` (like  `BGM_*` to only generate txtp for music)
  - *Groups:* options may be needed for games that use playlists for many tracks in annoying ways
  - if you have voices may want to set a default language
  - if you want to distribute your rip perhaps set *TXTP subdir* to `..` (so txtp are created before the *base dir* and wem/bnk data go in a subdir)
- remove unwanted .txtp and press the *Move .wm/bnk not used in .txtp* to move unneeded files to a dir
  - check if *(name)[unwanted]* has wanted music (you may have removed good .txtp)
  - *(name)[unused]* may have interesting variations, or just useless clones
- 7zip the files and subdirs (.txtp preferably in root folder) + upload the rip somewhere
  - you may need to re-generate when new features/fixes are added (!!!) so don't throw away .bnk or helper .xml/txt/etc files!

Note! .txtp are Good Enough but not perfect in all cases. This means you may need to generate them again later when I fix bugs. I wanted to make them future-proof and avoid re-generating but it was too time-consuming, sorry.

**NOTE ABOUT WWISE**
Wwise never, ever plays *(number).wem* directly. Instead, it uses .bnk to indirectly play one or many .wem, through "events", with config. wwiser creates .txtp that simulate that so results are as accurate as possible. Loops and other audio info is in the .bnk, not the .wem. Please Understand.

This tool doesn't and won't modify .bnk.


## OTHER NOTES
Recommended steps to follow when ripping Wwise games.

### EXPLORING BANKS
You may want to check the bank's internal info, press *View banks*. Not for the faint of heart though, ignore if you aren't *really* interested. If you are bored press the "doc" button and try to understand the whole thing.

*"But I just want to mod audio"*: good luck, you'll need to understand how Wwise works *and* how the `.bnk` works to do so (read other docs too).

### ISSUES WHEN GENERATING TXTPS
PAY ATTENTION TO THE LOG! If you get lines like "load more banks?", you may have to, well, make sure all appropriate banks are loaded (can't guess which banks). Some games have a few base/external .bnk and others inside bigfiles and needs some spelunking. Banks can be buggy too and just have missing things anyway (but do try to find other banks first).

If you get are more ominous-sounding ERRORs, report (still WIP).

### ISSUES WITH TXTPS
Particularly note of `.txtp` filenames with: *{!}*=missing .wem/features, *{r}*=random .wem (may need to manually select one), *{s}*=multi-tracks (may need to manually silence wems), *{m}*=multi-loops (looping can't be exactly simulated ATM).

Since .txtp are generated for each "usable audio", there may be an excess of unwanted things like SFX (if `.bnk` mixes music and sfx together). You'll need to so some manual cleanup, unfortunately (use the *Filter* box when *Generating TXTP* to make your life easier).

.txtp names are constructed from "usable parts" and tend to be a bit goofy and long-winded, but it's hard to make them meaningful otherwise. There is only so much the tool can do automagically. There is a *Renames* box to make names a bit more pleasant.

Also check *WWISER.md* for some more explanations about wierder cases.

### GETTING MORE NAMES
If you don't have companion files with names (with names like `BGM-0591-event.txtp`), or the tool uses  funny Wwise numbers like `play_bgm [3991942870=1859734558].txtp`, there is a chance to improve this.

Follow this guide https://github.com/bnnm/wwiser-utils/blob/master/doc/NAMES.md and with some luck those can become `play_bgm [Music=bgm001].txtp`. You'll need to generate .txtp again though. This is not always possible though, so accept and move on.


### REPORTING ISSUES
Wwise is extremely complex, so sometimes TXTP can't play a song 100% like they should, or have bugs that cause some generation error, report those cases to see if something can be done. But read the README first: https://github.com/bnnm/wwiser/blob/master/README.md

A common issue is *overlapped transitions*, where audio at loop points sounds a bit odd/skips this will be fixed when the time is right:
https://github.com/vgmstream/vgmstream/issues/1262


## POSSIBLY ASKED Qs

### "I WANT TO MOD WWISE AUDIO, CAN I USE WWISER"
Nope, sorry. This tool is not intended for that and can only read files, and will **never** modify .bnk.

### "I HAVE .WEM BUT I DELETED ALL .BNK, CAN I USE WWISER?"
Nope, sorry. Info about .wems is inside .bnk.

### "I USED SOUNDBANKINFO.XML TO RENAME .WEM TO SOMETHING ELSE, CAN I USE WWISER?"
.bnk and generated .txtp point to original names/numbers. You must re-rip, or un-rename to original Wwise numbers. Note wwiser has an option to create !tags.m3u (tags for vgmstream) for .wem.

### "I DON'T LIKE WWISE NUMBERS AND WANT TO RENAME .WEM TO OTHER THINGS"
This tool needs original Wwise numbers. There is an option to add .wem names to .txtp though. Understand those .wem names are never used, they are simply references for the sound designers during development. "Song names" would be event names + variable names (what is used in generated .txtp). 

### "SOME GENERATED TXTP DON'T WORK"
First, open the .txtp, and check all the (number).(ext) exist in the /wem (or configured) folder, as well as (name).bnk. If they don't, you need to fix that (remember .wem may be in some .pck or bigfile). If all looks in place yet fails, report and upload the .bnk and .wem.

### "SOME TXTP SOUNDS OFF/LOOP POINT ISN'T SMOOTH/HAS PROBLEMS"
This tool is still WIP. See wwiser's README for info about missing features, report bugs other than those.

### "WEM FOLDER HAS BYTE-EXACT FILE DUPES WITH DIFFERENT NUMBERS, CAN I REMOVE THEM?"
Not unless you want to manually change every .txtp that uses them, the tool can't guess this. But saving a few MB is not worth the effort (plus you may need to re-generate .txtp later and repeat that), storage is cheap.

### "I USED SOME RANDOM PROGRAM TO EXTRACT .WEM/BNK FROM .PCK AND GENERATED TXTP DON'T WORK"
This tool needs original Wwise numbers and correct extensions. Make sure you use this .bms to extract `.pck`:
https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise_pck_extractor.bms

### "I USED SOME RANDOM PROGRAM TO EXTRACT .WEM FROM .BNK AND GENERATED TXTP DON'T WORK"
First consider if you *REALLY* want this. The guide recommends to include `.bnk` in the rip for a reason, so might as well leave it untouched in the /wem dir. "*But my `.bnk` has sfx too!!!*". Well. Is it really worth for you wasting time to trim a few MB from a file you won't ever see or open manually? If so, make sure you check "treat internal .wem as external" when generating `.txtp`, and use this .bms to extract `.bnk`:
https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise_bnk_extractor.bms

If a file is marked with `{!}` this means it uses some hard-to-simulate feature and won't play/sound off/silent.

### "I DON'T HAVE .WEM BUT .WAV/XMA/OGG, WHAT DO I DO?"
Early games (before mid-2011) use those extensions, don't rename to .wem! That's correct and will work fine as-is, just pretend they are .wem. There is an option to use .logg/.lwav too, but it's not needed (.txtp work fine with .ogg/wav). Conversely if you used some random program to extract from bigfiles and your game is after mid-2011, you need to rename to .wem first.

### "I LOADED SOME .BNK THAT SHOULD CONTAIN MUSIC BUT NO TXTP ARE GENERATED"
You probably need to load the "base" bank together with that bank (try looking for files that have "event" in the name). If that fails load all banks at once. Games load bank combos manually so no way to guess.

### "I HAVE A BIG .BNK, DO I REALLY NEED TO KEEP IT IN THE RIP?"
You don't "need" to, but when this tool is updated you may need to re-generate .txtp, and keeping it around makes this easier (no need to re-rip the whole thing), plus having .bnk is a proof you did a decent rip.

### "THIS PROGRAM SUCKS AND I WON'T USE IT BECAUSE (something)"
You should enjoy your music in whichever way you prefer, so I (bnnm) am not bothered or anything if you don't want this. Though consider how complex Wwise is, so it's pretty awesome there is a tool that reverses it and creates pretty decent txtps, if I do say so myself.

### "I DON'T LIKE SOME OF THOSE STEPS, DO I REALLY NEED TO FOLLOW THIS?"
This is just a general guide to point you toward better Wwise rips. If you know what you are doing, well.
