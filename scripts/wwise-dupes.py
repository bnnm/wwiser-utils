# moves .wem in /unused to /unused/dupe
# doesn't move dupe .wem in other folder since'd be used by some .txtp
#
# ex.
#   ./wem/123.wem
#   ./unused/456.wem    #moved to /unused/dupe since it's a clone of 123.wem


import glob, os, hashlib

unused_dir = 'unused'
dupe_dir = 'dupe'

def hash(filename):
    chunk_size = 1024*64
    with open(filename, "rb") as file:
        file_hash = hashlib.md5()
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            file_hash.update(chunk)
    return file_hash.hexdigest() #file_hash.digest()

def main():
    glob_base = './**/*.%s'
    glob_exts = ['wem', 'xma', 'ogg', 'wav', 'logg', 'lwav']

    # wems any folders
    files = []
    for glob_ext in glob_exts:
        files += glob.glob(glob_base % (glob_ext))

    # find dupes that exist in unused
    files_move = []
    hashes = {}
    for filename in files:
        file_hash = hash(filename)
        if file_hash in hashes and unused_dir in filename:
            files_move.append(filename)
        hashes[file_hash] = True

    # move remaining in folders = unused
    for file_move in files_move:
        file_dupe = os.path.join(dupe_dir, file_move)

        os.makedirs(os.path.dirname(file_dupe), exist_ok=True)
        os.rename(file_move, file_dupe)

    moved = (len(files_move))
    print("moved %i" % (moved))
    #input()

if __name__ == "__main__":
    main()
