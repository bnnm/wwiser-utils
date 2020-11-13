# Reads from words.txt (list of words) + formats.txt (a list of formats) and makes
# possible ordered combos, splitting by _ and appliying formats. Also has a bunch
# of options to generate/test combos of words.
#
# This is meant to be used with some base list of wwnames, when some working
# variations might not be included. With some useful word list + formats finds
# a bunch of good names.
#
# example:
# - from word Play_Stage_01 + format %s (default)
#   * makes: Play, Stage, 01, Play_Stage, Stage_01, Play_Stage_01
#   * "Stage", "Stage_01" could be valid names
# - from word Play_Stage_01 + format BGM_%s:
#   * makes: BGM_Play, BGM_Stage, BGM_01, BGM_Play_Stage, BGM_Stage_01, BGM_Play_Stage_01
#   * "BGM_Play", "BGM_Stage", "BGM_Play_Stage" could be valid names
# - using combinator mode with value 3 + word list with "BGM", "Play", "Stage"
#   * makes: BGM_Play_Stage, BGM_Stage_Play Stage_BGM_Play, Stage_Play_BGM, etc
#   * also applies formats
# - using the "reverse" it only prints results that match a FNV id list
#   * with combinator mode and big word list may take ages and make lots of false positives,
#     use with care 

import argparse, re, itertools


