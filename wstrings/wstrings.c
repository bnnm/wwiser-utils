/* WSTRINGS
 *
 * Finds valid strings within files recursively, mainly to reverse Wwise names (or "parts" for words.py).
 *
 * Similar to strings2 (https://github.com/glmcdona/strings2) with these diffs:
 * - skips dupes (case insensitive by default for wwise)
 *   - may not skip all dupes depending on set memory limit, but that's fine for this use case
 * - ignores some short strings that aren't useful for Wwise
 * - reads files in paths recursively and dumps everything automatically to ww_<dirname>.txt
 * - string detection is simpler since it's mainly geared towards Wwise needs
 *   (ex. it may not extract UTF8 correctly, but those can't be used for Wwise anyway)
 *
 * Compile as 64-bit to open large files:
 *     gcc -m64 -Wall -O3 wstrings.c
 */
//TODO: remove more useless strings such as trailing spaces contrinubting to length
//TODO: use int64s instead of size_t?
//TODO: skip useless stuff like .png or fourccs with a flag? (can't test renamed files or bigfile with N types though)
//TODO: allow only %s if entry is .exe?

//-------------------------------------------------------------------------------------------------

// needed for large file support?
#define _FILE_OFFSET_BITS 64
#define _LARGEFILE64_SOURCE

#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <inttypes.h>

// mmap, files
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <unistd.h>
#endif

//-------------------------------------------------------------------------------------------------
// CONFIG 

#define CFG_MAX_PATH 4096

#define STR_MAX 1024

#define CFG_INITIAL_SET_SIZE (1u << 24) // N entries * 8 bytes = ~ 128MB
#define CFG_MAX_SET_SIZE_MB 512
#define CFG_MIN_LEN 4
#define CFG_MAX_LEN 256
#define CFG_SKIP_THRESHOLD 6 //check valid wwise chars up to this length

typedef struct {
    int min_len;
    int max_len;
    int skip_threshold;
    bool verbose;
    bool case_sensitive;
    size_t max_table_mb;

    const char* exe_name;
    const char* out_name;
    const char* base_dir;
    FILE* out;
} config_t;


//-------------------------------------------------------------------------------------------------
// HASH SET
// Simple probing/linear set for hashed strings (64-bit).
// Maybe should use a bucket hash or something external/more robust but seems fast enough.

#define U64SET_EVICT_FRACTION 0.30  // tombstone entries to evict when table is full.
#define U64SET_MAX_LOAD_FACTOR 0.70 // resize when this load factor is exceeded (not too high or low for optimal use)
#define U64SET_MARKER_EMPTY 0
#define U64SET_MARKER_TOMBSTONE 1
#define U64SET_MARKER_HASH 2

typedef struct {
    uint64_t* slots;     // 0 = empty, 1 = tombstone, >=2 = valid hash
    size_t size;         // should be power of two
    size_t mask;         // size - 1
    size_t count;        // number of valid hashes (>=2)
    size_t max_bytes;    // max slots
    size_t evict_cursor; // rotating cursor for eviction
} u64set_t;

static bool u64set_initialize(u64set_t* set, size_t initial_size, size_t max_bytes) {

    // Adjust initial size down if bigger than configured max (must be power of two)
    while (initial_size > 1024 && initial_size * sizeof(uint64_t) > max_bytes) {
        initial_size >>= 1;
    }

    size_t bytes = initial_size * sizeof(uint64_t);
    if (bytes > max_bytes)
        return false;

    set->slots = calloc(initial_size, sizeof(uint64_t));
    if (!set->slots)
        return false;

    set->size = initial_size;
    set->mask = initial_size - 1;
    set->count = 0;
    set->max_bytes = max_bytes;
    set->evict_cursor = 0;

    return true;
}

