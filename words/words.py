# Reads word from input file, splitting by _ and appliying formats, and makes word combos. Files:
# - words.txt: list of words, in the form of (word1), (word2)_(word3), etc. By default words are
#   split by _ as this increases the chance of finding variations (can be disabled, see examples).
#   Lower/uppercase/symbols/incorrect words are fine (will be adjusted as needed).
# - formats.txt: list of formats, in the form of %s, (text)_%s_(text), etc. By default uses %s
#   if not found/empty. This is meant to include "probable" prefixes/suffixes.
# - fnv.txt: list of FNV IDs, to reverse instead of creating words. If this list is found (optional,
#   not active if not found/empty) it activates the "reverse" mode, which is useful to target a few IDs.
# - words_out.txt: output generated words, or reversed FNV IDs.
# Some of the above can be passed with parameters.
#
# This is meant to be used with some base list of wwnames.txt, when some working
# variations might not be included, but we can guess some prefixes/suffixes.
# Using useful word lists + formats this can find a bunch of good names.
#
# Modes of operacion:
# - default: creates words from words
# - combinations: takes input words and combines them: A, B, C: A_B, A_C, B_A, C_A, etc.
# - permutations: takes input words divided into "sections". Add "###" in words.txt to end
#   a section. If section 1 has A, B and section 2 has C, D, makes: A_C, A_D, B_C, B_D.
# All those are also combines with formats.txt ("play_%s": play_A_C, ...)
# By default words are combined adding "_" but can be avoided via parameters.
# 
# When reversing it uses "fuzzy matches" (ignores last letter) to find FNV IDs, this can
# be disabled (latter two modes are very prone to false positives).
#
# Examples:
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
#   * with combinator/permutation mode and big word list may take ages and make lots
#     of false positives, use with care 

import argparse, re, itertools

# TODO:
# - try implementing hashing in .c and calling that for performance?
# - when using combinations, first part's hash can be precalculated 
# - load words that end with "= 0" as-is for buses (not useful?)
# - allow %i to make N numbers




