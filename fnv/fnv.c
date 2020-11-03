#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <ctype.h>

// FNV.EXE
// Reverses Wwise fnv hashes.
// 
// Some parts but have been coded for performance reasons, may be improved.
// We want to reduce ops+ifs, and calling separate functions with less ifs is a
// good way, though the copy-pasting could be improved with some inline'ing.
// fors are faster with fixed values, so it uses a list of allowed chars.


#define ENABLE_BANLIST  1

#define FNV_VERSION "1.0"

#define MAX_CHARS 64
#define MAX_TARGETS 256
#define MAX_BASE 1024 //in case of starting words
#define MAX_DEPTH 16
#define MAX_LETTERS 37
#define MAX_TABLE 123 //z= 123 = ASCII max

// constants
const char* dict = "abcdefghijklmnopqrstuvwxyz_0123456789";
const char* list_name = "fnv.lst";
const int default_depth = 7;

// config
const int list_start = 0;
const int list_inner = 1;
uint8_t list[2][MAX_TABLE][MAX_TABLE];
char name[MAX_DEPTH + 1] = {0};
char base_name[MAX_BASE + 1] = {0};

typedef struct {
    //config
    char start_letter;
    char end_letter;
    int begin_i;
    int end_i;

    char name_prefix[MAX_CHARS];
    char name_suffix[MAX_CHARS];
    
    int ignore_banlist;
    int print_text;
    int restrict_letters;

    //state
    const char* targets_s[MAX_TARGETS];
    uint32_t target;
    uint32_t targets[MAX_TARGETS];
    int targets_count;
    int reverse_names;

    int max_depth;
    int max_depth_1;

} fnv_config;

fnv_config cfg;


static void print_name(int depth, int show_suffix) {
    printf("* match: ");

    if (cfg.name_prefix)
        printf("%s", cfg.name_prefix);

    if (depth >= 0)
        printf("%.*s", depth + 1, name);

    if (show_suffix && cfg.name_suffix)
        printf("%s", cfg.name_suffix);

    printf("\n");
}


static inline void fnv_test_suffix(const uint32_t cur_hash, const int depth, const char elem) {
    uint32_t new_hash = cur_hash;
    for (int n = 0; n < strlen(cfg.name_suffix); n++) {
        new_hash = (new_hash * 16777619) ^ cfg.name_suffix[n];
    }
    if (new_hash == cfg.target) {
        name[depth] = elem;
        print_name(depth, 1);
    }
}

// depth of N for suffixes
static void fvn_depth_suffix(const uint32_t cur_hash, const int depth, int pos) {
    char prev = name[depth-1];


    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
#if ENABLE_BANLIST
        if (!list[pos][prev][elem])
            continue;
#endif

        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        fnv_test_suffix(new_hash, depth, elem);

        if (depth < cfg.max_depth) {
            name[depth] = elem;
            fvn_depth_suffix(new_hash, depth + 1, list_inner);
        }
    }
}



// depth of exactly N letters
static void fvn_depth_max(const uint32_t cur_hash, const int depth) {

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
        //if (!list[1][prev][elem])
        //    continue;

        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth, 0);
        }
    }
}

// depth of N letters up to last
static void fvn_depth2(const uint32_t cur_hash, const int depth) {
    int pos = list_inner;
    char prev = name[depth-1];
    

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
#if ENABLE_BANLIST
        if (!list[pos][prev][elem])
            continue;
#endif

        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth, 0);
        } 

        if (depth < cfg.max_depth_1) {
            name[depth] = elem;
            fvn_depth2(new_hash, depth + 1);
        }
        else {
            name[depth] = elem;
            fvn_depth_max(new_hash, depth + 1);
        }
    }
}


// depth of 2 letters
static void fvn_depth1(uint32_t cur_hash, int depth) {
    int pos = list_start;
    char prev = name[depth-1];

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
#if ENABLE_BANLIST
        if (!list[pos][prev][elem])
            continue;
#endif

        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        if (cfg.name_suffix) {
            fnv_test_suffix(new_hash, depth, elem);
        }
        else if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth, 0);
        }

        if (depth < cfg.max_depth) {
            name[depth] = elem;
            fvn_depth2(new_hash, depth + 1);
        }
    }
}


// depth of 1 letter (base)
static void fvn_depth0(uint32_t cur_hash) {
    int depth = 0;

    //for (int i = 0; i < MAX_LETTERS; i++) {
    for (int i = cfg.begin_i; i < cfg.end_i; i++) { //slower but ok at this level
        char elem = dict[i];
        if (cfg.print_text)
            printf("- letter: %c\n", elem);

        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        if (cfg.name_suffix) {
            fnv_test_suffix(new_hash, depth, elem);
        }
        else if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth, 0);
        }

        if (depth < cfg.max_depth) {
            name[depth] = elem;

            if (cfg.name_suffix)
                fvn_depth_suffix(new_hash, depth + 1, list_start);
            else
                fvn_depth1(new_hash, depth + 1);
        }
    }
}


