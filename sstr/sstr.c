#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <ctype.h>

// SSTR.EXE
// Extracts sized strings (ASCII only)
//
// A specialized version of strings2.exe
// Some games have strings like (size)(id)(string), or (size)(string).
// strings2.exe trips on those and may create things like "b(string)A",
// while this program should handle them fine (may still output some false positives though)
// Mainly for names found in stuff like the Decima engine.

// todo config bufsize
// todo BE mode
// todo configure allowed dictionary

#define SSTR_VERSION "1.0"
#define MIN_STR 3
#define MAX_STR 255
#define BUF_HEAD (0x04 + 0x04 + MAX_STR)  //(size)(id)(string)
#define BUF_TAIL (0x04 + 0x04 + MAX_STR)  //(size)(id)(string)
#define MAX_TARGETS 512
#define DEFAULT_BUFSIZE  0x20000000 // ~512MB



typedef struct {
    uint32_t buf_size;
    const char* targets[MAX_TARGETS];
    uint32_t targets_count;
    bool limited;
} sstr_config;

//*************************************************************************

static uint32_t get_u32le(const uint8_t *p) {
    uint32_t ret;
    ret  = ((uint32_t)(const uint8_t)p[0]) << 0;
    ret |= ((uint32_t)(const uint8_t)p[1]) << 8;
    ret |= ((uint32_t)(const uint8_t)p[2]) << 16;
    ret |= ((uint32_t)(const uint8_t)p[3]) << 24;
    return ret;
}

static int is_ascii_str(const uint8_t* buf, int str_len, bool limited) {
    if (limited) {
        // decima hashes only
        for (int i = 0; i < str_len - 1; i++) {
            uint8_t curr = buf[i];
            if (curr < 0x2d && curr != 0x20 || curr > 0x7a || curr >= 0x3b && curr <= 0x40 || curr >= 0x5b && curr <= 0x5e)
                return 0;
        }
    }
    else {
        // useful only ASCII
        for (int i = 0; i < str_len - 1; i++) {
            uint8_t curr = buf[i];
            if (curr < 0x20 || curr >= 0x7F)
                return 0;
        }
    }

    // last char can be a null
    uint8_t last = buf[str_len-1];
    if (last != 0 && last < 0x20 || last >= 0x7F)
        return 0;

    return 1;
}

static int test_str(const uint8_t* buf, int str_len, bool limited) {
    if (is_ascii_str(buf, str_len, limited)) {
        printf("%.*s\n", str_len, buf);
        return 1;
    }
    return 0;
}

static void find_string(const uint8_t* buf, uint32_t buf_size, bool limited) {
    uint32_t pos = 0;

    // test (len)(str) and (len)(id)(str)
    while (pos < buf_size) {
        uint32_t str_len = get_u32le(buf + pos + 0x00);
        if (str_len > MIN_STR && str_len < MAX_STR) {
            // both are possible at the same time in some cases
            int test1 = test_str(buf + pos + 0x04, str_len, limited);
            int test2 = test_str(buf + pos + 0x08, str_len, limited);

            if (test2) {
                pos += 0x08 + str_len;
            }
            else if (test1) {
                pos += 0x04 + str_len;
            }
            else {
                pos++;
            }
        }
        else {
            pos++;
        }
    }
}


//*************************************************************************

static void print_usage(const char* name) {
    fprintf(stderr,"SSTR " SSTR_VERSION " (" __DATE__ ")\n\n"
            "Finds sized strings within files\n"
            "Usage: %s [options] (files)\n"
            "Options:\n"
            "    -h: show this help\n"
            ,
            name);
}


#define CHECK_EXIT(condition, ...) \
    do {if (condition) { \
       fprintf(stderr, __VA_ARGS__); \
       return 0; \
    } } while (0)

static int parse_cfg(sstr_config* cfg, int argc, const char* argv[]) {
    cfg->buf_size = DEFAULT_BUFSIZE;
    
    for (int i = 1; i < argc; i++) {

        if (argv[i][0] != '-') {
            cfg->targets[cfg->targets_count] = argv[i];
            cfg->targets_count++;

            CHECK_EXIT(cfg->targets_count >= MAX_TARGETS, "ERROR: too many files");
            continue;
        }

        switch(argv[i][1]) {
            case 'h':
                print_usage(argv[0]);
                return 0;
            case 'l':
                cfg->limited = true;
                break;
            default:
                CHECK_EXIT(1, "ERROR: unknown parameter '%s'\n", argv[i]);
                break;
        }
    }

    CHECK_EXIT(cfg->targets_count <= 0, "ERROR: target file not specified\n");

    return 1;
}

#if 0
static void print_time(const char* info) {
    time_t timer;
    struct tm* tm_info;

    timer = time(NULL);
    tm_info = localtime(&timer);
    printf("%s: %s", info, asctime(tm_info));
}
#endif

int main(int argc, const char* argv[]) {
    sstr_config cfg = {0};
    
    if (argc <= 1) {
        print_usage(argv[0]);
        return 1;
    }

    if (!parse_cfg(&cfg, argc, argv)) {
        return 1;
    }

    //print_time("start");
    for (int i = 0; i < cfg.targets_count; i++) {
        const char* filename = cfg.targets[i];
        
        FILE* file = fopen(filename, "rb");
        if (!file) {
            printf("file found (%s)\n", filename);
            continue;
        }
        printf("reading %s...\n", filename);

        fseek(file, 0, SEEK_END);
        uint32_t src_size = ftell(file);
        fseek(file, 0, SEEK_SET);

        // alloc for: chunk string + main + extra for tail string reads
        uint8_t* buf = malloc(BUF_HEAD + cfg.buf_size + BUF_TAIL);
        if (!buf) {
            printf("can't allocate buffer\n");
            fclose(file);
            continue;
        }
        memset(buf, 0, BUF_HEAD);
        memset(buf + BUF_HEAD + cfg.buf_size, 0, BUF_TAIL);

        // read file in chunks (so doesn't need too much memory)
        // must read from (buf + string max) as an string could be cut between chunks and must reserve that space for cut parts
        // - loop 1: (reserved null N bytes)(actual data).....(last N bytes that could be an string cut in half)
        // - loop 2: (copied last N bytes)(rest of the string).....(actual data)
        // ...
        while (1) {
            size_t bytes = fread(buf + BUF_HEAD, 1, cfg.buf_size, file);
            if (!bytes)
                break;

            find_string(buf, BUF_HEAD + bytes, cfg.limited);

            // copy last bytes as next head (shouldn't overlap)
            memcpy(buf, buf + BUF_HEAD + bytes - BUF_HEAD, BUF_HEAD);
        }

        fclose(file);
        free(buf);
    }
    //print_time("end");

    return 0;
}
