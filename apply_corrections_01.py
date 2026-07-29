#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_01.py — партия правок по скриншотам Замира (08.07).
Меняет recipes.json + micronutrients_per_portion.json (+ клон в KBJU/микро для
переименования сахзама). ПЕРЕСЧЁТ порций и 26 микро — 1-в-1 как add_recipe.py
(per100 × вес_группы). Веса порций (g) НЕ трогаем — только КБЖУ/микро.

Запуск:  python3 apply_corrections_01.py --dry   (показать, ничего не писать)
         python3 apply_corrections_01.py          (бэкап + запись)

Правила партии:
  1. Ванилин — во ВСЕХ рецептах база пересчитывается так, чтобы на экране (в самой
     большой группе m90p) было ≤0.1 г. Ванилин ~0 ккал, на КБЖУ почти не влияет.
  2. Экстракт ванили — кап так, чтобы на экране ≤1 г (только если сейчас больше).
  3. Сахарозаменитель → «Сахарозаменитель эритритол» (клон записи в KBJU+микро,
     КБЖУ не меняется, переименование во всех рецептах).
  4. Обведённое ÷2 (по id): сахар fr_179292; пудра fr_74708, fr_184278;
     сухие дрожжи fr_2874; пищевые дрожжи vg_041; соус терияки fr_2729;
     сахзам fr_168839; ванильный сахар fr_184098.
  5. Заметка в шаги про ванилин/экстракт «на кончике ножа».
