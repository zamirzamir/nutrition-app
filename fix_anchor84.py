#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_anchor84.py — целевая перегенерация ОДНОГО якоря (#84 m70 2883, экстремальный
профиль Б130/Ж60/У455). ±3% по макро для него структурно недостижим (доказано:
0 дней в пределах 10% на 400k случайных). Поэтому берём 30 ЛУЧШИХ достижимых дней:
  • первично — минимум макс-отклонения по 4 макро-осям (тянемся к цели),
  • среди близких — максимум микро-покрытия RDA + сложные углеводы (как в супер-пресетах),
  • жёстко — не превышаем UL (с зазором 0.8 для токсичных),
  • разнообразие — жадный отбор без повторов блюд.
Пишет назад в anchors_seeds.json (бэкап уже сделан отдельно) + в чекпоинт seeds_super/.
"""
import json, random, time
from collections import defaultdict

TIME_BUDGET = 20.0
CARB_W = 4.0
MACRO_W = 200.0         # вес близости к макро в пуле (md доминирует; микро — тайбрейк)
DIVERSITY_REUSE_PEN = 0.55

recs = {x['id']: x for x in json.load(open('recipes.json', encoding='utf-8'))}
MM = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))['dishes']
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
CUR = json.load(open('anchors_seeds.json', encoding='utf-8'))

RDA = {'vitamin_a':900,'vitamin_b1':1.2,'vitamin_b2':1.3,'vitamin_b3':16,'vitamin_b5':5,'vitamin_b6':1.3,
 'vitamin_b9':400,'vitamin_b12':2.4,'vitamin_c':90,'vitamin_k':120,'calcium':1000,'iron':8,'magnesium':400,
 'phosphorus':700,'potassium':3400,'zinc':11,'selenium':55,'omega3':1.6,'omega6':17,'fiber':38}
UL = {'vitamin_a':3000,'vitamin_b3':35,'vitamin_b6':100,'vitamin_b9':1000,'vitamin_c':2000,'vitamin_d':100,
 'vitamin_e':1000,'calcium':2500,'iron':45,'zinc':40,'selenium':400,'phosphorus':4000}
UL_SAFE = {'vitamin_a':0.8,'vitamin_d':0.8,'iron':0.8,'zinc':0.8,'selenium':0.8}
ULcap = {k: UL[k]*UL_SAFE.get(k,1.0) for k in UL}
SCORE_F = [k for k in RDA if k not in ('vitamin_d','vitamin_e')]

REFINED = ['белый хлеб','батон','бейгл','багет','булочк','круассан','макарон','вермишель',
           'спагетти','лапша','сахар','пончик','вафл']
COMPLEX = ['овсян','геркулес','гречк','бурый рис','дикий рис','киноа','булгур','перлов',
           'чечевиц','фасоль','нут','горох','цельнозерн','отруб','батат','пшено']
def carb_fracs(x):
    ings = x.get('ingredients') or []; tot=ref=cpx=0.0
    for i in ings:
        g=float(i.get('amount_g',0) or 0)
        if g<=0: continue
        tot+=g; n=(i.get('id','') or '').lower()
        if any(w in n for w in REFINED): ref+=g
        if any(w in n for w in COMPLEX): cpx+=g
    if tot<=0: return 0.0,0.0
    return ref/tot, cpx/tot

SNACK_CONC = ('сухофрукт','изюм','курага','чернослив','финик','инжир','урюк','цукат',
              'вялен','сушён','сушен','шоколад','батончик','гранат')
def is_snack_concentrate(x):
    name=(x.get('name','') or '').lower(); tags=x.get('tags') or {}
    cats=set(tags.get('cats') or [])
    if tags.get('dish_type')=='снек-сухофрукты': return True
    if cats & {'сухофрукты','орехи'} and len(x.get('ingredients') or [])<=2: return True
    return any(w in name for w in SNACK_CONC) and len(x.get('ingredients') or [])<=2
def works(x,G):
    if x.get('balance_off'): return False
    if is_snack_concentrate(x): return False
    p=(x.get('portions') or {}).get(G)
    return bool(p and p.get('p') and p.get('f') and p['p']>=1.2*p['f'])

# ---- целевой якорь ----
ai=[i for i,a in enumerate(CUR['anchors']) if a['anchor']['group']=='m70' and a['anchor']['kcal']==2883][0]
A=CUR['anchors'][ai]; spec=A['anchor']; slots=A['slots']; G=spec['group']
print(f'Якорь #{ai}: {spec}')

deck={s:[] for s in set(slots)}
for i,x in recs.items():
    if not works(x,G) or i not in MM: continue
    mt=x.get('meal_type') or []; p=x['portions'][G]; mg=MM[i]['groups'].get(G)
    if not mg: continue
    ref,cpx=carb_fracs(x)
    rec={'id':i,'kcal':p['kcal'],'p':p['p'],'f':p['f'],'c':p['c'],
         'M':{k:mg.get(k,0) for k in FIELDS},'ref':ref,'cpx':cpx,
         'ings':set((ii.get('id','') or '') for ii in (x.get('ingredients') or []))}
    for s in set(slots):
        if s in mt: deck[s].append(rec)
print('дека по слотам:', {s:len(deck[s]) for s in set(slots)})

tk,tp,tf,tc=spec['kcal'],spec['p'],spec['f'],spec['c']
def macro_dev(k,p,f,c):
    return max(abs(k-tk)/tk,abs(p-tp)/tp,abs(f-tf)/tf,abs(c-tc)/tc)

pool=[]; t0=time.time(); random.seed(7); tried=0; best_md=1e9
while time.time()-t0<TIME_BUDGET:
    for _ in range(2000):
        tried+=1
        day=[random.choice(deck[s]) for s in slots]
        k=sum(d['kcal'] for d in day);p=sum(d['p'] for d in day)
        f=sum(d['f'] for d in day);c=sum(d['c'] for d in day)
        md=macro_dev(k,p,f,c)
        if md<best_md: best_md=md
        M={key:sum(d['M'][key] for d in day) for key in FIELDS}
        if any(M[key]>ULcap[key] for key in UL): continue     # UL-безопасность жёстко
        micro=sum(min(M[key]/RDA[key],1.0) for key in SCORE_F)
        cc=sum(d['c'] for d in day) or 1.0
        ref=sum(d['ref']*d['c'] for d in day)/cc; cpx=sum(d['cpx']*d['c'] for d in day)/cc
        carbq=cpx-ref
        score=-MACRO_W*md + micro + CARB_W*carbq              # близость доминирует, микро тянет
        ids=tuple(d['id'] for d in day)
        allings=set()
        for d in day: allings|=d['ings']
        pool.append({'score':score,'md':md,'ids':ids,'micro':micro,'M':M,'ref':ref,'cpx':cpx,'ings':allings})
    if len(pool)>6000:
        pool.sort(key=lambda z:-z['score']); pool=pool[:1500]
print(f'перебрано ~{tried}, лучший макро-md={best_md*100:.1f}%, пул={len(pool)}')
pool.sort(key=lambda z:-z['score']); pool=pool[:1500]

# жадный отбор 30: ПРИОРИТЕТ макро-близость (md доминирует), микро/разнообразие — мягкий тайбрейк
used=defaultdict(int); usedi=defaultdict(int); chosen=[]; seen=set()
while len(chosen)<30 and pool:
    best=None; bv=-1e9
    for c in pool:
        if c['ids'] in seen: continue
        rep=sum(used[i] for i in c['ids'])
        ingrep=sum(usedi[i] for i in c['ings'])/max(1,len(c['ings']))
        # -100*md тянет к близким дням; микро (0..20) и штраф повтора — вторичны
        v=-100.0*c['md'] + 0.5*c['micro'] - 0.4*rep - 0.1*ingrep
        if v>bv: bv=v; best=c
    if best is None: break
    chosen.append(best); seen.add(best['ids'])
    for i in best['ids']: used[i]+=1
    for i in best['ings']: usedi[i]+=1
    pool=[c for c in pool if c['ids']!=best['ids']]

if len(chosen)<30 and chosen:
    i=0
    while len(chosen)<30: chosen.append(chosen[i%len(chosen)]); i+=1

mds=[c['md'] for c in chosen]; mics=[c['micro'] for c in chosen]
print(f'отобрано {len(chosen)} дней · макро-откл: min {min(mds)*100:.1f}% / медиана {sorted(mds)[len(mds)//2]*100:.1f}% / max {max(mds)*100:.1f}%')
print(f'микро-покрытие (из {len(SCORE_F)}): среднее {sum(mics)/len(mics):.2f}')

# записать назад
new_days=[list(c['ids']) for c in chosen]
CUR['anchors'][ai]['days']=new_days
json.dump(CUR, open('anchors_seeds.json','w',encoding='utf-8'), ensure_ascii=False)
# обновить чекпоинт (1-based idx = ai+1)
import os
os.makedirs('seeds_super', exist_ok=True)
ck=f'seeds_super/anchor_{ai+1:03d}_{G}.json'
json.dump({'anchor':spec,'slots':slots,'days':new_days,
           'metrics':{'n_days':30,'note':'best-effort: ±3% недостижим для этого хвостового якоря'}},
          open(ck,'w',encoding='utf-8'), ensure_ascii=False)
print('записано в anchors_seeds.json и', ck)
