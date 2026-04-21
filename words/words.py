# WORDS.PY
#
# Reverses hashes by combining words in various ways (see README.md)
# NOTE: use pypy for better performance.

import argparse, re, itertools, time, glob, os, datetime
import fnmatch

# TODO: simplify word loader
# TODO: multicommand mode
# TODO: improve loader._words, etc
# TODO: add more hash modes
# TODO: change cut-last/first for %s[x:x]

# max length of a line in input files (typically pre-split by tools like wstrings)
WORDS_LINE_MAX = 500

#------------------------------------------------------------------------------

# sorts output results by context
class ResultsSorter():
    _CONTEXT_BOTTOM = b'### VA'  #TODO: other contexts?

    def __init__(self, args, contexts, hasher):
        self._results_contexts = True
        self._output_file = args.output_file
        self._contexts = contexts
        self._hasher = hasher
        self._ctx_filter = '' #TODO add

    # read output file and separate hash + name(s)
    def _read_results(self, inname):
        results = {}
        try:
            with open(inname, 'rb') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    match = self._hasher.split_match(line)
                    if not match:
                        continue

                    hash, name = match
                    if hash not in results:
                        results[hash] = []
                    results[hash].append(name)
        except FileNotFoundError:
            pass
        return results

    # sort results by context (if any) and name
    def _sort_results(self, items):

        if self._results_contexts:
            remove_repeats = True

            done = {} #hash > context
            lines = []

            contexts = self._get_contexts()
            for context in contexts:
                # note that the same key may be in multiple contexts (ignored by default)

                # mark names per context and repeats
                subitems = {}
                for hash in self._contexts.get_context_hashes(context):
                    if hash in done and done[hash] != context and remove_repeats:
                        continue
                    if hash in items:
                        done[hash] = context
                        subitems[hash] = items[hash]
                if not subitems:
                    continue

                if context:
                    ctx_str = context.decode("utf-8")
                    if self._ctx_filter and self._ctx_filter in ctx_str:
                        continue
                    lines.append(ctx_str)
                lines += self._sort_lines(subitems)
                lines.append('')

            # rare but just in case of bugs
            subitems = {}
            for hash in items:
                if hash in done and remove_repeats:
                    continue
                #done[hash] = context
                subitems[hash] = items[hash]
                
            if subitems:
                lines += self._sort_lines(subitems)
            
        else:
            lines = self._sort_lines(items)

        return lines

    # sort a hash=name dict
    def _sort_lines(self, subitems):
        lines = []
        items = []

        #items = [(key,val) for key,val in items.items()]
        for key,vals in subitems.items():
            for val in vals:
                items.append( (key, val) )

        #items = list(items.values())
        items.sort(key=lambda x : x[1].lower())
        for hash, name in items:
            match = self._hasher.format_match(hash, name)
            lines.append(str(match, 'utf-8'))

        return lines

    def _get_contexts(self):
        # put variables + values at the end, since they are simpler to clasify
        contexts = []
        contexts_bottom = []

        for context in self._contexts.get_context_names():
            if context and self._CONTEXT_BOTTOM in context.upper():
                contexts_bottom.append(context)
            else:
                contexts.append(context)

        contexts.extend(contexts_bottom)
        return contexts

    # overwrite output file
    @staticmethod
    def _write_results(outname, lines):
        #outname = outname.replace('.txt', '-order.txt')
        with open(outname, 'w') as f:
           f.write('\n'.join(lines))

    def sort(self):
        inname = self._output_file
        results = self._read_results(inname)
        if not results:
            return

        lines = self._sort_results(results)

        self._write_results(inname, lines)

#------------------------------------------------------------------------------