static bool u64set_resize(u64set_t* set) {
    size_t new_size = set->size * 2; //should be power of two
    size_t new_bytes = new_size * sizeof(uint64_t);

    if (new_bytes > set->max_bytes)
        return false;

    // can't use realloc due to mask-index
    uint64_t* new_slots = calloc(new_size, sizeof(uint64_t));
    if (!new_slots)
        return false;

    // re-position new entries
    size_t new_mask = new_size - 1;
    for (size_t i = 0; i < set->size; i++) {
        uint64_t hash = set->slots[i];
        if (hash == U64SET_MARKER_EMPTY || hash == U64SET_MARKER_TOMBSTONE)
            continue;

        size_t idx = hash & new_mask;
        while (new_slots[idx] != 0)
            idx = (idx + 1) & new_mask;

        new_slots[idx] = hash;
    }

    free(set->slots);
    set->slots = new_slots;
    set->size = new_size;
    set->mask = new_mask;
    set->evict_cursor = 0;

    return true;
}

// Evict a % of entries by turning some valid slots into tombstones.
// This means some dupes are possible if max set size is small enough, but it's fine for words.py
static void u64set_evict(u64set_t* set, double percent) {
    if (percent <= 0.0)
        return;

    if (percent > 1.0)
        percent = 1.0;

    size_t target = (size_t)((double)set->size * percent);
    if (target == 0)
        return;

    size_t evicted = 0;
    size_t idx = set->evict_cursor & set->mask;

    for (size_t scanned = 0; scanned < set->size && evicted < target; scanned++) {
        uint64_t slot = set->slots[idx];
        if (slot >= 2) {
            set->slots[idx] = U64SET_MARKER_TOMBSTONE;
            if (set->count > 0)
                set->count--;
            evicted++;
        }
        idx = (idx + 1) & set->mask;
    }

    set->evict_cursor = idx;
}

#if 0
static bool u64set_exists(u64set_t* set, uint64_t hash) {
    size_t idx = hash & set->mask;

    while (true) {
        uint64_t slot = set->slots[idx];
        if (slot == U64SET_MARKER_EMPTY)
            return false;

        if (slot == hash)
            return true;

        // should never be full
        idx = (idx + 1) & set->mask;
    }
}
#endif

static bool u64set_insert(u64set_t* set, uint64_t hash, bool verbose) {
    // handle special markers
    if (hash == U64SET_MARKER_EMPTY || hash == U64SET_MARKER_TOMBSTONE)
        hash = U64SET_MARKER_HASH;

    // resize if possible or evict entries if needed (this means some dupes are possible, but it's fine)
    double load = (double)set->count / (double)set->size;
    if (load > U64SET_MAX_LOAD_FACTOR) {
        if (verbose)
            printf("resizing set\n");


        if (!u64set_resize(set)) {
            if (verbose)
                printf("evicting set\n");

            u64set_evict(set, U64SET_EVICT_FRACTION);
        }
    }

    // find first available slot within rarge from base index
    size_t idx = hash & set->mask;
    int64_t first_tombstone_idx = -1;
    while (true) {
        uint64_t slot = set->slots[idx];

        if (slot == U64SET_MARKER_EMPTY) {
            // insert here (or in first tombstone) as a new entry.
            size_t insert_idx = (first_tombstone_idx >= 0) ? (size_t)first_tombstone_idx : idx;
            set->slots[insert_idx] = hash;
            set->count++;
            return true;
        }

        if (slot == hash) {
            return false; // already present
        }

        if (slot == U64SET_MARKER_TOMBSTONE && first_tombstone_idx < 0) {
            first_tombstone_idx = (int64_t)idx;
        }

        // should never be full (resized/evicted above)
        idx = (idx + 1) & set->mask;
    }
}

static void u64set_free(u64set_t* set) {
    free(set->slots);
    set->slots = NULL;
    set->size = 0;
    set->mask = 0;
    set->count = 0;
    set->max_bytes = 0;
    set->evict_cursor = 0;
}


//-----------------------------------------------------------------------------
// HASHING

static bool is_skippable_string(const uint8_t* bytes, size_t len, const config_t* cfg) {
    if (len < cfg->min_len || len > cfg->max_len)
        return true;

    // check wwise-only chars in short strings
    if (len <= cfg->skip_threshold) {
        for (size_t i = 0; i < len; i++) {
            unsigned char c = bytes[i];
            bool ok =
                (c >= 'A' && c <= 'Z') ||
                (c >= 'a' && c <= 'z') ||
                (c >= '0' && c <= '9') ||
                (c == '_') ||
                (c == '%'); //some exes have %s_blah, so allow % too
            if (!ok)
                return true;
        }
    }

    return false;
}


