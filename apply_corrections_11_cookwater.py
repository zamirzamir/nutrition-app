#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_corrections_11_cookwater.py — варочная вода по коэффициентам Замира.
Вода = Σ(вес сухой крупы/пасты × коэф). Коэф: паста/рис/гречка 2.0; овсян.крупа/пшено 2.5; перловка 3.0;
булгур/киноа/кускус 2.0. Только где ВАРИТСЯ (boil в шагах), НЕ суп, НЕ выпечка/жарка/смузи.
  python3 ... --dry | без --dry = бэкап+запись
"""
import json, os, sys, re, datetime, shutil
DRY = '--dry' in sys.argv
os.chdir(os.path.dirname(os.path.abspath(__file__)))
kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
KBF = ['calories', 'protein', 'fat', 'carbs']
mi_doc = json.load(open('micronutrients.json', encoding='utf-8')); mi = mi_doc['ingredients']; FIELDS = mi_doc['fields']
R = json.load(open('recipes.json', encoding='utf-8')); MP = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))

# коэффициент воды по подстроке имени ингредиента (порядок важен: сначала исключения-муки)
def ratio_for(name):
    s = name.lower()
    if 'мука' in s or 'хлопь' in s or 'лапша рисов' in s or 'рисовая лапша' in s: return 0  # мука/хлопья/рис.лапша — не варим тут
    if any(x in s for x in ['макарон','спагетти','вермишел','пенне','рожки','фузилли','тальятел','феттуч','удон','соба','орзо']): return 2.0
    if 'перловк' in s: return 3.0
    if 'пшено' in s or 'пшённ' in s or 'пшенн' in s: return 2.5
    if 'овсяная крупа' in s or 'овсянная крупа' in s: return 2.5
    if s == 'рис' or s.startswith('рис ') or 'рис бас' in s or 'рис кругл' in s or 'рис длин' in s or 'дикий рис' in s or 'бурый рис' in s: return 2.0
    if 'гречка' in s or 'гречнев' in s and 'мука' not in s: return 2.0
    if 'булгур' in s or 'киноа' in s or 'кинва' in s or 'кускус' in s or 'кус-кус' in s or 'полб' in s or 'ячнев' in s: return 2.0
    return 0

SOUP = re.compile(r'суп|шурпа|борщ|\bщи\b|бульон|похлёб|похлеб|уха|рассольник|солянк|харчо|рамен|том.?ям|спринг|ролл|плов|ризотто|кисель|компот', re.I)
BAKE = re.compile(r'кекс|маффин|сырник|печень|смузи|панкейк|вафл|чизкейк|торт|брауни|оладь|блин|запеканк|десерт|мусс|крем|коктейл|батончик|гранол|мюсли|пудинг|суфле', re.I)
BOIL = re.compile(r'отвар|варите|до кипения|варить|залейте.*вод|вскипят|откинь|дуршлаг', re.I)
def steps(r): return ' '.join(r.get('instructions') or [])
def is_excluded(r):
    dt = (r.get('tags') or {}).get('dish_type', '')
    if dt in ('суп', 'выпечка_десерт', 'блины_оладьи', 'запеканка'): return True
    if SOUP.search(r['name']) or SOUP.search(steps(r).lower()): return True
    if BAKE.search(r['name']): return True
    return False

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

changed = []; samples = []
for r in R:
    if is_excluded(r): continue
    if not BOIL.search(steps(r)): continue
    need = sum(i.get('amount_g', 0) * ratio_for(i['id']) for i in r['ingredients'])
    if need <= 0: continue                          # нет варимой крупы/пасты
    # уже имеющаяся варочная жидкость (молоко/кефир/сливки и пр.) покрывает потребность
    LIQ = ['молоко', 'кефир', 'ряженк', 'сливки', 'простокваш', 'айран', 'йогурт питьев']
    milk = sum(i.get('amount_g', 0) for i in r['ingredients']
               if any(x in i['id'].lower() for x in LIQ))
    w = next((i for i in r['ingredients'] if i['id'] == 'Вода'), None)
    old = w['amount_g'] if w else 0
    newv = max(0, round(need - milk))
    if abs(old - newv) < 2: continue                # уже норм
    if w: w['amount_g'] = newv
    else: r['ingredients'].append({'id': 'Вода', 'amount_g': newv})
    k = per100(r['ingredients'], kb, KBF); m = per100(r['ingredients'], mi, FIELDS)
    for g, pg in r.get('portions', {}).items():
        gg = pg['g']
        pg['kcal'] = round(k['calories'] * gg / 100); pg['p'] = round(k['protein'] * gg / 100, 1)
        pg['f'] = round(k['fat'] * gg / 100, 1); pg['c'] = round(k['carbs'] * gg / 100, 1)
    d = MP.get('dishes', {}).get(r['id'])
    if d:
        d['per100g'] = {f: round(m[f], 3) for f in FIELDS}
        for g, gr in d.get('groups', {}).items():
            gg = gr['g']
            for f in FIELDS: gr[f] = round(m[f] * gg / 100, 3)
    changed.append(r['id'])
    if len(samples) < 16:
        gr = [f"{i['id']} {i['amount_g']}г" for i in r['ingredients'] if ratio_for(i['id']) > 0]
        samples.append((r['id'], r['name'][:32], old, newv, ', '.join(gr)))

print(f'Изменено рецептов (варочная вода): {len(changed)}')
print('id | блюдо | вода было→стало | крупа/паста')
for rid, nm, o, n, gr in samples:
    print(f'   {rid:12} {nm:32} {o}→{n}г   [{gr}]')
if DRY:
    print('\n[DRY] не записано.'); sys.exit()
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
for f in ['recipes.json', 'micronutrients_per_portion.json']:
    shutil.copy(f, f'backups/{f}.before_cookwater_{stamp}')
json.dump(R, open('recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MP, open('micronutrients_per_portion.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ Записано. Бэкап: backups/*.before_cookwater_{stamp}')
