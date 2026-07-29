#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_03_fixweights.py — ЗАДАЧА 1: вшить фикс-веса в список.
Набор = сладкие запеканки (isSweetZapekanka) + творог>60% (не запеканки).
Каждому: tags.fixed_g=true; portions[группа].g = ZAP_FIXED_G[группа] для всех 6 групп;
пересчёт kcal/p/f/c и 26 микро на новый вес.
  python3 apply_corrections_03_fixweights.py --dry  |  без --dry = бэкап+запись
"""
import json, os, sys, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))

ZAP_FIXED_G = {'f60': 80, 'm70': 100, 'f80': 100, 'm90': 120, 'f80p': 120, 'm90p': 140}
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8'))
mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8'))
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

ZAP_SAV = ['мясо','фарш','говяд','свин','телятин','баран','куриное филе','куриная грудк','куриное бедро',
 'куриный фарш','курица','курицей','цыпл','индейк','индюш','рыб','лосос','тунец','минтай','треск','семг',
 'горбуш','сельд','креветк','кальмар','краб','мидии','ветчин','бекон','колбас','сосиск','карбонад',
 'картоф','картош','макарон','вермишел','спагетти','капуст','кабачок','цукини','баклажан','брокколи',
 'цветная','шампинь','вешенк','чечевиц','фасол','горох','шпинат']
def savory(idn):
    s = (idn or '').lower()
    if 'крахмал' in s or 'яйцо' in s: return False
    return any(x in s for x in ZAP_SAV)
def is_zap(r):
    nm = (r.get('name') or '').lower(); dt = (r.get('tags') or {}).get('dish_type', '')
    if 'запеканк' not in nm and dt != 'запеканка': return False
    ings = r['ingredients']
    if not any('творог' in (i.get('id') or '').lower() for i in ings): return False
    if any(savory(i.get('id')) for i in ings): return False
    return True
def tvorog_share(r):
    tot = sum(i.get('amount_g', 0) for i in r['ingredients'])
    tw = sum(i.get('amount_g', 0) for i in r['ingredients'] if 'творог' in (i.get('id') or '').lower())
    return (tw / tot) if tot else 0
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

zap = [r for r in R if is_zap(r)]
tv60 = [r for r in R if tvorog_share(r) > 0.60 and not is_zap(r)]
fixset = {r['id']: r for r in (zap + tv60)}
print(f'Сладкие запеканки: {len(zap)} | Творог>60% (не запеканки): {len(tv60)} | ИТОГО фикс-набор: {len(fixset)}')

for rid, r in fixset.items():
    r.setdefault('tags', {})['fixed_g'] = True
    k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
    for g in ZAP_FIXED_G:
        gg = ZAP_FIXED_G[g]
        r.setdefault('portions', {}).setdefault(g, {})
        r['portions'][g] = {'g': gg,
            'kcal': round(k['calories'] * gg / 100), 'p': round(k['protein'] * gg / 100, 1),
            'f': round(k['fat'] * gg / 100, 1), 'c': round(k['carbs'] * gg / 100, 1)}
    d = MP.get('dishes', {}).get(rid)
    if d:
        d['per100g'] = {f: round(m[f], 3) for f in FIELDS}
        d.setdefault('groups', {})
        for g in ZAP_FIXED_G:
            gg = ZAP_FIXED_G[g]
            d['groups'][g] = {'g': gg, **{f: round(m[f] * gg / 100, 3) for f in FIELDS}}

# показать пример
ex = zap[0]
print('пример:', ex['id'], ex['name'], '→ portions g:', {g: p['g'] for g, p in ex['portions'].items()},
      '| m70:', ex['portions']['m70']['kcal'], 'ккал')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_fixw_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_fixw_{stamp}')
