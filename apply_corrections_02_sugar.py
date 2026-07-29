#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_02_sugar.py — сахар ÷2 в СЛАДКИХ блюдах, где на экране (m90p) >20 г.
Один проход. Несладкие (с мясом/рыбой) исключаются. Пересчёт порций+микро.
  python3 apply_corrections_02_sugar.py --dry   |   без --dry = бэкап+запись
"""
import json, os, sys, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))

kb_doc = json.load(open('ingredients_kbju.json', encoding='utf-8'))
kb = {e['name']: e for e in kb_doc['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8'))
mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8'))
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

MEAT = ['свинин', 'говядин', 'куриц', 'курин', 'индейк', 'фарш', 'мясо', 'бекон',
        'ветчин', 'колбас', 'сосиск', 'рыб', 'креветк', 'лосос', 'тунец', 'форел',
        'кальмар', 'краб', 'сельд', 'скумбри']

def per100(ings, table, fields):
    tot = sum(float(i.get('amount_g', 0) or 0) for i in ings)
    out = {f: 0.0 for f in fields}
    if tot <= 0: return out
    for ing in ings:
        rec = table.get(ing.get('id', ''))
        if not rec: continue
        src = rec if fields[0] in rec else (rec.get('micro') or {})
        amt = float(ing.get('amount_g', 0) or 0)
        for f in fields: out[f] += (src.get(f, 0) or 0) * amt / tot
    return out

def is_savory(r):
    for i in r['ingredients']:
        nm = (i.get('id') or '').lower()
        if 'яйц' in nm:  # «Куриное яйцо» — не мясо
            continue
        if any(m in nm for m in MEAT):
            return True
    return False

changed = []; skipped_savory = []; still_high = []
for r in R:
    ing = next((i for i in r['ingredients'] if i.get('id') == 'Сахар'), None)
    if not ing: continue
    tot = sum(i.get('amount_g', 0) for i in r['ingredients'])
    gmax = max((g['g'] for g in r.get('portions', {}).values()), default=350) or 350
    disp = ing['amount_g'] * gmax / tot if tot else 0
    if disp <= 20: continue
    if is_savory(r):
        skipped_savory.append((r['id'], r['name'][:30], round(disp, 1))); continue
    old = ing['amount_g']; ing['amount_g'] = round(old / 2, 3)
    changed.append(r['id'])
    new_disp = ing['amount_g'] * gmax / (tot - old + ing['amount_g'])
    if new_disp > 20: still_high.append((r['id'], r['name'][:30], round(new_disp, 1)))

# пересчёт
for rid in changed:
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

print(f'Сахар ÷2: изменено {len(changed)} сладких рецептов.')
print(f'Пропущено несладких (мясо/рыба): {len(skipped_savory)} → {skipped_savory}')
print(f'После ÷2 всё ещё >20 г на экране: {len(still_high)} (топ) → {sorted(still_high,key=lambda x:-x[2])[:12]}')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_sugar_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_sugar_{stamp}')