# Info about current "### (context)" where a hash was found
# This is used to sort results or filter contexts to fine-tune searches.
class WordsContexts():
    def __init__(self):
        self._contexts = {}
        self._curr_context = None
        self._curr_context_lw = None
        self._contexts[self._curr_context] = []

        self._filter_hashes = []
        self._filter_names = []
        self._skip_hashes = []
        self._skip_names = []

    def get_context_names(self):
        return self._contexts.keys()

    def get_context_hashes(self, context):
        return self._contexts[context]

    def set_context(self, line):
        self._curr_context = line.strip()
        self._curr_context_lw = self._curr_context.lower()
        if self._curr_context not in self._contexts: # in case of repeats
            self._contexts[self._curr_context] = []

    def set_context_temp(self, line):
        self._curr_context = line.strip()
        self._curr_context_lw = self._curr_context.lower()
        #if self._curr_context not in self._contexts: # in case of repeats
        #    self._contexts[self._curr_context] = []

    def reset_context(self):
        self._curr_context = None

    def is_context(self, line):
        return line.startswith(b'### ') # and b' NAMES' in line

    def add_hash(self, hash):
        self._contexts[self._curr_context].append(hash)

    def _is_filtered_internal(self, filters, flag):
        if not self._curr_context:
            return False

        if not filters:
            return False

        found = any(fnmatch.fnmatch(self._curr_context_lw, pattern) for pattern in filters)
        if found:
            return flag

        return not flag

    def add_filters(self, line):

        # allow hashes in the listed contexts
        if line.startswith(b'#@filter-hashes'):
            items = line.split(b' ')[1:]
            self._filter_hashes = [item.lower() for item in items]
            return True

        # allow names in the listed contexts
        if line.startswith(b'#@skip-hashes'):
            items = line.split(b' ')[1:]
            self._skip_hashes = [item.lower() for item in items]
            return True

        # allow names in the listed contexts
        if line.startswith(b'#@filter-names'):
            items = line.split(b' ')[1:]
            self._filter_names = [item.lower() for item in items]
            return True

        # skip names in the listed contexts
        if line.startswith(b'#@skip-names'):
            items = line.split(b' ')[1:]
            self._skip_names = [item.lower() for item in items]
            return True

        return False

    # current context has any of the filters: allow/ignore
    def is_hashes_filtered(self):
        return self._is_filtered_internal(self._filter_hashes, False)

    def is_names_filtered(self):
        return self._is_filtered_internal(self._filter_names, False)

    def is_hashes_skipped(self):
        return self._is_filtered_internal(self._skip_hashes, True)

    def is_names_skipped(self):
        return self._is_filtered_internal(self._skip_names, True)

#------------------------------------------------------------------------------

class WordsCombinator():
    def __init__(self, args, words, formats, sections, joiners):
        self._args = args
        self._words = words
        self._formats = formats
        self._sections = sections
        self._joiners = joiners

    @staticmethod
    def test(combos):
        start_time = time.time()

        i = 0
        for combo in combos:
            #print(combo)
            i += 1

        end_time = time.time()

        elapsed = end_time - start_time
        print(f"words test done, elapsed: {elapsed:.5f}s")
        exit()

    def get_formats(self):
        # pre-loaded
        return self._formats.values()

    def _get_permutations(self):
        #joiners = self._joiners
        #combinations = len(self._sections)

        parts = []
        for i, section in enumerate(self._sections):
            # .values() = original, .keys() = transformed
            words = section.keys()

            parts.append(words)

            # prepare [words, joiner, words, joiner, ...]
            #if i < combinations - 1 and joiners:
            #    parts.append(joiners)

        elems = itertools.product(*parts)
        return elems

    def _get_combinations(self):
        #joiners = self._joiners
        combinations = int(self._args.combinations)

        # .values() = original, .keys() = transformed
        words = self._words.keys()

        if self._args.combinations_unique:
            elems = itertools.permutations(words, r=combinations)
            # not appropriate due to removed elems
            #elems = itertools.combinations(words, r=combinations)
            #elems = itertools.combinations_with_replacement(words, r=combinations)
        else:
            parts = []
            for i in range(combinations):
                parts.append(words)

                # prepare [words, joiner, words, joiner, ...]
                #if i < combinations - 1 and joiners:
                #    parts.append(joiners)

            elems = itertools.product(*parts)

            # without joiners
            #elems = itertools.product(words, repeat=combinations)

        return elems

    def _get_basewords(self):
        # .values() = original, .keys() = transformed
        words = self._words.keys()

        return words

    def get_combos(self):

        # huge memory consumption, not iterator
        #words = ["_".join(x) for x in self._get_xxx()]

        if self._args.permutations:
            words = self._get_permutations()
        elif self._args.combinations:
            words = self._get_combinations()
        else:
            words = self._get_basewords()

        #self.test(words)

        return words

    def get_joiner(self):
        return self._joiners[0] if self._joiners else b''

    # can't use len() with generators 
    def show_totals(self):
        w_len = len(self._words)
        f_len = len(self._formats)
        s_len = len(self._sections)

        total = 0
        type_name = '?'
        if self._args.permutations:
            type_name = 'permutations'
            total = 1
            for section in self._sections:
                total *= len(section)

        elif self._args.combinations:
            type_name = 'combinations'

            combinations = int(self._args.combinations)
            if self._args.combinations_unique:
                total = 1
                for i in range(w_len, w_len - combinations, -1):
                    total *= i
            else:
                total = pow(w_len, combinations)

        else:
            type_name = 'words'
            total = w_len

        if self._args.permutations:
            print(f"creating {total} {type_name} * {f_len} formats ({s_len} sections)")
        else:
            print(f"creating {total} {type_name} * {f_len} formats = {total * f_len}")

        return total



