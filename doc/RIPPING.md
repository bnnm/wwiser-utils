# RIPPING WWISE GAMES

## TL;DR:
Quick guide to get decent Wwise rips
- get latest wwiser: https://github.com/bnnm/wwiser/releases
- put all .bnk and .wem in a dir
  - .bnk/wem may be in other bigfiles like .pck, use this:
     https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise_pck_extractor.bms
- put SoundbankInfo.xml/(bankname).txt/Wwise_IDs.h/etc (or `wwnames.txt`) with the `.bnk` too
  - you want ALL of those, SoundbankInfo.xml doesn't have every name
  - if you don't have those it's still possible to get names using `wwnames.txt`, see
    https://github.com/bnnm/wwiser-utils/blob/master/doc/NAMES.md
- open (double click) wwiser.pyz
  - make sure you have "wwnames.db3" in wwiser folder
- press LOAD and choose some .bnk (bgm.bnk or just all of them)
  - It's recommented to load `init.bnk` (also `1355168291.bnk`) too if you have companion files.
- check `move referenced .wem to subdir` if you are doing a distributable rip
  - if you aren't, you can uncheck it and set `wem subdir` to `..` so you don't have to move wem/bnk files later
- press GENERATE to get .txtp (pay attention to log, you may need to tweak things manually)
  - this creates /txtp folder with .txtp and /txtp/wem folders with .wem
