#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_recipes.py — приведение recipes.json к правилу проекта:
  «Полный (многопорционный) рецепт НЕ хранится — только порция на 1 человека
   (base_servings = 1), развёрнутая в 6 групп» (CLAUDE.md §3).

Что делает:
  1. Каждому рецепту с base_servings > 1 делит amount_g всех ингредиентов на
     base_servings (округление до 0.1 г) и ставит base_servings = 1.
     МАТЕМАТИКА ДВИЖКА НЕ МЕНЯЕТСЯ: scaleRecipe и так делит на base_servings,
     теперь деление выполнено заранее в данных. portions (6 групп) не трогаем.
  2. ПОСЛЕ нормализации заново ищет реальные ошибки пропорций (их делением
     не исправить) и ставит balance_off:
       a) хлеб/мучное/сахар > 60% веса состава (кроме односоставных снеков);
       b) один ТВЁРДЫЙ ингредиент (не вода/бульон/молоко для варки) > 500 г
          в порции на одного;
       c) суммарный вес порции на одного > 1200 г.
  3. Отчёт: НОРМАЛИЗАЦИЯ_отчёт.md + список новых флагов.

Запуск:
  python3 normalize_recipes.py --dry    # только показать, что изменится
  python3 normalize_recipes.py          # применить (с бэкапом)
"""
import json, sys, shutil, datetime, os

DRY = '--dry' in sys.argv
SRC = 'recipes.json'

BREADS = ('хлеб','батон','лаваш','тост','багет','булочк','бейгл','мука','сахар')
LIQUIDS = ('вода','бульон','молоко','кефир','кипяток')

recs = json.load(open(SRC, encoding='utf-8'))
norm_cnt = 0
flag_new = []

def raw_weight(x):
    return sum(i.get('amount_g', 0) or 0 for i in (x.get('ingredients') or []))

for x in recs:
    b = x.get('base_servings') or 1
    if b > 1:
        for i in (x.get('ingredients') or []):
            g = i.get('amount_g')
            if g is not None:
                i['amount_g'] = round(g / b, 1)
        x['base_servings'] = 1
        if x.get('base_weight_g'):
            x['base_weight_g'] = round(x['base_weight_g'] / b, 1)
        norm_cnt += 1

# --- пере-детект реальных ошибок пропорций (после нормализации) ---
for x in recs:
    if x.get('balance_off'):
        continue
    ings = x.get('ingredients') or []
    tot = raw_weight(x)
    if tot <= 0 or len(ings) <= 1:
        continue                       # односоставные снеки — легитимны
    reasons = []
    bread = sum(i.get('amount_g', 0) or 0 for i in ings
                if any(bw in (i.get('id','') or '').lower() for bw in BREADS))
    if bread / tot > 0.60:
        reasons.append(f'мучное {bread:.0f}г из {tot:.0f}г ({bread/tot:.0%})')
    for i in ings:
        nm = (i.get('id','') or '').lower()
        g = i.get('amount_g', 0) or 0
        if g > 500 and not any(l in nm for l in LIQUIDS):
            reasons.append(f'{i.get("id")} {g:.0f}г в порции на одного')
    if tot > 1200:
        reasons.append(f'порция на одного весит {tot:.0f}г')
    if reasons:
        x['balance_off'] = True
        flag_new.append({'id': x['id'], 'name': x['name'], 'reasons': reasons})

# --- отчёт ---
L = [f'# Нормализация recipes.json — {datetime.date.today()}',
     f'',
     f'- Рецептов приведено к порции на одного (base_servings→1): **{norm_cnt}**',
     f'- Новых balance_off (ошибки пропорций, делением не лечатся): **{len(flag_new)}**',
     f'',
     f'## Новые флаги balance_off']
for f in flag_new:
    L.append(f"- `{f['id']}` «{f['name']}» — {'; '.join(f['reasons'])}")
open('НОРМАЛИЗАЦИЯ_отчёт.md', 'w', encoding='utf-8').write('\n'.join(L))

print(f'нормализовано: {norm_cnt} · новых balance_off: {len(flag_new)}')
for f in flag_new[:15]:
    print(' -', f['id'], f['name'][:40], '|', f['reasons'][0])
if len(flag_new) > 15:
    print(f'   … и ещё {len(flag_new)-15} (полный список в НОРМАЛИЗАЦИЯ_отчёт.md)')

if DRY:
    print('\n--dry: файл recipes.json НЕ изменён.')
else:
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(f'backups/snapshot_{stamp}_нормализация', exist_ok=True)
    shutil.copy(SRC, f'backups/snapshot_{stamp}_нормализация/recipes.json')
    json.dump(recs, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'\n✅ записано. Бэкап: backups/snapshot_{stamp}_нормализация/recipes.json')
