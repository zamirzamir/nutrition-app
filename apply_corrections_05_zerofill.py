#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_05_zerofill.py — ЗАДАЧА: автозаполнение 0г-приправ.
Правила (концентрация X г на 100 г блюда, затем потолок в граммах базового веса):
  соль        1 г/100г,  потолок 1.5 г   (сладкое блюдо: 0.2 г/100г, потолок 0.5 г)
  перец       0.2 г/100г, потолок 0.5 г   (БОЛГАРСКИЙ/СЛАДКИЙ перец — овощ, НЕ трогаем)
  свеж.зелень 3 г/100г,  потолок 8 г
  сух.зелень  0.4 г/100г, потолок 1 г
  горчица     3 г/100г,  потолок 5 г
Только там, где сейчас 0 г. Пересчёт КБЖУ+микро (соль даёт натрий).
  python3 apply_corrections_05_zerofill.py --dry  |  без --dry = бэкап+запись
"""
import json, os, sys, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8'))
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

SWEET_DT = ['выпечка_десерт', 'блины_оладьи', 'запеканка']
def is_sweet(r):
    dt = (r.get('tags') or {}).get('dish_type', '')
    if dt in SWEET_DT: return True
    nm = (r.get('name') or '').lower()
    return any(x in nm for x in ['десерт','сырник','панкейк','вафл','кекс','маффин','брауни','чизкейк','сладк','запеканк','блин','оладь'])

def rule(ingname, sweet):
    s = ingname.lower()
    if 'болгарск' in s or 'сладкий перец' in s: return None      # овощ
    if 'сем' in s: return None                                   # семена/семечки, не зелень
    if s == 'соль' or s.startswith('соль'):
        return (0.2, 0.5) if sweet else (1.0, 1.5)
    if 'горчиц' in s: return (3.0, 5.0)
    if 'перец' in s: return (0.2, 0.5)
    for d in ['сушен','сушён','прован','орегано','тимьян','розмарин']:
        if d in s: return (0.4, 1.0)
    for f in ['укроп','петрушк','кинза','базилик','рукол','зелень','зелён','мята','шпинат','салат','микс салат']:
        if f in s: return (3.0, 8.0)
    return None

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

touched = set(); filled = []
from collections import Counter
bycat = Counter()
for r in R:
    sweet = is_sweet(r)
    tot0 = sum(i.get('amount_g', 0) for i in r['ingredients'])
    # опорная порция m70 (сколько человек реально съедает) — от неё считаем потолок
    pm70 = ((r.get('portions') or {}).get('m70') or {}).get('g') or 275
    for i in r['ingredients']:
        if (i.get('amount_g') or 0) != 0: continue
        rl = rule(i['id'], sweet)
        if not rl: continue
        per, cap = rl
        # плотность = min(X/100, потолок/порция_m70); базовый вес = плотность × сумма блюда
        dens = min(per / 100.0, cap / pm70) if pm70 else per / 100.0
        newamt = round(dens * tot0, 3)
        if newamt <= 0: continue
        i['amount_g'] = newamt; touched.add(r['id'])
        bycat[i['id'].split()[0]] += 1
        disp70 = round(newamt * pm70 / tot0, 2) if tot0 else newamt
        filled.append((r['id'], r['name'][:26], i['id'], newamt, disp70, tot0, sweet))

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

print(f'Заполнено 0г-приправ: {len(filled)} позиций в {len(touched)} рецептах')
print('по категориям:', dict(bycat))
print('\nПРИМЕРЫ (приправа | на порцию m70 | база | блюдо | сладкое?):')
seen = set()
for rid, nm, ing, amt, disp70, tot0, sw in filled:
    key = (ing, sw)
    if key in seen: continue
    seen.add(key)
    print(f'   {ing:24} на порцию ~{disp70:>4} г  (база {amt:>5}г, блюдо {tot0:.0f}г, сладк={sw})')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_zerofill_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_zerofill_{stamp}')
