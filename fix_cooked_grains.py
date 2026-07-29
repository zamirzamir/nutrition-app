#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_cooked_grains.py — переводит варёные крупы/пасту в существующих рецептах
на модель «сырое + вода». Для каждого рецепта, где есть варёный ингредиент
(Киноа/Булгур/Кускус/Рисовая лапша), заменяет его на сухой эквивалент и
добавляет Воду (впитанную), сохраняя суммарные калории. Затем пересчитывает
portions (по 6 группам) и micronutrients_per_portion. С бэкапом.

Конверсия калорий-нейтральна: dry_g = cooked_g × cooked_kcal / dry_kcal,
water_g = cooked_g − dry_g. Итоговый вес и КБЖУ почти не меняются — меняется
лишь ЧЕСТНОСТЬ состава (сухая крупа + вода вместо «варёной»).

Запуск: python3 fix_cooked_grains.py
"""
import json

MAP = {'Киноа':'Киноа сухая','Булгур':'Булгур сухой','Кускус':'Кускус сухой','Рисовая лапша':'Рисовая лапша сухая'}

kb = {e['name']: e for e in json.load(open('ingredients_kbju.json', encoding='utf-8'))['ingredients']}
mi = json.load(open('micronutrients.json', encoding='utf-8'))['ingredients']
micro_doc = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
GROUPS = ['m70','m90','m90p','f60','f80','f80p']
R = json.load(open('recipes.json', encoding='utf-8'))

def total_g(r): return sum(float(i.get('amount_g',0) or 0) for i in r['ingredients'])

def recompute(r):
    tot = total_g(r)
    if tot <= 0: return
    p100 = {'calories':0.0,'protein':0.0,'fat':0.0,'carbs':0.0}
    m100 = {f:0.0 for f in FIELDS}
    for ing in r['ingredients']:
        amt = float(ing.get('amount_g',0) or 0); nm = ing.get('id','')
        e = kb.get(nm)
        if e:
            for k in p100: p100[k] += (e.get(k,0) or 0)*amt/tot
        rec = mi.get(nm)
        if rec:
            mm = rec.get('micro') or {}
            for f in FIELDS: m100[f] += (mm.get(f,0) or 0)*amt/tot
    for g in GROUPS:
        pg = (r.get('portions') or {}).get(g)
        if not pg: continue
        gg = float(pg.get('g',0) or 0)
        pg['kcal']=round(p100['calories']*gg/100); pg['p']=round(p100['protein']*gg/100,1)
        pg['f']=round(p100['fat']*gg/100,1); pg['c']=round(p100['carbs']*gg/100,1)
    ent = micro_doc['dishes'].get(r['id'])
    if ent:
        ent['per100g'] = {f:round(m100[f],3) for f in FIELDS}
        for g,gv in ent.get('groups',{}).items():
            gg=float(gv.get('g',0) or 0)
            for f in FIELDS: gv[f]=round(m100[f]*gg/100,3)

changed=[]
for r in R:
    hit=False
    for ing in list(r['ingredients']):
        nm=ing.get('id','')
        if nm in MAP:
            dry=MAP[nm]; ck=kb[nm]['calories']; dk=kb[dry]['calories'] or 1
            cooked_g=float(ing.get('amount_g',0) or 0)
            dry_g=round(cooked_g*ck/dk,1); water_g=round(cooked_g-dry_g,1)
            ing['id']=dry; ing['amount_g']=dry_g
            # добавить воду (слить с существующей, если есть)
            w=next((x for x in r['ingredients'] if x.get('id')=='Вода'),None)
            if w: w['amount_g']=round(float(w.get('amount_g',0) or 0)+water_g,1)
            elif water_g>0: r['ingredients'].append({'id':'Вода','amount_g':water_g})
            hit=True
    if hit:
        # добавить шаг варки, если его нет
        ins=r.get('instructions') or []
        if not any(w in ' '.join(ins).lower() for w in ['отвар','свар','вар ','залей','запар']):
            r['instructions']=['Крупу отварить в воде до готовности.']+ins
        recompute(r)
        changed.append(r['id'])

json.dump(R,open('recipes.json','w',encoding='utf-8'),ensure_ascii=False)
json.dump(micro_doc,open('micronutrients_per_portion.json','w',encoding='utf-8'),ensure_ascii=False)
print(f'Переведено рецептов на сырое+вода: {len(changed)}')
print('id:', ', '.join(changed[:40]))
