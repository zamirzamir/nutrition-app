#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_08_renames.py — убрать приставки «ресторанный/домашний/фирменный/
авторский» (любые родовые формы) из НАЧАЛА названий. Только имя, данные не трогаем.
  python3 ... --dry | без --dry = бэкап+запись
"""
import json, os, sys, re, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open('recipes.json', encoding='utf-8'))
ROOTS = ['ресторан', 'домашн', 'фирмен', 'авторск']
# первое слово, начинающееся с одного из корней
pat = re.compile(r'^\s*([А-Яа-яЁё]+)\s+', re.U)

def fix(name):
    m = pat.match(name)
    if not m: return name
    w = m.group(1).lower()
    if any(w.startswith(r) for r in ROOTS):
        rest = name[m.end():]
        if not rest: return name
        return rest[0].upper() + rest[1:]
    return name

changed = 0; samples = []
for r in R:
    old = r['name']; new = fix(old)
    if new != old:
        r['name'] = new; changed += 1
        if len(samples) < 20: samples.append((old, new))
print(f'Переименовано: {changed}')
for a, b in samples: print(f'   «{a}» → «{b}»')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
shutil.copy('recipes.json', f'backups/recipes.json.before_rename_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/recipes.json.before_rename_{stamp}')
