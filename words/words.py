# WORDS.PY
#
# Reads word from input files, splitting by _ and applying formats, and makes word combos. Files:
# - wwnames*.txt: lists of words, in the form of (word1), (word2)_(word3), etc, that are split in
#   various ways (configurable). Lower/uppercase/symbols/incorrect words are fine (will be ignored
#   or adjusted as needed). Should include a list of FNV IDs, to reverse instead of creating words.
# - formats.txt: list of formats, in the form of %s, (text)_%s_(text), etc. By default uses %s
#   if not found/empty. This is meant to include "probable" prefixes/suffixes.
# - ww.txt: extra list of wwise words only (may use this instead of wwnames.txt)
# - fnv.txt: extra list of fnv IDs only (may use this instead of wwnames.txt)
# - words_out.txt: output of reversed FNV IDs.
# Some of the above can be passed with parameters.
#
# This is meant to be used with some base list of wwnames.txt, when some working
# variations might not be included, but we can guess some prefixes/suffixes.
# Using useful word lists + formats this can find a bunch of good names.
#
# Modes of operation:
# - default: creates words from words
# - combinations: takes input words and combines them: A, B, C: A_B, A_C, B_A, C_A, etc.
# - permutations: takes input words divided into "sections". Add "#@section#" in words list to end
#   a section, or a new file. If section 1 has A, B and section 2 has C, D, makes: A_C, A_D, B_C, B_D.
# All those are also combines with formats.txt ("play_%s": play_A_C, ...)
# By default words are combined adding "_" but can be avoided via parameters.
# 
# When reversing it may enable/disable "fuzzy matches" (ignores last letter) to find FNV IDs,
# as some modes are very prone to false positives.
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

import argparse, re, itertools, time, glob

# TODO:
# - try implementing hashing in .c and calling that for performance?
# - first part's hash can be precalculated + saved
# - load words that end with "= 0" as-is for buses (not useful?)
# - allow %i to make N numbers




