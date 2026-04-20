# WORDS.PY

Reverses hashes by reading words and hashing new word combos.

It reads from various pre-formatted files and mixes words depending on input flags (see *usage*).

## Explanation
*words.py* uses a type of dictionary attack, so it needs words lists from games to work properly, plus hashes to reverse.

The theory being, if a game uses `play_bgm_01` it might as well use `stop_bgm_01` `play_bgm_02` or `play_sfx_01`. So it also needs `stop` and `sfx` somewhere in the word list (even if those aren't valid hashes) and a reversable hash like `3030862532` (`stop_bgm_01`). It will create a lists of candidate names in the form of: `3030862532 : stop_bgm_01`.

Word lists with lower/uppercase/symbols/incorrect words are fine, will be ignored or adjusted as needed. The idea is being able to put extracted string from binaries (from `wstrings` or other tools) and still work reasonably well (quantity over quality).

It's mainly geared towards to reverse Wwise hashes but can be tweaked for use others.

## Usage
The tool is meant to be used like this:
- generate `wwnames*.txt` that includes both known valid hashable words plus a list of missing hashes
- optionally include `ww.txt` with potentially useful names as ingredients for other words
- optionally create `formats.txt` to fine-tune mixing rules
- run `words.py` and it will create `words_out*.txt` if matches are found
- open `words_out*.txt` and select useful reserved hashes in the form of `3030862532 : stop_bgm_01`
  - since 32-bit hashes create many false positives this must be done carefully
- copy those reversed `hash : name` strings as-is in `wwnames*.txt` 
  - hashes will be recognized ignored from future reversing attempts
  - names can be used as pieces for more words in future reversing attempts
- re-run `words.py` with more flags
- repeat until satisfied

There are probably much better ways, but it's basically the dumb workflow developed to reverse Wwise names as various ideas were attempted.

## Input files

### wwnames*.txt
Default lists of words *words.py*. It's meant to be a distributable list of valid words and missing hashes.

It handles lines like this:
- `(lines)`: regular words used to reverse (typically valid words)
- `# (number)`: reversable hashes
- `# (text)`: ignored lines
- `### (section)`: contexts used to sort results (such as hashes from certain files), which make detecting false positives easier
- `(number) : (line)`: reversed hash, removed from the reversable list
- `(number)`: used as words (since it could be `02` to join as stems)

By default *lines* are also split by a separator, which defaults to `_` in Wwise but configurable to be 'empty'. Meaning `(word1)_(word2)_(word3)` is used to reverse but also `(word1)`, `(word2)`, `(word3)` but also `(word1)_(word2)` (not joining `(word1)_(word3)` by default).

Lowercase/uppercase/symbols/incorrect words are fine (will be ignored or adjusted as needed). Characters that aren't part of words are split as well: `(word1)_(word2) (word3)$(word4)` are takes as `(word1)_(word2)`. `(word3)` and `(word4)` (but not `(word3)$(word4)`).

### formats.txt
List of formats, in the form of `%(command)`. By default uses `%s` if not found/empty.

It's meant to be used to include "probable" prefixes/suffixes like `Play_%s`, `%s_bgm`.

Available commands:
- `%s`: basic ("Play_%s": combines with existing words)
- `%Nd`/`%Ni`/`%Nx`: adds 0, 1, 2..., where N is max number of chars (up to 8)
- `%0Nd`/`%0Ni`/`%0Nx`: same but 0-padded
- `%0Nd:M:`: same but adds numbers in steps of M (`Play_BGM_%03i:5:` makes `Play_BGM_000`, `Play_BGM_005`, ...)
- `%0Nd^M^`: same but limits numbers to M (`Play_BGM_%03i^20^` makes `Play_BGM_000` up to `Play_BGM_020`)
- `%0Nd:M:^M^`: same combined
- `%[123abc]`: adds 1,2,3,a,b,c (`Play_BGM_1%[ab]` makes Play_BGM_1a, Play_BGM_1b)
- `%c`: same as [abcd(..)z]

Any can be combined but may only use one `%s`: `play_%02x_%s`, `play_%i_%i_%d` but not `play_%s_%s`.

Can also add filters to only accept or skip only some names/hashes within sections (`### (something)` in `wwnames.txt`):
- `#@filter-names *music_data* *_mu_playgo* *_Music* *MasteryChallenge_Music*`
- `#@filter-hashes *BNK_DLC_14800_Music_Data*`
- `#@skip-names *(langs*`
- `#@skip-hashes *(langs*`

### ww.txt
Extra list of words. It's meant to supplement the base game list to the main game lists.

Unlike `wwnames*.txt` it ignores hashes/sections and these words don't participate in some flags by default.

### hashes.txt
Extra list of hashable IDs only.

Unlike `wwnames*.txt` it only reads numbers.

### words_out.txt
Output of reversed hashes in the form of `3030862532 : stop_bgm_01`.

## Modes
Modes of operation:
- default: creates words from words
- combinations: takes input words and combines them: A, B, C: A_B, A_C, B_A, C_A, etc.
- permutations: takes input words divided into "sections". Add "#@section#" in words list to end
  a section, or a new file. If section 1 has A, B and section 2 has C, D, makes: A_C, A_D, B_C, B_D.
- auto-formats: generates words as formats, combined with the amove for many variations: A_B may make %s_A_B, A_%s_B, A_B_%s

By default words are combined with a separator like `_` but can be modified via parameters.

They also combine with `formats.txt` (`play_%s`: `play_A_C`, ...).

When reversing it may enable/disable "fuzzy matches" (ignores last letter) to find hashes, as some modes are very prone to false positives.

Examples:
- from word `Play_Stage_01` + format `%s` (default)
  - makes: `Play`, `Stage`, `01`, `Play_Stage`, `Stage_01`, `Play_Stage_01`
  - `Stage`, `Stage_01` could be valid names
- from word `Play_Stage_01` + format `BGM_%s`:
  - makes: `BGM_Play`, `BGM_Stage`, `BGM_01`, `BGM_Play_Stage`, `BGM_Stage_01`, `BGM_Play_Stage_01`
  - `BGM_Play`, `BGM_Stage`, `BGM_Play_Stage` could be valid names
- using combinator mode with value 3 + word list with "BGM", "Play", "Stage"
  - makes: `BGM_Play_Stage`, `BGM_Stage_Play`, `Stage_BGM_Play`, `Stage_Play_BGM`, etc
  - also applies formats


## Performance
This tool is fairly slow, but it's reasonably fast when using *pypy* and mainly uses python for flexibility. It's meant to test variations of small-ish word lists and prograssively using more complex modes.

While it could be improved to handle bigger lists/modes faster, the actual limitation of Wwise 32-bit hashes is the high number of false positives (that look plausible enough without context). Making it faster would just make unusable results faster, so using smaller sets is recommended.
