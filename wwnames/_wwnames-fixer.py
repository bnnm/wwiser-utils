# Tool to fill IDs in wwnames:
# - make a missing ID list with missing IDs
#   - should have lines like "# 3933301714"
# - add words.py reversed names, format "3933301714: banana"
# - run this tool (drag and drop)
#   - this will replace "# 3933301714" with "banana"
#   - if list has "### (name)" sections, sections are sorted too
# - output is "(name)-clean.txt", except if (name) is wwname-*.txt in which case will be replaced
# - if some name is wrong add "#ko" at the end ("ZZSXSBanana #ko")
#   - use this script and wrong name will be converted back to "# (hash number)"

import sys, re

FULL_CLEAN = True
CLEAN_ORDER = True
UPDATE_ORIGINAL = True
FNV_FORMAT = re.compile(r"^[A-Za-z_][A-Za-z0-9\_]*$")
HDR_FORMAT1 = re.compile(r"^###.+\(langs/(.+)\.bnk\)")
HDR_FORMAT2 = re.compile(r"^###.+\((.+)\.bnk\)")


def is_hashable(hashname):
    return FNV_FORMAT.match(hashname)


def get_fnv(name):
    namebytes = bytes(name.lower(), 'UTF-8')
    hash = 2166136261 #FNV offset basis

    for namebyte in namebytes:  #for i in range(len(namebytes)):
        hash = hash * 16777619 #FNV prime
        hash = hash ^ namebyte #FNV xor
        hash = hash & 0xFFFFFFFF #python clamp
    return hash

def get_solved(line):
    if ':' not in line:
        return None

    sid, hashname = line.split(':', 1)
    sid = sid.strip()
    hashname = hashname.strip()

    if not sid.isdigit():
        return None
    if not is_hashable(hashname):
        return None
    return (sid, hashname)

# remove double \n
def clean_lines(clines):
    prev = '****'
    lines = []
    for line in clines:
        if not line and not prev:
            continue
        prev = line
        lines.append(line)

    return lines

def sorter(elem):
    pos = 0
    item = elem.lower()
    if not elem:
        pos = 10
    elif elem[0].isdigit():
        pos = 1
    elif elem[0] == '#':
        pos = 2
        item = None # don't change order vs original (sometimes follows dev order)
    return (pos, item)

def order_list(clines):
    if not CLEAN_ORDER:
        return clines

    lines = [] #final list
    
    section = None
    slines = [] #temp section list

    for line in clines:
        s_end = not line
        s_start = line.startswith('### ')

        if (s_end or s_start) and section:
            # section end
            if slines: #only if section has something
                slines.sort(key=sorter)
                lines.append(section)
                lines.extend(slines)
            section = None
            slines = []

        if s_start:
            # register section header
            section = line
            continue

        if section:
            # lines within section
            slines.append(line)
        else:
            # any other
            lines.append(line)

    # trailing section
    if section and slines:
        slines.sort(key=sorter)
        lines.append(section)
        lines.extend(slines)

    return lines



def fix_wwnames(inname):
    blines = []
    hashed = {}
    koed   = set()
    cases  = {}


    # first pass
    with open(inname, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\r')
            line = line.strip('\n')

            items = get_solved(line)
            if items:
                # register solved ids and ignore line
                sid, hashname = items
                if sid not in hashed:
                    hashed[sid] = []
                if hashname not in hashed[sid]:
                    hashed[sid].append(hashname)
            else:
                # register base lines as-is, except when fixing headers
                if line.startswith('### '):
                    bankname = ''

                    match = HDR_FORMAT1.match(line)
                    if not match:
                        match = HDR_FORMAT2.match(line)
                    if match:
                        bankname, = match.groups()

                    if bankname.isdigit():
                        sid = int(bankname)
                        hashnames = hashed.get(sid)
                        if hashnames:
                            line = line.replace('.bnk', '.bnk: %s' % hashnames[0])

                # use case as found in first line 
                # (so if BLAH is used in several points and changed once to Blah, other points use that too)
                if line.lower() in cases:
                    line = cases[line.lower()]
                else:
                    cases[line.lower()] = line
                blines.append(line)

                if not line.startswith('#'):
                    hashname = line.split('#')[0]
                    sid = get_fnv(hashname)
                    if sid not in hashed:
                        hashed[sid] = []
                    if hashname not in hashed[sid]:
                        hashed[sid].append(hashname)


    section = False
    clines = []
    for bline in blines:
        if bline.startswith('### '):
            section = True
    
        if bline.lower() in koed:
            sid = get_fnv(bline)
            bline = "# %s" % (sid)

        if bline and bline.startswith('#ko') and ':' in bline and FULL_CLEAN:
            _, hashname = bline.split(':')
            hashname = hashname.strip()
            sid = get_fnv(hashname)
            koed.add(hashname.lower())
            if section:  # '#ko' on top get ignored
                bline = "# %s" % (sid)
            else:
                continue

        if bline.endswith('#ko') and FULL_CLEAN:
            if bline.startswith('# '):
                fnv = bline.split(' ')[1]
                koed.add(fnv.strip())
                continue
            elif bline.startswith('#'):
                pass
            else:
                hashname, _ = bline.split('#ko', 1)
                hashname = hashname.strip()
                sid = get_fnv(hashname)
                koed.add(hashname.lower())
                if section: # '#ko' on top get ignored
                    bline = "# %s" % (sid)
                else:
                    continue


        if bline.startswith('# ') and ':' not in bline:
            sid = bline[2:].strip()
            if sid in hashed:
                hashnames = hashed[sid]
                for i, hashname in enumerate(hashnames):
                    if FULL_CLEAN:
                        bline = "%s" % (hashname)
                    else:
                        bline = "%s: %s" % (sid, hashname)
                    if i > 0:
                        bline += ' #alt'
                    clines.append(bline)
                continue

        clines.append(bline)


    clines = order_list(clines)
    clines = clean_lines(clines)
    outname = inname
    
    update = UPDATE_ORIGINAL and 'wwnames' in outname
    if not update:
        outname = outname.replace('.txt', '-clean.txt')
    with open(outname, 'w', encoding='utf-8') as f:
       f.write('\n'.join(clines))


def main():
    if len(sys.argv) < 2:
        print("name not found")
        return
        
    for i in range(1, len(sys.argv)):
        inname = sys.argv[i]
        fix_wwnames(inname)

if __name__ == "__main__":
    main()