- before continuing on make sure about these points:
  - if you loaded `C:\blah\bgm.bnk` and generated TXTP, you should now have a `C:\blah\txtp\` folder
  - inside that new folder, there is a bunch of (something).txtp
  - each .txtp points to one or several .wem files, that (by default) are expected to be inside `C:\blah\txtp\wem\`
  - with the `move .wem to subdir` option wems are moved automatically, so you should have `C:\blah\txtp\wem\123456789.wem`
  - in some cases you also need to move .bnk to `C:\blah\txtp\wem\`
    - *wwiser* tells you which ones in the output log, or just move all .bnk
- test .txtp with vgmstream (you may need to tweak some manually to improve)
  - if you change .txtp also change the filename so it doesn't get overwritten if re-generated
    - ex. from "blah {r}.txtp" you may need to make "blah {r1}.txtp" "blah {r2}.txtp"
- remove unwanted .txtp (like voices)
- use these scripts to move .wem not in .txtp to /unwanted:
  https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise-cleaner.py
  https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise-cleaner-bnk.py
  - this only moves .wem from the /wem (or similarly named) folder
  - check if /unwanted does have wanted music (you may have removed good .txtp)
  - normally you don't need to keep /unwanted in the rip, if it only contains sfx/voices
- use this script to remove unused .bnk as well:
  https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise-cleaner-bnk.py
  - this moves .bnk in /wem folder, and the folder with .txtp (so move .bnk there first)
  - note that it will keep .bnk used to generate, .bnk used to play, and init.bnk
- check if there are .wem in root (before /txtp folder) not moved with have useful/unused audio
  - put those in "/unused" folder
  - these can be unused unique .wem, unused copies of other .wem, or unused copies of .wem inside .bnk
  - use this script to move .wem in /unused that aren't unique to dupe folder:
    https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise-dupes.py
- include companion files (.xml/.txt/etc) + .bnk in some /extra folder or !extra.7z
  - you may need to re-generate when new features/fixes are added (!!!)
  - some .bnk may need to go to /wem folder instead (see log!), might as well put all files there
- 7zip files and folders (with .txtp in root) + upload rip somewhere

Note! .txtp are Good Enough but not perfect in all cases. This means you may need to generate them again later when I fix bugs. I wanted to make them future-proof and avoid re-generating but it was too time-consuming, sorry.

**NOTE ABOUT WWISE**
Wwise never, ever plays *(number).wem* directly. Instead, it uses .bnk to indirectly play one or many .wem, through "events", with config. wwiser creates .txtp that simulate that so results are as accurate as possible. Loops and other audio info is in the .bnk, not the .wem. Please Understand.

This tool doesn't and won't modify .bnk.


## LONG GUIDE
Recommended steps to follow when ripping Wwise games.


### FIND FILES
You *need* `.bnk` and possibly `.wem`, put those together in a dir. Banks store song info (loops) and sometimes audio, `.wem` are audio.

If your game has `.pck`, extract `.bnk+wem` inside first using: https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise_pck_extractor.bms (you don't need to extract `.wem` inside `.bnk`).


### FIND NAMES
Games may have "companion files" with names, like one of the following: `SoundbankInfo.xml`, `(bnk name).txt`, `Wwise_IDs.h`.

Put together with the `.bnk` so the tool can use them to get names.

If game doesn't have them, some name lists for known games can be found here, download and put wwnames.txt near the .bnk: https://github.com/bnnm/wwiser-utils/blob/master/wwnames/


### OPEN WWISER
Make sure `wwiser.pyz` has a file called `wwnames.db3` nearby (has common names = good). Double click to open the GUI, then "LOAD" and select `bgm.bnk` or similar banks that may contain music.

If your files only have funny numbers, try to locate `412724365.bnk` (bgm.bnk in Wwise), `3991942870.bnk` (music.bnk) or open big-ish banks first, or open all banks even.

For games with companion files it's a good idea to load `init.bnk` (`1355168291.bnk`), as some names that bnk/txtp uses are only in `init.txt`. Similarly some games load multiple `.bnk` at once 


### EXPLORE BANK
You may want to check the bank's internal info, press "Viewer START", not for the faint of heart though. If you are bored press the "doc" button and try to understand the whole thing.


### GENERATE TXTP
In the GUI, you should probably check "move .wem referenced in banks" (change dir name as preferred), then press the GENERATE button.

PAY ATTENTION TO THE LOG! If you get lines like "load more banks?", you may have to, well, load multiple banks at the same time to get all songs (can't guess which banks). But banks can be buggy too and just have missing things (but do try to find other banks first, maybe in bigfiles). If you still can't guess which banks to load just load all at the same time, though you'll get lots of sfx .txtp. If you get warning "unused audio" there is an option to generate it, BUT first try loading other banks first and see if message goes away (you'll get better results).

If you get are more ominous-sounding ERRORs, report (still WIP).


### CHECK TXTP
If all went well, there should be a *txtp* subfolder, and `.wem` inside. Open the .txtp with vgmstream and listen a bit to check it all worked. Particularly filenames with: *{!}*=missing .wem/features, *{r}*=random .wem (may need to manually select one), *{s}*=multi-tracks (may need to manually silence wems), *{m}*=multi-loops (looping can't be exactly simulated ATM).

Since .txtp are generated for each "usable audio", there may be an excess of unwanted things like SFX (if `.bnk` mixes music and sfx together). You'll need to so some manual cleanup, unfortunately.

.txtp names are constructed from "usable parts" and tend to be a bit goofy and long-winded, but it's hard to make them meaningful otherwise. There is only so much the tool can do automagically.

There may be some `.wem` that weren't moved. These could be from other banks (like sfx), or unused `.wem` not used at all by any bank (not uncommon!). Move useful unused `.wem` to some "/unused" folder. Note that unused audio can be clones of other files, or `.wem` that are inside some `.bnk`, you can ignore those.

The `/wem` folder may have some unwanted SFX/voices moved automatically, previously used by deleted .txtp. Use this `.py` to find and move .wem not referenced in .txtp:
https://raw.githubusercontent.com/bnnm/wwiser-utils/master/scripts/wwise-cleaner.py


### GET MORE NAMES
If you don't have companion files with names (with names like `BGM-0591-event.txtp`), or the tool uses  funny Wwise numbers like `play_bgm [3991942870=1859734558].txtp`, there is a chance to improve this.

Follow this guide https://github.com/bnnm/wwiser-utils/blob/master/doc/NAMES.md and with some luck those can become `play_bgm [Music=bgm001].txtp`. You'll need to generate .txtp again though. This is not always possible though, so accept and move on.


### PREPARE RIP
Don't throw away the `.bnk` and companion files used to generate `.txtp`, put them in a "/extra" folder or !extra.zip or something (or /wem folder if they are needed, log will mention this).

Seriously, KEEP THE BNKS! When the tool is updated you may have to generate .txtp again to fix bugs.

Then zip the .txtp (in root folder) + /wem + /extra (+ maybe /unused) and upload that.


### REPORT ISSUES
Wwise is extremely complex, so sometimes TXTP can't play a song 100% like they should, or have bugs that cause some generation error, report those cases to see if something can be done. But read the README first: https://github.com/bnnm/wwiser/blob/master/README.md


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
