# moves .wem not used in .txtp to 'unwanted' folder
#
# ex.
#   ./wem/123.wem
#   ./wem/456.wem     #moved to /unwanted since it's not referenced by any .txtp
#   ./song.txtp      #points to 123.wem

#todo improve mixed case (.WEM will be moved to .wem)

import glob, os, re, sys

move_dir = 'unwanted'

# put filenames to print on which .txtp they are referenced
targets = []
targets_done = {}
if len(sys.argv) > 1:
    for i in range(1, len(sys.argv)):
        targets.append(sys.argv[i].lower())

def main():
    # folders are taken from .txtp (meaning with no .txtp moves nothing)
    glob_folders = set() #set(['wem', 'sound', 'audio'])
    # fixed list since folders may have more extensions than those used in .txtp
    glob_exts = ['wem', 'xma', 'ogg', 'wav', 'logg', 'lwav'] #, 'bnk', 'txt', 'xml'
    # base txtps
    glob_txtps = '*.txtp'

    # catch folder-like parts followed by name + extension
    pattern = re.compile(r"^[ ]*[?]*[ ]*([0-9a-zA-Z_\- \\/\.]*[0-9a-zA-Z_]+\.[0-9a-zA-Z_]+).*$")


    # wems in txtp
    txtps = glob.glob(glob_txtps)
    files_used = set()
    for txtp in txtps:
        with open(txtp, 'r', encoding='utf-8-sig') as infile:
            for line in infile:
                if line.startswith('#'):
                    continue
                match = pattern.match(line)
                if match:
                    name, = match.groups()
                    file = os.path.normpath(name)
                    file = os.path.normcase(file)
                    path = os.path.dirname(file)
                    files_used.add(file)
                    glob_folders.add(path)

                    if targets:
                        basename = os.path.basename(name.lower())
                        basename = os.path.splitext(basename)[0]
                        if (txtp,basename) in targets_done:
                            continue
                        targets_done[(txtp,basename)] = True
                        for target in targets:
                            if basename.endswith(target):
                                print("file %s in %s" % (target, txtp))

    if targets:
        print("done")
        return

    # wems in folders
    files_move = set()
    for glob_folder in glob_folders:
        for glob_ext in glob_exts:
            glob_search = os.path.join(glob_folder, '*.%s' % (glob_ext))
            files = glob.glob(glob_search)
            for file in files:
                path = os.path.normpath(file)
                path = os.path.normcase(path)
                files_move.add(path)

    # remove used from folders
    for file_used in files_used:
        files_move.discard(file_used)

    # move remaining in folders = unused
    for file_move in files_move:
        file_unwanted = os.path.join(move_dir, file_move)
        if '..' in file_unwanted:
            file_unwanted = file_unwanted.replace('..\\', 'prev\\')
            file_unwanted = file_unwanted.replace('../', 'prev/')

        os.makedirs(os.path.dirname(file_unwanted), exist_ok=True)
        os.rename(file_move, file_unwanted)

    moved = (len(files_move))
    print("moved %i" % (moved))
    #input()

if __name__ == "__main__":
    main()
