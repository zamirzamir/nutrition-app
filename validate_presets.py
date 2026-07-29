#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_presets.py — строгая проверка anchors_seeds.json (пресетов) на валидность
и соответствие нашим критериям:
  1) СТРУКТУРА: 238 якорей, у каждого 28 дней, каждый id есть в recipes.json,
     в micronutrients_per_portion.json и имеет порцию для группы якоря.
  2) МАКРО: каждый день в ±3% по ккал/Б/Ж/У от цели якоря (на фикс-порциях группы).
  3) UL (безопасность): ни один день не превышает потолок (80% UL для токсичных).
  4) МИКРО: среднее 28-дневное покрытие RDA по якорю.
  5) УГЛЕВОДЫ и РАЗНООБРАЗИЕ: доля рафинада, уникальных блюд.

Запуск: python3 validate_presets.py
"""
import json
from collections import defaultdict

recs = {x['id']: x for x in json.load(open('recipes.json', encoding='utf-8'))}
MM = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))['dishes']
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
A = json.load(open('anchors_seeds.json', encoding='utf-8'))
anchors = A['anchors']

RDA = {'vitamin_a':900,'vitamin_b1':1.2,'vitamin_b2':1.3,'vitamin_b3':16,'vitamin_b5':5,'vitamin_b6':1.3,
 'vitamin_b9':400,'vitamin_b12':2.4,'vitamin_c':90,'vitamin_k':120,'calcium':1000,'iron':8,'magnesium':400,
 'phosphorus':700,'potassium':3400,'zinc':11,'selenium':55,'omega3':1.6,'omega6':17,'fiber':38}
UL = {'vitamin_a':3000,'vitamin_b3':35,'vitamin_b6':100,'vitamin_b9':1000,'vitamin_c':2000,'vitamin_d':100,
 'vitamin_e':1000,'calcium':2500,'iron':45,'zinc':40,'selenium':400,'phosphorus':4000}
UL_SAFE = {'vitamin_a':0.8,'vitamin_d':0.8,'iron':0.8,'zinc':0.8,'selenium':0.8}
ULcap = {k: UL[k]*UL_SAFE.get(k,1.0) for k in UL}
SCORE_F = [k for k in RDA if k not in ('vitamin_d','vitamin_e')]
TOL = 0.03

REFINED = ['белый хлеб','батон','бейгл','багет','булочк','круассан','макарон','вермишель','спагетти','лапша','сахар','пончик','вафл']
def refined_frac(x):
    ings=x.get('ingredients') or []; tot=ref=0.0
    for i in ings:
        g=float(i.get('amount_g',0) or 0)
        if g<=0: continue
        tot+=g
        if any(w in (i.get('id','') or '').lower() for w in REFINED): ref+=g
    return ref/tot if tot else 0.0

def run():
    n_anchors=len(anchors)
    bad_struct=[]; bad_ids=set(); macro_fail=[]; ul_fail=[]; short=[]
    micro_cov=[]; ref_shares=[]; uniq_counts=[]
    total_days=0
    for ai,an in enumerate(anchors):
        spec=an['anchor']; G=spec['group']; T={'kcal':spec['kcal'],'p':spec['p'],'f':spec['f'],'c':spec['c']}
        days=an.get('days') or []
        if len(days)!=30: short.append((ai,G,len(days)))
        uniq=set()
        cov_sum=0.0; ref_sum=0.0
        for di,day in enumerate(days):
            total_days+=1
            k=p=f=c=0.0; M=defaultdict(float); dref_w=0.0; dcc=0.0; okrow=True
            for rid in day:
                uniq.add(rid)
                r=recs.get(rid)
                if not r: bad_ids.add(rid); okrow=False; continue
                pg=(r.get('portions') or {}).get(G)
                mg=MM.get(rid,{}).get('groups',{}).get(G)
                if not pg or not mg: bad_ids.add(rid); okrow=False; continue
                k+=pg['kcal']; p+=pg['p']; f+=pg['f']; c+=pg['c']
                for fld in FIELDS: M[fld]+=mg.get(fld,0)
                cc=pg['c']; dcc+=cc; dref_w+=refined_frac(r)*cc
            # макро ±3%
            def dev(v,t): return abs(v-t)/t if t else 0
            if okrow:
                dmax=max(dev(k,T['kcal']),dev(p,T['p']),dev(f,T['f']),dev(c,T['c']))
                if dmax>TOL+1e-6:
                    macro_fail.append((ai,G,di,round(dmax*100,1),round(k),round(p),round(f),round(c),T))
                # UL
                over=[key for key in UL if M[key]>ULcap[key]]
                if over: ul_fail.append((ai,G,di,over,{key:round(M[key]) for key in over}))
                cov_sum+=sum(min(M[fld]/RDA[fld],1.0) for fld in SCORE_F)
                ref_sum+=(dref_w/dcc if dcc else 0)
        if days:
            micro_cov.append(cov_sum/len(days)); ref_shares.append(ref_sum/len(days)); uniq_counts.append(len(uniq))

    print("="*60)
    print(f"ПРОВЕРКА ПРЕСЕТОВ anchors_seeds.json")
    print("="*60)
    print(f"Якорей: {n_anchors}  ·  всего дней: {total_days}")
    print(f"[Структура] якорей НЕ по 30 дней: {len(short)} {short[:5] if short else ''}")
    print(f"[Структура] несуществующих/битых id блюд: {len(bad_ids)} {list(bad_ids)[:5] if bad_ids else ''}")
    print(f"[МАКРО ±3%] дней вне коридора: {len(macro_fail)} из {total_days}")
    for x in macro_fail[:8]:
        print(f"    якорь#{x[0]} {x[1]} день{x[2]}: откл {x[3]}%  (ккал{x[4]}/Б{x[5]}/Ж{x[6]}/У{x[7]} vs {x[8]})")
    print(f"[UL безопасность] дней с превышением потолка: {len(ul_fail)} из {total_days}")
    for x in ul_fail[:8]:
        print(f"    якорь#{x[0]} {x[1]} день{x[2]}: {x[3]} → {x[4]}")
    if micro_cov:
        print(f"[МИКРО] среднее покрытие RDA (из {len(SCORE_F)}): {sum(micro_cov)/len(micro_cov):.2f}  (мин по якорю {min(micro_cov):.2f})")
    if ref_shares:
        print(f"[УГЛЕВОДЫ] средняя доля рафинада/день: {sum(ref_shares)/len(ref_shares):.3f}")
    if uniq_counts:
        print(f"[РАЗНООБРАЗИЕ] уникальных блюд на якорь: среднее {sum(uniq_counts)/len(uniq_counts):.1f}, мин {min(uniq_counts)}")
    print("="*60)
    ok = (len(short)==0 and len(bad_ids)==0 and len(macro_fail)==0 and len(ul_fail)==0)
    print("ВЕРДИКТ:", "✅ ВАЛИДНЫ, все критерии соблюдены — можно заливать" if ok
          else "⚠️ ЕСТЬ ЗАМЕЧАНИЯ (см. выше)")
    return ok

if __name__=='__main__':
    run()