//*************************************************************************

static int get_dict_pos(char comp) {
    // must translate values as banlist works with ASCII
    int pos = -1;
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == comp) {
            pos = i;
        }
    }

    return pos;
}

static void read_banlist_restrict() {
    // overwrite values in banlist
    if (!cfg.restrict_letters)
        return;
    
    if (cfg.start_letter != '\0') {
        for (int i = 0; i < MAX_TABLE; i++) {
            int pos = get_dict_pos(i);
            if (pos >= 0 && pos < cfg.begin_i) {
                for (int j = 0; j < MAX_TABLE; j++) {
                    list[0][i][j] = 0;
                    list[1][i][j] = 0;
                }
            }
        }
    }

    if (cfg.end_letter != '\0') {
        for (int i = 0; i < (uint8_t)cfg.start_letter; i++) {
            int pos = get_dict_pos(i);
            if (pos >= 0 &&pos > cfg.end_i) {
                for (int j = 0; j < MAX_TABLE; j++) {
                    list[0][i][j] = 0;
                    list[1][i][j] = 0;
                }
            }
        }
    }

}

static void read_begin_end() {
    int begin = 0;
    int end = MAX_LETTERS;
    
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == cfg.start_letter) {
            begin = i;
        }
        if (dict[i] == cfg.end_letter) {
            end = i + 1;
        }
    }

    cfg.begin_i = begin;
    cfg.end_i = end;
}


static int in_dict(char chr) {
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == chr)
            return 1;
    }

    return 0;
}

static int read_banlist() {
    // 2 ASCII chars = 0x7F | 0x7F, where [char][char] = 0/1, [0] = begin, [1] = middle
    for (int i = 0; i < MAX_TABLE; i++) {
        for (int j = 0; j < MAX_TABLE; j++) {
            list[0][i][j] = 1;
            list[1][i][j] = 1;
        }
    }

    //for (int i = 0; i < MAX_LETTERS; i++) {
    //    letters[i] = dict[i];
    //}

    if (cfg.ignore_banlist)
        return 1;

    FILE* file = fopen(list_name, "r");
    if (!file) {
        printf("ignore list not found (%s)\n", list_name);
        return 1;
    }


    char line[0x2000];
    while (fgets(line, sizeof(line), file)) {
        if (line[0] == '#')
            continue;

        int posA = 0;
        int posB = 1;
        int index = 1;
        if (line[0] == '^') {
            posA++;
            posB++;
            index = 0;
        }

        if ( !in_dict(line[posA]) )
            continue;

        if (line[posB] == '[') {
            posB++;
            while( in_dict(line[posB]) ) {
                list[index][ (uint8_t)line[posA] ][ (uint8_t)line[posB] ] = 0;
                //printf("- %c%c / %i %i\n", line[posA], line[posB], line[posA], line[posB]);
                posB++;
            }
        }
        else if ( in_dict(line[posB]) ) {
            list[index][ (uint8_t)line[posA] ][ (uint8_t)line[posB] ] = 0;
            //printf("- %c%c / %i %i\n", line[posA], line[posB], line[posA], line[posB]);
        }
    }

    printf("loaded ignore list\n");

    fclose(file);
    return 1;
}

//*************************************************************************

static void print_usage(const char* name) {
    fprintf(stderr,"Wwise FNV name reversing tool " FNV_VERSION " " __DATE__ "\n\n"
            "Finds original name for Wwise event/variable IDs (FNV hashes)\n"
            "Usage: %s [options] (target id)\n"
            "Options:\n"
            "    -p NAME_PREFIX: start text of original name\n"
            "       Use when possible to reduce search space (ex. 'play_')\n"
            "    -s NAME_SUFFIX: end text of original name\n"
            "       Use when possible to reduce search space (ex. '_bgm')\n"
            "    -l START_LETTER: start letter (use to resume searches)\n"
            "    -L END_LETTER: end letter\n"
            "       Dictionary letters: %s\n"
            "    -r: restrict START/END letters on all levels (default to base level only)\n"
            "    -m N: max characters in name (default %i)\n"
            "       Beyond 8 search is too slow and gives too many false positives\n"
            "    -i: ignore ban list (%s)\n"
            "       List greatly improves speed and results but may skip valid names\n"
            "       (try disabling if no proper names are found for smaller variables)\n"
            "    -t: print letter text info (when using high max characters)\n"
            "    -n: treat input as names and prints FNV IDs\n"
            "    -h: show this help\n"
            ,
            name,
            dict,
            default_depth,
            list_name);
}


#define CHECK_EXIT(condition, ...) \
    do {if (condition) { \
       fprintf(stderr, __VA_ARGS__); \
       return 0; \
    } } while (0)

