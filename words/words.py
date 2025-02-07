# WORDS.PY
# 
# Reads word from input files, splitting by _ and applying formats, and makes word combos. Files:
# - wwnames*.txt: lists of words, in the form of (word1), (word2)_(word3), etc, that are split in
#   various ways (configurable). Lower/uppercase/symbols/incorrect words are fine (will be ignored
#   or adjusted as needed). Should include a list of FNV IDs, to reverse instead of creating words.
#
# - formats.txt: list of formats, in the form of %(command). By default uses %s if not found/empty.
#   This is meant to be used to include "probable" prefixes/suffixes ("Play_%s", "%s_bgm").
#   Available commands:
#   - "%s": basic ("Play_%s": combines with existing words)
#   - "%Nd/%Ni/%Nx": adds 0, 1, 2..., where N is max number of chars (up to 8)
#   - "%0Nd/%0Ni/%0Nx": same but 0-padded
#   - "%0Nd:M:": same but adds numbers in steps of M ("Play_BGM_%03i:5:" makes Play_BGM_000, Play_BGM_005, ...)
#   - "%0Nd^M^": same but limits numbers to M ("Play_BGM_%03i^20^" makes Play_BGM_000 up to Play_BGM_020)
#   - "%0Nd:M:^M^": same combined
#   - "%[123abc]": adds 1,2,3,a,b,c ("Play_BGM_1%[ab]" makes Play_BGM_1a, Play_BGM_1b)
#   - "%c": same as [abcd(..)z]
#   Any can be combined but may only use one %s (play_%02x_%s, play_%i_%i_%d but not play_%s_%s)
#
# - ww.txt: extra list of wwise words only (may use this instead of wwnames.txt)
#
# - fnv.txt: extra list of fnv IDs only (may use this instead of wwnames.txt)
#
# - words_out.txt: output of reversed FNV IDs.
#
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

import argparse, re, itertools, time, glob, os, datetime
import fnmatch

# TODO:
# - load words that end with "= 0" as-is for buses (not useful?)

