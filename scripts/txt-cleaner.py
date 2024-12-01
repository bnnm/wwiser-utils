# Cleans text files from strings2.exe garbage
#TODO IDEAS
#- make N-grams from ENG words > not accurate enough (games use custom stuff)
#- ignore start of N chars if not good enough > time consuming to make
#- ignore words that don't contain anything from a ENG list > may skip useful names to be used


import os, sys, itertools, re
import fnmatch

SPLIT_LINES = True
LINE_MAX = 60
REMOVE_NUMBERS = False
REMOVE_NUMBER_LETTERS_MAX = 0 #5abcd abcd5
MIN_LETTERS = 4
ACCEPTABLES_MIN = 50
REMOVE_IGNORABLES = True
REMOVE_NON_VOCALS = False

RENAMES_FILE = '_txt-renames.txt'
IGNORABLES_FILE = '_txt-ignorables.txt'

_PATTERN_WRONG = re.compile(r'[\t.<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
_PATTERN_SPLIT = re.compile(r'[\t.<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*% -]')
_WORD_ALLOWED = ['xiii', 'xviii','zzz']

_RENAMES = []
_IGNORABLES = []
_IGNORABLES_START = []
_IGNORABLES_MIDDLE = []
_IGNORABLES_END = []

_RENAMES_START = []
_RENAMES_MIDDLE = []
_RENAMES_END = []

_ACCEPTABLES_START = []
_ACCEPTABLES_MIDDLE = []

REPEATS_EXTENDED = ['i', 't', 'l']

DONE = set()


def get_external_lines(filename):
    items = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    continue
                line = line.split('#')[0]
                line = line.strip()
                items.append(line)
    except FileNotFoundError:
        pass
    return items
        

def load_renames():
    lines = get_external_lines(RENAMES_FILE)
    _RENAMES.extend(lines)

    for _RENAME in _RENAMES:
        if _RENAME.startswith('*') and _RENAME.endswith('*'):
            _RENAMES_MIDDLE.append(_RENAME[1:-1].lower())
        elif _RENAME.endswith('*'):
            _RENAMES_START.append(_RENAME[:-1].lower())
        elif _RENAME.startswith('*'):
            _RENAMES_END.append(_RENAME[1:].lower())

def load_ignorables():
    lines = get_external_lines(IGNORABLES_FILE)
    _IGNORABLES.extend(lines)

    for _IGNORABLE in _IGNORABLES:
        if _IGNORABLE.startswith('*') and _IGNORABLE.endswith('*'):
            _IGNORABLES_MIDDLE.append(_IGNORABLE[1:-1].lower())
        elif _IGNORABLE.endswith('*'):
            _IGNORABLES_START.append(_IGNORABLE[:-1].lower())
        elif _IGNORABLE.startswith('*'):
            _IGNORABLES_END.append(_IGNORABLE[1:].lower())
        

load_renames()
load_ignorables()

#----

def get_match_max(line, regex):
    count = 0
    for match in regex.finditer(line):
        count += 1
    return count

def is_match_max(line, count, max):
    if count >= max:
        return True
       
    return False
   

def is_line_ok(line):
    line = line.strip()
    line_lw = line.lower()
    line_len = len(line)
    #print(line, line_len)

    if line_lw in DONE:
        return None
    DONE.add(line_lw) #hash may take less memory, python hash function isn't useful here tho

    if line_lw in _WORD_ALLOWED:
        return True

    if MIN_LETTERS and line_len < MIN_LETTERS:
        return False
        
    #if '\x00' in line:
    #    return False

    # skip wonky mini words
    if line_len <= 4 and _PATTERN_WRONG.search(line):
        return False
    
    if REMOVE_NON_VOCALS and not any(char in 'aeiou' for char in line_lw):
        return False
        
    if LINE_MAX and line_len > LINE_MAX:
        return False
    
    if REMOVE_NUMBER_LETTERS_MAX and line_len <= REMOVE_NUMBER_LETTERS_MAX:
        if any(char in '1234567890' for char in line_lw):
            return False

    
    # skip mini words with several letters
    max_match = get_match_max(line, _PATTERN_WRONG)
    if (line_len >= 4 and line_len <= 5) and max_match == 2:
        return False
    if (line_len < 10) and max_match >= 3:
        return False
    #if (line_len > 50) and max_match >= 10:
    #    return False

    #if line_len < 12:
    #    for key, group in itertools.groupby(line):
    #        group_len = len(list(group))
    #        if key.lower() in ['0', '1', 'x', ' ']: #allow 000, 111, xxx
    #            continue
    #        if group_len > 2:
    #            return False

    if REMOVE_NUMBERS and line.isnumeric():
        return False

    if REMOVE_IGNORABLES:
        #for ignorable in _IGNORABLES:
        #    if fnmatch.fnmatch(line_lw, ignorable):
        #        return False
        if any(line_lw.startswith(sub) for sub in _IGNORABLES_START):
            return False
        if any(line_lw.endswith(sub) for sub in _IGNORABLES_END):
            return False
        if any(sub in line_lw for sub in _IGNORABLES_MIDDLE):
            return False

    # odd 'xAxBxCx' repeats
    if '_' not in line_lw and '_0x' not in line_lw:
        # - not lowercase to avoid stuff like HallucinogenicInitial many i
        # - don't skip valid words like 'Abilities', 'Parallels'
        #TODO: skip "takayama", "deleteme"
        is_extended = any(sub in line_lw for sub in REPEATS_EXTENDED)
        if line_len >= 6 and not is_extended:
            # not 'i' since 'Abilities' 
            for i in range(6, line_len):
                if line[i-0] != line[i-1]:
                    if line[i-0] == line[i-2] == line[i-4] and line[i-0] not in REPEATS_EXTENDED:
                        return False
        if line_len >= 8 and is_extended:
            for i in range(6, line_len):
                if line[i-0] != line[i-1]:
                    if line[i-0] == line[i-2] == line[i-4] == line[i-6]:
                        return False
        #else:
        #    for i in range(6, line_len):
        #        if line_lw[i-0] != line_lw[i-1]:
        #            if line_lw[i-0] == line_lw[i-2] == line_lw[i-4]:
        #                return False

    if _ACCEPTABLES_START:
        is_acceptable = False
        for acceptable in _ACCEPTABLES_START:
            if line_lw.startswith(acceptable):
                is_acceptable = True
                break
        if not is_acceptable:
            return False

    if _ACCEPTABLES_MIDDLE:
        is_acceptable = False
        for acceptable in _ACCEPTABLES_MIDDLE:
            if acceptable in line_lw and not line_lw.startswith(acceptable):
                is_acceptable = True
                break
        if not is_acceptable:
            return False

    return True


def read_line_main(line, outfile_ok, outfile_ko, outfile_dp):
    if not line:
        return

    if True:
        line_lw = line.lower()
        for _RENAME in _RENAMES_START:
            if line_lw.startswith(_RENAME):
                line    = line   [len(_RENAME):]
                line_lw = line.lower()
                break
        for _RENAME in _RENAMES_END:
            if line_lw.endswith(_RENAME):
                line    = line   [:-len(_RENAME)]
                line_lw = line.lower()
                break

    res = is_line_ok(line)
    if res is None:
        outfile_dp.write(line + '\n')
    elif not res:
        outfile_ko.write(line + '\n')
    else:
        outfile_ok.write(line + '\n')


def read_line(line, outfile_ok, outfile_ko, outfile_dp):
    line = line.strip("\n")
    line = line.replace('\x00', ' ')
    if not line:
        return

    if SPLIT_LINES:
        items = _PATTERN_SPLIT.split(line)
        if len(items) == 1:
            read_line_main(line, outfile_ok, outfile_ko, outfile_dp)
        else:
            for item in items:
                read_line_main(item, outfile_ok, outfile_ko, outfile_dp)
    else:
        read_line_main(line, outfile_ok, outfile_ko, outfile_dp)


def read_file(in_name, out_name_ok, out_name_ko, out_name_dp):
    encodings = ['utf-8-sig', 'iso-8859-1']
    done = False
    try:
        for encoding in encodings:
            try:
                with open(in_name, 'r', encoding=encoding) as infile, open(out_name_ok, 'w', encoding=encoding) as outfile_ok, open(out_name_ko, 'w', encoding=encoding) as outfile_ko, open(out_name_dp, 'w', encoding=encoding) as outfile_dp:
                    for line in infile:
                        read_line(line, outfile_ok, outfile_ko, outfile_dp)
                    done = True
                break
            except UnicodeDecodeError:
                continue
    except FileNotFoundError:
        print("file not found")
        pass

    if not done:
        print("couldn't read input file %s (bad encoding?)" % (in_name))

def main():
    if len(sys.argv) <= 1:
        print("missing filename")
        return

    try:
    #if True:
        with open('fnv3.lst', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    line, number = line.split(':')
                    if int(number) < ACCEPTABLES_MIN:
                        continue
                if line.startswith('^'):
                    _ACCEPTABLES_START.append(line[1:]) # + '*'
                else:
                    _ACCEPTABLES_MIDDLE.append(line) #'*' + line + '*'
        print("loaded trigrams")
    except:
        # not found
        #print("ignored trigrams")
        pass


    for i in range(1, len(sys.argv)):
        in_name = sys.argv[i]
        if 'split' in in_name:
            SPLIT_LINES = True

        base, _ = os.path.splitext(in_name)
        out_name_ok = base + "_ok.txt"
        out_name_ko = base + "_ko.txt"
        out_name_dp = base + "_dp.txt"
        read_file(in_name, out_name_ok, out_name_ko, out_name_dp)

# #####################################

if __name__ == "__main__":
    main()
