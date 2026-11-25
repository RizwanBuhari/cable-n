"""Generates the Cable-N brand SVGs into frontend/public/brand/.

Mark: a cable cross-section - red sheath disc, a faint metallic-screen ring,
and three insulated cores laid in trefoil with dark conductors.
Wordmark: "Cable-N" in Montserrat ExtraBold (SIL Open Font License),
converted to outlines so the files render identically without the font.

Run:  backend\\.venv\\Scripts\\python scripts\\brand\\build_brand.py
"""
import math
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / 'frontend' / 'node_modules' / '@fontsource' / 'montserrat' / 'files'
OUT = ROOT / 'frontend' / 'public' / 'brand'
RED, INK, MUTED, WHITE = '#CE1B28', '#212121', '#6F7378', '#FFFFFF'


def icon_shapes(sheath, core, conductor, ring_opacity=0.32, ring=WHITE):
    """64x64 mark. Cores touch (centre spacing = 2 x core radius), as a real trefoil."""
    cx = cy = 32.0
    R = 10.9
    rc = R * math.sqrt(3) / 2
    s = [f'<circle cx="32" cy="32" r="30" fill="{sheath}"/>',
         f'<circle cx="32" cy="32" r="26.2" fill="none" stroke="{ring}" stroke-opacity="{ring_opacity}" '
         f'stroke-width="1.3"/>']
    for ang in (-90, 30, 150):
        x = cx + R * math.cos(math.radians(ang))
        y = cy + 1.2 + R * math.sin(math.radians(ang))
        s.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{rc - 0.35:.3f}" fill="{core}"/>')
        s.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{rc * 0.44:.3f}" fill="{conductor}"/>')
    return s


def text_path(font_file, text, size, x0, baseline, tracking=-0.012):
    f = TTFont(font_file)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f['head'].unitsPerEm
    sc = size / upm
    paths = []
    x = x0
    for ch in text:
        gname = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        tpen = TransformPen(pen, (sc, 0, 0, -sc, x, baseline))
        gs[gname].draw(tpen)
        paths.append((ch, pen.getCommands()))
        x += gs[gname].width * sc + tracking * size
    return paths, x


def wordmark(x0, baseline, size, ink, accent, tagline_color=None):
    font = FONT / 'montserrat-latin-800-normal.woff'
    parts, end = text_path(font, 'Cable', size, x0, baseline)
    els = [f'<path d="{" ".join(d for _, d in parts)}" fill="{ink}"/>']
    # hyphen drawn as a rounded "conductor bar" in the accent colour
    hx = end + size * 0.05
    hw, hh = size * 0.30, size * 0.115
    hy = baseline - size * 0.36
    els.append(f'<rect x="{hx:.2f}" y="{hy:.2f}" width="{hw:.2f}" height="{hh:.2f}" rx="{hh / 2:.2f}" fill="{accent}"/>')
    nparts, end2 = text_path(font, 'N', size, hx + hw + size * 0.05, baseline)
    els.append(f'<path d="{nparts[0][1]}" fill="{accent}"/>')
    width = end2
    if tagline_color:
        tfont = FONT / 'montserrat-latin-600-normal.woff'
        tsize = size * 0.205
        tp, tend = text_path(tfont, 'CABLE SIZING & ENGINEERING INTELLIGENCE', tsize, x0 + 1, baseline + size * 0.42,
                             tracking=0.14)
        els.append(f'<path d="{" ".join(d for _, d in tp)}" fill="{tagline_color}"/>')
        width = max(width, tend)
    return els, width


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="{title}"><title>{title}</title>' + ''.join(body) + '</svg>\n')


def logo(variant='color', tagline=False):
    pal = {
        'color': (RED, WHITE, INK, INK, RED, MUTED, WHITE),
        'mono-dark': (INK, WHITE, INK, INK, INK, INK, WHITE),
        'mono-white': (WHITE, 'none', WHITE, WHITE, WHITE, WHITE, INK),
        'on-dark': (RED, WHITE, INK, WHITE, RED, '#B9BDC2', WHITE),
    }[variant]
    sheath, core, cond, ink, accent, tag, ring = pal
    if variant == 'mono-white':
        # white mark: white disc with transparent cores (cut-outs) via mask
        icon = ['<defs><mask id="m"><rect width="64" height="64" fill="#fff"/>',
                *[c.replace(f'fill="{WHITE}"', 'fill="#000"') for c in icon_shapes(WHITE, WHITE, '#fff')[2::2]],
                '</mask></defs>', '<circle cx="32" cy="32" r="30" fill="#fff" mask="url(#m)"/>']
        for c in icon_shapes(WHITE, WHITE, '#fff')[3::2]:
            icon.append(c)
    else:
        icon = icon_shapes(sheath, core, cond, ring=ring)
    size = 44
    words, wend = wordmark(78, 47 if not tagline else 41, size, ink, accent, tag if tagline else None)
    h = 64 if not tagline else 66
    return svg(wend + 4, h, icon + words, 'Cable-N')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        'cable-n-icon.svg': svg(64, 64, icon_shapes(RED, WHITE, INK), 'Cable-N'),
        'cable-n-icon-mono-dark.svg': svg(64, 64, icon_shapes(INK, WHITE, INK), 'Cable-N'),
        'cable-n-logo.svg': logo('color'),
        'cable-n-logo-full.svg': logo('color', tagline=True),
        'cable-n-logo-on-dark.svg': logo('on-dark'),
        'cable-n-logo-full-on-dark.svg': logo('on-dark', tagline=True),
        'cable-n-logo-mono-dark.svg': logo('mono-dark'),
        'cable-n-logo-mono-white.svg': logo('mono-white'),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding='utf-8')
    (ROOT / 'frontend' / 'public' / 'favicon.svg').write_text(files['cable-n-icon.svg'], encoding='utf-8')
    print('wrote', ', '.join(files))


if __name__ == '__main__':
    main()
