#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_recipe.py — ПОМОЩНИК «добавить рецепт под ключ».
На входе — человеческая часть рецепта (название, приём, состав, шаги).
На выходе — полностью готовый рецепт: порции по 6 группам + 26 микронутриентов
на группу, с валидацией (КБЖУ, Б≥1.2×Ж, UL-безопасность, известность ингредиентов).
Дописывает в recipes.json + micronutrients_per_portion.json (с бэкапом).

ВХОД: JSON-файл со списком рецептов (по умолчанию new_recipes.json). Формат — см.
new_recipes_TEMPLATE.json (создаётся при первом запуске, если файла нет).

ЗАПУСК:
    python3 add_recipe.py                 # проверить + добавить из new_recipes.json
    python3 add_recipe.py --dry           # только проверка, БЕЗ записи
    python3 add_recipe.py мой_файл.json   # другой входной файл
"""
import json, sys, os, difflib, datetime
from collections import Counter

DRY = '--dry' in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith('--')]
IN = args[0] if args else 'new_recipes.json'

# стандартные веса порции по группам (из базы) + микро-поля/нормы
STD_G = {'m70':275,'m90':310,'m90p':350,'f60':240,'f80':275,'f80p':310}
GROUPS = list(STD_G.keys())
UL = {'vitamin_a':3000,'vitamin_b3':35,'vitamin_b6':100,'vitamin_b9':1000,'vitamin_c':2000,'vitamin_d':100,
 'vitamin_e':1000,'calcium':2500,'iron':45,'zinc':40,'selenium':400,'phosphorus':4000}
UL_SAFE={'vitamin_a':0.8,'vitamin_d':0.8,'iron':0.8,'zinc':0.8,'selenium':0.8}
ULcap={k:UL[k]*UL_SAFE.get(k,1.0) for k in UL}
VALID_MEALS={'breakfast','lunch','snack','dinner'}

kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
micro_doc = json.load(open('micronutrients.json', encoding='utf-8'))
mi = micro_doc['ingredients']; FIELDS = micro_doc['fields']

TEMPLATE = [{
  "name": "Рисовая тарелка с курицей и овощами",
  "meal_type": ["lunch", "dinner"],
  "dish_type": "основное_блюдо",
  "cats": ["злаки", "птица", "овощи"],
  "groups": ["крупы", "птица"],
  "ingredients": [
    {"id": "Рис", "amount_g": 120},
    {"id": "Куриное филе", "amount_g": 150},
    {"id": "Морковь", "amount_g": 50},
    {"id": "Растительное масло", "amount_g": 5}
  ],
  "instructions": ["Отварить рис.", "Обжарить куриное филе с морковью.", "Смешать, посолить."],
  "image_url": "",
  "base_portion_g": 275,
  "balance_off": 0
}]

def per100(ingredients, table, fields):
    tot = sum(float(i.get('amount_g',0) or 0) for i in ingredients)
    out = {f:0.0 for f in fields}
    if tot<=0: return out, tot, []
    unknown=[]
    for ing in ingredients:
        nm=ing.get('id',''); amt=float(ing.get('amount_g',0) or 0)
        rec=table.get(nm)
        if not rec: unknown.append(nm); continue
        src = rec if fields[0] in rec else (rec.get('micro') or {})
        for f in fields: out[f]+= (src.get(f,0) or 0)*amt/tot
    return out, tot, unknown

def suggest(nm, pool):
    m=difflib.get_close_matches(nm, list(pool), n=3, cutoff=0.6)
    return m

def process(rc, existing_ids, next_num):
    errs=[]; warns=[]
    name=rc.get('name','').strip()
    if not name: errs.append('нет названия')
    meals=rc.get('meal_type') or []
    if not meals or any(m not in VALID_MEALS for m in meals):
        errs.append(f'meal_type должен быть из {sorted(VALID_MEALS)}')
    ings=rc.get('ingredients') or []
    if not ings: errs.append('пустой состав')

    # КБЖУ на 100 г
    kb_fields=['calories','protein','fat','carbs']
    k100,tot,unk_kb = per100(ings, kb, kb_fields)
    # микро на 100 г
    m100,_,unk_mi = per100(ings, mi, FIELDS)
    unknown=sorted(set(unk_kb+unk_mi))
    for u in unknown:
        s=suggest(u, kb.keys())
        errs.append(f'неизвестный ингредиент «{u}»' + (f' — возможно: {", ".join(s)}' if s else ''))

    if errs:
        return None, errs, warns

    base = float(rc.get('base_portion_g') or STD_G['m70'])
    ratio = base/STD_G['m70']
    portions={}; micro_groups={}
    for g in GROUPS:
        gg = round(STD_G[g]*ratio)
        portions[g] = {'g':gg,
                       'kcal':round(k100['calories']*gg/100),
                       'p':round(k100['protein']*gg/100,1),
                       'f':round(k100['fat']*gg/100,1),
                       'c':round(k100['carbs']*gg/100,1)}
        micro_groups[g] = {'g':gg, **{f:round(m100[f]*gg/100,3) for f in FIELDS}}

    # --- валидация ---
    p=portions['m70']
    # 1) ккал ≈ 4Б+9Ж+4У
    calc=p['p']*4+p['f']*9+p['c']*4
    if p['kcal']>0 and abs(calc-p['kcal'])/p['kcal']>0.15:
        warns.append(f'ккал {p["kcal"]} расходится с 4Б+9Ж+4У={round(calc)} (>15%) — проверь состав')
    # 2) Б≥1.2×Ж (иначе движок отрежет)
    if p['p'] < 1.2*p['f']:
        warns.append(f'Б({p["p"]})<1.2×Ж({p["f"]}) → блюдо АВТО-ОТРЕЖЕТСЯ фильтром деки. '
                     'Ок только если это junk с balance_off, иначе снизь жир/добавь белок')
    # 3) UL-безопасность по всем группам
    for g in GROUPS:
        over=[f'{key} {round(micro_groups[g][key])}>{round(ULcap[key])}' for key in UL if micro_groups[g][key]>ULcap[key]]
        if over: errs.append(f'ПРЕВЫШЕН UL в группе {g}: {", ".join(over)} — опасно, снизь дозу')
    if errs:
        return None, errs, warns

    rid = rc.get('id') or f'fr_{next_num}'
    if rid in existing_ids: errs.append(f'id {rid} уже занят'); return None, errs, warns

    tags = rc.get('tags') or {}
    tags.setdefault('cats', rc.get('cats') or [])
    tags.setdefault('groups', rc.get('groups') or [])
    tags['dish_type'] = rc.get('dish_type','основное_блюдо')
    tags['n_ingredients'] = len(ings)
    tags.setdefault('cook_total_min', rc.get('cook_time',15))

    recipe = {
        'id':rid, 'name':name, 'meal_type':meals,
        'prep_time':rc.get('prep_time',0), 'cook_time':rc.get('cook_time',15),
        'base_servings':1, 'base_weight_g':round(base),
        'tags':tags, 'ingredients':ings, 'instructions':rc.get('instructions') or [],
        'image_url':rc.get('image_url') or f'dish_photos/{rid}.webp',
        'score':0, 'portions':portions, 'balance_off':int(rc.get('balance_off',0) or 0)
    }
    micro_entry = {'name':name, 'meal_type':meals,
                   'per100g':{f:round(m100[f],3) for f in FIELDS}, 'groups':micro_groups}
    return (recipe, micro_entry, rid), errs, warns


def run():
    if not os.path.exists(IN):
        json.dump(TEMPLATE, open(IN,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'Создан шаблон {IN}. Заполни его своими рецептами и запусти снова.')
        return
    new = json.load(open(IN, encoding='utf-8'))
    if isinstance(new, dict): new=[new]
    R = json.load(open('recipes.json', encoding='utf-8'))
    MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
    existing = set(r['id'] for r in R)
    nums = [int(r['id'][3:]) for r in R if r['id'].startswith('fr_') and r['id'][3:].isdigit()]
    next_num = max(nums)+1 if nums else 300000

    ready=[]; skipped=[]
    for i,rc in enumerate(new,1):
        res, errs, warns = process(rc, existing, next_num)
        title = rc.get('name','?')[:40]
        if res:
            recipe, micro_entry, rid = res
            existing.add(rid); next_num = max(next_num, int(rid[3:])+1) if rid[3:].isdigit() else next_num+1
            ready.append((recipe, micro_entry))
            pm=recipe['portions']['m70']
            print(f'✅ [{i}] {title} → {rid}  (m70: {pm["kcal"]}ккал Б{pm["p"]}/Ж{pm["f"]}/У{pm["c"]})')
            for w in warns: print(f'     ⚠️ {w}')
        else:
            skipped.append((title,errs))
            print(f'❌ [{i}] {title} — НЕ добавлен:')
            for e in errs: print(f'     • {e}')
            for w in warns: print(f'     ⚠️ {w}')

    print(f'\nИтог: готово {len(ready)}, пропущено {len(skipped)}.')
    if DRY:
        print('Режим --dry: НИЧЕГО не записано. Убери --dry, чтобы добавить в базу.')
        return
    if not ready:
        print('Добавлять нечего.'); return
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backups',exist_ok=True)
    json.dump(R, open(f'backups/recipes_before_add_{stamp}.json','w',encoding='utf-8'), ensure_ascii=False)
    for recipe, micro_entry in ready:
        R.append(recipe); MP['dishes'][recipe['id']] = micro_entry
    json.dump(R, open('recipes.json','w',encoding='utf-8'), ensure_ascii=False)
    json.dump(MP, open('micronutrients_per_portion.json','w',encoding='utf-8'), ensure_ascii=False)
    print(f'Добавлено в recipes.json + micronutrients_per_portion.json: {len(ready)}. Бэкап: backups/recipes_before_add_{stamp}.json')
    print('Дальше: 1) добавь фото dish_photos/<id>.webp;  2) для попадания в дефолтные пресеты — пересобери якоря (build_super_presets.py).')

if __name__=='__main__':
    run()
