#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_10_water_nonpasta.py — не-паста вода по вердикту субагента.
Ставит Вода=нужное значение, пересчёт КБЖУ+микро. python3 ... --dry | без --dry = запись.
"""
import json, os, sys, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8')); byid = {r['id']: r for r in R}
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

SET = {
    # овощ/картофель/грибы/бланш отварены и слиты → 0
    'fr_2291': 0, 'fr_229239': 0, 'fr_270493': 0, 'fr_176269': 0, 'fr_231359': 0, 'fr_251593': 0, 'fr_230473': 0,
    # крупа/паста/бобовые слиты → впитавшееся (2.5×крупы / 1.2×пасты)
    'fr_216575': 83, 'fr_191404': 423, 'fr_234846': 63, 'fr_163743': 500, 'fr_232912': 450,
    'poy_veg_020': 540, 'poy_veg_087': 240,
    # смешанные — в блюде только соус/тесто/заливка
    'fr_189853': 375, 'fr_189585': 250, 'fr_189624': 250, 'fr_216507': 247,
    # категория A, но воды физически не впитать (крупа на порцию, вода на весь рецепт) → 2.5×крупы
    'fr_239969': 137, 'fr_231544': 137, 'fr_197498': 83, 'fr_158910': 158,
}

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

rows = []
for rid, neww in SET.items():
    r = byid.get(rid)
    if not r: rows.append((rid, 'НЕТ', '', '')); continue
    w = next((i for i in r['ingredients'] if i['id'] == 'Вода'), None)
    if not w: rows.append((rid, r['name'][:30], 'нет воды', '')); continue
    old = w['amount_g']; w['amount_g'] = neww
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
    rows.append((rid, r['name'][:30], f'{old}→{neww}г', f'm70 {r["portions"]["m70"]["kcal"]}ккал'))

print(f'Изменено рецептов: {sum(1 for x in rows if "→" in str(x[2]))}')
for rid, nm, ch, kc in rows: print(f'   {rid:12} {nm:30} {ch:14} {kc}')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_water2_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_water2_{stamp}')