class Words(object):
    DEFAULT_FORMAT = '%s'
    FILENAME_IN = 'words.txt'
    FILENAME_OUT = 'words_out.txt'
    FILENAME_FORMATS = 'formats.txt'
    FILENAME_REVERSE = 'fnv.txt'
    PATTERN_LINE = re.compile(r'[\t\n\r .<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|]')
    PATTERN_WORD = re.compile(r'[_]')

    def __init__(self):
        self._args = None
        self._words = {} #set() #ordered in python 3.7+, might as well
        self._formats = []
        self._sections = []
        self._sections.append({})
        self._section = 0
        self._fnv = Fnv()

    def _parse(self):
        description = (
            "word generator"
        )
        epilog = (
            "creates lists of words from words.txt + formats.txt to words_out.txt\n"
            "examples:\n"
            "  %(prog)s\n"
            "  - makes output with default files\n"
            "  %(prog)s -F BGM_%%s_01\n"
            "  - may pass formats directly (formats.txt can be ommited)\n"
            "  %(prog)s -c 3\n"
            "  - combines words from list: A_A_A, A_A_B, A_A_C ...\n"
            "  %(prog)s -p\n"
            "  - combines words from sections in list: A1_B1_C1, A1_B2_C1, ...\n"
            "    (end sections in words.txt with ###)\n"
            "  %(prog)s -c 4 -r 123543234 654346764\n"
            "  - combines words from list and tries to match them to FNV IDs\n"
        )

        parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-i',  '--input_file',   help="Input list", default=self.FILENAME_IN)
        parser.add_argument('-o',  '--output_file',  help="Output list", default=self.FILENAME_OUT)
        parser.add_argument('-f',  '--formats-file', help="Format list file\n- use %%s to replace a word from input list", default=self.FILENAME_FORMATS)
        parser.add_argument('-F',  '--formats',      help="Pass extra formats", default=[], nargs='*')
        parser.add_argument('-c',  '--combinations', help="Combine words in input list by N\nWARNING! don't set high with lots of formats/words\nand use -S")
        parser.add_argument('-p',  '--permutations', help="Permute words in input sections (section 1 * 2 * 3...)\n.End a section in words.txt and start next with ###\nWARNING! don't combine many sections+words", action='store_true')
        parser.add_argument('-r',  '--reverse-file', help="FNV list to reverse\nOutput will only writes words that match FND IDs", default=self.FILENAME_REVERSE)
        parser.add_argument('-R',  '--reverse',      help="Pass FNV list", nargs='*')
        parser.add_argument('-j',  '--join-blank', help="Join words without '_'\n(Word + Word = WordWord instead of Word_Word)", action='store_true')
        parser.add_argument('-ns', '--no-split', help="Disable splitting words by '_'", action='store_true')
        parser.add_argument('-nz', '--no-fuzzy', help="Disable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
        return parser.parse_args()

    def _add_format(self, format):
        format = format.strip()
        if not format:
            return
        if format.startswith('#'):
            return
        if format.count('%s') != 1:
            print("ignored wrong format:", format)
            return

        self._formats.append(format)

    def _process_formats(self):
        for format in self._args.formats:
            self._add_format(format)

        try:
            with open(self._args.formats_file, 'r') as infile:
                for line in infile:
                    self._add_format(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._formats.append(self.DEFAULT_FORMAT)

    def _get_joiner(self):
        joiner = "_"
        if self._args.join_blank:
            joiner = ""
        return joiner

    def _add_word(self, elem):
        if not elem:
            return

        if self._args.permutations:
            words = self._sections[self._section]
        else:
            words = self._words

        if self._args.no_split:
            words[elem.lower()] = elem
            return

        joiner = self._get_joiner()

        subwords = self.PATTERN_WORD.split(elem)
        for i, j in itertools.combinations(range(len(subwords) + 1), 2):
            combo = joiner.join(subwords[i:j])
            if not combo:
                continue
            words[combo.lower()] = combo

    def _read_words(self):
        try:
            with open(self._args.input_file, 'r') as infile:
                for line in infile:
                    # section end when using permutations
                    if self._args.permutations and line.startswith('###'):
                        self._sections.append({})
                        self._section += 1
                        continue
                    # comment
                    if line.startswith('#'):
                        continue

                    elems = self.PATTERN_LINE.split(line)
                    for elem in elems:
                        self._add_word(elem)
        except FileNotFoundError:
            print("couldn't find input file %s" % (self._args.input_file))

    def _get_permutations(self):
        permutations = 1
        for section in self._sections:
            permutations *= len(section.keys())
        print("creating %i permutations * %i formats" % (permutations, len(self._formats)) )

        elems = itertools.product(*self._sections)
        return elems

    def _get_combinations(self):
        total = len(self._words)
        combinations = int(self._args.combinations)
        print("creating %i combinations * %i formats" % (pow(total, combinations), len(self._formats)) )

        words = self._words.values()
        elems = itertools.product(words, repeat = combinations)
        return elems

    def _get_basewords(self):
        elems = self._words.values()
        print("creating %i words * %i formats" % (len(elems), len(self._formats)))
        return elems

    def _write_words(self):
        #words = ["_".join(x) for x in self._get_xxx()] #huge memery consumption, not iterator?
        if self._args.permutations:
            words = self._get_permutations()
        elif self._args.combinations:
            words = self._get_combinations()
        else:
            words = self._words.values()

        if not words:
            print("no words found")
            return

        fnv_dict, fuzzy_dict = self.get_reverse()
        if fnv_dict:
            print("reversing FNVs")
        else:
            print("generating words")
        reversed = {}

        joiner = self._get_joiner()
        combine = self._args.combinations or self._args.permutations

        count = 0
        top = 10000000
        written = 0
        with open(self._args.output_file, 'w') as outfile:
            for word in words:
                for format in self._formats:
                    if combine:
                        out = format % (joiner.join(word))
                    else:
                        out = format % (word)

                    if fnv_dict:
                        #out = out.lower()
                        fnv_base = self._fnv.get_hash(out.lower())
                        fnv_fuzz = fnv_base & 0xFFFFFF00
                        if fnv_fuzz in fuzzy_dict:
                            for fnv in fnv_dict.keys():
                                if self._args.no_fuzzy:
                                    # regular match
                                    if fnv != fnv_base:
                                        continue
                                    out_final = out
                                else:
                                    # multiple fnv may use the same fuzz
                                    if fnv_fuzz != fnv & 0xFFFFFF00:
                                        continue
                                    if fnv == fnv_base:
                                        out_final = out
                                    else:
                                        out_final = self._fnv.unfuzzy_hashname(fnv, out)
                                    if not out_final: #shouln't happen for proper cases
                                        #out_final = "%s???" % (out)
                                        continue

                                if out_final in reversed:
                                    continue
                                reversed[out_final] = True
                                outfile.write("%s: %s\n" % (fnv, out_final))
                                outfile.flush() #reversing is most interesting with lots of loops = slow, keep flushing
                                written += 1
                    else:
                        outfile.write(out + '\n')
                        written += 1
                count += 1
                if count == top:
                    top += 1000000
                    print("%i..." % (count), word)
        if fnv_dict:
            print("found %i matches" % (written))
        else:
            print("created %i words" % (written))
        print("done")


    # use fuzzy values for better chance to reverse
    def get_reverse(self):
        try:
            fnv_dict = {} #faster to test than a list 
            try:
                with open(self._args.reverse_file, 'r') as infile:
                    for line in infile:
                        if line.startswith('#'):
                            continue
                        elem = line.strip()
                        if not elem:
                            continue
                        fnv_dict[int(elem)] = True
            except FileNotFoundError:
                pass

            if self._args.reverse:
                for elem in self._args.reverse:
                    elem = line.strip()
                    if not elem:
                        continue
                    fnv_dict[int(elem)] = True

            fuzzy_dict = {}
            for elem in fnv_dict.keys():
                fnv = elem & 0xFFFFFF00
                fuzzy_dict[fnv] = True #may be smaller than fnv_dict with similar FNVs

            return (fnv_dict, fuzzy_dict)

        except (TypeError, ValueError):
            print("wrong elems in FNV ID list")
            return (None, None)

    def start(self):
        self._args = self._parse()
        self._process_formats()
        self._read_words()
        self._write_words()



class Fnv(object):
    FNV_DICT = '0123456789abcdefghijklmnopqrstuvwxyz_'
    FNV_FORMAT = re.compile(r"^[a-z_][a-z0-9\_]*$")

    def is_hashable(self, lowname):
        return self.FNV_FORMAT.match(lowname)


    # Find actual name from a close name (same up to last char) using some fuzzy searching
    # ('bgm0' and 'bgm9' IDs only differ in the last byte, so it calcs 'bgm' + '0', '1'...)
    def unfuzzy_hashname(self, id, hashname):
        if not id or not hashname:
            return None

        namebytes = bytearray(hashname.lower(), 'UTF-8')
        basehash = self._get_hash(namebytes[:-1]) #up to last byte
        for c in self.FNV_DICT: #try each last char
            id_hash = self._get_partial_hash(basehash, ord(c))

            if id_hash == id:
                c = c.upper()
                for cs in hashname: #upper only if all base name is all upper
                    if cs.islower():
                       c = c.lower()
                       break

                hashname = hashname[:-1] + c
                #logging.info("names: unfuzzied name %s", hashname)
                return hashname

        return None

    # Partial hashing for unfuzzy'ing.
    def _get_partial_hash(self, hash, value):
        hash = hash * 16777619 #FNV prime
        hash = hash ^ value #FNV xor
        hash = hash & 0xFFFFFFFF #python clamp
        return hash

    # Standard AK FNV-1 with 32-bit.
    def _get_hash(self, namebytes):
        hash = 2166136261 #FNV offset basis

        for i in range(len(namebytes)):
            hash = hash * 16777619 #FNV prime
            hash = hash ^ namebytes[i] #FNV xor
            hash = hash & 0xFFFFFFFF #python clamp
        return hash

    # Standard AK FNV-1 with 32-bit.
    def get_hash(self, lowname):
        namebytes = bytes(lowname, 'UTF-8')
        return self._get_hash(namebytes)

# #####################################

if __name__ == "__main__":
    Words().start()
