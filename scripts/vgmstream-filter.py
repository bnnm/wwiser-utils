#!/usr/bin/env python3
from __future__ import division
import argparse, subprocess, zlib, os, re, sys, fnmatch, logging as log

#******************************************************************************
# VGMSTREAM FILTER
#
# Moves files that don't match filters
#******************************************************************************

class Cli(object):
    MOVE_DIR = 'filtered'

    def _parse(self):
        description = (
            "Filters vgmstream files in folder that don't match filters and moves them to subfolder"
        )
        epilog = (
            "examples:\n"
            "  %(prog)s *.adx\n"
            "  - does nothing (needs at least one filter)\n"
            "  %(prog)s *.txtp -fcm 2 -fms 5.0\n"
            "  - move files that have less that 2 channels and 5 seconds (mono voices)\n"
            "  %(prog)s *.adx -fd\n"
            "  - move files that have output (.wav) duplicates\n"
            "  %(prog)s *.* -p \"{fs}: channels={ch}, samples={sn}\"\n"
            "  - prints formatted info for all files\n"
            "  %(prog)s *.* -fcm 2 -p \"{fn}: channels={ch}, samples={ns}\"\n"
            "  - prints formatted info for all non-mono files\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('files', help="Files to process (wildcards work)", nargs='+')
        p.add_argument('-c',   dest='cli', help="Set path to CLI (default: auto)")
        p.add_argument('-r',   dest='recursive', help="Find files recursively", action='store_true')
        p.add_argument('-m',   dest='move_dir', help="Set subdir where filtered files go", default=self.MOVE_DIR)
        p.add_argument('-fd',  dest='dupes', help="Filter by duplicate wavs (slower)", action='store_true')
        p.add_argument('-fcm', dest='min_channels', help="Filter by less than channels", type=int)
        p.add_argument('-fcM', dest='max_channels', help="Filter by more than channels", type=int)
        p.add_argument('-frm', dest='min_sample_rate', help="Filter by less than sample rate", type=int)
        p.add_argument('-frM', dest='max_sample_rate', help="Filter by more than sample rate", type=int)
        p.add_argument('-fsm', dest='min_seconds', help="Filter by less than seconds (N.N)", type=float)
        p.add_argument('-fsM', dest='max_seconds', help="Filter by more than seconds (N.N)", type=float)
        p.add_argument('-fss', dest='min_subsongs', help="Filter min subsongs\n(1 filters formats incapable of subsongs)", type=int)
        p.add_argument('-p',   dest='print_info', help=("Print text info, formatted using:\n"
                                                      "- {fn}=filename\n"
                                                      "- {ss}=total subsong)\n"
                                                      "- {in}=internal stream name\n"
                                                      "- {if}=internal name or filename if not found\n"
                                                      "- {ns}=number of samples\n"
                                                      "- {ls}=loop start\n"
                                                      "- {le}=loop end\n"
                                                      "- {sr}=sample rate\n"
                                                      "- {ch}=channels\n"
                                                      "* may be inside <...> for conditional text\n"
                                                      "Example: file {fn} = {ns}< {ls}>< {le}>\n"))

        return p.parse_args()

    def start(self):
        args = self._parse()
        if not args.files:
            return
        Logger(args).setup_cli()
        App(args).start()

#******************************************************************************

class Logger(object):
    def __init__(self, cfg):
        levels = {
            'info': log.INFO,
            'debug': log.DEBUG,
        }
        self.level = levels.get('info', log.ERROR) #cfg.log_level

    def setup_cli(self):
        log.basicConfig(level=self.level, format='%(message)s')

#******************************************************************************

class Cr32Helper(object):

    def __init__(self, args):
        self.args = args
        self.crc32_map = {}
        self.last_dupe = False

    def get_crc32(self, filename):
        buf_size = 0x8000
        with open(filename, 'rb') as file:
            buf = file.read(buf_size)
            crc32 = 0
            while len(buf) > 0:
                crc32 = zlib.crc32(buf, crc32)
                buf = file.read(buf_size)
        return crc32 & 0xFFFFFFFF 

    def update(self, filename):
        self.last_dupe = False
        if not self.args.dupes:
            return
        if not os.path.exists(filename):
            return

        crc32_str = format(self.get_crc32(filename),'08x')
        if (crc32_str in self.crc32_map):
            self.last_dupe = True
            return
        self.crc32_map[crc32_str] = True

        return

    def is_last_dupe(self):
        return self.last_dupe

#******************************************************************************

class CliFilter(object):

    def __init__(self, args, output_b, basename):
        self.args = args
        self.basename = basename
        self.output = str(output_b).replace("\\r","").replace("\\n","\n")
        self.channels = self._get_value("channels: ")
        self.sample_rate = self._get_value("sample rate: ")
        self.num_samples = self._get_value("stream total samples: ")
        self.loop_start = self._get_value("loop start: ")
        self.loop_end = self._get_value("loop end: ")
        self.stream_count = self._get_value("stream count: ")
        self.stream_index = self._get_value("stream index: ")
        self.stream_name = self._get_text("stream name: ")

        if self.channels <= 0 or self.sample_rate <= 0:
            raise ValueError('Incorrect command result')

        self.stream_seconds = self.num_samples / self.sample_rate
        self.ignorable = self._is_ignorable()
        self.has_filters = self._has_filters()

    def __str__(self):
        return str(self.__dict__)

    def _get_string(self, str, full=False):
        find_pos = self.output.find(str)
        if (find_pos == -1):
            return None
        cut_pos = find_pos + len(str)
        str_cut = self.output[cut_pos:]
        if full:
            return str_cut.split("\n")[0].strip()
        else:
            return str_cut.split()[0].strip()

    def _get_text(self, str):
        return self._get_string(str, full=True)

    def _get_value(self, str):
        res = self._get_string(str)
        if not res:
           return 0
        return int(res)

    def is_ignorable(self):
        return self.ignorable

    def _has_filters(self):
        cfg = self.args
        if cfg.min_channels or cfg.max_channels or cfg.min_sample_rate or cfg.max_sample_rate:
            return True
        if cfg.min_seconds or cfg.max_seconds or cfg.min_subsongs:
            return True
        return False

    def _is_ignorable(self):
        cfg = self.args
        if cfg.min_channels and self.channels < cfg.min_channels:
            return True
        if cfg.max_channels and self.channels > cfg.max_channels:
            return True
        if cfg.min_sample_rate and self.sample_rate < cfg.min_sample_rate:
            return True
        if cfg.max_sample_rate and self.sample_rate > cfg.max_sample_rate:
            return True
        if cfg.min_seconds and self.stream_seconds < cfg.min_seconds:
            return True
        if cfg.max_seconds and self.stream_seconds > cfg.max_seconds:
            return True
        if cfg.min_subsongs and self.stream_count < cfg.min_subsongs:
            return True
        return False

#******************************************************************************

class App(object):
    def __init__(self, args):
        self.args = args
        self.crc32 = Cr32Helper(args)

    # check CLI in path (can be called, not just file exists)
    def _test_cli(self):
        clis = []
        if self.args.cli:
            clis.append(self.args.cli)
        else:
            clis.append('vgmstream_cli')
            clis.append('test.exe')

        for cli in clis:
            try:
                with open(os.devnull, 'wb') as DEVNULL: #subprocess.STDOUT #py3 only
                    cmd = "%s" % (cli)
                    subprocess.check_call(cmd, stdout=DEVNULL, stderr=DEVNULL)
                self.args.cli = cli
                return True #exists and returns ok
            except subprocess.CalledProcessError as e:
                self.args.cli = cli
                return True #exists but returns strerr (ran with no args)
            except Exception as e:
                continue #doesn't exist

        #none found
        return False

    def _make_cmd(self, filename_in, filename_out, target_subsong=0):
        if self.args.dupes:
            cmd = "%s -s %s -i -o \"%s\" \"%s\"" % (self.args.cli, target_subsong, filename_out, filename_in)
        else:
            cmd = "%s -s %s -m -i -O \"%s\"" % (self.args.cli, target_subsong, filename_in)
        return cmd

    def _find_files(self, dir, pattern):
        if os.path.isfile(pattern):
            return [pattern]
        if os.path.isdir(pattern):
            dir = pattern
            pattern = None

        files = []
        for root, dirnames, filenames in os.walk(dir):
            for filename in fnmatch.filter(filenames, pattern):
                files.append(os.path.join(root, filename))

            if not self.args.recursive:
                break

        return files


    def _print_info(self, filter):
        cfg = self.args

        stream_name = filter.stream_name
        internal_filename = stream_name
        if not internal_filename:
            internal_filename = filter.basename

        if not filter.stream_count:
            subsongs = None
        else:
            subsongs = str(filter.stream_count)
            
        
        ns = filter.num_samples
        ns_le = (((ns << 24) & 0xFF000000) |
                ((ns <<  8) & 0x00FF0000) |
                ((ns >>  8) & 0x0000FF00) |
                ((ns >> 24) & 0x000000FF))
        hex_ns_le = "%08x" % (ns_le)
        hex_ns_be = "%08x" % (ns)

        replaces = {
            'fn': filter.basename,
            'ss': subsongs,
            'in': stream_name,
            'if': internal_filename,
            'ns': str(filter.num_samples),
            'ls': str(filter.loop_start),
            'le': str(filter.loop_end),
            'sr': str(filter.sample_rate),
            'ch': str(filter.channels),
            'hsle': hex_ns_le,
            'hsbe': hex_ns_be,
        }

        pattern1 = re.compile(r"<(.+?)>")
        pattern2 = re.compile(r"{(.+?)}")
        txt = cfg.print_info

        txt = txt.replace('\\t', '\t')
        txt = txt.replace('\\n', '\n')


        # print optional info like "<text__{cmd}__>" only if value in {cmd} exists
        optionals = pattern1.findall(txt)
        for optional in optionals:
            has_values = False
            cmds = pattern2.findall(optional)
            for cmd in cmds:
                if cmd in replaces and replaces[cmd] is not None:
                    has_values = True
                    break
            if has_values: #leave text there (cmds will be replaced later)
                txt = txt.replace('<%s>' % optional, optional, 1)
            else:
                txt = txt.replace('<%s>' % optional, '', 1)

        # replace "{cmd}" if cmd exists with its value (non-existent values use '')
        cmds = pattern2.findall(txt)
        for cmd in cmds:
            if cmd in replaces:
                value = replaces[cmd]
                if value is None:
                   value = ''
                txt = txt.replace('{%s}' % cmd, value, 1)

        print(txt)


    def _move(self, filename_in):
        basename_in = os.path.basename(filename_in)

        dirname_out = os.path.dirname(basename_in)
        dirname_out = os.path.join(dirname_out, self.args.move_dir)
        filename_out = os.path.join(dirname_out, basename_in)
        if os.path.exists(filename_out):
            log.info("ignoring existing file: %s". filename_in)

        os.makedirs(dirname_out, exist_ok=True)

        os.rename(filename_in, filename_out)

    def start(self):
        if not self._test_cli():
            log.error("ERROR: CLI not found")
            return

        filenames_in = []
        for filename in self.args.files:
            filenames_in += self._find_files('.', filename)

        total_filtered = 0
        total_errors = 0
        for filename_in in filenames_in:

            #skip starting dot for extensionless files
            if filename_in.startswith(".\\"):
                filename_in = filename_in[2:]

            basename_in = os.path.basename(filename_in)
            filename_out = ".temp." + basename_in + ".wav"

            try:
                cmd = self._make_cmd(filename_in, filename_out)
                log.debug("calling: %s", cmd)
                output_b = subprocess.check_output(cmd, shell=False) #stderr=subprocess.STDOUT
            except subprocess.CalledProcessError as e:
                log.debug("ignoring CLI error in %s: %s", filename_in, str(e.output))
                total_errors += 1
                break

            filter = CliFilter(self.args, output_b, basename_in)

            if not filter.is_ignorable():
                self.crc32.update(filename_out)
            filtered = filter.is_ignorable() or self.crc32.is_last_dupe()

            if self.args.print_info and (filtered or not filter.has_filters):
                self._print_info(filter)
            elif filter.is_ignorable() or self.crc32.is_last_dupe():
                self._move(filename_in)
                total_filtered += 1

            if os.path.exists(filename_out):
                os.remove(filename_out)

        if not self.args.print_info:
            log.info("done! (%s filtered, %s errors)", total_filtered, total_errors)


if __name__ == "__main__":
    Cli().start()

    #if len(sys.argv) > 1:
    #    Cli().start()
    #else:
    #    Gui().start()