// FNV-1a 64-bit, fast and shouldn't have too many collisions (hopefully)
static uint64_t hash64(const uint8_t* buf, size_t len, bool case_sensitive) {
    uint64_t hash = 1469598103934665603ULL; // FNV offset basis

    for (size_t i = 0; i < len; i++) {
        uint8_t chr = buf[i];
        if (!case_sensitive && chr >= 'A' && chr <= 'Z')
            chr += 32; // lowercase since wwise is case-insensitive
        hash ^= chr;
        hash *= 1099511628211ULL; // FNV prime
    }
    return hash;
}

static void add_string(const uint8_t* buf, size_t len, const config_t* cfg, u64set_t* set) {
    if (is_skippable_string(buf, len, cfg))
        return;

    uint64_t hash = hash64(buf, len, cfg->case_sensitive);

    bool inserted = u64set_insert(set, hash, cfg->verbose);
    if (!inserted) // already present
        return;

    fprintf(cfg->out, "%.*s\n", (int)len, buf); //write bytes up to expected length
}

//-------------------------------------------------------------------------------------------------
// STRING PROCESSING

static bool is_printable_ascii(uint8_t c) {
    // ignores line feeds too
    return (c >= 32 && c <= 126);
}

#define POS_INVALID ((size_t)-1) //TO-DO: a bit odd since size_t is unsigned

// extracts ascii-like strings from 0 to filesize
static void extract_ascii(const uint8_t* buf, size_t size, const config_t* cfg, u64set_t* set) {
    size_t pos_start = POS_INVALID;

    for (size_t i = 0; i < size; i++) {
        uint8_t chr = buf[i];

        if (is_printable_ascii(chr)) {
            // new string candidate, or continue existing string
            if (pos_start == POS_INVALID)
                pos_start = i;
            continue;
        }

        // no string yet
        if (pos_start == POS_INVALID)
            continue;

        // end of string candidate
        size_t len = i - pos_start;
        add_string(buf + pos_start, len, cfg, set);

        pos_start = POS_INVALID;
    }

    // trailing string
    if (pos_start != POS_INVALID) {
        size_t len = size - pos_start;
        add_string(buf + pos_start, len, cfg, set);
    }
}

static void utf16le_to_ascii(uint8_t* dst, const uint8_t* src, size_t pos_start, size_t src_len) {
    for (size_t i = 0; i < src_len; i++) {
        dst[i] = src[pos_start + i * 2];
    }
}

// Extracts ascii-like strings from 0 to filesize, in UTF-16LE encoding.
// Same as above, but uses a temp buf to convert to single-byte ascii.
static void extract_utf16le(const uint8_t* buf, size_t size, const config_t* cfg, u64set_t* set) {
    size_t pos_start = POS_INVALID;
    uint8_t tmp[STR_MAX];


    size_t i = 0;
    while (i + 1 < size) {
        uint8_t chr_lo = buf[i + 0];
        uint8_t chr_hi = buf[i + 1];

        if (chr_hi == 0 && is_printable_ascii(chr_lo)) {
            // new string candidate, or continue existing string
            if (pos_start == POS_INVALID)
                pos_start = i;
            i += 2;
            continue;
        }

        // no string yet
        if (pos_start == POS_INVALID) {
            i++;
            continue;
        }

        // end of string candidate
        size_t len = (i - pos_start) / 2;

        if (len >= (size_t)cfg->min_len) {
            if (len >= STR_MAX)
                len = STR_MAX - 1;
            utf16le_to_ascii(tmp, buf, pos_start, len);

            add_string(tmp, len, cfg, set);
        }

        pos_start = POS_INVALID;
        i++;
    }

    // trailing string
    if (pos_start != POS_INVALID) {
        size_t len = (size - pos_start) / 2;

        if (len >= (size_t)cfg->min_len){
            if (len >= STR_MAX)
                len = STR_MAX - 1;
            utf16le_to_ascii(tmp, buf, pos_start, len);

            add_string(tmp, len, cfg, set);
        }
    }
}

