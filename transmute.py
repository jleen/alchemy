import getopt
import os
import re
import sys
import xml

debug = False
templates = None

ITALIC = r"/([^/]+)/"

escapes = [
    [ r'^=> (?P<file>.*)$', None, 'include' ],
    [ r'^=(?P<cmd>[A-Za-z]+) (?P<arg>.*)$', None, 'directive' ],
    [ r'^==(?P<cmd>[A-Za-z]+) \< (?P<file>.*)$', None, 'include_macro' ],
    [ r'^==(?P<cmd>[A-Za-z]+)(?: (?P<arg>[^<]*))?==$', None, 'macro' ],
    [ r'^==(?P<cmd>[A-Za-z]+)(?: (?P<arg>[^=<]*))?$', "^==$", 'macro' ],
    [ r'^===(?P<cmd>[A-Za-z]+)(?: (?P<arg>[^=<]*))?$', "^===$", 'macro' ],
    [ r'^== (?P<arg>.*) ==$', None, 'section' ]
]

class IteratorStack:
    iter_stack = [[].__iter__()] 

    def __iter__(self):
        return self

    def next(self):
        if debug: print 'next', self.iter_stack[-1]
        self.iter_stack[-1].next()

    def push(self, iterator):
        if debug: print 'push', iterator
        self.iter_stack += [iterator]

    def pop(self):
        if debug: print 'pop', self.iter_stack[1:]
        self.iter_stack = self.iter_stack[1:]

runtime_dir = os.path.split(sys.argv[0])[0]
def runtime_file(name):
    return os.path.join(runtime_dir, name)

class Formatter:
    fields = {}

    def __init__(self, transformer, line_mode):
        self.transformer = transformer
        self.line_mode = line_mode

    def begin(self):
        if debug: print "Beginning", self.debug_name
        self.fields = {}
        self.fields["body"] = ''
        self.fields["title"] = ''
        self.fields["date"] = ''

    def end(self):
        if debug: print "Ending", self.debug_name

    def include_macro(self, cmd, file):
        if debug: print 'Including', file, 'for macro', cmd
        include_fh = open(file + '.prose', 'r')
        include_lines = include_fh.readlines()
        include_fh.close()
        self.macro(cmd, None, include_lines)

    def section(self, arg):
        self.macro("section", arg)

    def macro(self, cmd, arg, lines = []):
        line_macro = templates[cmd]['line_macro']
        subfmt = self.__class__(self.transformer, line_macro)
        if debug: subfmt.debug_name = "inner"
        subfmt.begin()
        if arg: arg = self.transformer.transform(arg)
        subfmt.fields["arg"] = arg
        subfmt.fill(lines)
        subfmt.end()

        sub_fields = subfmt.get_fields()
        self.fields["body"] += fill_template(templates[cmd]['text'], sub_fields)

    def include(self, file):
        if debug: print 'Including ', file
        include_fh = open(file + '.prose', 'r')
        include_lines = include_fh.readlines()
        include_fh.close()
        self.fill(include_lines)

    def directive(self, cmd, arg):
        if debug: print "Directive", cmd, arg
        self.fields[cmd] = self.transformer.transform(arg)

    def get_fields(self):
        return self.fields

    def line(self, str):
        if self.line_mode:
            if debug: print 'Processing line with macro', self.line_mode
            self.macro(self.line_mode, str)
        else:
            if debug: print 'Processing paragraph with transformer'
            self.fields["body"] += self.transformer.transform_line(str)

    def fill(self, lines):
        cur_line = ''
        fresh_line = True
        line_iter = lines.__iter__()
        while True:
            line = ''
            try: line = line_iter.next()
            except StopIteration: break
            line = line.strip()
            if debug: print "Filling", self.debug_name, "from", line
            if line.startswith('='):
                for pat, end_pat, cmd in escapes:
                    cmd_impl = getattr(self, cmd)
                    found = pat.match(line)
                    if found:
                        if end_pat:
                            inner_lines = []
                            line = line_iter.next().strip()
                            while not end_pat.match(line):
                                inner_lines += [line]
                                line = line_iter.next().strip()
                            cmd_impl(lines = inner_lines, *found.groups())
                        else:
                            cmd_impl(*found.groups())
            elif self.line_mode:
                self.line(line)
            elif line != '':
                if not fresh_line:
                    cur_line += ' '
                else:
                    fresh_line = False
                cur_line += line
            else:
                if not fresh_line:
                    self.line(cur_line)
                fresh_line = True
                cur_line = ''
        if not fresh_line: self.line(cur_line)


