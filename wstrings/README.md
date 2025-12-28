# WSTRINGS

Finds valid strings within files recursively, mainly to reverse Wwise names (or "parts" for words.py).
 
Similar to strings2 with these diffs:
- skips dupes (case insensitive by default for wwise)
  - may not skip all dupes depending on set memory limit, but that's fine for this use case
- ignores some short strings that aren't useful for Wwise
- reads files in paths recursively and dumps everything automatically to ww_<dirname>.txt
- string detection is simpler since it's mainly geared towards Wwise needs
  (ex. it may not extract UTF8 correctly, but those can't be used for Wwise anyway)

Compile as 64-bit to open large files:
```
gcc -m64 -Wall -O3 wstrings.c
``` 