//-------------------------------------------------------------------------------------------------
// HELPERS

#ifdef _WIN32
//TODO: use in various places
static wchar_t* utf8_to_wide(const char* src, wchar_t* dst, size_t dst_size) {
    if (!src || !dst || dst_size == 0)
        return NULL;

    int needed = MultiByteToWideChar(CP_UTF8, 0, src, -1, NULL, 0);
    if (needed <= 0 || needed > dst_size)
        return NULL;

    if (MultiByteToWideChar(CP_UTF8, 0, src, -1, dst, dst_size) <= 0)
        return NULL;

    return dst;
}

static char *wide_to_utf8(const wchar_t* src, char* dst, size_t dst_size) {
    if (!src || !dst || dst_size == 0)
        return NULL;

    int needed = WideCharToMultiByte(CP_UTF8, 0, src, -1, NULL, 0, NULL, NULL);
    if (needed <= 0 || (size_t)needed > dst_size)
        return NULL;

    if (WideCharToMultiByte(CP_UTF8, 0, src, -1, dst, dst_size, NULL, NULL) <= 0)
        return NULL;

    return dst;
}
#endif


static const char* extract_name(const char* path) {
    const char* name = strrchr(path, '/');
#ifdef _WIN32
    const char* name_w = strrchr(path, '\\');
    if (name_w && (!name || name_w > name))
        name = name_w;
#endif
    return name ? name + 1 : path;
}

static void get_real_directory(const char* src, char *dst, int dst_len) {
#ifdef _WIN32
    wchar_t wbuf[CFG_MAX_PATH];
    wchar_t wfull[CFG_MAX_PATH];

    if (!utf8_to_wide(src, wbuf, CFG_MAX_PATH)) {
        snprintf(dst, dst_len, "%s", src);
        return;
    }

    DWORD n = GetFullPathNameW(wbuf, CFG_MAX_PATH, wfull, NULL);
    if (n == 0 || n >= CFG_MAX_PATH) {
        snprintf(dst, dst_len, "%s", src);
        return;
    }

    if (!wide_to_utf8(wfull, dst, dst_len)) {
        snprintf(dst, dst_len, "%s", src);
    }
#else
    char tmp[CFG_MAX_PATH];
    if (realpath(src, tmp) == NULL) {
        snprintf(dst, dst_len, "%s", src);
        return;
    }
    snprintf(dst, dst_len, "%s", tmp);
#endif
}

static inline int32_t get_s32be(const uint8_t* p) {
    return ((uint32_t)p[0]<<24) | ((uint32_t)p[1]<<16) | ((uint32_t)p[2]<<8) | ((uint32_t)p[3]);
}
static inline uint32_t get_u32be(const uint8_t* p) { return (uint32_t)get_s32be(p); }

static inline /*const*/ uint32_t get_id32be(const char* s) {
    return (uint32_t)((uint8_t)s[0] << 24) | ((uint8_t)s[1] << 16) | ((uint8_t)s[2] << 8) | ((uint8_t)s[3] << 0);
}

static bool is_skippable_filename(const char* path, const config_t* cfg) {
    // ignore program name itself
    const char* base = extract_name(path);
    if (strcmp(base, cfg->exe_name) == 0)
        return true;
    if (strcmp(base, cfg->out_name) == 0)
        return true;

    return false;
}

static bool is_skippable_header(const uint8_t* buf, size_t size) {
    if (size <= 4)
        return true;
    
    uint32_t header_id = get_u32be(buf);
    if (header_id == get_id32be("BKHD"))
        return true;
    if (header_id == get_id32be("RIFF"))
        return true;
    if (header_id == get_id32be("AKPK"))
        return true;

    return false;
}

//-------------------------------------------------------------------------------------------------
// FILE PROCESSING
// Uses mmap mainly to avoid handling edge buf strings.

//TODO: test more: from tests it didn't seem very different
#define CFG_SMALL_FILE_THRESHOLD (8 * 1024) // files smaller than this are read fully instead of mmap'ing (potentially slower)
uint8_t mmap_buf[CFG_SMALL_FILE_THRESHOLD]; //not thread-safe but we only process 1 file at a time