class Words(object):
    DEFAULT_FORMAT = '%s'
    FILENAME_WWNAMES = 'wwnames*.txt'
    FILENAME_IN = 'ww.txt'
    FILENAME_OUT = 'words_out.txt'
    FILENAME_OUT_EX = 'words_out%s.txt'
    FILENAME_FORMATS = 'formats.txt'
    FILENAME_SKIPS = 'skips.txt'
    FILENAME_REVERSABLES = 'fnv.txt'
    PATTERN_LINE = re.compile(r'[\t\n\r .<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
    PATTERN_WORD = re.compile(r'[_]')
    PATTERN_WRONG = re.compile(r'[\t.<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
    WORD_ALLOWED = ['xiii', 'xviii','zzz']

    FORMAT_TYPE_NONE = 0
    FORMAT_TYPE_PREFIX = 1
    FORMAT_TYPE_SUFFIX = 2
    FORMAT_TYPE_BOTH = 3

    def __init__(self):
        self._args = None

        self._formats = {}
        self._skips = set()
        self._reversables = set()
        self._fuzzies = set()

        # With dicts we use: words[index] = value, index = lowercase name, value = normal case.
        # When reversing uses lowercase to avoid lower() loops, but normal case when returning results
        self._words = {} #OrderedDict() # dicts are ordered in python 3.7+
        self._words_reversed = set()

        #self._format_fnvs = {} #stem = base FNV
        #self._format_baselen = {} #stem = base lenth

        self._sections = []
        self._sections.append(self._words)
        self._section = 0

        self._fnv = Fnv()

    def _parse(self):
        description = (
            "word generator"
        )
        epilog = (
            "Creates lists of words from wwnames.txt + formats.txt to words_out.txt\n"
            "Reverse FNV IDs if fnv.txt is provided instead\n"
            "Examples:\n"
            "  %(prog)s\n"
            "  - makes output with default files\n"
            "  %(prog)s -c 2\n"
            "  - combines words from list: A_A, A_B, A_C ...\n"
            "  %(prog)s -p\n"
            "  - combines words from sections in list: A1_B1_C1, A1_B2_C1, ...\n"
            "    (end sections in word list with #@section)\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        # files
        p.add_argument('-w',  '--wwnames-file', help="wwnames input list (word list + FNV list)", default=self.FILENAME_WWNAMES)
        p.add_argument('-i',  '--input-file',   help="Input list", default=self.FILENAME_IN)
        p.add_argument('-o',  '--output-file',  help="Output list", default=self.FILENAME_OUT)
        p.add_argument('-f',  '--formats-file', help="Format list file\n- use %%s to replace a word from input list", default=self.FILENAME_FORMATS)
        p.add_argument('-s',  '--skips-file',   help="List of words to ignore\n(so they arent tested again when doing test variations)", default=self.FILENAME_SKIPS)
        p.add_argument('-r',  '--reverse-file', help="FNV list to reverse\nOutput will only write words that match FND IDs", default=self.FILENAME_REVERSABLES)
        p.add_argument('-to',  '--text-output', help="Write words rather than reversing", action='store_true')
        # modes
        p.add_argument('-c',  '--combinations', help="Combine words in input list by N\nWARNING! don't set high with lots of formats/words")
        p.add_argument('-p',  '--permutations', help="Permute words in input sections (section 1 * 2 * 3...)\n.End a section in words list and start next with #@section\nWARNING! don't combine many sections+words", action='store_true')
        p.add_argument('-zd', '--fuzzy-disable',help="Disable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
        p.add_argument('-ze', '--fuzzy-enable', help="Enable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
        # other flags

        p.add_argument('-mc',  '--max-chars',   help="Ignores results that go beyond N chars", type=int)        
        p.add_argument('-js', '--join-spaces',  help="Join words with spaces in lines\n('Word Word' = 'Word_Word')", action='store_true')
        p.add_argument('-jb', '--join-blank',   help="Join words without '_'\n('Word' + 'Word' = WordWord instead of Word_Word)", action='store_true')
        p.add_argument('-j',  '--joiner',       help="Set word joiner")
        p.add_argument('-iw', '--ignore-wrong', help="Ignores words that don't make much sense\nMay remove unusual valid words, like rank_sss", action='store_true')
        p.add_argument('-ho', '--hashable-only',help="Consider only hashable chunks\nSet to ignore numbers", action='store_true')
        p.add_argument('-sc', '--split-caps',   help="Splits words by (Word)(...)(Word) and makes (word)_(...)_(word)", action='store_true')
        p.add_argument('-sp', '--split-prefix', help="Splits words by (prefix)_(word) rather than any '_'", action='store_true')
        p.add_argument('-ss', '--split-suffix', help="Splits words by (word)_(suffix) rather than any '_'", action='store_true')
        p.add_argument('-sb', '--split-both',   help="Splits words by (prefix)_(word)_(suffix) rather than any '_'", action='store_true')
        p.add_argument('-fs', '--full-split',   help="Only adds stems (from 'aa_bb_cc' only adds 'aa', 'bb', 'cc')", action='store_true')
        p.add_argument('-ns', '--no-split',     help="Disable splitting words by '_'", action='store_true')
        p.add_argument('-cl', '--cut-last',     help="Cut last N chars (for strings2.exe off results like bgm_main8)", type=int)
        return p.parse_args()

    #--------------------------------------------------------------------------

    def _add_format(self, format):
        format = format.strip()
        if not format:
            return
        if format.startswith('#'):
            return
        if format.count('%s') != 1:
            print("ignored wrong format:", format)
            return

        format_lw = format.lower()
        if format == '%s':
            type = self.FORMAT_TYPE_NONE
            pre = None
            suf = None

        elif format.endswith('%s'):
            type = self.FORMAT_TYPE_PREFIX
            pre = format_lw[:-2]
            suf = None

        elif format.startswith('%s'):
            type = self.FORMAT_TYPE_SUFFIX
            pre = None
            suf = format_lw[2:]

        else:
            type = self.FORMAT_TYPE_BOTH
            presuf = format_lw.split('%s')
            pre = presuf[0]
            suf = presuf[1]

        key = format.lower()
        if self._args.text_output:
            val = format
        else:
            val = key

        prebytes = None
        sufbytes = None
        if pre:
            prebytes = bytes(pre, 'UTF-8')
        if suf:
            sufbytes = bytes(suf, 'UTF-8')

        self._formats[key] = (val, format, type, prebytes, sufbytes)

        #index = format.index('%')
        #if index:
        #    val = self._fnv.get_hash(format[0:index])
        #else:
        #    val = None
        #self._format_fnvs[key] = val
        #self._format_baselen[key] = index

    def _read_formats(self, file):
        try:
            with open(file, 'r') as infile:
                for line in infile:
                    self._add_format(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._add_format(self.DEFAULT_FORMAT)

    #--------------------------------------------------------------------------

    def _add_skip(self, line):
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
            self._skips.add(elem_hashable)
            self._skips.add(elem)

    def _read_skips(self, file):
        try:
            with open(file, 'r') as infile:
                for line in infile:
                    self._add_skip(line)
        except FileNotFoundError:
            pass

    #--------------------------------------------------------------------------

    def _add_reversable(self, line):
        if line.startswith('# '): #allow fnv in wwnames.txt with -sm
            line = line[2:]
        if line.startswith('#'):
            return

        elem = line.strip()
        if not elem:
            return
        if not elem.isnumeric():
            return

        try:
            key = int(elem)
        except (TypeError, ValueError):
            return

        if key < 0xFFFFF or key > 0xFFFFFFFF:
            return

        # skip already useful names in wwnames.txt
        if self._parsing_wwnames:
            if key in self._words_reversed:
                return

        self._reversables.add(key)

    def _read_reversables(self, file):
        try:
            with open(file, 'r') as infile:
                for line in infile:
                    self._add_reversable(line)
        except FileNotFoundError:
            pass

        for elem in self._reversables:
            fnv = elem & 0xFFFFFF00
            self._fuzzies.add(fnv) #may be smaller than fnv_dict with similar FNVs

    #--------------------------------------------------------------------------

    def _get_joiner(self):
        joiner = "_"
        if self._args.join_blank:
            joiner = ""
        if self._args.joiner:
            joiner = self._args.joiner
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
            # (ex. if combining format "play_bgm_%s" and number in list is reasonable)
            if self._args.hashable_only and not self._fnv.is_hashable(combo_hashable):
                continue
            combo_hashable = bytes(combo_hashable, "UTF-8")
            words[combo_hashable] = combo

        # add itself (needed when joiner is not _)
        if add_self:
            elem_hashable = elem.lower()
            if self._fnv.is_hashable(elem_hashable):
                elem_hashable = bytes(elem_hashable, "UTF-8")
                words[elem_hashable] = elem

    def _is_line_ok(self, line):
        line = line.strip()
        line_len = len(line)

        if line.lower() in self.WORD_ALLOWED:
            return True

        # skip wonky mini words
        if line_len < 4 and self._PATTERN_WRONG.search(line):
            return False

        if line_len < 12:
            # check for words like 
            for key, group in itertools.groupby(line):
                group_len = len(list(group))
                if key.lower() in ['0', '1', 'x', ' ']: #allow 000, 111, xxx
                    continue
                if group_len > 2:
                    return False

        return True

    def _read_words_lines(self, infile):
        print("reading words: %s" % (infile.name))

        for line in infile:
            # section end when using permutations
            if self._args.permutations and line.startswith('#@section'):
                self._words = {} #old section is in _sections
                self._sections.append(self._words)
                self._section += 1
                continue

            if line.startswith('#@nofuzzy'):
                self._args.fuzzy_disable = True
                continue

            # comment
            if line.startswith('#'):
                continue

            if len(line) > 500:
                continue

            line = line.strip("\n")
            if not line:
                continue

            # skip wonky words created by strings2
            if self._args.ignore_wrong and self._is_line_ok(line):
                continue

            # games like Death Stranding somehow have spaces in their names
            if self._args.join_spaces:
                line = line.replace(' ', '_')

            # clean vars
            types = ['%d' '%c' '%s' '%f' '0x%08x' '%02d' '%u' '%4d' '%10d']
            for type in types:
                line = line.replace(type, '')

            # clean copied fnvs
            if ': ' in line:
                index = line.index(': ') 
                if line[0:index].isnumeric():
                    line = line[index+1:]

            elems = self.PATTERN_LINE.split(line)
            for elem in elems:
                self._add_word(elem)

                if elem and len(elem) > 1 and self._args.split_caps and not elem.islower() and not elem.isupper():
                    new_elem = ''
                    pre_letter = ''
                    for letter in elem:
                        if letter.isupper() or letter.isdigit():
                            if pre_letter.islower():
                                new_elem += "_"
                            new_elem += letter.lower()
                        else:
                            new_elem += letter
                        pre_letter = letter

                    if '_' in new_elem:
                        self._add_word(new_elem)

                if self._args.cut_last and elem:
                    elem_len = len(elem)
                    max = self._args.cut_last
                    if elem_len <= max:
                        continue
                    for i in range(1, self._args.cut_last+1):
                        elem_cut = elem[0:-i]
                        self._add_word(elem_cut)

                # When reading wwnames.txt that contain IDs, should ignore IDs that are included in the file
                # This way we keep can keep adding reversed names to wwnames.txt without having to remove IDs
                # Only for base elem and not derived parts.
                if self._parsing_wwnames:
                    elem_lw = elem.lower()
                    if self._fnv.is_hashable(elem_lw):
                        fnv = self._fnv.get_hash(elem_lw)
                        self._words_reversed.add(int(fnv))


    def _read_words(self, file):
        encodings = ['utf-8-sig', 'iso-8859-1']
        try:
            done = False
            for encoding in encodings:
                try:
                    with open(file, 'r', encoding=encoding) as infile:
                        self._read_words_lines(infile)
                        done = True
                    break
                except UnicodeDecodeError:
                    continue

            if not done:
                print("couldn't read input file %s (bad encoding?)" % (file))

        except FileNotFoundError:
            pass

    #--------------------------------------------------------------------------

    def _get_formats(self):
        #formats = []
        #for key in self._formats:
        #    format, format_og, type, sub = self._formats[key]
        #    formats.append(format) #original/lowercase

        # pre-loaded
        return self._formats.values()

    def _get_permutations(self):
        permutations = 1
        sections = []
        for section in self._sections:
            if self._args.text_output:
                words = section.values() #original
            else:
                words = section.keys() #lowercase

            permutations *= len(words)
            sections.append(words)

        f_len = len(self._formats)
        print("creating %i permutations * %i formats (%s sections)" % (permutations, f_len, len(self._sections)) )

        elems = itertools.product(*sections)
        return elems

    def _get_combinations(self):
        if self._args.text_output:
            words = self._words.values() #original
        else:
            words = self._words.keys() #lowercase bytes

        w_len = len(words)
        f_len = len(self._formats)
        combinations = int(self._args.combinations)
        print("creating %i combinations * %i formats" % (pow(w_len, combinations), f_len) )

        elems = itertools.product(words, repeat=combinations)
        return elems

    def _get_basewords(self):
        if self._args.text_output:
            words = self._words.values() #original
        else:
            words = self._words.keys() #lowercase bytes

        w_len = len(words)
        f_len = len(self._formats)
        print("creating %i words * %i formats" % (w_len, f_len))
        return words

    #--------------------------------------------------------------------------

    def _write_words(self):
        is_text_output = self._args.text_output
        no_fuzzy = self._args.fuzzy_disable

        # huge memory consumption, not iterator?
        #words = ["_".join(x) for x in self._get_xxx()]
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

        reversables = self._reversables
        fuzzies = self._fuzzies
        if not is_text_output and not reversables:
            print("no reversable IDs found")
            return

        if is_text_output:
            print("generating words")
        else:
            print("reversing FNVs")

        joiner = self._get_joiner()
        combine = self._args.combinations or self._args.permutations

        # info
        info_count = 0
        info_add = 5000000 // len(formats)
        info_top = info_add
        written = 0
        start_time = time.time()

        joinerbytes = bytes(joiner, 'UTF-8')

        with open(self._args.output_file, 'w') as outfile, open(self._args.skips_file, 'a') as skipfile:
            for word in words:
                for full_format in formats:
                    format, _, type, pre, suf = full_format

                    if is_text_output:
                        out = self._get_outword(full_format, word, joiner, combine, True)
                        outfile.write(out + '\n')
                        written += 1
                        continue

                    # concats, slower (30-50%?)
                    #out = self._get_outword(full_format, word, joiner, combine)
                    # inline'd FNV hash, ~5% speedup
                    #fnv_base = self._fnv.get_hash_lw(out_lower)

                    #----------------------------------------------------------
                    # MAIN HASHING (inline'd)
                    #
                    # 'word' is a list on combos like ("aaa", "bbb") + formats "base_%s".
                    # Instead of hash("base_aaa_bbb") we can avoid str concat by doing 
                    # hash("base_"), hash("aaa"), hash("_"), hash("bbb") passing output as next seed.
                    # combos are pre-converted to bytes for a minor speed up too.
                    hash = 2166136261 #base FNV hash

                    if pre:
                        for namebyte in pre:
                            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF 

                    if combine:
                        # quick ignore non-hashable
                        if not pre and 0x30 <= word[0][0] <= 0x39: #.isdigit():
                            continue

                        len_word = len(word) - 1
                        for i, subword in enumerate(word):
                            for namebyte in subword:
                                hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF 
                            if i < len_word:
                                for namebyte in joinerbytes:
                                    hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF 

                    else:
                        # quick ignore non-hashable
                        if not pre and 0x30 <= word[0] <= 0x39: #.isdigit():
                            continue

                        for namebyte in word:
                            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF 

                    if suf:
                        for namebyte in suf:
                            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF 

                    fnv_base = hash
                    
                    #----------------------------------------------------------

                    # its ~2-5% faster calc FNV + check if it a target FNV, than checking for skips first (less common)
                    # non-empty test first = minor speedup if file doesn't exist
                    #if self._skips and out in self._skips:
                    #    continue

                    if no_fuzzy and fnv_base not in reversables:
                        continue

                    fnv_fuzz = fnv_base & 0xFFFFFF00
                    if fnv_fuzz in fuzzies:
                        for fnv in reversables:
                            if self._args.fuzzy_disable:
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
                                    out_lower = self._get_outword(full_format, word, joiner, combine)
                                    out_final = self._fnv.unfuzzy_hashname_lw(fnv, out_lower, out_final)
                                    if not out_final: #may happen in rare cases
                                        continue

                            out_final_lw = out_final.lower()
                            if out_final_lw in self._skips:
                                continue
                            self._skips.add(out_final_lw)

                            # don't print non-useful hashes
                            if not self._fnv.is_hashable(out_final_lw):
                                continue
                            if self._args.max_chars and len(out_final) > self._args.max_chars:
                                continue

                            outfile.write("%s: %s\n" % (fnv, out_final))
                            outfile.flush() #reversing is most interesting with lots of loops = slow, keep flushing

                            skipfile.write("%s: %s\n" % (fnv, out_final_lw))

                            written += 1

                info_count += 1
                if info_count == info_top:
                    info_top += info_add
                    print("%i..." % (info_count), word)


        print("total %i results" % (written))

        end_time = time.time()
        print("done (elapsed %ss)" % (end_time - start_time))

    def _get_outword(self, full_format, word, joiner, combine, text=False):
        format, _, type, pre, suf = full_format    

        if pre:
            pre = pre.decode("utf-8") 
        if suf:
            suf = suf.decode("utf-8") 

        if combine:
            if text:
                baseword = joiner.join(word)
            else:
                temp = [x.decode('utf-8') for x in word]
                baseword = joiner.join(temp)
        else:
            if text:
                baseword = word
            else:
                baseword = word.decode("utf-8")

        # doing "str % (str)" every time is ~40% slower
        if   type == self.FORMAT_TYPE_NONE:
            out = baseword
        elif type == self.FORMAT_TYPE_PREFIX:
            out = pre + baseword
        elif type == self.FORMAT_TYPE_SUFFIX:
            out = baseword + suf
        else: #prefix+suffix
            #out = format % (baseword) 
            out = pre + baseword + suf

        return out

    # when reversing format/word are lowercase, but we have regular case saved to get original combo
    def _get_original_case(self, format, word, joiner):
        _, format_og, _, _, _ = self._formats[format]

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

    #--------------------------------------------------------------------------

    def _process_config(self):
        cb = self._args.combinations
        pt = self._args.permutations

        # separate output files to make it clearer
        if self._args.output_file == self.FILENAME_OUT:
            if cb:
                self._args.output_file = self.FILENAME_OUT_EX % (cb)
            elif pt:
                self._args.output_file = self.FILENAME_OUT_EX % ('p')

        # unless splicitly enabled, don't use fuzzy in these modes
        if not self._args.fuzzy_enable and (cb or pt):
            self._args.fuzzy_disable = True


    def start(self):
        self._args = self._parse()

        self._read_formats(self._args.formats_file)

        self._parsing_wwnames = True
        files = glob.glob(self._args.wwnames_file)
        for file in files:
            self._read_words(file)
            self._read_reversables(file)
        self._parsing_wwnames = False

        self._read_words(self._args.input_file)
        self._read_reversables(self._args.reverse_file)
        self._read_skips(self._args.skips_file)

        self._process_config()
        self._write_words()

###############################################################################

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
