#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_09_pastawater.py — п.9 (безопасное подмножество): варочную воду
паст/лапши свести к ВПИТАВШЕЙСЯ. Варёная паста ~2.25× сухой → вода ≈ 1.25× сухой пасты.
Только паста+слив в шагах+НЕ суп+вода>30%. Пересчёт КБЖУ+микро.
  python3 ... --dry | без --dry = бэкап+запись
"""
import json, os, sys, re, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8')); MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
byid = {r['id']: r for r in R}

DRAIN = re.compile(r'слей|слить|отки[нд]|дуршлаг|откинь', re.I)
PASTA = ['макарон', 'спагетти', 'вермишел', 'лапш', 'фузилли', 'пенне', 'рожки', 'фарфалле', 'тальятел', 'удон', 'соба', 'феттуч', 'букатини']
SOUP = re.compile(r'суп|шурпа|борщ|\bщи\b|бульон|похлёб|похлеб|уха|рассольник|солянк|харчо|лагман|рамен|том.?ям', re.I)
ABSORB = 1.25  # вода впитавшаяся = 1.25× сухой пасты (варёная ~2.25×)

def per100(ings, table, fields):
    tot = sum(float(i.get('amount_g', 0) or 0) for i in ings); out = {f: 0.0 for f in fields}
    if tot <= 0: return out
    for ing in ings:
        rec = table.get(ing.get('id', ''))
        if not rec: continue
        src = rec if fields[0] in rec else (rec.get('micro') or {})
        amt = float(ing.get('amount_g', 0) or 0)
        for f in fields: out[f] += (src.get(f, 0) or 0) * amt / tot
    return out

targets = []
for r in R:
    ings = r['ingredients']; nm = r['name']
    w = next((i for i in ings if i['id'] == 'Вода'), None)
    if not w or w['amount_g'] <= 0: continue
    tot = sum(i.get('amount_g', 0) for i in ings); wshare = w['amount_g'] / tot if tot else 0
    pasta_g = sum(i.get('amount_g', 0) for i in ings if any(p in (i.get('id') or '').lower() for p in PASTA))
    if pasta_g <= 0 or wshare <= 0.30: continue
    steps = ' '.join(r.get('instructions') or [])
    if not DRAIN.search(steps): continue
    if r.get('tags', {}).get('dish_type') == 'суп' or SOUP.search(nm) or SOUP.search(steps.lower()): continue
    targets.append((r, w, pasta_g))

samples = []
for r, w, pasta_g in targets:
    old = w['amount_g']; w['amount_g'] = round(ABSORB * pasta_g)
    k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
    for g, pg in r.get('portions', {}).items():
        gg = pg['g']
        pg['kcal'] = round(k['calories'] * gg / 100); pg['p'] = round(k['protein'] * gg / 100, 1)
        pg['f'] = round(k['fat'] * gg / 100, 1); pg['c'] = round(k['carbs'] * gg / 100, 1)
    d = MP.get('dishes', {}).get(r['id'])
    if d:
        d['per100g'] = {f: round(m[f], 3) for f in FIELDS}
        for g, gr in d.get('groups', {}).items():
            gg = gr['g']
            for f in FIELDS: gr[f] = round(m[f] * gg / 100, 3)
    if len(samples) < 12:
        newtot = sum(i.get('amount_g', 0) for i in r['ingredients'])
        samples.append((r['id'], r['name'][:34], old, w['amount_g'], round(pasta_g), round(newtot), r['portions']['m70']['kcal']))

print(f'Паст исправлено: {len(targets)}')
print('id | блюдо | вода было→стало | паста | новый вес базы | m70 ккал')
for rid, nm, ob, nb, pg, nt, kc in samples:
    print(f'   {rid:12} {nm:34} {ob}→{nb}г  паста {pg}г  база {nt}г  m70 {kc}ккал')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_pastawater_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_pastawater_{stamp}')