class WordsLoader():
    _DEFAULT_FORMAT = b'%s'
    _WORD_ALLOWED = [b'xiii', b'xviii', b'zzz']

    def __init__(self, args, hasher, contexts):
        self._args = args
        self._hasher = hasher
        self._contexts = contexts

        self._formats = {} # format_hashable > format_hashable, format, prefix, suffix, pre_hash

        self._skips = set()
        self._reversables = set()
        self._fuzzies = set()

        # With dicts we use: words[index] = value, index = transformed name, value = original name.
        # When reversing uses transformed to avoid hasher.transform() loops, while using original name when returning results
        self._words = {} #OrderedDict() # dicts are ordered in python 3.7+
        self._words_reversed = set()

        self._sections = []
        self._sections.append(self._words)
        self._section = 0

    #--------------------------------------------------------------------------

    @staticmethod
    def is_alpha(word):
        return all(
            0x41 <= ch <= 0x5A or 0x61 <= ch <= 0x7A
            for ch in word
        )

    #--------------------------------------------------------------------------

    def _read_format_flags(self, elem):
        done = self._contexts.add_filters(elem)
        if done:
            return
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
                self._add_format_s(format + sf)
        self._add_format_s(format)

    def _add_format_s(self, format):
        flag = b'%s'
        parts = format.split(flag)
        prefix = self._hasher.transform(parts[0])
        suffix = self._hasher.transform(parts[1])

        key = prefix + flag + suffix
        if key in self._formats:
            return

        # useful?
        if not prefix:
            prefix = None
        if not suffix:
            suffix = None

        pre_hash = None
        if prefix:
            pre_hash = self._hasher.get_hash(prefix)

        self._formats[key] = (key, format, prefix, suffix, pre_hash)


    def _read_formats(self, file):
        try:
            with open(file, 'rb') as infile:
                for line in infile:
                    self._add_format(line)
        except FileNotFoundError:
            pass

        if not self._formats:
            self._add_format(self._DEFAULT_FORMAT)

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

        subwords = self._hasher.split_word(elem)
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
            if not combo:
                continue
            combo_hashable = self._hasher.transform(combo)

            # makes only sense on simpler cases with no formats
            # (ex. if combining format "play_bgm_%s" and number in list is reasonable)
            #if self._args.hashable_only and not self._hasher.is_hashable(combo_hashable):
            #    continue

            if self._args.alpha_only and not self.is_alpha(combo_hashable):
                continue

            if self._args.format_begins:
                if not any(combo_hashable.startswith(fb) for fb in self._args.format_begins):
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
            elem_hashable = self._hasher.transform(elem)
            if not self._hasher.is_hashable(elem_hashable):
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
        if self._contexts.is_context(line):
            self._contexts.set_context(line)
            return

        if self._contexts.is_hashes_filtered():
            return
        if self._contexts.is_hashes_skipped():
            return

        if line.startswith(b'# '): #allow hashes in wwnames.txt with -sm
            line = line[2:]
        if line.startswith(b'#'):
            return

        elem = line.strip()
        if not elem:
            return

        key = self._hasher.read_hash(elem)
        if not key:
            return

        # skip already useful names in wwnames.txt
        if self._parsing_wwnames:
            if key in self._words_reversed:
                return

        self._reversables.add(key)
        self._contexts.add_hash(key)

    def _read_reversables(self, file, reset_if_found=False):
        try:
            self._contexts.reset_context()
            with open(file, 'rb') as infile:
                if reset_if_found:
                    print("ignoring existing wwnames hashes to use external list")
                    self._reversables = set()

                for line in infile:
                    self._add_reversable(line)
        except FileNotFoundError:
            pass

        if not self._args.fuzzy_disable:
            for elem in self._reversables:
                fuzzy_hash = elem & 0xFFFFFF00
                self._fuzzies.add(fuzzy_hash) #may be smaller than hash dict

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
            elem_hashable = self._hasher.transform(elem)
            words[elem_hashable] = elem
            return

        joiner = self._get_joiner()

        subwords = self._hasher.split_word(elem)
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
            combo_hashable = self._hasher.transform(combo)

            # makes only sense on simpler cases with no formats
            # (ex. if combining format "play_bgm_%s" and number in list is reasonable)
            if self._args.hashable_only and not self._hasher.is_hashable(combo_hashable):
                continue

            if self._args.alpha_only and not self.is_alpha(combo_hashable):
                continue

            words[combo_hashable] = combo

        # add itself (needed when joiner is not _)
        if add_self:
            elem_hashable = self._hasher.transform(elem)
            if self._hasher.is_hashable(elem_hashable):
                words[elem_hashable] = elem

    #TODO: improve, not very useful and possibly slower
    def _is_line_ok(self, line):
        #line = line.strip()
        line_len = len(line)

        line_transformed = line
        if line_len <= 6:
            line_transformed = self._hasher.transform(line)

        if line_transformed in self._WORD_ALLOWED:
            return True

        # skip wonky mini words #TODO: remove? may be split anyway
        if line_len < 4 and not self._hasher.is_hashable(line_transformed):
            return False

        #if line_len < 12:
        #    for key, group in itertools.groupby(line):
        #        group_len = len(list(group))
        #        if key.lower() in [b'0', b'1', b'x', b' ']: #allow 000, 111, xxx
        #            continue
        #        if group_len > 2:
        #            return False

        return True

    # converts getBlah > get_blah (will be transformed later if needed)
    def _transform_caps(self, elem):
        if not elem or len(elem) == 0:
            return elem
        
        if elem.islower() or elem.isupper():
            return elem
    
        curr = b''
        prev = b''
        for letter in elem:
            letter_b = bytes([letter])
            if letter_b.isupper() or letter_b.isdigit():
                if prev.islower():
                    curr += b'_'
                curr += letter_b.lower()
            else:
                curr += letter_b
            prev = letter_b

        return curr

    def _read_words_lines(self, infile):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("reading words: %s (%s)" % (infile.name, ts))

        num = 0
        for line in infile:
            num += 1
            if num % 1000000 == 0:
                print(" %i lines..." % (num))

            if self._contexts.is_context(line):
                self._contexts.set_context_temp(line)
                continue

            if self._contexts.is_names_filtered():
                continue
            if self._contexts.is_names_skipped():
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

            if len(line) > WORDS_LINE_MAX:
                continue

            line = line.strip(b'\n')
            line = line.strip(b'\r')
            if not line:
                continue

            # skip wonky words created by strings2
            if self._args.ignore_wrong and self._is_line_ok(line):
                continue

            # ignore matches like '(number) : name' copied from results'
            if self._parsing_wwnames:
                match = self._hasher.split_match(line)
                if match:
                    hash, name = match
                    self._add_word(name)
                    self._words_reversed.add(hash)
                    continue

            # clean vars
            var_types = [b'%d' b'%c' b'%s' b'%f' b'0x%08x' b'%02d' b'%u' b'%4d' b'%10d']
            for var_type in var_types:
                line = line.replace(var_type, b'')

            # clean copied hashes
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

            elems = self._hasher.split_line(line)
            for elem in elems:

                # convert caps to _ (first so other flags work over this)
                if self._args.split_caps:
                    elem = self._transform_caps(elem)

                # regular elem
                self._add_word(elem)

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
                    elem_hashable = self._hasher.transform(elem)
                    if self._hasher.is_hashable(elem_hashable):
                        hash = self._hasher.get_hash(elem_hashable)
                        self._words_reversed.add(hash)

            # most of the time only makes sense to automake formats from wwnames and not ww.txt
            if self._args.format_auto and (self._parsing_wwnames or self._args.format_auto_all):
                for elem in elems:
                    self._add_format_auto(elem)

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("reading done (%s)" % (ts) )


    def _read_words(self, file):
        try:
            # lines are read as binary (works fine) to simplify and slightly speed up loading
            self._contexts.reset_context()
            with open(file, 'rb') as infile:
                self._read_words_lines(infile)
        except FileNotFoundError:
            pass

    def parse_files(self):
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