class Words(object):
    DEFAULT_FORMAT = '%s'
    FILENAME_IN = 'words.txt'
    FILENAME_OUT = 'words_out.txt'
    FILENAME_FORMATS = 'formats.txt'
    FILENAME_SKIPPED = 'skipped.txt'
    FILENAME_REVERSE = 'fnv.txt'
    PATTERN_LINE = re.compile(r'[\t\n\r .<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~]')
    PATTERN_WORD = re.compile(r'[_]')

    def __init__(self):
        self._args = None

        # With dicts we use: words[index] = value, index = lowercase name, value = normal case.
        # When reversing uses lowercase to avoid lower() loops, but normal case when returning results
        self._words = {} #OrderedDict() # dicts are ordered in python 3.7+
        self._formats = {}
        self._skipped = {}

        self._sections = []
        self._sections.append(self._words)
        self._section = 0

        self._reverse = False
        self._fnv_dict = {}
        self._fuzzy_dict = {}

        self._fnv = Fnv()

    def _parse(self):
        description = (
            "word generator"
        )
        epilog = (
            "Creates lists of words from words.txt + formats.txt to words_out.txt\n"
            "Reverse FNV IDs if fnv.txt is provided instead\n"
            "Examples:\n"
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
        parser.add_argument('-F',  '--formats-list', help="Pass extra formats", default=[], nargs='*')
        parser.add_argument('-s',  '--skipped-file', help="List of words to ignore\n(so they arent tested again when doing test variations)", default=self.FILENAME_SKIPPED)
        parser.add_argument('-c',  '--combinations', help="Combine words in input list by N\nWARNING! don't set high with lots of formats/words")
        parser.add_argument('-p',  '--permutations', help="Permute words in input sections (section 1 * 2 * 3...)\n.End a section in words.txt and start next with ###\nWARNING! don't combine many sections+words", action='store_true')
        parser.add_argument('-r',  '--reverse-file', help="FNV list to reverse\nOutput will only write words that match FND IDs", default=self.FILENAME_REVERSE)
        parser.add_argument('-R',  '--reverse-list', help="Pass FNV list", nargs='*')
        parser.add_argument('-j',  '--join-blank',   help="Join words without '_'\n(Word + Word = WordWord instead of Word_Word)", action='store_true')
        parser.add_argument('-ho', '--hashable-only',help="Consider only hashable chunks\nSet to ignore numbers", action='store_true')
        parser.add_argument('-sp', '--split-prefix', help="Splits words by (prefix)_(word) rather than any '_'", action='store_true')
        parser.add_argument('-ss', '--split-suffix', help="Splits words by (word)_(suffix) rather than any '_'", action='store_true')
        parser.add_argument('-sb', '--split-both',   help="Splits words by (prefix)_(word)_(suffix) rather than any '_'", action='store_true')
        parser.add_argument('-fs', '--full-split',   help="Only adds stems (from 'aa_bb_cc' only adds 'aa', 'bb', 'cc')", action='store_true')
        parser.add_argument('-cl', '--cut-last',     help="Cut last N chars (for strings2.exe off results like bgm_main8)", type=int)
        parser.add_argument('-ns', '--no-split',     help="Disable splitting words by '_'", action='store_true')
        parser.add_argument('-nz', '--no-fuzzy',     help="Disable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
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

        self._formats[format.lower()] = format

    def _process_formats(self):
        for format in self._args.formats_list:
            self._add_format(format)

        try:
            with open(self._args.formats_file, 'r') as infile:
                for line in infile:
                    self._add_format(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._add_format(self.DEFAULT_FORMAT)

    def _add_skipped(self, line):
        line = line.strip()
        if not line:
            return
        if line.startswith('#'):
            return
        elems = line.split()
        for elem in elems:
            elem_hashable = elem.lower()
            if not self._fnv.is_hashable(elem_hashable):
                continue
            self._skipped[elem_hashable] = True
            self._skipped[elem] = True

    def _process_skipped(self):
        try:
            with open(self._args.skipped_file, 'r') as infile:
                for line in infile:
                    self._add_skipped(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._add_format(self.DEFAULT_FORMAT)

    def _get_joiner(self):
        joiner = "_"
        if self._args.join_blank:
            joiner = ""
        return joiner

    def _add_word(self, elem):
        if not elem:
            return
        if elem.count('_') > 20: #bad line like _______...____
            return

        words = self._words
        if self._args.no_split:
            words[elem.lower()] = elem
            return

        joiner = self._get_joiner()

        subwords = self.PATTERN_WORD.split(elem)
        combos = []
        add_self = True

        if self._args.full_split:
            for subword in subwords:
                if '_' in subword:
                    continue
                combos.append(subword)

            add_self = False

            #print("ful:", combos)
            #return

        elif self._args.split_prefix:
            prefix = subwords[0]
            word = joiner.join(subwords[1:])
            combos.extend([prefix, word])

            #print("pre: %s: %s / %s" % (elem, prefix, word))
            #return

        elif self._args.split_suffix:
            suffix = subwords[-1]
            word = joiner.join(subwords[:-1])
            combos.extend([word, suffix])

            #print("suf: %s: %s / %s" % (elem, word, suffix))
            #return

        elif self._args.split_both:
            prefix = subwords[0]
            suffix = subwords[-1]
            word = joiner.join(subwords[1:-1])
            combos.extend([prefix, word, suffix])

            #print("bot: %s: %s / %s / %s" % (elem, prefix, word, suffix))

        else:
            # all combos by default
            for i, j in itertools.combinations(range(len(subwords) + 1), 2):
                combos.append( joiner.join(subwords[i:j]) )

        for combo in combos:
            if not combo:
                continue
            combo_hashable = combo.lower()
            # makes only sense on simpler cases with no formats
            if self._args.hashable_only and not self._fnv.is_hashable(combo_hashable):
                continue
            words[combo_hashable] = combo

        # add itself (needed when joiner is not _)
        if add_self:
            elem_hashable = elem.lower()
            if self._fnv.is_hashable(elem_hashable):
                words[elem_hashable] = elem


    def _read_words_lines(self, infile):
        for line in infile:
            # section end when using permutations
            if self._args.permutations and line.startswith('###'):
                self._words = {} #old section is in _sections
                self._sections.append(self._words)
                self._section += 1
                continue

            # comment
            if line.startswith('#'):
                continue

            if len(line) > 500:
                continue

            elems = self.PATTERN_LINE.split(line)
            for elem in elems:
                self._add_word(elem)
                if self._args.cut_last and elem:
                    elem_len = len(elem)
                    max = self._args.cut_last
                    if elem_len <= max:
                        continue
                    for i in range(1, self._args.cut_last+1):
                        elem_cut = elem[0:-i]
                        self._add_word(elem_cut)

                
                

    def _read_words(self):
        print("reading words")

        encodings = ['utf-8-sig', 'iso-8859-1']
        try:
            done = False
            for encoding in encodings:
                try:
                    with open(self._args.input_file, 'r', encoding=encoding) as infile:
                        self._read_words_lines(infile)
                        done = True
                    break
                except UnicodeDecodeError:
                    continue

            if not done:
                print("couldn't read input file %s (bad encoding?)" % (self._args.input_file))

        except FileNotFoundError:
            print("couldn't find input file %s" % (self._args.input_file))


    def _get_formats(self):
        formats = []
        for format_key, format_val in self._formats.items():
            if self._reverse:
                format = format_key #lowercase
            else:
                format = format_val #original
            formats.append(format)

        return formats

    def _get_permutations(self):
        permutations = 1
        sections = []
        for section in self._sections:
            if self._reverse:
                words = section.keys() #lowercase
            else:
                words = section.values() #original

            permutations *= len(words)
            sections.append(words)

        f_len = len(self._formats)
        print("creating %i permutations * %i formats" % (permutations, f_len) )

        elems = itertools.product(*sections)
        return elems

    def _get_combinations(self):
        if self._reverse:
            words = self._words.keys() #lowercase
        else:
            words = self._words.values() #original

        w_len = len(words)
        f_len = len(self._formats)
        combinations = int(self._args.combinations)
        print("creating %i combinations * %i formats" % (pow(w_len, combinations), f_len) )

        elems = itertools.product(words, repeat=combinations)
        return elems

    def _get_basewords(self):
        if self._reverse:
            words = self._words.keys() #lowercase
        else:
            words = self._words.values() #original

        w_len = len(words)
        f_len = len(self._formats)
        print("creating %i words * %i formats" % (w_len, f_len))
        return words

    def _write_words(self):
        #words = ["_".join(x) for x in self._get_xxx()] #huge memory consumption, not iterator?
        if self._args.permutations:
            words = self._get_permutations()
        elif self._args.combinations:
            words = self._get_combinations()
        else:
            words = self._get_basewords()
        if not words:
            print("no words found")
            return
            
        formats = self._get_formats()
        if not formats:
            print("no formats found")
            return

        if self._reverse:
            print("reversing FNVs")
        else:
            print("generating words")
        reversed = {}

        joiner = self._get_joiner()
        combine = self._args.combinations or self._args.permutations

        info_count = 0
        info_add = 1000000 // len(formats)
        info_top = info_add
        written = 0
        with open(self._args.output_file, 'w') as outfile:
            for word in words:
                for format in formats:
                    if combine:
                        out = format % (joiner.join(word))
                    else:
                        out = format % (word)

                    if out in self._skipped:
                        continue

                    if self._reverse:
                        out_lower = out #out.lower() #should be pre-lowered already
                        fnv_base = self._fnv.get_hash_lw(out_lower)
                        fnv_fuzz = fnv_base & 0xFFFFFF00
                        if fnv_fuzz in self._fuzzy_dict:
                            for fnv in self._fnv_dict.keys():
                                if self._args.no_fuzzy:
                                    # regular match
                                    if fnv != fnv_base:
                                        continue
                                    out_final = self._get_original_case(format, word, joiner)
                                else:
                                    # multiple fnv may use the same fuzz
                                    if fnv_fuzz != fnv & 0xFFFFFF00:
                                        continue
                                    out_final = self._get_original_case(format, word, joiner)
                                    if fnv != fnv_base:
                                        out_final = self._fnv.unfuzzy_hashname_lw(fnv, out_lower, out_final)
                                        if not out_final: #may happen in rare cases
                                            continue

                                if out_final in reversed:
                                    continue
                                if out_final in self._skipped:
                                    continue
                                reversed[out_final] = True
                                
                                # don't print non-useful hashes
                                if not self._fnv.is_hashable(out_final.lower()):
                                    continue
                                outfile.write("%s: %s\n" % (fnv, out_final))
                                outfile.flush() #reversing is most interesting with lots of loops = slow, keep flushing
                                written += 1
                    else:
                        outfile.write(out + '\n')
                        written += 1

                info_count += 1
                if info_count == info_top:
                    info_top += info_add
                    print("%i..." % (info_count), word)

        if self._reverse:
            print("found %i matches" % (written))
        else:
            print("created %i words" % (written))
        print("done")

    # when reversing format/word are lowercase, but we have regular case saved to get original combo
    def _get_original_case(self, format, word, joiner):
        format_og = self._formats[format]
        
        if self._args.permutations:
            word_og = []
            i = 0
            for subword in word:
                subword_og = self._sections[i][subword]
                i += 1
                word_og.append(subword_og)
            return format_og % (joiner.join(word_og))

        elif  self._args.combinations:
            word_og = []
            for subword in word:
                subword_og = self._words[subword]
                word_og.append(subword_og)
            return format_og % (joiner.join(word_og))
        else:
            word_og = self._words[word]
            return format_og % (word_og)

    # use fuzzy values for better chance to reverse
    def _process_reverse(self):
        try:
            try:
                with open(self._args.reverse_file, 'r') as infile:
                    for line in infile:
                        if line.startswith('#'):
                            continue
                        elem = line.strip()
                        if not elem:
                            continue
                        self._fnv_dict[int(elem)] = True
            except FileNotFoundError:
                pass

            if self._args.reverse_list:
                for elem in self._args.reverse:
                    elem = elem.strip()
                    if not elem:
                        continue
                    self._fnv_dict[int(elem)] = True

            for elem in self._fnv_dict.keys():
                fnv = elem & 0xFFFFFF00
                self._fuzzy_dict[fnv] = True #may be smaller than fnv_dict with similar FNVs
                
            self._reverse = len(self._fnv_dict) > 0

        except (TypeError, ValueError):
            print("wrong elems in FNV ID list, ignoring")

    def start(self):
        self._args = self._parse()
        self._process_formats()
        self._process_skipped()
        self._process_reverse()
        self._read_words()
        self._write_words()



class Fnv(object):
    FNV_DICT = '0123456789abcdefghijklmnopqrstuvwxyz_'
    FNV_FORMAT = re.compile(r"^[a-z_][a-z0-9\_]*$")
    FNV_FORMAT_EX = re.compile(r"^[a-z_0-9][a-z0-9_()\- ]*$")

    def is_hashable(self, lowname):
        return self.FNV_FORMAT.match(lowname)

    def is_hashable_extended(self, lowname):
        return self.FNV_FORMAT_EX.match(lowname)


    # Find actual name from a close name (same up to last char) using some fuzzy searching
    # ('bgm0' and 'bgm9' IDs only differ in the last byte, so it calcs 'bgm' + '0', '1'...)
    def unfuzzy_hashname_lw(self, id, lowname, hashname):
        if not id or not hashname:
            return None

        namebytes = bytearray(lowname, 'UTF-8')
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
                return hashname
        # it's possible to reach here with incorrect (manually input) ids,
        # since not all 255 values are in FNV_DICT
        return None

    def unfuzzy_hashname(self, id, hashname):
        return self.unfuzzy_hashname_lw(id, hashname.lower(), hashname)

    # Partial hashing for unfuzzy'ing.
    def _get_partial_hash(self, hash, value):
        hash = hash * 16777619 #FNV prime
        hash = hash ^ value #FNV xor
        hash = hash & 0xFFFFFFFF #python clamp
        return hash

    # Standard AK FNV-1 with 32-bit.
    def _get_hash(self, namebytes):
        hash = 2166136261 #FNV offset basis

        for namebyte in namebytes:  #for i in range(len(namebytes)):
            hash = hash * 16777619 #FNV prime
            hash = hash ^ namebyte #FNV xor
            hash = hash & 0xFFFFFFFF #python clamp
        return hash

    def get_hash(self, name):
        return self.get_hash_lw(name.lower())

    def get_hash_lw(self, lowname):
        namebytes = bytes(lowname, 'UTF-8')
        return self._get_hash(namebytes)


# #####################################

if __name__ == "__main__":
    Words().start()
