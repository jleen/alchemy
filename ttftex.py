import os
import sys
#pre-setup: copy T1-WGL4.enc to new dir texmf/pdftex/base
#echo 'map +ttfonts.map' >> "$LOCAL_PATH/pdftex/config/pdftex.cfg"
#local\miktex\config\updmap.cfg must contain "Map pdfttfonts.map"
#put pdfttfonts.map in local\pdftex\config


# das ding an sich
LOCAL_PATH='/Opt/MiKTeX/local'
VF_PATH = os.path.join(LOCAL_PATH, 'fonts/vf/ttf')
TFM_PATH = os.path.join(LOCAL_PATH, 'fonts/tfm/ttf')
TTFONTS_MAP_PATH = os.path.join(LOCAL_PATH, 'ttf2tfm/base/ttfonts.map')
LATEX_TTF_PATH = os.path.join(LOCAL_PATH, 'tex/latex/ttf')
PDFTEX_MAP_PATH = os.path.join(LOCAL_PATH, 'pdftex/config/pdfttfonts.map')
TTF_PATH = os.path.join(LOCAL_PATH, 'fonts/truetype')

def ensure_open(filename, mode = 'r'):
    (dir, leaf) = os.path.split(filename)
    try: os.makedirs(dir)
    except: pass
    return open(filename, mode)

def make_tfm(font, ttfsuffix, slant):
    ttf = font + ttfsuffix + '.ttf'
    suffix = ttfsuffix
    if slant: suffix += 'o'
    vpl = 'ttf-' + font + suffix + '.vpl'
    vf = 'ttf-' + font + suffix + '.vf'
    rtfm = 'rttf-' + font + suffix + '.tfm'
    tfm = 'ttf-' + font + suffix + '.tfm'
    sflag = ''
    if slant: sflag = '-s .167'
    ttf2tfm = ' '.join((
        'ttf2tfm', ttf, '-q -T T1-WGL4.enc', sflag, '-v', vpl, rtfm))
    p = os.popen(ttf2tfm)
    ttfonts = ensure_open(TTFONTS_MAP_PATH, 'a')
    ttfonts.write(p.read())
    p.close()
    ttfonts.close()
    os.system(' '.join(('vptovf', vpl, vf, tfm)))
    os.remove(vpl)
    os.renames(vf, os.path.join(VF_PATH, font, vf))
    os.renames(tfm, os.path.join(TFM_PATH, font, tfm))
    os.renames(rtfm, os.path.join(TFM_PATH, font, rtfm))

    ttfcopy = ensure_open(os.path.join(TTF_PATH, ttf), 'w')
    ttforig = open(ttf)
    ttfcopy.write(ttforig.read())
    ttfcopy.close()
    ttforig.close()

    f = ensure_open(PDFTEX_MAP_PATH, 'a')
    f.write('rttf-' + font + ' <' + ttf + ' <T1-WGL4.enc\n')
    f.close()

def create_fd_file(font, variants, subs):
    fd_fn = 't1' + font + '.fd'
    f = ensure_open(os.path.join(LATEX_TTF_PATH, fd_fn), 'w')
    f.write('\\ProvidesFile{t1' + font + '.fd}\n')
    f.write('\n')
    f.write('\\DeclareFontFamily{T1}{' + font + '}{}\n')
    f.write('\n')
    for (weight, slant, suffix) in variants:
        f.write('\\DeclareFontShape')
        f.write('{T1}{' + font + '}{' + weight + '}{' + slant + '}')
        f.write('{<-> ttf-' + font + suffix + '}{}\n')
    for (weight, slant, sweight, sslant) in subs:
        f.write('\\DeclareFontShape')
        f.write('{T1}{' + font + '}{' + weight + '}{' + slant + '}')
        f.write('{<->ssub * ' + font + '/' + sweight + '/' + sslant + '}{}\n')
    f.write('\\endinput\n')
    f.close()

def refresh_texmf():
    os.system('initexmf -u')
    os.system('initexmf --mkmaps')


all_variants = [['m', 'n', ''],
                ['m', 'it', 'i'],
                ['b', 'n', 'b'],
                ['b', 'it', 'bi']]

all_slant_variants = [['m', 'sl', 'o'],
                      ['b', 'sl', 'bo']]

family = sys.argv[1]

subs = []
variants = []
for (weight, slant, suffix) in all_variants:
    if os.path.exists(family + suffix + '.ttf'):
        make_tfm(family, suffix, False)
        variants += [[weight, slant, suffix]]
        if weight == 'b':
            subs += [['bx', slant, 'b', slant]]

slant_variants = []
for (weight, slant, suffix) in all_slant_variants:
    if os.path.exists(family + suffix[:-1] + '.ttf'):
        make_tfm(family, suffix[:-1], True)
        slant_variants += [[weight, slant, suffix]]
        subs += [['bx', slant, 'b', slant]]

create_fd_file(family, variants + slant_variants, subs)

refresh_texmf()
