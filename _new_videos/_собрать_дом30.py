#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Лист «ДОМ — 30 упражнений» со старыми превью-фото (позы A и B) из app-v2/workout_photos."""
import base64, html, os, re, sys

PROJ = os.path.expanduser('~/Claude/Projects/nutrition-app')
JS = os.path.join(PROJ, 'app-v2', 'workouts.js')
PHOTOS = os.path.join(PROJ, 'app-v2', 'workout_photos')
HIRES = os.path.join(PROJ, '_new_videos', '_thumbs_home')   # переснятые кадры вместо 240×240
OUT = os.path.join(PROJ, '_new_videos', 'ДОМ_30_с_фото.html')

# ---------- 1. домашние упражнения из workouts.js ----------
src = open(JS, encoding='utf-8').read()
blk = src[src.index('const EX = ['):src.index('\n  ];', src.index('const EX = ['))]
rows = re.findall(
    r"\{\s*id:'([^']+)'.*?place:'(\w+)'.*?grp:'(\w+)'.*?name:'([^']+)'.*?equip:'([^']*)'", blk)
home = [{'id': i, 'grp': g, 'name': n, 'equip': e}
        for i, p, g, n, e in rows if p == 'home']

GROUPS = [
    ('chest',     'Грудь',   '#e8624a'),
    ('back',      'Спина',   '#3f8fd6'),
    ('shoulders', 'Плечи',   '#d9a13b'),
    ('arms',      'Руки',    '#8b6ed6'),
    ('legs',      'Ноги',    '#3fa87a'),
    ('glutes',    'Ягодицы', '#c76b3a'),
    ('core',      'Пресс',   '#4fb0a8'),
    ('cardio',    'Кардио',  '#7d8a95'),
]
known = {k for k, _, _ in GROUPS}
lost = [x for x in home if x['grp'] not in known]
if lost:
    print('!! неизвестная группа:', lost); sys.exit(1)

# ---------- 2. картинки ----------
def data_uri(path):
    ext = 'jpeg' if path.endswith('.jpg') else 'webp'
    with open(path, 'rb') as fh:
        return f'data:image/{ext};base64,' + base64.b64encode(fh.read()).decode('ascii')

def pick(ex, pose):
    """A — переснятый кадр, если старое превью было 240×240; B — всегда старое фото."""
    hi = os.path.join(HIRES, ex['id'] + '.jpg')
    if pose == 'a' and os.path.exists(hi):
        return data_uri(hi), True
    p = os.path.join(PHOTOS, ex['id'] + ('_b' if pose == 'b' else '') + '.webp')
    return (data_uri(p), False) if os.path.exists(p) else (None, False)

missing, upgraded = [], []
for ex in home:
    ex['a'], ex['frame'] = pick(ex, 'a')
    ex['b'], _ = pick(ex, 'b')
    if ex['frame']:
        upgraded.append(ex['id'])
    if not ex['a']:
        missing.append(ex['id'])
if missing:
    print('!! нет фото:', missing); sys.exit(1)

# ---------- 3. HTML ----------
cards = []
for key, title, color in GROUPS:
    items = [x for x in home if x['grp'] == key]
    rows_html = []
    for n, ex in enumerate(items, 1):
        b = f'<img class="pb" src="{ex["b"]}" alt="">' if ex['b'] else ''
        mark = '<span class="vid">кадр из видео</span>' if ex['frame'] else ''
        rows_html.append(
            f'<div class="row"><img class="pa" src="{ex["a"]}" alt="">{b}'
            f'<div class="txt"><span class="n">{n}</span>'
            f'<b>{html.escape(ex["name"])}</b>{mark}'
            f'<span class="eq">{html.escape(ex["equip"])}</span></div></div>')
    cards.append(f'<div class="grp" style="--c:{color}">'
                 f'<div class="gh">{title}<b>{len(items)}</b></div>'
                 f'{"".join(rows_html)}</div>')