#--------------------------------------------------------------------------

class WordsReverser():

    def __init__(self, args, hasher, loader):
        self._args = args
        self._hasher = hasher
        self._loader = loader

    def reverse_words(self):
        args = self._args
        loader = self._loader

        reversables = loader._reversables
        if not reversables:
            print("no reversable IDs found")
            return
        print("reversing %i hashes" % (len(reversables)))

        joiner = loader._get_joiner()
        joiners = [joiner]
        combinator = WordsCombinator(args, loader._words, loader._formats, loader._sections, joiners)

        totals = combinator.show_totals()
        if not totals:
            print("no words found")
            return

        # info
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("writting %s (%s)" % (args.output_file, ts))

        # main process
        with open(args.output_file, 'w') as outfile, open(args.skips_file, 'a') as skipfile:
            self._outfile = outfile
            self._skipfile = skipfile

            start_time = time.time()
            if isinstance(self._hasher, (WwiseHasher, WwiseExHasher)):
                written = self._reverse_wwise(combinator)
            else:
                written = self._reverse_common(combinator)
            end_time = time.time()

            self._outfile = None
            self._skipfile = None
   
        print("total %i results" % (written))

        if written == 0:
            os.remove(args.output_file)
        else:
            print("wrote %s" % (args.output_file))

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("reversing done (%s, elapsed %ss)" % (ts, end_time - start_time))


    # MAIN HASHING (inline'd with various microoptimizations, see comments)
    #
    # 'words' is a list on combos like ("aaa", "bbb") + formats "base_%s".
    # Instead of hash("base_aaa_bbb") we can avoid str concat by doing
    # hash("base_"), hash("aaa"), hash("_"), hash("bbb")
    #
    # micro-optimizations:
    # - uses words as bytes (rather than encoding/decoding) for some speed up.
    # - local variables (slightly faster)
    # - inline'd hash (25-50% speed up). calling a static func as a var is slow, and object's method call even slower
    # - ifs: could use separate functions to avoid ifs but don't seem much faster
    # - mixing formats x words (rather than words x formats)
    #
    # ignored optimizations:
    # - frozenset(reversables): ignored, no apparent changes
    # - reversables_in = reversables.__contains__: not noticeable, probably optimized out in pypy
    # - in mode_combine, using word_iter = iter(word) to avoid if: not noticeable
    # - in mode_combine, including joiners as part of the generator to void if: not noticeable
    # - don't check for skips first: its ~2-5% faster to hash + check, than check skips first (less common)
    # - unrolled words for combinations 2/3: ~<1% and ugly
    def _reverse_wwise(self, combinator):
        written = 0
        loader = self._loader

        # local variables, possibly faster
        no_fuzzy = self._args.fuzzy_disable
        mode_combine = self._args.combinations or self._args.permutations
        hash_fuzzy = 0

        reversables = loader._reversables
        fuzzies = loader._fuzzies

        joiner = combinator.get_joiner()
        formats = combinator.get_formats()

        # info
        progress_count = 0
        progress_add = 20000000 #// len(formats)
        progress_top = progress_add

        for (format_key, _format, prefix, suffix, pre_hash) in formats:
            #format, _, pre, suf, pre_hash = full_format #slightly slower?
            combos = combinator.get_combos()
            for word in combos:
                # progress info, shouldn't affect performance too much and useful to see it's working
                progress_count += 1
                if progress_count == progress_top:
                    progress_top += progress_add
                    print("%i..." % (progress_count), word)


                hash = 2166136261 #base FNV hash

                if prefix:
                    hash = pre_hash

                if mode_combine:
                    # quick ignore non-hashable
                    if not prefix and 0x30 <= word[0][0] <= 0x39: #.isdigit():
                        continue

                    for i, subword in enumerate(word):
                        if i > 0:
                            for namebyte in joiner:
                                hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF
                        for namebyte in subword:
                            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF

                else:
                    # quick ignore non-hashable
                    #if not prefix and 0x30 <= word[0] <= 0x39: #.isdigit():
                    #    continue

                    for namebyte in word:
                        hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF

                if suffix:
                    for namebyte in suffix:
                        hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF

                #----------------------------------------------------------

                if no_fuzzy:
                    if hash not in reversables:
                        continue
                else:
                    hash_fuzzy = hash & 0xFFFFFF00
                    if hash_fuzzy not in fuzzies:
                        continue

                done = self._handle_match(word, joiner, hash, hash_fuzzy, format_key)
                written += done

        return written

    # similar to the above, but less optimized
    def _reverse_common(self, combinator):
        written = 0
        loader = self._loader
        hasher = self._hasher

        # local variables, possibly faster
        no_fuzzy = self._args.fuzzy_disable
        mode_combine = self._args.combinations or self._args.permutations
        hash_fuzzy = 0
        hash_default = hasher.get_hash_base()

        reversables = loader._reversables
        fuzzies = loader._fuzzies

        joiner = combinator.get_joiner()
        formats = combinator.get_formats()

        # info
        progress_count = 0
        progress_add = 20000000 #// len(formats)
        progress_top = progress_add

        for (format_key, _format, prefix, suffix, pre_hash) in formats:
            #format, _, pre, suf, pre_hash = full_format #slightly slower?
            combos = combinator.get_combos()
            for word in combos:
                # progress info, shouldn't affect performance too much and useful to see it's working
                progress_count += 1
                if progress_count == progress_top:
                    progress_top += progress_add
                    print("%i..." % (progress_count), word)


                hash = hash_default

                if prefix:
                    hash = pre_hash

                if mode_combine:
                    for i, subword in enumerate(word):
                        if i > 0:
                            hash = hasher.get_hash_update(joiner, hash)
                        hash = hasher.get_hash_update(subword, hash)
                else:
                    hash = hasher.get_hash_update(word, hash)

                if suffix:
                    hash = hasher.get_hash_update(suffix, hash)

                #----------------------------------------------------------

                if no_fuzzy:
                    if hash not in reversables:
                        continue
                else:
                    hash_fuzzy = hash & 0xFFFFFF00
                    if hash_fuzzy not in fuzzies:
                        continue

                done = self._handle_match(word, joiner, hash, hash_fuzzy, format_key)
                written += done

        return written

    # handles a confirmed match
    # this doesn't happen often so there is no need to over-optimize
    # (it's faster to hash > match > check, than check > ... )
    def _handle_match(self, word, joiner, hash, hash_fuzzy, format_key):
        args = self._args
        hasher = self._hasher
        loader = self._loader

        reversables = loader._reversables
        mode_combine = args.combinations or args.permutations
        written = 0

        # match (regular or fuzzy)
        if args.fuzzy_disable:
            name = self._get_original_case(format_key, word, joiner)
            done = self._write_match(hash, name)
            if done:
                written += 1
        else:
            # multiple words may use the same fuzz
            for valid_hash in reversables:
                if hash_fuzzy != valid_hash & 0xFFFFFF00:
                    continue
                name = self._get_original_case(format_key, word, joiner)
                if valid_hash != hash: #TODO: recheck
                    outword = self._get_outword(format_key, word, joiner, mode_combine)
                    name = hasher.unfuzzy_hashname(valid_hash, outword, name)
                    if not name: #may happen in rare cases
                        continue

                done = self._write_match(valid_hash, name)
                if done:
                    written += 1

        if written:
            # reversing is most interesting with lots of loops = slow, keep flushing (rare)
            self._outfile.flush()

        return written
    
    def _write_match(self, hash, name):
        args = self._args
        hasher = self._hasher
        skips = self._loader._skips

        name_hashable = hasher.transform(name)
        if name_hashable in skips:
            return False
        skips.add(name_hashable)

        # don't print non-useful hashes
        if not hasher.is_hashable(name_hashable):
            return False
        if args.max_chars and len(name) > args.max_chars:
            return False

        match = hasher.format_match(hash, name)
        self._outfile.write(str(match, 'utf-8') + "\n")

        match = hasher.format_match(hash, name_hashable)
        self._skipfile.write(str(match, 'utf-8') + "\n")

        return True

    def _get_outword(self, format_key, word, joiner, mode_combine):
        loader = self._loader
        _format_key, format, prefix, suffix, _pre_hash = loader._formats[format_key]

        if mode_combine:
            baseword = joiner.join(word)
        else:
            baseword = word

        # doing "str % (str)" every time is ~40% slower
        if prefix and suffix:
            out = prefix + baseword + suffix
        elif prefix:
            out = prefix + baseword
        elif suffix:
            out = baseword + suffix
        else:
            out = baseword

        return out

    # when reversing format/word are lowercase, but we have regular case saved to get original combo
    def _get_original_case(self, format_key, word, joiner):
        args = self._args
        loader = self._loader

        _format_key, format, _prefix, _suffix, _pre_hash = loader._formats[format_key]

        if args.permutations:
            #joiner = b'' #with joiners part of word
            word_og = []
            i = 0
            for subword in word:
                subword_og = loader._sections[i].get(subword, subword)
                i += 1
                word_og.append(subword_og)
            return format % (joiner.join(word_og))

        elif  args.combinations:
            #joiner = b'' #with joiners part of word
            word_og = []
            for subword in word:
                subword_og = loader._words.get(subword, subword)
                word_og.append(subword_og)
            return format % (joiner.join(word_og))

        else:
            word_og = loader._words[word]
            return format % (word_og)

