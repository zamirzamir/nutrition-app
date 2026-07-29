#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_04_sugar15.py — ЗАДАЧА 2: сахар ≤15 г на 100 г блюда (=15% веса).
Сначала ОТКАТ всех прежних правок сахара (восстановить исходный «Сахар» из
before_corr01), затем кап: где сахар >15% веса → new = 0.15*(тотал_без_сахара)/0.85.
Пересчёт КБЖУ+микро на ТЕКУЩИЕ веса порций (у запеканок уже вшитые 80–140).
  python3 apply_corrections_04_sugar15.py --dry  |  без --dry = бэкап+запись
"""
import json, os, sys, datetime, shutil, glob
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))

kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8'))
mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8'))
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
ORIG = {r['id']: r for r in json.load(open('backups/recipes.json.before_corr01_20260708_111750', encoding='utf-8'))}

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
def sugar_ing(r): return next((i for i in r['ingredients'] if i.get('id') == 'Сахар'), None)

reverted = 0; capped = []
touched = set()
for r in R:
    ing = sugar_ing(r)
    if not ing: continue
    o = ORIG.get(r['id'])
    if not o: continue
    oing = sugar_ing(o)
    if not oing: continue
    orig_amt = oing['amount_g']
    # 1) откат к исходному
    if abs(ing['amount_g'] - orig_amt) > 1e-6:
        ing['amount_g'] = orig_amt; reverted += 1; touched.add(r['id'])
    # 2) кап 15%
    tot = sum(i.get('amount_g', 0) for i in r['ingredients'])
    if tot > 0 and ing['amount_g'] / tot > 0.15:
        base = tot - ing['amount_g']              # масса без сахара
        new = round(0.15 * base / 0.85, 3)
        capped.append((round(ing['amount_g']/tot*100, 1), r['id'], r['name'][:32], ing['amount_g'], new))
        ing['amount_g'] = new; touched.add(r['id'])

# пересчёт КБЖУ+микро на текущие веса порций
for rid in touched:
    r = next(x for x in R if x['id'] == rid)
    k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
    for g, pg in r.get('portions', {}).items():
        gg = pg['g']
        pg['kcal'] = round(k['calories'] * gg / 100); pg['p'] = round(k['protein'] * gg / 100, 1)
        pg['f'] = round(k['fat'] * gg / 100, 1); pg['c'] = round(k['carbs'] * gg / 100, 1)
    d = MP.get('dishes', {}).get(rid)
    if d:
        d['per100g'] = {f: round(m[f], 3) for f in FIELDS}
        for g, gr in d.get('groups', {}).items():
            gg = gr['g']
            for f in FIELDS: gr[f] = round(m[f] * gg / 100, 3)

print(f'Откат сахара к исходному: {reverted} рец. | Кап 15%: {len(capped)} рец. | Всего затронуто: {len(touched)}')
print('топ-12 капнутых (было% → грамм было→стало):')
for pc, rid, nm, ob, nb in sorted(capped, reverse=True)[:12]:
    print(f'   {pc:>4}%  {rid:11} {nm:32} {ob}→{nb} г')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_sugar15_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_sugar15_{stamp}')
