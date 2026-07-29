#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_quotes_brands.py — ПОИСК (только чтение) в ШАГАХ: кавычки и бренды.
Запуск:  python3 scan_quotes_brands.py
"""
import json, re, sys
R = json.load(open('recipes.json', encoding='utf-8'))

BRANDS = ['global village', 'выгодно и удобно', 'красная цена', 'рестория',
          'станция молочная', 'селяночка', 'простоквашино', 'sea salt',
          'danone', 'эрмигурт', 'активиа', 'растишка', 'агуша', 'чудо',
          'мираторг', 'вкусвилл', 'домик в деревне', 'president', 'president',
          'валио', 'valio', 'савушкин', 'брест-литовск', 'коровка из кореновки']
QUOTE = re.compile(r'[«»""“”]')

print('=== БРЕНДЫ В ШАГАХ ===')
brand_hits = {}
for r in R:
    steps = r.get('instructions') or []
    for n, s in enumerate(steps):
        sl = s.lower()
        for b in BRANDS:
            if b in sl:
                brand_hits.setdefault(b, []).append((r['id'], r['name'], n + 1, s))
if not brand_hits:
    print('  брендов в шагах не найдено')
for b, lst in sorted(brand_hits.items(), key=lambda x: -len(x[1])):
    print(f'\n[{b}] — {len(lst)} шт:')
    for rid, nm, step, s in lst:
        print(f'   {rid} | {nm} | шаг {step}: …{s[:120]}…')

print('\n\n=== КАВЫЧКИ В ШАГАХ ===')
q_hits = []
for r in R:
    for n, s in enumerate(r.get('instructions') or []):
        if QUOTE.search(s):
            for m in re.findall(r'[«"“]([^»"”]{1,40})[»"”]', s):
                q_hits.append((r['id'], r['name'], n + 1, m.strip(), s))
print(f'Всего шагов с кавычками: {len(q_hits)}')
for rid, nm, step, inner, s in q_hits:
    print(f'   {rid} | {nm} | шаг {step} | «{inner}»')