typedef struct {
    uint8_t* data;
    size_t size;
#ifdef _WIN32
    HANDLE hFile;
    HANDLE hMap;    
#else
    int fd;
#endif
    bool is_mapped;
} mmap_t;

static bool mmap_open(mmap_t* mmap_ctx, const char* path) {
#ifdef _WIN32
    wchar_t wpath[MAX_PATH];
    MultiByteToWideChar(CP_UTF8, 0, path, -1, wpath, MAX_PATH);

    mmap_ctx->hFile = CreateFileW(wpath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (mmap_ctx->hFile == INVALID_HANDLE_VALUE)
        return false;

    LARGE_INTEGER size = {0};
    if (!GetFileSizeEx(mmap_ctx->hFile, &size) || size.QuadPart == 0)
        return false;
    mmap_ctx->size = size.QuadPart;

    if (mmap_ctx->size <= CFG_SMALL_FILE_THRESHOLD) {
        mmap_ctx->data = mmap_buf;

        DWORD read = 0;
        if (!ReadFile(mmap_ctx->hFile, mmap_ctx->data, (DWORD)mmap_ctx->size, &read, NULL) || read != mmap_ctx->size)
            return false;
    }
    else {
        mmap_ctx->hMap = CreateFileMappingW(mmap_ctx->hFile, NULL, PAGE_READONLY, 0, 0, NULL);
        if (!mmap_ctx->hMap)
            return false;

        mmap_ctx->data = (uint8_t*)MapViewOfFile(mmap_ctx->hMap, FILE_MAP_READ, 0, 0, 0);
        if (!mmap_ctx->data)
            return false;

        mmap_ctx->is_mapped = true;
    }

    return true;
#else
    mmap_ctx->fd = open(path, O_RDONLY);
    if (mmap_ctx->fd < 0)
        return false;

    struct stat st;
    if (fstat(mmap_ctx->fd, &st) < 0 || st.st_size == 0)
        return false;
    mmap_ctx->size = st.st_size;

    if (mmap_ctx->size <= CFG_SMALL_FILE_THRESHOLD) {
        mmap_ctx->data = mmap_buf;

        ssize_t bytes = read(mmap_ctx->fd, mmap_ctx->data, mmap_ctx->size);
        if (bytes != mmap_ctx->size)
            return false;
    }
    else {
        mmap_ctx->data = (uint8_t*)mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE, mmap_ctx->fd, 0);
        if (mmap_ctx->data == MAP_FAILED) {
            mmap_ctx->data = NULL;
            return false;
        }

        mmap_ctx->is_mapped = true;
    }

    return true;
#endif
}

static void mmap_close(mmap_t* mmap_ctx) {
#ifdef _WIN32
    if (mmap_ctx->data && mmap_ctx->is_mapped)
        UnmapViewOfFile(mmap_ctx->data);

    if(mmap_ctx->hMap)
        CloseHandle(mmap_ctx->hMap);
    
    if (mmap_ctx->hFile)
        CloseHandle(mmap_ctx->hFile);
#else
    if (mmap_ctx->data && mmap_ctx->is_mapped)
        munmap(mmap_ctx->data, mmap_ctx->size);

    if (mmap_ctx->fd >= 0)
        close(mmap_ctx->fd);
#endif
}

static void process_file(const char* path, const config_t* cfg, u64set_t* set) {
    if (is_skippable_filename(path, cfg))
        return;

    if (cfg->verbose)
        printf("processing: %s\n", path);
    fprintf(cfg->out, "\n%s\n", path); //write bytes up to expected length

    mmap_t mmap_ctx = {0};
    bool ok = mmap_open(&mmap_ctx, path) ;
    if (ok) {
        if (!is_skippable_header(mmap_ctx.data, mmap_ctx.size)) {
            extract_ascii(mmap_ctx.data, mmap_ctx.size, cfg, set);
            extract_utf16le(mmap_ctx.data, mmap_ctx.size, cfg, set);
        }
    }

    mmap_close(&mmap_ctx);
}


//-------------------------------------------------------------------------------------------------
// DIRECTORY WALKING

