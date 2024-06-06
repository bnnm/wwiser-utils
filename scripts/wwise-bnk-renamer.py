# renames (number).bnk to (name).bnk from a wwnames.txt file


import glob, os, hashlib, struct

force_internal_id = False #use internal data to get bank ID rathen than filename
undo_rename = False
unused_dir = 'unused'
dupe_dir = 'dupe'

def fnv(name):
    namebytes = bytes(name.lower(), 'UTF-8')
    hash = 2166136261 #FNV offset basis

    for namebyte in namebytes:  #for i in range(len(namebytes)):
        hash = hash * 16777619 #FNV prime
        hash = hash ^ namebyte #FNV xor
        hash = hash & 0xFFFFFFFF #python clamp
    return hash

def main():

    names = {}
    try:
        with open("wwnames.txt", 'r') as infile:
            for line in infile:
                if line.startswith('#'):
                    continue

                line = line.strip()
                # for "id: name" results
                if ':' in line:
                    line = line.split(':')[1].strip()
                key = fnv(line)
                names[key] = line
    except:
        print("can't open wwnames.txt")
        return

    files = glob.glob("*.bnk")

    for file in files:

        basefile = os.path.basename(file)
        basefile, __ = os.path.splitext(basefile)
        
        if undo_rename:
            if basefile.isnumeric():
                continue
            name = '%s' % (fnv(basefile))

        elif force_internal_id:
            with open(file, 'rb') as f:
                data = f.read(0x100)
            if data[0:4] != b'BKHD':
                continue
            test_be, = struct.unpack_from('>I', data, 0x04)
            test_le, = struct.unpack_from('<I', data, 0x04)
            if test_le > test_be:
                internal_id, = struct.unpack_from('>I', data, 0x0c)
            else:
                internal_id, = struct.unpack_from('<I', data, 0x0c)

            key = internal_id
            name = names.get(key)
                
        else:
            if not basefile.isnumeric():
                continue
            key = int(basefile)
            name = names.get(key)

        if not name:
            continue
        file_new = file.replace(basefile, name)

        #print(file, file_new)
        try:
            os.rename(file, file_new)
        except:
            print("can't rename", file, file_new)

if __name__ == "__main__":
    main()
