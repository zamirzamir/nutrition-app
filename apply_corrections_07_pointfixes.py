#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_07_pointfixes.py — batch A1: точечные правки рецептов.
  паста fr_229219: убрать Авокадо + Вода(слив); добавить Хлеб цельнозерновой ~40г/порц
  чечевица poy_vegan_002: добавить Рис ~30г/порц + Вода +90г/порц (варка) + шаг
  запеканка fr_229108: meal_type → snack
  гречаники fr_206563: убрать Макароны; имя → «Котлеты из курицы и гречки»
  смузи fr_252886: убрать дубль-клубнику 0г; клубнику урезать до ~100г/порц на экране
Пересчёт КБЖУ+микро. python3 ... --dry | без --dry = бэкап+запись
"""
import json, os, sys, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8')); byid = {r['id']: r for r in R}
MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

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
def tot_of(r): return sum(i.get('amount_g', 0) for i in r['ingredients'])
def pm70(r): return (r.get('portions', {}).get('m70', {}) or {}).get('g') or 275
changed = set()

# 1) ПАСТА fr_229219 — убрать Авокадо, Тостовый хлеб(0г), Вода(слив-разморозка)
r = byid['fr_229219']
r['ingredients'] = [i for i in r['ingredients'] if i['id'] not in ('Авокадо', 'Вода', 'Тостовый хлеб')]
T = tot_of(r); P = pm70(r)
base_bread = round(40 * T / (P - 40), 1)           # чтобы на порцию m70 вышло ~40г
r['ingredients'].append({'id': 'Хлеб цельнозерновой', 'amount_g': base_bread})
changed.add('fr_229219')

# 2) ЧЕЧЕВИЦА poy_vegan_002 — убрать варочную воду чечевицы (сливается!),
#    добавить сухой Рис 30г/порц + вода на рис 90г/порц (впитывается)
r = byid['poy_vegan_002']
r['ingredients'] = [i for i in r['ingredients'] if i['id'] != 'Вода']
T = tot_of(r); P = pm70(r)                          # T без воды и без риса
rice = round(30 * T / (P - 120), 1); wateradd = round(90 * T / (P - 120), 1)
if not any(i['id'] == 'Рис' for i in r['ingredients']):
    r['ingredients'].append({'id': 'Рис', 'amount_g': rice})
else:
    next(i for i in r['ingredients'] if i['id'] == 'Рис')['amount_g'] = rice
r['ingredients'].append({'id': 'Вода', 'amount_g': wateradd})
ins = r.get('instructions') or []
if not any('рис' in s.lower() and 'отвар' in s.lower() for s in ins):
    ins.insert(1, 'Промойте рис и отварите в подсолённой воде до готовности.')
r['instructions'] = ins
changed.add('poy_vegan_002')

# 3) ЗАПЕКАНКА без манки fr_229108 → snack
byid['fr_229108']['meal_type'] = ['snack']; changed.add('fr_229108')

# 4) ГРЕЧАНИКИ fr_206563 → котлеты, убрать макароны
r = byid['fr_206563']
r['ingredients'] = [i for i in r['ingredients'] if i['id'] != 'Макароны']
r['name'] = 'Котлеты из курицы и гречки'
r['instructions'] = [s.replace('гречаники', 'котлеты').replace('Гречаники', 'Котлеты') for s in (r.get('instructions') or [])]
changed.add('fr_206563')

# 5) СМУЗИ fr_252886 — убрать дубль-клубнику 0г, урезать клубнику до ~100г/порц m70
r = byid['fr_252886']
# удалить нулевую клубнику (оставить одну — основную)
kl = [i for i in r['ingredients'] if i['id'] == 'Клубника']
r['ingredients'] = [i for i in r['ingredients'] if i['id'] != 'Клубника']
main_kl = max(kl, key=lambda i: i['amount_g']) if kl else {'id': 'Клубника', 'amount_g': 0}
O = tot_of(r); P = pm70(r)                          # прочие ингредиенты (без клубники)
newkl = round(100 * O / (P - 100), 1)               # displayed m70 ~100г
main_kl['amount_g'] = newkl
r['ingredients'].append(main_kl)
changed.add('fr_252886')

# --- пересчёт КБЖУ+микро ---
for rid in changed:
    r = byid[rid]; k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
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

# отчёт
for rid in ['fr_229219', 'poy_vegan_002', 'fr_229108', 'fr_206563', 'fr_252886']:
    r = byid[rid]; T = tot_of(r); P = pm70(r)
    print(f'--- {rid} | {r["name"]} | meal={r.get("meal_type")} ---')
    for i in r['ingredients']:
        print(f'     {i["id"]:26} {i["amount_g"]}г  экран_m70~{i["amount_g"]*P/T:.1f}г')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_point_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_point_{stamp}')