static int parse_cfg(fnv_config* cfg, int argc, const char* argv[]) {
    cfg->max_depth = default_depth;
    
    for (int i = 1; i < argc; i++) {

        if (argv[i][0] != '-') {
            cfg->targets_s[cfg->targets_count] = argv[i];
            cfg->targets_count++;

            CHECK_EXIT(cfg->targets_count >= MAX_TARGETS, "ERROR: too many targets");
            continue;
        }

        switch(argv[i][1]) {
            case 'p':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing name prefix");
                strncpy(cfg->name_prefix, argv[i], MAX_CHARS);
                break;
            case 's':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing name suffix");
                strncpy(cfg->name_suffix, argv[i], MAX_CHARS);
                break;
            case 'l':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing start letter");
                CHECK_EXIT(strlen(argv[i]) > 1, "ERROR: start letter must be 1 character");
                cfg->start_letter = argv[i][0];
                break;
            case 'L':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing end letter");
                CHECK_EXIT(strlen(argv[i]) > 1, "ERROR: end letter must be 1 character");
                cfg->end_letter = argv[i][0];
                break;
            case 'i':
                cfg->ignore_banlist = 1;
                break;
            case 't':
                cfg->print_text = 1;
                break;
            case 'm':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing max characters");
                cfg->max_depth = strtoul(argv[i], NULL, 10);
                break;
            case 'n':
                cfg->reverse_names = 1;
                break;
            case 'r':
                cfg->restrict_letters = 1;
                break;
            case 'h':
                print_usage(argv[0]);
                return 0;
            default:
                CHECK_EXIT(1, "ERROR: unknown parameter '%s'\n", argv[i]);
                break;
        }
    }


    CHECK_EXIT(cfg->max_depth < 0, "ERROR: too few letters\n");
    CHECK_EXIT(cfg->max_depth >= MAX_DEPTH, "ERROR: too many letters\n");
    CHECK_EXIT(cfg->max_depth >= MAX_DEPTH, "too many letters\n");
    CHECK_EXIT(cfg->targets_count <= 0, "ERROR: target ids not specified\n");

    if (!cfg->reverse_names) {
        for (int i = 0; i < cfg->targets_count; i++) {
            const char* name = cfg->targets_s[i];

            uint32_t target = strtoul(name, NULL, 10);
            cfg->targets[i] = target;

            CHECK_EXIT(target == 0, "ERROR: incorrect value for target");
        }
    }

    if (cfg->name_prefix) {
        for (int i = 0; i < strlen(cfg->name_prefix); i++) {
            cfg->name_prefix[i] = tolower(cfg->name_prefix[i]);
        }
    }

    if (cfg->name_suffix) {
        for (int i = 0; i < strlen(cfg->name_suffix); i++) {
            cfg->name_suffix[i] = tolower(cfg->name_suffix[i]);
        }
    }
    
    read_begin_end();
    
    return 1;
}    

static void print_time(const char* info) {
    time_t timer;
    struct tm* tm_info;

    timer = time(NULL);
    tm_info = localtime(&timer);
    printf("%s: %s", info, asctime(tm_info));
}

static void reverse_names(fnv_config* cfg) {
    for (int t = 0; t < cfg->targets_count; t++) {
        const char* name = cfg->targets_s[t];

        uint32_t hash = 2166136261;
        for (int i = 0; i < strlen(name); i++) {
            char c = tolower(name[i]);
            hash = (hash * 16777619) ^ (uint8_t)c;
        }

        printf("%s: %u / 0x%x\n", name, hash, hash);
        //printf("%u: \"%s\",\n", hash, name);
    }
}

int main(int argc, const char* argv[]) {
    if (argc <= 1) {
        print_usage(argv[0]);
        return 1;
    }

    if (!parse_cfg(&cfg, argc, argv)) {
        return 1;
    }

    if (cfg.reverse_names) {
        reverse_names(&cfg);
        return 0;
    }

    if (!read_banlist()) {
        return 1;
    }
    read_banlist_restrict();
    


    cfg.max_depth--;
    cfg.max_depth_1 = cfg.max_depth - 1;

    printf("starting, max %i letters\n", cfg.max_depth + 1);
    printf("\n");

    uint32_t base_hash = 2166136261;
    if (cfg.name_prefix) {
        for (int i = 0; i < strlen(cfg.name_prefix); i++) {
            base_hash = (base_hash * 16777619) ^ cfg.name_prefix[i];
        }

        if (base_hash == cfg.target) {
            print_name(-1, 0);
        }
    }

    for (int t = 0; t < cfg.targets_count; t++) {
        cfg.target = cfg.targets[t];

        printf("finding %u\n", cfg.target);
        print_time("start");

        fvn_depth0(base_hash);

        print_time("end");
        printf("\n");
    }


    return 0;
}