class Words(object):
    DEFAULT_FORMAT = b'%s'
    FILENAME_WWNAMES = 'wwnames*.txt'
    FILENAME_IN = 'ww.txt'
    FILENAME_OUT = 'words_out.txt'
    FILENAME_OUT_EX = 'words_out%s.txt'
    FILENAME_FORMATS = 'formats.txt'
    FILENAME_SKIPS = 'skips.txt'
    FILENAME_REVERSABLES = 'fnv.txt'
    #PATTERN_LINE = re.compile(r'[\t\n\r .<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
    PATTERN_LINE = re.compile(b'[^A-Za-z0-9_]')
    PATTERN_WORD = re.compile(b'[_]')
    PATTERN_WRONG = re.compile(b'[^A-Za-z0-9_]')
    #PATTERN_WRONG = re.compile(r'[\t.<>,;.:{}\[\]()\'"$&/=!\\/#@+\^`´¨?|~*%]')
    WORD_ALLOWED = [b'xiii', b'xviii', b'zzz']

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
        
        # info about current "### (type) NAMES" where the ID was found (context > ids)
        self._contexts = {}
        self._curr_context = None
        self._curr_context_lw = None
        self._contexts[self._curr_context] = []
        self._ctx_filter = ''

        self._filter_fnvs = []
        self._filter_names = []

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
        p.add_argument('-i',  '--input-file',   help="Input list (ignores FNVs)", default=self.FILENAME_IN)
        p.add_argument('-o',  '--output-file',  help="Output list", default=self.FILENAME_OUT)
        p.add_argument('-f',  '--formats-file', help="Format list file\n- use %%s to replace a word from input list", default=self.FILENAME_FORMATS)
        p.add_argument('-s',  '--skips-file',   help="List of words to ignore\n(so they arent tested again when doing test variations)", default=self.FILENAME_SKIPS)
        p.add_argument('-r',  '--reverse-file', help="FNV list to reverse\nOutput will only write words that match FND IDs in the list", default=self.FILENAME_REVERSABLES)
        p.add_argument('-to', '--text-output',  help="Write words rather than reversing", action='store_true')
        p.add_argument('-de', '--delete-empty', help="Delete empty output files", action='store_true')
        p.add_argument('-rs', '--results-sort', help="Sort results after processing", action='store_true', default=True)
        p.add_argument('-rc', '--results-contexts',help="Order by #@classify-bank section (if found)", action='store_true', default=True)
        # modes
        p.add_argument('-c',  '--combinations',         help="Combine words in input list by N (repeats words)\nWARNING! don't set high with lots of formats/words")
        p.add_argument('-p',  '--permutations',         help="Permute words in input sections (section 1 * 2 * 3...)\n.End a section in words list and start next with #@section\nWARNING! don't combine many sections+words", action='store_true')
        p.add_argument('-cu', '--combinations-unique',  help="Combine words with unique combos only\nMakes a_b, b_a but not a_a, b_b", action='store_true')
        p.add_argument('-zd', '--fuzzy-disable',        help="Disable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
        p.add_argument('-ze', '--fuzzy-enable',         help="Enable 'fuzzy matching' (auto last letter) when reversing", action='store_true')

        # other flags
        p.add_argument('-mc',  '--max-chars',   help="Ignores results that go beyond N chars", type=int)
        p.add_argument('-js', '--join-spaces',  help="Join words with spaces in lines\n('Word Word' = 'Word_Word')", action='store_true')
        p.add_argument('-jb', '--join-blank',   help="Join words without '_'\n('Word' + 'Word' = WordWord instead of Word_Word)", action='store_true')
        p.add_argument('-j',  '--joiner',       help="Set word joiner")

        p.add_argument('-fa', '--format-auto',  help="Auto-makes format combos of (prefix)_%%s_(suffix)", action='store_true')
        p.add_argument('-fam','--format-auto-mix',     help="Autoformats mixes words like blah_blah_blah = blah_%s_blah", action='store_true')
        p.add_argument('-fap','--format-auto-prefix',  help="Autoformats include up to N prefix parts", type=int)
        p.add_argument('-fas','--format-auto-suffix',  help="Autoformats include up to N suffix parts", type=int)
        p.add_argument('-fj', '--format-joiner',help="Set auto-format joiner")
        p.add_argument('-fp', '--format-prefix',help="Add prefixes to all formats", nargs='*')
        p.add_argument('-fs', '--format-suffix',help="Add suffixes to all formats", nargs='*')
        p.add_argument('-fb', '--format-begins',help="Use only auto-formats that begin with text", nargs='*')
        p.add_argument('-iw', '--ignore-wrong', help="Ignores words that don't make much sense\nMay remove unusual valid words, like rank_sss", action='store_true')
        p.add_argument('-ho', '--hashable-only',help="Consider only hashable chunks", action='store_true')
        p.add_argument('-ao', '--alpha-only',   help="Ignores words with numbers (no play_12345)", action='store_true')
        p.add_argument('-sc', '--split-caps',   help="Splits words by (Word)(...)(Word) and makes (word)_(...)_(word)", action='store_true')
        p.add_argument('-sp', '--split-prefix', help="Splits words by (prefix)_(word) rather than any '_'", action='store_true')
        p.add_argument('-ss', '--split-suffix', help="Splits words by (word)_(suffix) rather than any '_'", action='store_true')
        p.add_argument('-sb', '--split-both',   help="Splits words by (prefix)_(word)_(suffix) rather than any '_'", action='store_true')
        p.add_argument('-sn', '--split-number', help="Splits in N parts: a_b_c with 2 = a_b, b_c", type=int)
        p.add_argument('-sf', '--split-full',   help="Only adds stems (from 'aa_bb_cc' only adds 'aa', 'bb', 'cc')", action='store_true')
        p.add_argument('-ns', '--no-split',     help="Disable splitting words by '_'", action='store_true')
        p.add_argument('-cf', '--cut-first',    help="Cut first N chars (for strings2.exe off results like 8bgm_main)", type=int)
        p.add_argument('-cl', '--cut-last',     help="Cut last N chars (for strings2.exe off results like bgm_main8)", type=int)
        return p.parse_args()

    #--------------------------------------------------------------------------

    def _reset_contexts(self):
        self._curr_context = None

    def _is_filtered(self, filters):
        
        if not self._curr_context:
            return False
        if not filters:
            return False

        found = any(fnmatch.fnmatch(self._curr_context_lw, pattern) for pattern in filters)
        if found:
            return False
        return True

    def _read_format_flags(self, elem):
        # use only FNV that match these
        if elem.startswith(b'#@filter-fnv'):
            items = elem.split(b' ')[1:]
            self._filter_fnvs = [item.lower() for item in items]

        if elem.startswith(b'#@filter-names'):
            items = elem.split(b' ')[1:]
            self._filter_names = [item.lower() for item in items]

        return

    def _add_format(self, format):
        format = format.strip()
        if not format:
            return

        if format.startswith(b'#@'):
            self._read_format_flags(format)
            return

        if format.startswith(b'#'):
            return

        if format.count(b'_') > 10: #bad line like _______...____
            return

        if b'%' not in format or format.count(b'%s') > 1:
            print("ignored wrong format (added as word):", format)
            self._add_word(format)
            return

        if b'%' not in format: #for combos
            print("ignored wrong format:", format)
            self._add_word(format)
            return

        self._add_format_subformats(format)
        return

    def _add_format_subformats(self, format):
        #if b':' in format:
        #    format = format[0: format.find(b':')]

        count = format.count(b'%')

        if count == 0: #'leaf' word (for blah_%d)
            self._add_word(format)
            self._add_format_pf(b"%s") #may be combined with anything
            return

        if count == 1 and b'%s' in format: #'leaf' format (for blah_%i_%s > blah_0_%s, blah_1_%s, ...)
            self._add_format_pf(format)
            return

        try:
            basepos = 0
            while True:
                st = format.index(b'%', basepos)
                nxt = format[st+1]

                # string: try again with pos after %s (only reaches here if there are more %)
                if nxt == ord(b's'):
                    basepos = st + 1
                    continue

                # letters
                if nxt == ord(b'c'):
                    ed = st + 1
                    items = b'abcdefghijklmnopkrstuvwxyz'
                    prefix = format[0:st]
                    suffix = format[ed+1:]
                    
                    for item in items:
                        subformat = b'%s%c%s' % (prefix, item, suffix)
                        self._add_format_subformats(subformat)
                    return

                # range: add per item
                if nxt == ord(b'['):
                    ed = format.index(b']', st)
                    items = format[st+2:ed]
                    prefix = format[0:st]
                    suffix = format[ed+1:]
                    
                    for item in items:
                        subformat = b'%s%c%s' % (prefix, item, suffix)
                        self._add_format_subformats(subformat)
                    return

                # numbers
                if nxt in b'0idxX': 
                    ed = st + 1

                    if format[ed] == ord(b'0'):
                        ed += 1

                    digits = 1
                    if format[ed] in b'123456789':
                        digits = int(format[ed:ed+1])
                        if digits >= 9: #just in case
                            print("ignored slow format: %s" % (format))
                            return
                        ed += 1

                    if format[ed] in b'id':
                        base = 10
                        ed += 1
                    elif format[ed] in b'xX':
                        base = 16
                        ed += 1
                    else:
                        print("unknown format: %s" % (format))
                        return

                    step = 1
                    limit = None

                    ed_fmt = ed
                    for extra in [b':', b'^']:
                        if ed < len(format) and format[ed] == ord(extra):
                            ed_stp = format.index(extra, ed + 1)
                            elem = int(format[ed+1:ed_stp])
                            ed = ed_stp + 1
                            if extra == b':':
                                step = elem
                            if extra == b'^':
                                limit = elem

                    prefix = format[0:st]
                    conversion = format[st:ed_fmt]
                    suffix = format[ed:]

                    if not limit:
                        limit = pow(base, digits)

                    rng = range(0, limit, step)
                    for i in rng:
                        # might as well reuse original conversion
                        subformat = (b'%s' + conversion + b'%s') % (prefix, i, suffix)
                        self._add_format_subformats(subformat)
                    return

                print("unknown format")    
                return

        except (ValueError, IndexError) as e:
            print("ignoring bad format", e)
            return
        
    def _add_format_pf(self, format):
        if self._args.format_prefix:
            for pf in self._args.format_prefix:
                pf = pf.encode('utf-8')
                self._add_format_sf(pf + format)
        self._add_format_sf(format)


    def _add_format_sf(self, format):
        if self._args.format_suffix:
            for sf in self._args.format_suffix:
                sf = sf.encode('utf-8')
                self._add_format_main(format + sf)
        self._add_format_main(format)

    def _add_format_main(self, format):
        format_lw = format.lower()
        key = format.lower()
        if key in self._formats:
            return

        if format == b'%s':
            type = self.FORMAT_TYPE_NONE
            pre = None
            suf = None

        elif format.endswith(b'%s'):
            type = self.FORMAT_TYPE_PREFIX
            pre = format_lw[:-2]
            suf = None

        elif format.startswith(b'%s'):
            type = self.FORMAT_TYPE_SUFFIX
            pre = None
            suf = format_lw[2:]

        else:
            type = self.FORMAT_TYPE_BOTH
            presuf = format_lw.split(b'%s')
            pre = presuf[0]
            suf = presuf[1]

        if self._args.text_output:
            val = format
        else:
            val = key

        pre_fnv = None
        if pre:
            #pre = bytes(pre, 'UTF-8')
            pre_fnv = self._fnv.get_hash_nb(pre)
        #if suf:
        #    suf = bytes(suf, 'UTF-8')

        self._formats[key] = (val, format, type, pre, suf, pre_fnv)

        #index = format.index(b'%')
        #if index:
        #    val = self._fnv.get_hash(format[0:index])
        #else:
        #    val = None
        #self._format_fnvs[key] = val
        #self._format_baselen[key] = index

    def _read_formats(self, file):
        try:
            with open(file, 'rb') as infile:
                for line in infile:
                    self._add_format(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._add_format(self.DEFAULT_FORMAT)

    def _add_format_auto(self, elem):
        if not elem:
            return
        if elem.count(b'_') > 20: #bad line like _______...____
            return

        mark = b'%s'
        joiner = self._get_format_joiner()

        if self._args.no_split:
            subformats = [
                elem + joiner + mark,
                mark + joiner + elem,
            ]
            for subformat in subformats:
                self._add_format(subformat)
            return

        subwords = self.PATTERN_WORD.split(elem)
        combos = []


        if self._args.format_auto_prefix:
            # blah_blah_blah w/ 2: blah_blah_%s, : blah_%s
            for i in range(0, self._args.format_auto_prefix):
                combo = joiner.join(subwords[:i+1]) + joiner + mark
                combos.append(combo)

        if self._args.format_auto_suffix:
            for i in range(0, self._args.format_auto_suffix):
                combo =  mark + joiner + joiner.join(subwords[-(i+1):])
                combos.append(combo)

        if self._args.format_auto_mix:
            for i in range(len(subwords)):
                for j in range(len(subwords)):
                    subitems = list(subwords)
                    subitems[j] = mark
                    combo = joiner.join(subitems)
                    combos.append(combo)

        if not combos:
            # blah_blah_blah > %s_blah_blah_blah, blah_%s_blah_blah, blah_blah_%s_blah, blah_blah_blah_%s
            for i in range(len(subwords)):
                items = itertools.combinations(subwords, i + 1)
                for item in items:
                    for j in range(len(item) + 1):
                        subitems = list(item)
                        subitems.insert(j, mark)

                        combo = joiner.join(subitems)
                        combos.append(combo)


        for combo in combos:
            if self._args.format_begins:
                combo_lw = combo.lower()
                if not any(combo_lw.startswith(fb) for fb in self._args.format_begins):
                    continue

            #print(combo)
            if not combo:
                continue
            combo_hashable = combo.lower()

            # makes only sense on simpler cases with no formats
            # (ex. if combining format "play_bgm_%s" and number in list is reasonable)
            #if self._args.hashable_only and not self._fnv.is_hashable(combo_hashable):
            #    continue
            if self._args.alpha_only and any(char_n < 0x30 and char_n > 0x39 for char_n in combo_hashable): #char.isdigit()
                continue
            self._add_format(combo)

    #--------------------------------------------------------------------------

    def _add_skip(self, line, full=False):
        line = line.strip()
        if not line:
            return
        if line.startswith(b'#'):
            return

        if full:
            elems = [line]
        else:
            elems = line.split()

        for elem in elems:
            elem_hashable = elem.lower()
            if not self._fnv.is_hashable(elem_hashable):
                continue
            self._skips.add(elem_hashable)
            self._skips.add(elem)

    def _read_skips(self, file):
        try:
            with open(file, 'rb') as infile:
                for line in infile:
                    self._add_skip(line)
        except FileNotFoundError:
            pass

    #--------------------------------------------------------------------------

    def _add_reversable(self, line):
        if line.startswith(b'### ') and b' NAMES' in line:
            self._curr_context = line.strip()
            self._curr_context_lw = self._curr_context.lower()
            if self._curr_context not in self._contexts: # in case of repeats
                self._contexts[self._curr_context] = []
            return

        if self._curr_context and self._filter_fnvs:
            if self._is_filtered(self._filter_fnvs):
                return

        if line.startswith(b'# '): #allow fnv in wwnames.txt with -sm
            line = line[2:]
        if line.startswith(b'#'):
            return

        elem = line.strip()
        if not elem:
            return
        if not elem.isdigit():
            return

        try:
            key = int(elem)
        except (TypeError, ValueError):
            return

        if key < 0xFFF or key > 0xFFFFFFFF:
            return

        # skip already useful names in wwnames.txt
        if self._parsing_wwnames:
            if key in self._words_reversed:
                return

        self._reversables.add(key)
        self._contexts[self._curr_context].append(key)

    def _read_reversables(self, file, reset_if_found=False):
        try:
            self._reset_contexts()
            with open(file, 'rb') as infile:
                if reset_if_found:
                    print("ignoring existing wwnames FNV to use external list")
                    self._reversables = set()

                for line in infile:
                    self._add_reversable(line)
        except FileNotFoundError:
            pass

        for elem in self._reversables:
            fnv = elem & 0xFFFFFF00
            self._fuzzies.add(fnv) #may be smaller than fnv_dict with similar FNVs

    #--------------------------------------------------------------------------

    def _get_joiner(self):
        joiner = b'_'
        if self._args.join_blank:
            joiner = b''
        if self._args.joiner:
            joiner = self._args.joiner
        return joiner

    def _get_format_joiner(self):
        joiner = b'_'
        #if self._args.join_blank:
        #    joiner = b''
        if self._args.format_joiner:
            joiner = self._args.format_joiner
        return joiner

    def _add_word(self, elem):
        if not elem:
            return
        if elem.count(b'_') > 20: #bad line like _______...____
            return

        words = self._words
        if self._args.no_split:
            words[elem.lower()] = elem
            return

        joiner = self._get_joiner()

        subwords = self.PATTERN_WORD.split(elem)
        combos = []
        add_self = True

        if self._args.split_full:
            for subword in subwords:
                if b'_' in subword:
                    continue
                combos.append(subword)

            add_self = False #when splitting full no need for the full word

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

        elif self._args.split_number:
            num = int(self._args.split_number)
            for i in range(len(subwords) + 1 - num):
                combos.append( joiner.join(subwords[i:i+num]) )

            add_self = False

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
            if self._args.alpha_only and any(char_n < 0x30 and char_n > 0x39 for char_n in combo_hashable): #char.isdigit()
            #if self._args.alpha_only and any(char.isdigit() for char in combo_hashable):
                continue

            #combo_hashable = bytes(combo_hashable, "UTF-8")
            words[combo_hashable] = combo

        # add itself (needed when joiner is not _)
        if add_self:
            elem_hashable = elem.lower()
            if self._fnv.is_hashable(elem_hashable):
                #elem_hashable = bytes(elem_hashable, "UTF-8")
                words[elem_hashable] = elem

    def _is_line_ok(self, line, line_lw):
        #line = line.strip()
        line_len = len(line)

        if line_lw in self.WORD_ALLOWED:
            return True

        # skip wonky mini words
        if line_len < 4 and self._PATTERN_WRONG.search(line):
            return False

        #if line_len < 12:
        #    for key, group in itertools.groupby(line):
        #        group_len = len(list(group))
        #        if key.lower() in [b'0', b'1', b'x', b' ']: #allow 000, 111, xxx
        #            continue
        #        if group_len > 2:
        #            return False

        return True

    def _read_words_lines(self, infile):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("reading words: %s (%s)" % (infile.name, ts))

        num = 0
        for line in infile:
            num += 1
            if num % 1000000 == 0:
                print(" %i lines..." % (num))

            if line.startswith(b'### ') and b' NAMES' in line:
                self._curr_context = line.strip()
                self._curr_context_lw = self._curr_context.lower()
                #if self._curr_context not in self._contexts: # in case of repeats
                #    self._contexts[self._curr_context] = []
                continue

            # section end when using permutations
            if self._args.permutations and line.startswith(b'#@section'):
                self._words = {} #old section is in _sections
                self._sections.append(self._words)
                self._section += 1
                continue

            if line.startswith(b'#@nofuzzy'):
                self._args.fuzzy_disable = True
                continue

            # allows partially using autoformats to combine with bigger word lists
            if line.startswith(b'#@noautoformat'):
                self._args.format_auto = False
                continue

            # comment
            if line.startswith(b'#'):
                continue

            if len(line) > 500:
                continue

            line = line.strip(b'\n')
            line = line.strip(b'\r')
            if not line:
                continue
            line_lw = line.lower()

            # skip wonky words created by strings2
            if self._args.ignore_wrong and self._is_line_ok(line, line_lw):
                continue

            if self._curr_context and self._filter_names:
                if self._is_filtered(self._filter_names):
                    continue

            # clean vars
            var_types = [b'%d' b'%c' b'%s' b'%f' b'0x%08x' b'%02d' b'%u' b'%4d' b'%10d']
            for var_type in var_types:
                line = line.replace(var_type, b'')

            # clean copied fnvs
            if b': ' in line:
                index = line.index(b': ')
                if line[0:index].strip().isdigit():
                    line = line[index+1:].strip()

            # games like Death Stranding somehow have spaces in their names
            if self._args.join_spaces:
                line = line.replace(b' ', b'_')

            # when parsing wwnames we may skip the full line
            if self._parsing_wwnames:
                self._add_skip(line, full=True)

            elems = self.PATTERN_LINE.split(line)
            for elem in elems:
                #if not self._args.split_caps:
                self._add_word(elem)

                if elem and len(elem) > 1 and self._args.split_caps and not elem.islower() and not elem.isupper():
                    # TODO fix
                    new_elem_b = b''
                    pre_letter_b = b''
                    for letter in elem:
                        letter_b = bytes([letter])
                        if letter_b.isupper() or letter_b.isdigit():
                            if pre_letter_b.islower():
                                new_elem_b += b'_'
                            new_elem_b += letter_b.lower()
                        else:
                            new_elem_b += letter_b
                        pre_letter_b = letter_b
    
                    if b'_' in new_elem_b:
                        self._add_word(new_elem_b)

                if self._args.cut_first and elem:
                    elem_len = len(elem)
                    max = self._args.cut_first
                    if elem_len <= max:
                        continue
                    for i in range(1, self._args.cut_first + 1):
                        elem_cut = elem[i:]
                        self._add_word(elem_cut)

                if self._args.cut_last and elem:
                    elem_len = len(elem)
                    max = self._args.cut_last
                    if elem_len <= max:
                        continue
                    for i in range(1, self._args.cut_last + 1):
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

            # most of the time only makes sense to automake formats from wwnames and not ww.txt
            if self._args.format_auto and self._parsing_wwnames:
                for elem in elems:
                    self._add_format_auto(elem)

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("reading done (%s)" % (ts) )


    def _read_words(self, file):
        try:
            # lines are read as binary (works fine) to simplify and slightly speed up loading
            self._reset_contexts()
            with open(file, 'rb') as infile:
                self._read_words_lines(infile)
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

        if self._args.combinations_unique:
            total = 1
            for i in range(w_len, w_len - combinations, -1):
                total *= i

            elems = itertools.permutations(words, r=combinations)
            # not appropriate due to removed elems
            #elems = itertools.combinations(words, r=combinations)
            #elems = itertools.combinations_with_replacement(words, r=combinations)
        else:
            total = pow(w_len, combinations)

            elems = itertools.product(words, repeat=combinations)
        print("creating %i combinations * %i formats" % (total, f_len) )

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
            print("reversing %i FNVs" % (len(reversables)))

        joiner = self._get_joiner()
        #joiner = bytes(joiner, 'UTF-8')
        combine = self._args.combinations or self._args.permutations

        # info
        info_count = 0
        info_add = 5000000 // len(formats)
        info_top = info_add
        written = 0
        start_time = time.time()

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("writting %s (%s)" % (self._args.output_file, ts))
        with open(self._args.output_file, 'w') as outfile, open(self._args.skips_file, 'a') as skipfile:
            for word in words:
                for full_format in formats:
                    format, _, type, pre, suf, pre_fnv = full_format

                    if is_text_output:
                        out = self._get_outword(full_format, word, joiner, combine)
                        out = str(out, 'utf-8') #for standard linesep'ing
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
                        hash = pre_fnv
                        #for namebyte in pre:
                        #    hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF

                    if combine:
                        # quick ignore non-hashable
                        if not pre and 0x30 <= word[0][0] <= 0x39: #.isdigit():
                            continue

                        len_word = len(word) - 1
                        for i, subword in enumerate(word):
                            for namebyte in subword:
                                hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF
                            if i < len_word:
                                for namebyte in joiner:
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

                            out_final = str(out_final, 'utf-8')
                            outfile.write("%s: %s\n" % (fnv, out_final))
                            outfile.flush() #reversing is most interesting with lots of loops = slow, keep flushing

                            out_final_lw = str(out_final_lw, 'utf-8')
                            skipfile.write("%s: %s\n" % (fnv, out_final_lw))

                            written += 1

                info_count += 1
                if info_count == info_top:
                    info_top += info_add
                    print("%i..." % (info_count), word)


        print("total %i results" % (written))

        if written == 0 and self._args.delete_empty:
            os.remove(self._args.output_file)
        else:
            print("wrote %s" % (self._args.output_file))

        end_time = time.time()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("writting done (%s, elapsed %ss)" % (ts, end_time - start_time))


    def _get_outword(self, full_format, word, joiner, combine):
        format, _, type, pre, suf, _ = full_format    

        #if pre:
        #    pre = pre.decode("utf-8")
        #if suf:
        #    suf = suf.decode("utf-8")

        if combine:
            baseword = joiner.join(word)
        else:
            baseword = word

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
        _, format_og, _type, _pre, _suf, _pre_fnv = self._formats[format]

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

    def _sort_results(self):
        if not self._args.results_sort:
            return

        inname = self._args.output_file

        # separate fnv + hash(es)
        names = {}
        try:
            with open(inname, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if ':' not in line:
                        continue

                    fnv, name = line.split(':')
                    fnv = int(fnv.strip())
                    name = name.strip()
                    if fnv not in names:
                        names[fnv] = []
                    names[fnv].append(name)
        except FileNotFoundError:
            return

        if self._args.results_contexts:
            remove_repeats = True
        
            done = {} #fnv set
            lines = []

            sections = self._sort_results_get_sections()
            for section in sections:
                # note that the same key may be in multiple contexts (ignored by default)

                # mark names per section and repeats
                subitems = {}
                for fnv in self._contexts[section]:
                    if fnv in done and done[fnv] != section and remove_repeats:
                        continue
                    if fnv in names:
                        done[fnv] = section
                        subitems[fnv] = names[fnv]
                if not subitems:
                    continue

                if section:
                    ctx_str = section.decode("utf-8")
                    if self._ctx_filter and self._ctx_filter in ctx_str:
                        continue
                    lines.append(ctx_str)
                lines += self._sort_results_lines(subitems)
                lines.append('')

            # rare but just in case of bugs
            subitems = {}
            for fnv in names:
                if fnv in done and remove_repeats:
                    continue
                #done[fnv] = section
                subitems[fnv] = names[fnv]
                
            if subitems:
                lines += self._sort_results_lines(subitems)
            
        else:
            lines = self._sort_results_lines(names)

        outname = inname #.replace('.txt', '-order.txt')
        with open(outname, 'w') as f:
           f.write('\n'.join(lines))

    def _sort_results_lines(self, subitems):
        lines = []
        items = []
        #items = [(key,val) for key,val in items.items()]
        for key,vals in subitems.items():
            for val in vals:
                items.append( (key, val) )
        #items = list(items.values())
        items.sort(key=lambda x : x[1].lower())
        for fnv, name in items:
            #fnv += ':'
            fnv = str(fnv).ljust(12)

            name = name.strip()
            lines.append("%s: %s" % (fnv, name))
        return lines

    def _sort_results_get_sections(self):
        # put variables + values at the end, since they are simpler to clasify
        sections = []
        sections_vars = []
        for section in self._contexts.keys():
            if section and b'### VA' in section:
                sections_vars.append(section)
            else:
                sections.append(section)
        sections.extend(sections_vars)
        return sections

    #--------------------------------------------------------------------------

    def _preprocess_config(self):
        if self._args.format_auto_prefix or self._args.format_auto_suffix or self._args.format_auto_mix:
            self._args.format_auto = True


    def _postprocess_config(self):
        cb = self._args.combinations
        pt = self._args.permutations
        fa = self._args.format_auto

        # separate output files to make it clearer
        if self._args.output_file == self.FILENAME_OUT:
            if cb:
                self._args.output_file = self.FILENAME_OUT_EX % (cb)
            elif pt:
                self._args.output_file = self.FILENAME_OUT_EX % ('p')

        # unless splicitly enabled, don't use fuzzy in these modes
        if not self._args.fuzzy_enable and (cb or pt or fa):
            self._args.fuzzy_disable = True


    def start(self):
        self._args = self._parse()
        self._preprocess_config()

        self._read_formats(self._args.formats_file)

        self._parsing_wwnames = True
        files = glob.glob(self._args.wwnames_file)
        for file in files:
            if file == self._args.input_file:
                continue
            self._read_words(file)
            self._read_reversables(file)
        self._parsing_wwnames = False

        files = glob.glob(self._args.input_file)
        for file in files:
            self._read_words(file)

        self._read_reversables(self._args.reverse_file, True)
        self._read_skips(self._args.skips_file)

        self._postprocess_config()
        self._write_words()
        self._sort_results()

###############################################################################

class Fnv(object):
    FNV_DICT = b'0123456789abcdefghijklmnopqrstuvwxyz_'
    FNV_FORMAT = re.compile(b"^[a-z_][a-z0-9\_]*$")
    FNV_FORMAT_EX = re.compile(b"^[a-z_0-9][a-z0-9_()\- ]*$")

    def is_hashable(self, lowname):
        return self.FNV_FORMAT.match(lowname)

    def is_hashable_extended(self, lowname):
        return self.FNV_FORMAT_EX.match(lowname)


    # Find actual name from a close name (same up to last char) using some fuzzy searching
    # ('bgm0' and 'bgm9' IDs only differ in the last byte, so it calcs 'bgm' + '0', '1'...)
    def unfuzzy_hashname_lw(self, id, lowname, hashname):
        if not id or not hashname:
            return None

        #namebytes = bytearray(lowname, 'UTF-8')
        namebytes = lowname
        basehash = self._get_hash(namebytes[:-1]) #up to last byte
        for c in self.FNV_DICT: #try each last char
            id_hash = self._get_partial_hash(basehash, c)  #ord(c) #already byte

            if id_hash == id:
                c_str = chr(c)
                for cs in hashname: #upper only if all base name is all upper
                    cs_str = chr(cs)
                    if cs_str.islower():
                       c_str = c_str.lower()
                       break

                hashname = hashname[:-1] + c_str.encode() #todo better way?
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
        #namebytes = bytes(lowname, 'UTF-8')
        namebytes = lowname
        return self._get_hash(namebytes)

    def get_hash_nb(self, namebytes):
        return self._get_hash(namebytes)

# #####################################

if __name__ == "__main__":
    Words().start()
