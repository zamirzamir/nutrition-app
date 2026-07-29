#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_recipes.py — ТОЛЬКО ЧТЕНИЕ (ничего не меняет). Собирает по всей базе то, что просил Замир:
  1) 0г-ингредиенты: сколько раз и в каких рецептах;
  2) бренды и кавычки в ШАГАХ;
  3) дроби / ч.л. / ст.л. / щепотки / стаканы в шагах;
  4) дрожжи — по типам (пекарские vs пищевые);
  5) творог >60% веса блюда (кандидаты на фикс), по приёмам;
  6) овощи с весом 0 (кандидаты на подсказку «можно добавить»);
  7) разрыхлитель 0г.
Запуск:  python3 audit_recipes.py        (печатает сводку)
         python3 audit_recipes.py fr_229219   (показать один рецепт целиком)
"""
import json, re, sys
from collections import Counter, defaultdict

R = json.load(open('recipes.json', encoding='utf-8'))
def ings(r):  return r.get('ingredients') or []
def steps(r): return '\n'.join(r.get('instructions') or [])
def meals(r): return r.get('meal_type') or []

# режим показа одного рецепта
if len(sys.argv) > 1 and sys.argv[1].startswith(('fr_','vt_','vg_','pdf_','sn_','poy','vk')):
    r = next((x for x in R if x['id'] == sys.argv[1]), None)
    if not r: print('нет такого id'); sys.exit()
    print(r['id'], '|', r['name'], '| meal:', meals(r), '| dish_type:', (r.get('tags') or {}).get('dish_type'))
    for i in ings(r): print('   ', i.get('id'), '=', i.get('amount_g'), 'г')
    for n, s in enumerate(r.get('instructions') or [], 1): print(f'  Шаг {n}: {s}')
    sys.exit()

BRANDS = ['global village','выгодно и удобно','красная цена','рестория','станция молочная',
          'селяночка','простоквашино','активиа','растишка','danone','эрмигурт','чудо','агуша']
SEEDS  = ['семена','кунжут','лен','лён','чиа','семеч']
GREENS = ['укроп','петрушк','кинза','базилик','зелен','рукола','розмарин','тимьян','орегано','мята','шпинат']
VEG    = ['овощ','огурец','помидор','томат','салатн','капуст','брокколи','морков','перец болг','кабачок','редис','цукини','руккол']
FRAC_RE = re.compile(r'\d\s*/\s*\d|½|¼|¾|\bч\.?\s?л\.?|\bст\.?\s?л\.?|чайн\w*\s+ложк|столов\w*\s+ложк|щепот|стакан|горст', re.I)

# 1) 0г
zero = Counter(); zero_by = defaultdict(list)
for r in R:
    for i in ings(r):
        if (i.get('amount_g') or 0) == 0:
            zero[i.get('id')] += 1; zero_by[i.get('id')].append(r['id'])
print('=== 1) 0г-ИНГРЕДИЕНТЫ ===')
print('рецептов с 0г:', len({rid for ids in zero_by.values() for rid in ids}), '| всего позиций:', sum(zero.values()))
for ing, c in zero.most_common(60): print(f'   {c:4}  {ing}')

# 2) бренды/кавычки в шагах
print('\n=== 2) БРЕНДЫ и КАВЫЧКИ в шагах ===')
bh = defaultdict(list); quotes = []
for r in R:
    s = steps(r).lower()
    for b in BRANDS:
        if b in s: bh[b].append(r['id'])
    if re.search(r'[«»"“”]', steps(r)): quotes.append(r['id'])
for b, ids in sorted(bh.items(), key=lambda x:-len(x[1])): print(f'   {b}: {len(ids)}  {ids[:5]}')
print('рецептов с кавычками в шагах:', len(quotes), '(первые):', quotes[:10])

# 3) дроби/ложки в шагах
frac = [r['id'] for r in R if FRAC_RE.search(steps(r))]
print('\n=== 3) ДРОБИ/ЛОЖКИ/ЩЕПОТКИ/СТАКАНЫ в шагах ===')
print('рецептов:', len(frac), '(первые):', frac[:15])

# 4) дрожжи по типам
print('\n=== 4) ДРОЖЖИ по типам ===')
dz = Counter()
for r in R:
    for i in ings(r):
        n = (i.get('id') or '').lower()
        if 'дрожж' in n: dz[i.get('id')] += 1
for name, c in dz.most_common(): print(f'   {c:4}  {name}')

# 5) творог >60%
print('\n=== 5) ТВОРОГ >60% веса (по приёмам) ===')
for r in R:
    tot = sum((i.get('amount_g') or 0) for i in ings(r))
    tw  = sum((i.get('amount_g') or 0) for i in ings(r) if 'творог' in (i.get('id') or '').lower())
    if tot > 0 and tw/tot > 0.60:
        print(f"   {r['id']:12} {int(tw/tot*100):3}%  {r['name'][:38]:38}  meal={','.join(meals(r))}  type={(r.get('tags') or {}).get('dish_type')}")

# 6) овощи 0г (подсказка «можно добавить»)
print('\n=== 6) ОВОЩИ с весом 0 (кандидаты на подсказку) ===')
vz = [r['id'] for r in R if any((i.get('amount_g') or 0)==0 and any(v in (i.get('id') or '').lower() for v in VEG) for i in ings(r))]
print('рецептов:', len(vz), '(первые):', vz[:15])

# 7) разрыхлитель 0г
rz = [r['id'] for r in R if any('разрыхл' in (i.get('id') or '').lower() and (i.get('amount_g') or 0)==0 for i in ings(r))]
print('\n=== 7) РАЗРЫХЛИТЕЛЬ 0г ===')
print('рецептов:', len(rz), rz[:15])
