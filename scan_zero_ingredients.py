#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_zero_ingredients.py — ПОИСК (только чтение) ингредиентов с весом 0 г.
Отдельно выделяет разрыхлитель. Даёт сводку «сколько раз 0 г» по каждому ингредиенту
и список рецептов для разрыхлителя (и любого запрошенного).
Запуск:  python3 scan_zero_ingredients.py                (сводка + разрыхлитель)
         python3 scan_zero_ingredients.py "Сода"         (список рецептов по ингредиенту)
"""
import json, sys
from collections import Counter, defaultdict
R = json.load(open('recipes.json', encoding='utf-8'))

zero = Counter(); by = defaultdict(list)
for r in R:
    for i in r.get('ingredients', []):
        if (i.get('amount_g') or 0) == 0:
            zero[i['id']] += 1
            by[i['id']].append((r['id'], r['name'], r.get('meal_type')))

if len(sys.argv) > 1:
    key = sys.argv[1]
    print(f'=== Рецепты, где «{key}» = 0 г ===')
    for rid, nm, mt in by.get(key, []):
        print(f'   {rid} | {nm} | {mt}')
    print(f'Всего: {len(by.get(key, []))}')
    sys.exit()

print('=== СВОДКА: ингредиенты с 0 г (сколько раз) ===')
print(f'Всего позиций 0 г: {sum(zero.values())} | уникальных ингредиентов: {len(zero)}')
for ing, c in zero.most_common():
    print(f'   {c:4}  {ing}')

print('\n=== РАЗРЫХЛИТЕЛЬ 0 г — рецепты ===')
for ing in zero:
    if 'разрыхл' in ing.lower():
        for rid, nm, mt in by[ing]:
            print(f'   {rid} | {nm} | {mt}')
raz = sum(c for ing, c in zero.items() if 'разрыхл' in ing.lower())
print(f'Всего разрыхлитель 0 г: {raz}')
print('\n(для списка по любому ингредиенту:  python3 scan_zero_ingredients.py "Имя ингредиента")')