###############################################################################

class Hasher(object):
    _SPLITTER_LINE = re.compile(b'[^A-Za-z0-9_]')
    _SPLITTER_WORD = re.compile(b'[_]')
    _HASHABLE_CHECKER = re.compile(b'^[a-z_][a-z0-9_]*$')

    # ------------
    # hash reading

    # change case/etc depending on hash's needs
    def transform(self, text):
        return text.lower()

    # check if hash is possible, assuming it has been transformed first
    def is_hashable(self, text):
        return self._HASHABLE_CHECKER.match(text)

    # split line into words that can be used for hashing
    def split_line(self, line):
        return self._SPLITTER_LINE.split(line)

    # split words into subwords that can be used for hashing
    def split_word(self, line):
        return self._SPLITTER_WORD.split(line)

    def read_hash(self, text, base=0):
        try:
            key = int(text, base)
        except (TypeError, ValueError):
            return 0

        if key < 0xFFF or key > 0xFFFFFFFF:
            return 0

        return key

    # writes a "hash : match" format
    def format_match(self, hash, name):
        name = name.strip()
        return b"%-11d : %s" % (hash, name)

    # reads a "hash : match" format, or None if not valid
    def split_match(self, text):
        items = text.split(b':')
        if len(items) != 2:
            return None
        hash, name = items
        hash = int(hash.strip())
        name = name.strip()
        return hash, name

    # ---------------
    # hash processing

    # hash an array of bytes
    def get_hash(self, namebytes):
        return 0

    # default base hash to use in get_hash_update
    def get_hash_base(self):
        return 0

    # hash a partial array of bytes, with an existing hash
    def get_hash_update(self, namebytes, hash):
        return 0

    # def allow fuzzy matching (ex. bgm0 and bgm9 have same fuzzy hash)
    def allow_fuzzy(self):
        return True

    def unfuzzy_hashname(self, id, namebytes, hashname):
        return None


