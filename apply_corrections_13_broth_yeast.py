#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_corrections_13_broth_yeast.py — бульоны (овощной допись + куриный шаг) + пометка дрожжей. Только текст шагов."""
import json, os, datetime, shutil, sys
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open('recipes.json', encoding='utf-8'))

FREEZE = ('Замораживайте бульон в формочках для льда или формах побольше, а как замёрзнут — '
          'сложите всё в один пакет и храните кубиками.')
VEG_OUT = ('Овощи после варки в этом рецепте не используются. Их можно выбросить или измельчить '
           'и использовать как основу для овощного супа или соуса.')
CHICKEN_STEP = ('Куриный бульон (приготовьте заранее, пригодится и в других блюдах). На ~1.5 л бульона: '
                'куриные части (спинки, крылья или окорочка) ~500 г, морковь 100 г, лук репчатый 100 г, '
                'вода 2000 мл, лавровый лист, соль. Залейте курицу и овощи холодной водой, доведите до кипения, '
                'снимите пену и варите на слабом огне 40–60 минут, затем процедите. ' + FREEZE +
                ' Отваренное мясо можно использовать в этом или других блюдах.')
YEAST_NOTE = ('Пищевые (неактивные) дрожжи — это приправа с сырно-ореховым вкусом. НЕ путай их с сухими '
              'пекарскими дрожжами для теста — здесь нужны именно пищевые неактивные дрожжи.')

ov_n = ku_n = yz_n = 0
for r in R:
    ings = r['ingredients']; instr = r.get('instructions') or []
    # 1) овощной бульон — дописать в шаг, начинающийся с «Овощной бульон»
    if any('овощной бульон' in i['id'].lower() and 'см. в шагах' in i['id'].lower() for i in ings):
        for n, s in enumerate(instr):
            if s.strip().lower().startswith('овощной бульон') and 'не используются' not in s:
                instr[n] = s.rstrip() + '\n\n' + FREEZE + '\n\n' + VEG_OUT
                ov_n += 1; break
    # 2) куриный бульон — если нет шага-рецепта, добавить первым
    if any(i['id'] == 'Куриный бульон' for i in ings):
        if not any(s.strip().lower().startswith('куриный бульон') for s in instr):
            instr.insert(0, CHICKEN_STEP); ku_n += 1
    # 3) пищевые дрожжи — пояснение
    if any(i['id'] == 'Пищевые дрожжи' for i in ings):
        if not any('неактивные' in s.lower() for s in instr):
            instr.append(YEAST_NOTE); yz_n += 1
    r['instructions'] = instr

print(f'Овощной бульон дописан: {ov_n} | Куриный бульон шаг добавлен: {ku_n} | Дрожжи-пометка: {yz_n}')
if DRY:
    # пример
    ex = next(r for r in R if any('овощной бульон' in i['id'].lower() and 'см. в шагах' in i['id'].lower() for i in r['ingredients']))
    print('\nпример овощного (шаг0):', ex['instructions'][0][:400])
    print('\n[DRY]'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); os.makedirs('backups', exist_ok=True)
shutil.copy('recipes.json', f'backups/recipes.json.before_broth_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап before_broth_{stamp}')
