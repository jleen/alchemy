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

    def __init__(self, transformer):
        self.transformer = transformer

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
        subfmt = self.__class__(self.transformer)
        if debug: subfmt.debug_name = "inner"
        subfmt.begin()
        if arg: arg = self.transformer.transform(arg)
        subfmt.fields["arg"] = arg
        subfmt.fill(lines)
        subfmt.end()

        sub_fields = subfmt.get_fields()
        self.fields["body"] += fill_template(templates[cmd], sub_fields)

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
        [ r'--',  '&endash; ' ],
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

    opts, args = getopt.getopt(
        sys.argv[1:],
        'pwxv', ['plain', 'html', 'tex', 'version'])

    transformer_type = "plain"

    for o, a in opts:
        if o in ('-v', '--verbose'):
            debug = True

    template = None
    if len(args) > 0:
        template = args[0]
        if not os.path.exists(template):
            template = runtime_file(template)
    else:
        template = runtime_file("plain.tmpl")

    for cmd in escapes:
        cmd[0] = re.compile(cmd[0])
        if cmd[1]: cmd[1] = re.compile(cmd[1])

    template_fh = open(template, 'r')
    template_lines = template_fh.readlines()
    template_fh.close()

    templates = { 'main': '' }
    current_template = 'main'
    for line in template_lines:
        line = line.strip()
        if line.startswith('===default '):
            transformer_type = line[11:]

        elif line.startswith('=='):
            current_template = line[2:]
            templates[current_template] = ''
        else:
            templates[current_template] += line + '\n'

    formatter = Formatter(get_transformer(transformer_type))
    if debug: formatter.debug_name = "outer"
    formatter.begin()
    formatter.fill(lines)
    formatter.end()

    print fill_template(templates['main'], formatter.get_fields())

main()
