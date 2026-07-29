#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_06_brands.py — убрать БРЕНДЫ из шагов (только текст, КБЖУ не трогает).
Кавычки-бренды удаляем целиком вместе с «…»; безкавычные (Global Village, Sea Salt) — токеном.
Чистим двойные пробелы и пробел перед запятой/точкой.
  python3 apply_corrections_06_brands.py --dry  |  без --dry = бэкап+запись
"""
import json, os, sys, re, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open('recipes.json', encoding='utf-8'))

QUOTED = ['простоквашино', 'селяночка', 'станция молочная', 'рестория',
          'выгодно и удобно', 'красная цена', 'global village', 'sea salt',
          'danone', 'эрмигурт', 'активиа', 'растишка', 'агуша']
UNQUOTED = ['global village', 'sea salt']  # встречаются без кавычек

def clean_step(s):
    orig = s
    # 1) «Бренд» (в любых кавычках) → убрать вместе с кавычками
    def repl_q(m):
        inner = m.group(1).strip().lower()
        return '' if any(b in inner for b in QUOTED) else m.group(0)
    s = re.sub(r'\s*[«"“]([^»"”]{1,40})[»"”]', repl_q, s)
    # 2) безкавычные бренды
    for b in UNQUOTED:
        s = re.sub(r'\s*' + re.escape(b), '', s, flags=re.I)
    # 3) чистка пробелов/пунктуации
    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r'\s+([,.;:!?])', r'\1', s)
    s = s.strip()
    return s, (s != orig)

changed = 0; samples = []
for r in R:
    instr = r.get('instructions') or []
    new = []; touched = False
    for s in instr:
        ns, ch = clean_step(s)
        if ch:
            touched = True
            if len(samples) < 14: samples.append((r['id'], s, ns))
        new.append(ns)
    if touched:
        r['instructions'] = new; changed += 1

print(f'Рецептов с изменёнными шагами: {changed}')
print('\nПРИМЕРЫ до/после:')
for rid, a, b in samples:
    print(f'  [{rid}]\n   БЫЛО:  {a}\n   СТАЛО: {b}')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
shutil.copy('recipes.json', f'backups/recipes.json.before_brands_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/recipes.json.before_brands_{stamp}')
