# Tool to fill IDs in wwnames:
# - make a missing ID list with missing IDs
#   - should have lines like "# 3933301714"
# - add words.py reversed names, format "3933301714: banana"
# - run this tool (drag and drop)
#   - this will replace "# 3933301714" by "banana"
#   - if list has "### (name)" sections (like made with "#@classify-bank"), sections are sorted too
# - output is "(name)-clean.txt"

import sys, re

FULL_CLEAN = True
CLEAN_ORDER = True
FNV_FORMAT = re.compile(r"^[A-Za-z_][A-Za-z0-9\_]*$")


def is_hashable(hashname):
    return FNV_FORMAT.match(hashname)


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


def clean_lines(clines):
    last = -1
    
    while not clines[last]:
        last += -1

    last += 1
    if last < -1:
        clines = clines[:last+1]
    return clines

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
    if section:
        slines.sort(key=sorter)
        lines.append(section)
        lines.extend(slines)

    return lines

def fix_wwnames(inname):
    blines = []
    solved = {}

    # first pass
    with open(inname, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\r')
            line = line.strip('\n')

            items = get_solved(line)
            if items:
                # register solved ids and ignore line
                sid, hashname = items
                solved[sid] = hashname
            else:
                # register base lines as-is
                blines.append(line)

    clines = []
    for bline in blines:
        if bline.startswith('# ') and ':' not in bline:
            sid = bline[2:].strip()
            if sid in solved:
                hashname = solved[sid]
                if FULL_CLEAN:
                    bline = "%s" % (hashname)
                else:
                    bline = "%s: %s" % (sid, hashname)

        clines.append(bline)

    clines = clean_lines(clines)
    clines = order_list(clines)
    outname = inname.replace('.txt', '-clean.txt')
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