typedef struct {
    char pathtmp[CFG_MAX_PATH];
    int pathtmp_len;

#if _WIN32
    HANDLE handle;
    WIN32_FIND_DATAW fd;
#else
    DIR* dir;
    struct dirent* entry;
    struct stat st;
#endif
} walkdir_t;

static walkdir_t* walkdir_alloc(const char* path) {
    // alloc stuff per dir since this is recursive, slightly slower but hopefully not that much
    walkdir_t* wd = calloc(1, sizeof(walkdir_t));
    if (!wd)
        return NULL;

    wd->pathtmp_len = CFG_MAX_PATH;
    //wd->pathtmp = malloc(wd->pathtmp_len);
    //if (!wd->pathtmp)
    //    return false;

#if _WIN32
    char path_tmp[CFG_MAX_PATH * 2]; 
    snprintf(path_tmp, sizeof(path_tmp), "%s\\*", path);

    wchar_t wpath_tmp[CFG_MAX_PATH];
    MultiByteToWideChar(CP_UTF8, 0, path_tmp, -1, wpath_tmp, MAX_PATH);

    HANDLE handle = FindFirstFileW(wpath_tmp, &wd->fd);
    if (handle == INVALID_HANDLE_VALUE)
        return NULL;

    wd->handle = handle;
#else
    wd->dir = opendir(path);
    if (!wd->dir)
        return NULL;

    wd->entry = readdir(wd->dir);
    if (!wd->entry)
        return NULL;
#endif

    return wd;
}

static void walkdir_free(walkdir_t* wd) {
#if _WIN32
    if (wd->handle)
        FindClose(wd->handle);
#else
    if (wd->dir)
        closedir(wd->dir);
#endif

    free(wd);
}

static bool walkdir_get_next_entry(walkdir_t* wd) {
#if _WIN32
    bool ok = FindNextFileW(wd->handle, &wd->fd);
    if (!ok)
        return false;
    return true;
#else
    wd->entry = readdir(wd->dir);
    if (!wd->entry)
        return false;
    return true;
#endif
}

static bool walkdir_setup_entry(walkdir_t* wd, const char* path) {
#if _WIN32
    char name_tmp[1024];
    WideCharToMultiByte(CP_UTF8, 0, wd->fd.cFileName, -1, name_tmp, sizeof(name_tmp), NULL, NULL);

    snprintf(wd->pathtmp, wd->pathtmp_len, "%s\\%s", path, name_tmp);

    return true;
#else
    snprintf(wd->pathtmp, wd->pathtmp_len, "%s/%s", path, wd->entry->d_name);

    if (stat(wd->pathtmp, &wd->st) < 0)
        return false;

    return true;
#endif
}

static bool walkdir_is_dir(walkdir_t* wd) {
#if _WIN32
    return wd->fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY;
#else
    return S_ISDIR(wd->st.st_mode);
#endif
}

static bool walkdir_is_file(walkdir_t* wd) {
#if _WIN32
    return !(wd->fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY); //TODO?
#else
    return S_ISREG(wd->st.st_mode);
#endif
}

static bool walkdir_is_dotpath(walkdir_t* wd) {
#if _WIN32
    return wcscmp(wd->fd.cFileName, L".") == 0 || wcscmp(wd->fd.cFileName, L"..") == 0;
#else
    return strcmp(wd->entry->d_name, ".") == 0 || strcmp(wd->entry->d_name, "..") == 0;
#endif
}

static void walk_dir(const char* path, const config_t* cfg, u64set_t* set) {

    // could use a stack/queue in walk_dir to minimize allocs but probably there won't be that many dirs
    walkdir_t* wd = walkdir_alloc(path);
    if (!wd) {
        if (cfg->verbose)
            printf("  cannot open dir: %s\n", path);
        return;
    }

    do {
        if (walkdir_is_dotpath(wd))
            continue;

        bool ok = walkdir_setup_entry(wd, path);
        if (!ok) {
            if (cfg->verbose)
                printf("  cannot setup entry: %s\n", wd->pathtmp);
            continue;
        }

        if (walkdir_is_dir(wd)) {
            walk_dir(wd->pathtmp, cfg, set);
        }
        else if (walkdir_is_file(wd)) {
            process_file(wd->pathtmp, cfg, set);
        }
    } while (walkdir_get_next_entry(wd));

    walkdir_free(wd);
}