class WwiseHasher(Hasher):
    _FNV_DICT = b'0123456789abcdefghijklmnopqrstuvwxyz_'

    #--------------------------------------------------------------------------

    # Find actual name from a close name (same up to last char) using some fuzzy searching
    # ('bgm0' and 'bgm9' IDs only differ in the last byte, so it calcs 'bgm' + '0', '1'...)
    def unfuzzy_hashname(self, hash, namebytes, hashname):
        if not hash or not hashname:
            return None

        basehash = self.get_hash(namebytes[:-1]) #up to last byte
        for c in self._FNV_DICT: #try each last char
            temp_hash = self._get_partial_hash(basehash, c)  #ord(c) #already byte

            if temp_hash != hash:
                continue
            c_str = chr(c)
            for cs in hashname: #upper only if all base name is all upper
                cs_str = chr(cs)
                if cs_str.islower():
                    c_str = c_str.lower()
                    break

            hashname = hashname[:-1] + c_str.encode() #TODO: improve?
            return hashname

        # it's possible to reach here with incorrect (manually input) ids,
        # since not all 255 values are in _FNV_DICT
        return None

    # Partial hashing for unfuzzy'ing.
    def _get_partial_hash(self, hash, value):
        hash = hash * 16777619 #FNV prime
        hash = hash ^ value #FNV xor
        hash = hash & 0xFFFFFFFF #python clamp
        return hash

    # Standard AK FNV-1 with 32-bit.
    # This variation seems slightly faster in python+pypy vs separate ops or local vars
    def get_hash(self, namebytes):
        hash = 2166136261
        for namebyte in namebytes:
            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF
        return hash

    def get_hash_base(self):
        return 2166136261

    def get_hash_update(self, namebytes, hash):
        for namebyte in namebytes:
            hash = ((hash * 16777619) ^ namebyte) & 0xFFFFFFFF
        return hash


