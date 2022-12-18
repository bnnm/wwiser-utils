# Cleans text files from strings2.exe garbage

import os, sys, itertools, re

_PATTERN_WRONG = re.compile(r'[\t.<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
_WORD_ALLOWED = ['xiii', 'xviii','zzz']
_BAD_GROUPS = ['uu', 'fwfw','ldlD', 'vwu']
_ENDS_WITH = ['bc']
DONE = set()

def is_match_max(line, regex, max):
    count = 0
    for match in regex.finditer(line):
        count += 1
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

    # skip wonky mini words
    if line_len < 4 and _PATTERN_WRONG.search(line):
        return False
        
    # skip mini words with several
    if (line_len >= 4 and line_len <= 5) and is_match_max(line, _PATTERN_WRONG, 2):
        return False

    if line_len < 12:
        # check for words like 
        for key, group in itertools.groupby(line):
            group_len = len(list(group))
            if key.lower() in ['0', '1', 'x', ' ']: #allow 000, 111, xxx
                continue
            if group_len > 2:
                return False

    if line_len < 7:
        for group in _BAD_GROUPS:
            if group in line_lw:
                return False

    for ew in _ENDS_WITH:
        if line_lw.endswith(ew):
            return False

    return True



def read_line(line, outfile_ok, outfile_ko, outfile_dp):
    line = line.strip("\n")
    if not line:
        return

    res = is_line_ok(line)
    if res is None:
        outfile_dp.write(line + '\n')
    elif res:
        outfile_ok.write(line + '\n')
    else:
        outfile_ko.write(line + '\n')


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

    for i in range(1, len(sys.argv)):
        in_name = sys.argv[i]

        base, _ = os.path.splitext(in_name)
        out_name_ok = base + "_ok.txt"
        out_name_ko = base + "_ko.txt"
        out_name_dp = base + "_dp.txt"
        read_file(in_name, out_name_ok, out_name_ko, out_name_dp)

# #####################################

if __name__ == "__main__":
    main()