"""
import json, os, sys, datetime, shutil

DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))

kb_doc = json.load(open('ingredients_kbju.json', encoding='utf-8'))
kb = {e['name']: e for e in kb_doc['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8'))
mi = mi_doc['ingredients']  # dict: name -> {"micro": {...}}
FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8'))
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
byid = {r['id']: r for r in R}

NOTE = ('Ванилин добавляй буквально на кончике ножа (~0.1 г) — не путай его с '
        'ванильным сахаром или экстрактом ванили, их берут больше.')

def per100(ings, table, fields):
    tot = sum(float(i.get('amount_g', 0) or 0) for i in ings)
    out = {f: 0.0 for f in fields}
    if tot <= 0: return out, tot
    for ing in ings:
        rec = table.get(ing.get('id', ''))
        if not rec: continue
        src = rec if fields[0] in rec else (rec.get('micro') or {})
        amt = float(ing.get('amount_g', 0) or 0)
        for f in fields:
            out[f] += (src.get(f, 0) or 0) * amt / tot
    return out, tot

def ing_of(r, name):
    return next((i for i in r['ingredients'] if i.get('id') == name), None)

def total(r):
    return sum(float(i.get('amount_g', 0) or 0) for i in r['ingredients'])

log = []
changed = set()

# --- 1. Ванилин: экранный вес ≤0.1 в m90p ---
van_n = 0
for r in R:
    ing = ing_of(r, 'Ванилин')
    if not ing: continue
    tot = total(r)
    gmax = max((r.get('portions', {}).get(g, {}).get('g', 0) for g in r.get('portions', {})), default=350) or 350
    cur = float(ing.get('amount_g', 0) or 0)
    disp_max = cur * gmax / tot if tot else 0
    if disp_max > 0.1:
        new = round(0.1 * tot / gmax, 3)
        if new < cur:
            ing['amount_g'] = new
            changed.add(r['id']); van_n += 1
# --- 2. Экстракт ванили: экранный вес ≤1 в m90p ---
ext_n = 0
for r in R:
    ing = ing_of(r, 'Экстракт ванили')
    if not ing: continue
    tot = total(r)
    gmax = max((r.get('portions', {}).get(g, {}).get('g', 0) for g in r.get('portions', {})), default=350) or 350
    cur = float(ing.get('amount_g', 0) or 0)
    if cur * gmax / tot > 1.0:
        new = round(1.0 * tot / gmax, 3)
        if new < cur:
            ing['amount_g'] = new
            changed.add(r['id']); ext_n += 1

# --- 3. Переименование сахзама (клон в таблицах) ---
OLD, NEW = 'Сахарозаменитель', 'Сахарозаменитель эритритол'
if OLD in kb and NEW not in kb:
    e = dict(kb[OLD]); e['name'] = NEW; kb_doc['ingredients'].append(e); kb[NEW] = e
if OLD in mi and NEW not in mi:
    mi[NEW] = json.loads(json.dumps(mi[OLD]))  # deep copy, dict keyed by name
ren_n = 0
for r in R:
    for i in r['ingredients']:
        if i.get('id') == OLD:
            i['id'] = NEW; changed.add(r['id']); ren_n += 1

# --- 4. Обведённое ÷2 ---
HALVE = [('fr_179292', 'Сахар'), ('fr_74708', 'Сахарная пудра'),
         ('fr_184278', 'Сахарная пудра'), ('fr_2874', 'Сухие дрожжи'),
         ('vg_041', 'Пищевые дрожжи'), ('fr_2729', 'Соус терияки'),
         ('fr_168839', 'Сахарозаменитель эритритол'), ('fr_184098', 'Ванильный сахар')]
halve_log = []
for rid, name in HALVE:
    r = byid.get(rid)
    if not r:
        halve_log.append(f'  ⚠ {rid} НЕ найден'); continue
    ing = ing_of(r, name)
    if not ing:
        # попробуем частичное совпадение
        ing = next((i for i in r['ingredients'] if name.split()[0].lower() in (i.get('id') or '').lower()), None)
    if not ing:
        halve_log.append(f'  ⚠ {rid}: нет ингредиента ~«{name}» (есть: {[i["id"] for i in r["ingredients"]]})'); continue
    old = float(ing.get('amount_g', 0) or 0)
    ing['amount_g'] = round(old / 2, 3)
    changed.add(rid)
    halve_log.append(f'  ✓ {rid} {r["name"][:28]:28} {ing["id"]}: {old}→{ing["amount_g"]} г')

# --- 5. Заметка в шаги (ванилин/экстракт) ---
note_n = 0
for r in R:
    has = any(i.get('id') in ('Ванилин', 'Экстракт ванили') for i in r['ingredients'])
    if has:
        instr = r.get('instructions') or []
        if not any('на кончике ножа' in s for s in instr):
            instr.append(NOTE); r['instructions'] = instr
            changed.add(r['id']); note_n += 1

# --- ПЕРЕСЧЁТ порций + микро для всех изменённых ---
for rid in changed:
    r = byid[rid]
    k100, _ = per100(r['ingredients'], kb, KBF)
    m100, _ = per100(r['ingredients'], mi, FIELDS)
    for g, pg in r.get('portions', {}).items():
        gg = pg.get('g', 0)
        pg['kcal'] = round(k100['calories'] * gg / 100)
        pg['p'] = round(k100['protein'] * gg / 100, 1)
        pg['f'] = round(k100['fat'] * gg / 100, 1)
        pg['c'] = round(k100['carbs'] * gg / 100, 1)
    d = MP.get('dishes', {}).get(rid)
    if d:
        d['per100g'] = {f: round(m100[f], 3) for f in FIELDS}
        for g, gr in d.get('groups', {}).items():
            gg = gr.get('g', 0)
            for f in FIELDS:
                gr[f] = round(m100[f] * gg / 100, 3)

print(f'Ванилин пересчитан: {van_n} | Экстракт: {ext_n} | Сахзам переименован: {ren_n} поз. | Заметок добавлено: {note_n}')
print('÷2 обведённое:')
print('\n'.join(halve_log))
print(f'ВСЕГО изменено рецептов: {len(changed)}')

if DRY:
    print('\n[DRY] ничего не записано.')
    sys.exit()

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json', 'ingredients_kbju.json', 'micronutrients.json']:
    shutil.copy(f, f'backups/{f}.before_corr01_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(kb_doc, open('ingredients_kbju.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(mi_doc, open('micronutrients.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_corr01_{stamp}')