class WwiseExHasher(WwiseHasher):
    _PATTERN_LINE = re.compile(b'[^A-Za-z0-9_ ()-]')
    _SPLITTER_WORD = re.compile(b'[_ ]')
    _HASHABLE_CHECKER = re.compile(b"^[a-z_0-9][a-z0-9_()\- ]*$")


class IntiCreatesHasher(Hasher):
    _SPLITTER_LINE = re.compile(b'[^A-Za-z0-9_.]')
    _SPLITTER_WORD = re.compile(b'[_.]') #currently must join exts manually though
    _HASHABLE_CHECKER = re.compile(b'^[A-Za-z_][A-Za-z0-9_.]*$')

    def transform(self, text):
        return text #case sensitive

    def read_hash(self, text):
        return super().read_hash(text, 16)

    def format_match(self, hash, name):
        name = name.strip()
        return b"%08x  : %s" % (hash, name)

    def split_match(self, text):
        items = text.split(b':')
        if len(items) != 2:
            return None
        hash, name = items
        hash = int(hash.strip(), 16)
        name = name.strip()
        return hash, name

    def get_hash(self, namebytes):
        hash = 0xCDE723A5
        for namebyte in namebytes:
            temp = (hash + namebyte) & 0xffffffff
            hash = (141 * temp) & 0xffffffff
        return hash

    def get_hash_base(self):
        return 0xCDE723A5

    def get_hash_update(self, namebytes, hash):
        for namebyte in namebytes:
            temp = (hash + namebyte) & 0xffffffff
            hash = (141 * temp) & 0xffffffff
        return hash

    def allow_fuzzy(self):
        return False # TODO: possibly ok but unsure

#------------------------------------------------------------------------------

class WordsDefaults():
    FILENAME_WWNAMES = 'wwnames*.txt'
    FILENAME_IN = 'ww.txt'
    FILENAME_OUT = 'words_out.txt'
    FILENAME_OUT_EX = 'words_out%s.txt'
    FILENAME_FORMATS = 'formats.txt'
    FILENAME_SKIPS = 'skips.txt'
    FILENAME_REVERSABLES = 'hashes.txt'

    HASH_TYPE_DEFAULT = 'wwise'
    HASH_TYPES = {
        'wwise': WwiseHasher,
        'wwise-ex': WwiseExHasher,
        'inti': IntiCreatesHasher,
    }
    HASH_NAMES = '; '.join(HASH_TYPES.keys())

#--------------------------------------------------------------------------

