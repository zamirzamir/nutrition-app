#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_corrections_12_composition.py — состав-правки ночного прогона."""
import json, os, datetime, shutil, sys
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8')); byid = {r['id']: r for r in R}
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
ZAP = {'f60': 80, 'm70': 100, 'f80': 100, 'm90': 120, 'f80p': 120, 'm90p': 140}

def per100(ings, table, fields):
    tot = sum(float(i.get('amount_g', 0) or 0) for i in ings); out = {f: 0.0 for f in fields}
    if tot <= 0: return out
    for ing in ings:
        rec = table.get(ing.get('id', ''))
        if not rec: continue
        src = rec if fields[0] in rec else (rec.get('micro') or {})
        a = float(ing.get('amount_g', 0) or 0)
        for f in fields: out[f] += (src.get(f, 0) or 0) * a / tot
    return out
def recompute(rid):
    r = byid[rid]; k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
    for g, pg in r.get('portions', {}).items():
        gg = pg['g']; pg['kcal'] = round(k['calories']*gg/100); pg['p'] = round(k['protein']*gg/100,1)
        pg['f'] = round(k['fat']*gg/100,1); pg['c'] = round(k['carbs']*gg/100,1)
    d = MP.get('dishes', {}).get(rid)
    if d:
        d['per100g'] = {f: round(m[f],3) for f in FIELDS}
        for g, gr in d.get('groups', {}).items():
            gg = gr['g']
            for f in FIELDS: gr[f] = round(m[f]*gg/100,3)
log = []

# 1) ÷2 кленовый сироп (vg_033), мускат (vt_036)
for rid, sub in [('vg_033', 'сироп'), ('vt_036', 'мускат')]:
    r = byid.get(rid)
    if r:
        for i in r['ingredients']:
            if sub in i['id'].lower():
                o = i['amount_g']; i['amount_g'] = round(o/2, 3); log.append(f'{rid} {i["id"]}: {o}→{i["amount_g"]}')
        recompute(rid)

# 2) vt_008 мука→Макароны + вода
r = byid.get('vt_008')
if r:
    for i in r['ingredients']:
        if 'мука' in i['id'].lower(): i['id'] = 'Макароны'; log.append(f'vt_008 мука→Макароны {i["amount_g"]}г')
    mac = sum(i['amount_g'] for i in r['ingredients'] if i['id'] == 'Макароны')
    w = next((i for i in r['ingredients'] if i['id'] == 'Вода'), None)
    if not w and mac > 0: r['ingredients'].append({'id': 'Вода', 'amount_g': round(mac*2)}); log.append(f'vt_008 +Вода {round(mac*2)}г')
    recompute('vt_008')

# 3) переименования блюд
for rid, newname in [('fr_216794', 'Необычные панкейки'), ('fr_235607', 'Оригинальный лагман'),
                     ('fr_154976', 'Тушёный картофель с индейкой')]:
    if byid.get(rid): byid[rid]['name'] = newname; log.append(f'{rid} → «{newname}»')

# 4) ингредиент «Азу из индейки» → «Индейка»
for r in R:
    for i in r['ingredients']:
        if i['id'] == 'Азу из индейки': i['id'] = 'Индейка'; log.append(f'{r["id"]} Азу→Индейка'); recompute(r['id'])

# 5) удалить дубли п.14 + генерик йогурт
DEL = {'pdf_540111','pdf_540074','pdf_540081','pdf_540095','pdf_540097','pdf_540091','pdf_540100','sn_274094'}
before = len(R)
R[:] = [r for r in R if r['id'] not in DEL]
byid = {r['id']: r for r in R}
for d in DEL: MP.get('dishes', {}).pop(d, None)
log.append(f'удалено дублей/йогурта: {before-len(R)} ({sorted(DEL)})')

# 6) бренд-продукты → фикс-вес упаковки
BRAND_W = {
 'Активиа натуральная':130,'Активиа творожная':130,'Питьевой йогурт Активиа':260,
 'Даниссимо классический':130,'Даниссимо пломбир':130,'Даниссимо с хрустящими шариками':105,
 'Йогурт Epica натуральный 6%':130,'Йогурт Epica с вишней':130,'Йогурт Чудо персик-маракуйя':290,
 'Питьевой йогурт Имунеле':100,'Творожок Простоквашино 5%':120,'Творожок Растишка':100,
 'Творожок Чудо воздушный':85,'Творожок Чудо клубника':100,'Творожок Чудо черника':100,
 'Творожок Чудо шоколад':100,'Чудо батончик':40}
bn = 0
for r in R:
    hit = [i for i in r['ingredients'] if i['id'] in BRAND_W]
    if len(hit) == 1 and len(r['ingredients']) == 1:   # односоставной брендовый снек
        w = BRAND_W[hit[0]['id']]; hit[0]['amount_g'] = w
        r.setdefault('tags', {})['fixed_g'] = True
        for g in ZAP: r.setdefault('portions', {})[g] = {'g': w}
        recompute(r['id']); bn += 1
log.append(f'бренд-продукты → фикс-вес: {bn}')

print('ИЗМЕНЕНИЯ:')
for l in log: print('  ', l)
print('рецептов теперь:', len(R))
if DRY:
    print('\n[DRY]'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); os.makedirs('backups', exist_ok=True)
for f in ['recipes.json','micronutrients_per_portion.json']: shutil.copy(f, f'backups/{f}.before_comp_{stamp}')
json.dump(R, open('recipes.json','w',encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json','w',encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап before_comp_{stamp}')
