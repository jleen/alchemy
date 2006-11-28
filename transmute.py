import getopt
import re
import sys
import xml

from Cheetah.Template import Template

lines = sys.stdin.readlines()

ITALIC = r"/([^/]*)/"

class Formatter:
    fields = {}

    def begin(self):
        self.fields = {}
        self.fields["body"] = ''
        self.fields["title"] = ''
        self.fields["date"] = ''

    def end(self): pass

    def directive(self, cmd, arg):
        self.fields[cmd] = self.transform(arg)

    def get_fields(self):
        return self.fields

    def transform(self, str):
        for xf in self.transforms:
            str = re.sub(xf[0], xf[1], str)
        return str

    def line(self, str):
        self.fields["body"] += self.transform(str) + '\n\n'

class Plain(Formatter):
    def section(self, str):
        self.fields["body"] += '\n'
        self.fields["body"] += '== ' + self.transform(str) + ' ==\n'
        self.fields["body"] += '\n'

    transforms = [
        [ r' +', ' ' ],
        [ r'`',  "'" ]
    ]

class Html(Formatter):
    def title(self, str):
        self.fields["body"] += '<title>' + self.transform(str) + '</title>\n'
        self.fields["body"] += '<h1>' + self.transform(str) + '</h1>\n'

    def section(self, str):
        self.fields["body"] += '<h2>' + self.transform(str) + '</h2>\n'

    def line(self, str):
        self.fields["body"] += '<p>' + self.transform(str) + '</p>\n'

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

class TeX(Formatter):
    def section(self, str):
        self.fields["body"] += '\\subsection*{' + self.transform(str) + '}\n\n'

    transforms = [
        [r' +',  ' '],
        [ITALIC, '{\\\\it \\1}']
    ]


opts, args = getopt.getopt(
    sys.argv[1:],
    'pwx', ['plain', 'html', 'tex'])

formatter = None

for o, a in opts:
    if o in ('-p', '--plain'):
        formatter = Plain()
    if o in ('-w', '--html'):
        formatter = Html()
    if o in ('-x', '--tex'):
        formatter = TeX()

if formatter == None:
    formatter = Plain()

template = None
if len(args) > 0:
    template = args[0]
else:
    if isinstance(formatter, Plain): template = "plain.tmpl"
    elif isinstance(formatter, Html): template = "html.tmpl"
    elif isinstance(formatter, TeX): template = "tex.tmpl"


escapes = [
    [ r'=(?P<cmd>[A-Za-z]+) (?P<arg>.*)', formatter.directive ],
    [ r'== (?P<str>.*) ==', formatter.section ]
]

for cmd in escapes: cmd[0] = re.compile(cmd[0])

formatter.begin()

cur_line = ''
fresh_line = True
for line in lines:
    line = line.strip()
    if line.startswith('='):
        for pat, cmd in escapes:
            found = pat.match(line)
            if found: cmd(*found.groups())
    elif line != '':
        if not fresh_line:
            cur_line += ' '
        else:
            fresh_line = False
        cur_line += line
    else:
        if not fresh_line:
            formatter.line(cur_line)
        fresh_line = True
        cur_line = ''

if not fresh_line: formatter.line(cur_line)

formatter.end()

t = Template(file = template, searchList = [formatter.get_fields()])
print str(t)
