# NGRAMS
# This tool makes a list of 3-gram counts based on a dictionary (words.txt), for fnv.exe to use.
# English words has many words like -ion but few like -urp. By making a list of counts
# and telling fnv.exe to ignore combos bellow some count, we can speed up search a lot.
# It also separates 3-grams at the beginning and middle (few words start with ion-) and
# inxcludes a few useful 3-grams for games, like **1.
# A weakness is that it's hard to make a dictionary of useful words for wwise, current list
# was made from generic English words.

import itertools, re

#TODO reset to start grams when _ is found

filename = 'words.txt'
filename_out = 'words_%sgrams.txt'
position_start = '1st'
position_mid = '2nd'
position_end = '3rd'


ngrams = {}
words_done = {}

valid_fnv = 'abcdefghijklmnopqrstuvwxyz'
valid_number = '0123456789'
valid_word = re.compile('[a-z0-9_]') #


def get_ngrams(ngrams, word, num):
    grams = ngrams.get(num)
    if not grams:
        grams = {}
        ngrams[num] = grams
    
    for i in range(len(word) - num + 1):
        sub = word[i:i+num]

        if i == 0:
            position = position_start
        else:
            position = position_mid

        items = grams.get(position)
        if not items:
            items = {}
            grams[position] = items
        
        if sub not in items:
            items[sub] = 0
        items[sub] += 1


def read_ngrams():
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip().lower()
            if not line or line[0] == '#':
                continue

            for word in line.split(' '):
                if word.isdigit():
                    continue
                #if not word.isalpha():
                #    continue
                if not valid_word.match(word):
                    continue

                if word in words_done:
                    continue
                #get_ngrams(ngrams, word, 2)
                get_ngrams(ngrams, word, 3)
                words_done[word] = True


def clamp_ngrams():
    for n in ngrams:
        for position in ngrams[n]:
            min = None
            max = None
            for count in ngrams[n][position].values():
                if min == None:
                    min = count
                if max == None:
                    max= count
                if  min > count:
                    min = count
                if  max < count:
                    max = count
            print(min, max)

# includes extra derived ngrams
# - *_(start): equivalent to a new word
# - *_0: end of a word
# - __*, *__: don't add (nothing)
# - 000, *00, **0, *0*, 0**: partially add 

def extra_ngrams():
    if 3 not in ngrams:
        return
    st_3grams = ngrams[3][position_start]
    md_3grams = ngrams[3][position_mid]

    for letter in valid_fnv:
        for ngram, count in st_3grams.items():
            oks = [
                letter + '_' + ngram[0],    #*_*
                '_' + ngram[0] + ngram[1],  #_**
                ngram[1] + ngram[2] + '_',  #**_
            ]
            for ok in oks:
                if ok not in md_3grams or md_3grams[ok] < count:
                    md_3grams[ok] = count

        for num in '012':
            oks = [
                letter + '_' + num,     #*_0
            ]
            for num2 in '012':
                oks2 = [
                    letter + num + num2,
                    '_' + num + num2,
                ]
                oks.extend(oks2)
                for num3 in '01':
                    oks3 = [
                        num + num2 + num3,
                    ]
                    oks.extend(oks3)

            for ok in oks:
                if ok not in md_3grams or md_3grams[ok] < count:
                    md_3grams[ok] = 10000 #?
            
    for num in valid_number:
        for ngram, count in st_3grams.items():
            oks = [
                num + '_' + ngram[0],    #*_*
            ]
            for ok in oks:
                if ok not in md_3grams or md_3grams[ok] < count:
                    md_3grams[ok] = count

    pass


def dump_ngrams():
    for n in ngrams:
        outname = filename_out % (n)
        with open(outname, 'w', encoding='utf-8') as f:
            lines = []
            for position in ngrams[n]:
                top = None
                elems = ngrams[n][position]

                totals = list(elems.items())
                totals.sort(reverse=True, key=lambda x: x[1])

                pre = ''
                if position == position_start:
                    pre = '^'
                for ngram, count in totals:
                    if not top:
                        top = count

                    lines.append("%s%s: %s" % (pre, ngram, count))

            f.write('\n'.join(lines))
    
read_ngrams()
extra_ngrams()
#clamp_ngrams()
dump_ngrams()
