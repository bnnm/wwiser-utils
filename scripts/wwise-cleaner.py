# moves .wem not used in .txtp to 'unwanted' folder
#
# ex.
#   ./wem/123.wem
#   ./wem/456.wem     #moved to /unwanted since it's not referenced by any .txtp
#   ./song.txtp      #points to 123.wem

#todo improve mixed case (.WEM will be moved to .wem)
#todo maybe use **/*.wem (python3.5 only) or os.walk (blerg)

import glob, os, re

move_dir = 'unwanted'
glob_paths = ['wem', 'sound', 'audio', 'music', 'sound-dlc03']
glob_exts = ['wem', 'xma', 'ogg', 'wav', 'logg', 'lwav']
glob_txtps = '*.txtp'


def main():
    txtps = glob.glob(glob_txtps)

    # wems in folders
    files_move = set()
    for glob_path in glob_paths:
        for glob_ext in glob_exts:
            files = glob.glob("%s/*.%s" % (glob_path, glob_ext))
            for file in files:
                path = os.path.normpath(file)
                path = os.path.normcase(path)
                files_move.add(path)
        
    # wems in txtp
    files_used = set()
    for txtp in txtps:
        pattern = re.compile(r"^[ ]*[?]*[ ]*([0-9a-zA-Z_\- \\/\.]*[0-9a-zA-Z_]+\.[0-9a-zA-Z_]+).*$")
        with open(txtp, 'r', encoding='utf-8') as infile:
            for line in infile:
                if line.startswith('#'):
                    continue
                match = pattern.match(line)
                if match:
                    name, = match.groups()
                    path = os.path.normpath(name)
                    path = os.path.normcase(path)
                    files_used.add(path)


    # remove used from folders
    for file_used in files_used:
        files_move.discard(file_used)

    # move remaining in folders = unused
    for file_move in files_move:
        file_unwanted = os.path.join(move_dir, file_move)

        os.makedirs(os.path.dirname(file_unwanted), exist_ok=True)
        os.rename(file_move, file_unwanted)

    moved = (len(files_move))
    print("moved %i" % (moved))


if __name__ == "__main__":
    main()