def get_transformer(which_one):
    if which_one == "plain": return Plain()
    if which_one == "html": return Html()
    if which_one == "tex": return TeX()

class Transformer:
    def transform(self, str):
        for xf in self.transforms:
            str = re.sub(xf[0], xf[1], str)
        return str

    def transform_line(self, str):
        return self.transform(str) + '\n\n'


class Dumb(Transformer):
    transforms = []


class Plain(Transformer):
    transforms = [
        [ r' +', ' ' ],
        [ r'`',  "'" ]
    ]


class Html(Transformer):
    def transform_line(self, str):
        return '<p>' + self.transform(str) + '</p>\n'

    transforms = [
        [ r' +',  ' ' ],
        [ r'<',   '&lt;' ],
        [ r'>',   '&gt;' ],
        [ r'&',   '&amp;' ],
        [ r'``',  '&ldquo;' ],
        [ r"''",  '&rdquo;' ],
        [ r'`',   '&lsquo;' ],
        [ r"'",   '&rsquo;' ],
        [ r'--',  '&endash;' ],
        [ r'\.\.\.',  '&hellip;' ],
        [ ITALIC, '<i>\\1</i>' ]
    ]


class TeX(Transformer):
    transforms = [
        [r' +',  ' '],
        [r'\\', '\\\\\\\\'], 
        [r'&', '\\&'],
        [r'\$', '\$'],
        [r'_', '\_'],
        [r'\^\^', '\\^'],
        [r'\^:', '\\"'],
        [r'\^AE', '\\AE{}'],
        [r'\s*--\s*',  '---' ],
        [r'//', '\\\\happyslash{}'],
        [r'==footnote ([^=]+)==', '\\\\footnote{\\1}'],
        [ITALIC, '{\\\\it \\1}']
    ]


def fill_template(template, fields):
    field_alternator = '|'.join([re.escape(key) for key in fields.keys()])
    filler = re.compile('\$(' + field_alternator + ')')
    return filler.sub(lambda match: fields[match.group(1)], template)

def main():
    global debug
    global templates

    lines = sys.stdin.readlines()

    template = None
    if lines[0].startswith('====template '):
        template = lines[0][13:].strip() + '.tmpl'

    opts, args = getopt.getopt(
        sys.argv[1:],
        'v', ['version'])

    transformer_type = "plain"

    for o, a in opts:
        if o in ('-v', '--verbose'):
            debug = True

    if len(args) > 0:
        template = args[0]

    if template and not os.path.exists(template):
        template = runtime_file(template)

    if not template or not os.path.exists(template):
        template = runtime_file("plain.tmpl")

    for cmd in escapes:
        cmd[0] = re.compile(cmd[0])
        if cmd[1]: cmd[1] = re.compile(cmd[1])

    template_fh = open(template, 'r')
    template_lines = template_fh.readlines()
    template_fh.close()

    templates = { 'main': '' }
    current_template = 'main'
    lines_re = re.compile(
        '^(?P<name>[A-Za-z]+) lines (?P<line_macro>[A-Za-z]+)$')
    for line in template_lines:
        line = line.strip()
        if line.startswith('===default '):
            transformer_type = line[11:]

        elif line.startswith('=='):
            current_template = line[2:]
            line_macro = None
            found = lines_re.match(current_template)
            if found:
                current_template = found.group('name')
                line_macro = found.group('line_macro')
            if debug: print 'Defining macro', current_template
            templates[current_template] = {}
            templates[current_template]['text'] = ''
            templates[current_template]['line_macro'] = line_macro

        else:
            templates[current_template]['text'] += line + '\n'

    line_mode = templates['main']['line_macro']
    formatter = Formatter(get_transformer(transformer_type), line_mode)
    if debug: formatter.debug_name = "outer"
    formatter.begin()
    formatter.fill(lines)
    formatter.end()

    print fill_template(templates['main']['text'], formatter.get_fields())

main()
