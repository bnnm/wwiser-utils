import sys, re
import xml.etree.ElementTree as ET

UPDATE_ORIGINAL = False

types = ['CAkFxCustom']
def read_banks():
    id_info = {}

    tree = ET.parse('banks.xml')
    doc = tree.getroot()
    for base in doc:
        if base.tag != 'base':
            continue

        for root in base:

            for obj in root:
                attrs = obj.attrib
                if 'na' not in attrs or attrs['na'] != 'HircChunk':
                    continue

                for elem in obj:
                    if elem.tag != 'lst':
                        continue
                    attrs = elem.attrib
                    if 'na' not in attrs or attrs['na'] != 'listLoadedItem':
                        continue
                    for subobj in elem:
                        name = subobj.attrib['na']
                        if name not in types:
                            continue
                        for fld in subobj:
                            if fld.attrib['ty'] != 'sid':
                                continue
                            sid = int(fld.attrib['va'])
                            id_info[sid] = name
                            break
                        
    return id_info

def update_names(inname, id_info):
    blines = []

    with open(inname, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\r')
            line = line.strip('\n')

            if ':' in line:
                fnv, text = line.split(':', 1)
                if fnv.isdigit():
                    fnv = int(fnv)
                    if fnv in id_info:
                        line += " ##%s #ko" % (id_info[fnv])

            if line.startswith('# '):
                fnv = line.split(' ')[1]
                if fnv.isdigit():
                    fnv = int(fnv)
                    if fnv in id_info:
                        line += " ##%s #ko" % (id_info[fnv])

            blines.append(line)

    outname = inname

    update = UPDATE_ORIGINAL and 'wwnames' in outname
    if not update:
        outname = outname.replace('.txt', '-clean.txt')
    with open(outname, 'w', encoding='utf-8') as f:
       f.write('\n'.join(blines))


def main():
    if len(sys.argv) < 2:
        print("name not found")
        return

    id_info = read_banks()
    for i in range(1, len(sys.argv)):
        inname = sys.argv[i]
        update_names(inname, id_info)


if __name__ == "__main__":
    main()