//-------------------------------------------------------------------------------------------------
// MAIN

static bool open_outfile(config_t* cfg, char* outname, size_t outname_len) {
    // resolve real directory to generate output filename
    char realdir[CFG_MAX_PATH];
    get_real_directory(cfg->base_dir, realdir, sizeof(realdir));

    const char* last = extract_name(realdir);
    snprintf(outname, outname_len, "ww_%s.txt", last);

    cfg->out = fopen(outname, "w");
    if (!cfg->out)
        return false;
    return true;
}

static void print_help(const char* prog) {
    printf("wwise strings extractor\nUsage: %s [options]\n", prog);
    printf("  -h           Show help\n");
    printf("  -d <dir>     Directory to scan (default: .)\n");
    printf("  -m <N>       Minimum string length (default: %i)\n", CFG_MIN_LEN);
    printf("  -M <N>       Maximum string length (default: %i)\n", CFG_MAX_LEN);
    printf("  -s <N>       Skip threshold (default: %i)\n", CFG_SKIP_THRESHOLD);
    printf("  -a <MB>      Max memory for hash set (default: %i)\n", CFG_MAX_SET_SIZE_MB);
    printf("  -c           Case-sensitive hashing\n");
    printf("  -v           Verbose output\n");
}

static bool parse_args(int argc, char** argv, config_t* cfg) {
    cfg->exe_name = extract_name(argv[0]);

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-h")) {
            print_help(argv[0]);
            return false;
        }
        else if (!strcmp(argv[i], "-d") && i + 1 < argc) {
            cfg->base_dir = argv[++i];
        }
        else if (!strcmp(argv[i], "-m") && i + 1 < argc) {
            cfg->min_len = atoi(argv[++i]);
        }
        else if (!strcmp(argv[i], "-M") && i + 1 < argc) {
            cfg->max_len = atoi(argv[++i]);
        }
        else if (!strcmp(argv[i], "-s") && i + 1 < argc) {
            cfg->skip_threshold = atoi(argv[++i]);
        }
        else if (!strcmp(argv[i], "-a") && i + 1 < argc) {
            cfg->max_table_mb = atoll(argv[++i]);
        }
        else if (!strcmp(argv[i], "-c")) {
            cfg->case_sensitive = true;
        }
        else if (!strcmp(argv[i], "-v")) {
            cfg->verbose = true;
        }
    }

    return true;
}

int main(int argc, char** argv) {
    config_t cfg = {0};

    cfg.base_dir       = ".";
    cfg.min_len        = CFG_MIN_LEN;
    cfg.max_len        = CFG_MAX_LEN;
    cfg.skip_threshold = CFG_SKIP_THRESHOLD;
    cfg.max_table_mb   = CFG_MAX_SET_SIZE_MB;

    if (!parse_args(argc, argv, &cfg)) {
        return EXIT_FAILURE;
    }

    if (cfg.max_len >= STR_MAX) {
        fprintf(stderr, "max string length (%d) must be less than %d\n", cfg.max_len, STR_MAX);
        return EXIT_FAILURE;
    }

    size_t max_bytes = cfg.max_table_mb * 1024ull * 1024ull;

    u64set_t set = {0};
    if (!u64set_initialize(&set, CFG_INITIAL_SET_SIZE, max_bytes)) {
        fprintf(stderr, "Error: cannot initialize hash set\n");
        return EXIT_FAILURE;
    }


    char outname[512];
    bool ok = open_outfile(&cfg, outname, sizeof(outname));
    if (!ok) {
        fprintf(stderr, "Error: cannot open output file '%s'\n", outname);
        u64set_free(&set);
        return EXIT_FAILURE;
    }
    cfg.out_name = outname;

    // main process
    printf("processing...\n");
    walk_dir(cfg.base_dir, &cfg, &set);
    printf("done\n");

    fclose(cfg.out);
    u64set_free(&set);
    return EXIT_SUCCESS;
}
