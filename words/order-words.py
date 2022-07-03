import sys

def main():
    if len(sys.argv) != 2:
        print("name not found")
        return
    inname = sys.argv[1]

    items = []
    with open(inname, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if ':' not in line:
                continue

            items.append( line.split(':') )

    lines = []
    items.sort(key=lambda x : x[1].lower())
    for fnv, name in items:
        fnv = fnv.ljust(12)
        name = name.strip()
        lines.append("%s: %s" % (fnv, name))

    outname = inname.replace('.txt', '-order.txt')
    with open(outname, 'w') as f:
       f.write('\n'.join(lines))

if __name__ == "__main__":
    main()
