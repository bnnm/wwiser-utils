# reads strings from .uasset (newer versions only)


import glob, os, hashlib, struct

def read_u32le(f):
    data = f.read(0x04)
    return struct.unpack('<I', data)[0]

def read_u16be(f):
    data = f.read(0x02)
    return struct.unpack('>H', data)[0]

def read_lines(f):
    lines = []
    
    unk = read_u32le(f)
    if unk != 0:
        return lines
    memory_start = read_u32le(f)
    if memory_start > 0xFFFFF:
        return lines
    read_u32le(f)
    read_u32le(f)
    
    read_u32le(f)
    read_u32le(f)
    read_u32le(f)
    read_u32le(f)
    
    read_u32le(f)
    read_u32le(f)
    read_u32le(f)
    read_u32le(f)
    
    read_u32le(f)
    strings_count = read_u32le(f)
    strings_size = read_u32le(f)
    read_u32le(f)

    read_u32le(f)
    for i in range(strings_count):
        f.read(0x08)

    strings_sizes = []
    for i in range(strings_count):
        string_size = read_u16be(f)
        strings_sizes.append(string_size)

    for string_size in strings_sizes:
        string_name = f.read(string_size)
        string_name = string_name.decode('utf-8')
        lines.append(string_name)
    
    return lines

def main():

    files = glob.glob("**/*.uasset", recursive=True)

    lines = []
    for file in files:
        lines.append(file)
        try:
            with open(file, 'rb') as f:
                lines += read_lines(f)
        except Exception as e:
            print("error", file, e)
            continue
    
    
    with open('ww_assets.txt', 'w') as f:
        f.write('\n'.join(lines))

if __name__ == "__main__":
    main()
