import sys

stems = ['play_','stop_','mute_','unmute_','reset_','skip_']

def main():
    doubles = {}
    inname = 'words_out.txt'
    if len(sys.argv) >= 2:
        inname = sys.argv[1]

    found = {}

    with open(inname, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if ':' not in line:
                continue

            text = line.split(':', 1)[1].strip()
            text_lw = text.lower()
            key = None
            
            for stem in stems:
                if text_lw.startswith(stem):
                    key = text_lw[ len(stem) : ]
                    break

            if not key:
                continue

            if key not in found:
                found[key] = []
            if line in found[key]:
                continue
            found[key].append(line)


    lines = []
    for items in found.values():
        if len(items) == 1:
            continue
        lines.extend(items)

    if not lines:
        return

    outname = inname.replace('.txt', '_pairs.txt')
    with open(outname, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == "__main__":
    main()