doc = f'''<meta charset="utf-8">
<title>Дом — {len(home)} упражнений</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#11161a;color:#e6edf3;font:400 13px/1.3 -apple-system,"Segoe UI",Roboto,sans-serif;
     padding:12px 14px}}
header{{display:flex;align-items:baseline;gap:14px;margin-bottom:10px}}
h1{{font-size:17px;font-weight:650}}
.sub{{font-size:12px;color:#8b98a5}}
.hint{{margin-left:auto;font-size:11px;color:#6b7783}}
.sheet{{column-count:6;column-gap:10px}}
.grp{{break-inside:avoid;border:1px solid #232c34;border-radius:8px;background:#161d23;
     overflow:hidden;margin-bottom:10px}}
.gh{{font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;
    padding:5px 9px;background:var(--c);color:#0d1114;display:flex}}
.gh b{{margin-left:auto;opacity:.65}}
.row{{display:flex;gap:8px;padding:5px 7px;border-top:1px solid #1e262d;align-items:center;
     position:relative;cursor:zoom-in}}
.row:first-of-type{{border-top:none}}
.row:hover{{background:#1e262d}}
.pa{{width:104px;height:139px;object-fit:cover;border-radius:5px;flex:0 0 auto;background:#0b0f12}}
.pb{{display:none}}
.txt{{min-width:0}}
.n{{color:#66727d;font-size:11px;font-weight:600;margin-right:5px}}
.txt b{{font-size:14px;font-weight:500;color:#e6edf3}}
.eq{{display:block;margin-top:4px;font-size:11.5px;color:#7f8b96}}
.vid{{display:inline-block;margin-left:6px;padding:1px 5px;border-radius:3px;background:#2b3a44;
     color:#8fd4c4;font-size:9.5px;font-weight:700;vertical-align:2px;white-space:nowrap}}
/* крупный просмотр: слева поза A, справа поза B */
.row::after,.row::before{{content:"";position:fixed;top:50%;width:340px;height:453px;max-height:84vh;
    transform:translateY(-50%) scale(.97);background:center/cover no-repeat #0b0f12;
    border-radius:12px;box-shadow:0 24px 70px #000c,0 0 0 1px #ffffff22;
    opacity:0;pointer-events:none;transition:opacity .12s,transform .12s;z-index:50}}
.row::after{{left:calc(50% - 350px);background-image:var(--a)}}
.row::before{{left:calc(50% + 10px);background-image:var(--b)}}
.row:hover::after,.row:hover::before{{opacity:1;transform:translateY(-50%) scale(1)}}
.row.solo::before{{display:none}}
.row.solo::after{{left:calc(50% - 170px)}}
@media print{{body{{background:#fff;color:#000}}.row::after,.row::before{{display:none}}}}
</style>
<header>
  <h1>ДОМ — {len(home)} упражнений</h1>
  <span class="sub">превью-фото из приложения · при наведении обе позы (A и B)</span>
  <span class="hint">7 помечены «кадр из видео» — они уже сняты, остальные 23 в списке на досъёмку</span>
</header>
<div class="sheet">{"".join(cards)}</div>
<script>
document.querySelectorAll('.row').forEach(r=>{{
  r.style.setProperty('--a','url('+r.querySelector('.pa').src+')');
  const b=r.querySelector('.pb');
  if(b) r.style.setProperty('--b','url('+b.src+')'); else r.classList.add('solo');
}});
</script>'''

open(OUT, 'w', encoding='utf-8').write(doc)
print('домашних упражнений:', len(home))
for k, t, _ in GROUPS:
    print(f'  {t}: {sum(1 for x in home if x["grp"] == k)}')
print('превью 240×240 заменены кадром из видео:', ', '.join(upgraded) or 'нет')
print(os.path.basename(OUT), round(os.path.getsize(OUT) / 1e6, 2), 'МБ')