def main(args):
    HasherClass = WordsDefaults.HASH_TYPES.get(args.type.lower())

    hasher = HasherClass()
    if not hasher.allow_fuzzy():
        args.fuzzy_disable = True

    contexts = WordsContexts()

    loader = WordsLoader(args, hasher, contexts)
    loader.parse_files()

    reverser = WordsReverser(args, hasher, loader)
    reverser.reverse_words()

    sorter = ResultsSorter(args, contexts, hasher)
    sorter.sort()


def parse():
    description = (
        "Reverses hashes by combining words in various ways\n"
    )
    epilog = (
        "Examples:\n"
        "  %(prog)s\n"
        "  - reverses with default files\n"
        "  %(prog)s -c 2\n"
        "  - reverses by doing combinations of 2 words from input list: A_A, A_B, A_C ...\n"
    )

    p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    # files
    p.add_argument('-t',  '--type',         help="Hash method: %s" % (WordsDefaults.HASH_NAMES), default=WordsDefaults.HASH_TYPE_DEFAULT)
    p.add_argument('-w',  '--wwnames-file', help="input names (word list + hash list)", default=WordsDefaults.FILENAME_WWNAMES)
    p.add_argument('-i',  '--input-file',   help="input word lists (ignores hashes)", default=WordsDefaults.FILENAME_IN)
    p.add_argument('-o',  '--output-file',  help="Output list", default=WordsDefaults.FILENAME_OUT)
    p.add_argument('-f',  '--formats-file', help="Format list file\n- use %%s to replace a word from input list", default=WordsDefaults.FILENAME_FORMATS)
    p.add_argument('-s',  '--skips-file',   help="List of words to ignore (so they arent tested again when doing test variations)", default=WordsDefaults.FILENAME_SKIPS)
    p.add_argument('-r',  '--reverse-file', help="Hash list to reverse", default=WordsDefaults.FILENAME_REVERSABLES)
    # modes
    p.add_argument('-c',  '--combinations',         help="Combine words in input list by N (repeats words)\nWARNING! don't set high with lots of formats/words")
    p.add_argument('-p',  '--permutations',         help="Permute words in input sections (section 1 * 2 * 3...)\n.End a section in words list and start next with #@section\nWARNING! don't combine many sections+words", action='store_true')
    p.add_argument('-cu', '--combinations-unique',  help="Combine words with unique combos only\nMakes a_b, b_a but not a_a, b_b", action='store_true')
    p.add_argument('-zd', '--fuzzy-disable',        help="Disable 'fuzzy matching' (auto last letter) when reversing", action='store_true')
    p.add_argument('-ze', '--fuzzy-enable',         help="Enable 'fuzzy matching' (auto last letter) when reversing", action='store_true')

    # other flags
    p.add_argument('-mc', '--max-chars',    help="Ignores results that go beyond N chars", type=int)
    p.add_argument('-js', '--join-spaces',  help="Join words with spaces in lines\n('Word Word' = 'Word_Word')", action='store_true')
    p.add_argument('-jb', '--join-blank',   help="Join words without '_'\n('Word' + 'Word' = WordWord instead of Word_Word)", action='store_true')
    p.add_argument('-j',  '--joiner',       help="Set word joiner")

    p.add_argument('-fa', '--format-auto',  help="Auto-makes format combos of (prefix)_%%s_(suffix)", action='store_true')
    p.add_argument('-fam','--format-auto-mix',     help="Autoformats mixes words like blah_blah_blah = blah_%%s_blah", action='store_true')
    p.add_argument('-fap','--format-auto-prefix',  help="Autoformats include up to N prefix parts", type=int)
    p.add_argument('-fas','--format-auto-suffix',  help="Autoformats include up to N suffix parts", type=int)
    p.add_argument('-faa','--format-auto-all',     help="Autoformats includes words from extra -i lists rather than just wwnames", action='store_true')
    p.add_argument('-fj', '--format-joiner',help="Set auto-format joiner (different than main joiner for flexibility)")
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
    p.add_argument('-cf', '--cut-first',    help="Cut first N chars (for strings2.exe odd results like 8bgm_main)", type=int)
    p.add_argument('-cl', '--cut-last',     help="Cut last N chars (for strings2.exe odd results like bgm_main8)", type=int)

    args = p.parse_args()

    # simplify
    if args.format_auto_prefix or args.format_auto_suffix or args.format_auto_mix:
        args.format_auto = True

    cb = args.combinations
    pt = args.permutations
    fa = args.format_auto

    # separate output files to make it clearer
    if args.output_file == WordsDefaults.FILENAME_OUT:
        if cb:
            args.output_file = WordsDefaults.FILENAME_OUT_EX % (cb)
        elif pt:
            args.output_file = WordsDefaults.FILENAME_OUT_EX % ('p')

    # unless splicitly enabled, don't use fuzzy in these modes
    if not args.fuzzy_enable and (cb or pt or fa):
        args.fuzzy_disable = True

    return args

if __name__ == "__main__":
    args = parse()
    main(args)
