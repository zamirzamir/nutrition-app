#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fingerprint_kbju.py — «цифровой отпечаток» мотора КБЖУ + выбора якоря.
Прогоняет СЕТКУ профилей (пол×вес×рост×возраст×активность×цель) через точную реплику
calculate() и pickAnchor() из cabinet.html. Для каждого профиля пишет:
  цель (ккал/Б/Ж/У), весовую группу, число приёмов, выбранный якорь, жир%/угл%.

Параметр FAT_FLOOR_PCT — пол жира для НАБОРА (доля калорий). 0 = как было (база),
0.21 = кандидат (жир набора ≥21% калорий). Позволяет снять карту ДО и ПОСЛЕ и точно
увидеть, где мотор изменился. Мотор не трогаем — предпросмотр.

Запуск:  python3 fingerprint_kbju.py 0    base
         python3 fingerprint_kbju.py 0.21 cand
"""
import json, sys, os

FAT_FLOOR_PCT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
TAG = sys.argv[2] if len(sys.argv) > 2 else ('base' if FAT_FLOOR_PCT==0 else 'cand')
OUT = f'fingerprint_{TAG}.json'
anchors = json.load(open('anchors_seeds.json', encoding='utf-8'))['anchors']

def weight_group(sex, w):
    if sex=='m': return 'm70' if w<70 else ('m90' if w<=90 else 'm90p')
    return 'f60' if w<60 else ('f80' if w<=80 else 'f80p')

def calc(sex, cw, tw, h, age, act):
    isMale = sex=='m'
    bmr = 10*cw + 6.25*h - 5*age + (5 if isMale else -161)
    af = {'sedentary':1.20,'light':1.375,'moderate':1.55,'active':1.725}[act]
    tdee = bmr*af
    isLoss = tw<cw; isGain = tw>cw
    lf = 0.80 if tdee>=2200 else 0.85
    kcal = tdee*lf if isLoss else (tdee*1.10 if isGain else tdee)
    kcal = round(kcal)
    kmin = 1500 if isMale else 1200
    if kcal<kmin: kcal=kmin
    bmi = cw/((h/100)**2); isObese = bmi>30; avgW=(cw+tw)/2
    below = act in ('sedentary','light')
    if isLoss: pc = 1.6 if below else (1.8 if act=='moderate' else 2.0)
    elif isGain: pc = 1.8 if below else 2.0
    else: pc = 1.6 if below else (1.8 if act=='moderate' else 2.0)
    pbw = avgW if isObese else cw
    if pc>2.0: pc=2.0
    protein = round(pbw*pc)
    if protein>220: protein=220
    fc = (0.8 if isLoss else 0.9) if isMale else (0.9 if isLoss else 1.0)
    if isGain: fc = 1.0
    fmin = 60 if isMale else 55
    if isObese:
        fat = round(fc*tw); cap = 100 if isMale else 90
        if fat>cap: fat=cap
    else:
        fat = round(cw*fc)
    if fat<fmin: fat=fmin
    # ПОЛ ЖИРА ДЛЯ НАБОРА (новое правило): жир ≥ FAT_FLOOR_PCT калорий
    if isGain and FAT_FLOOR_PCT:
        fl = round(FAT_FLOOR_PCT*kcal/9)
        if fat<fl: fat=fl
    carbs = round((kcal - protein*4 - fat*9)/4)
    if carbs<130:
        coef=pc
        while carbs<130 and coef>1.6:
            coef=round((coef-0.1)*10)/10; protein=round(pbw*coef)
            if protein>220: protein=220
            carbs=round((kcal-protein*4-fat*9)/4)
        if carbs<0: carbs=0
    meal = 5 if isGain else 4
    return kcal, protein, fat, carbs, meal

def pick_anchor(kcal, p, f, c, meal, g):
    if not kcal: return None
    up, uf, uc = p*4/kcal, f*9/kcal, c*4/kcal
    def rd(t): return abs(t['p']*4/t['kcal']-up)+abs(t['f']*9/t['kcal']-uf)+abs(t['c']*4/t['kcal']-uc)
    best=None; bestD=1e18
    for i,a in enumerate(anchors):
        t=a['anchor']
        if t['meal']!=meal or t['group']!=g: continue
        d=rd(t)
        if d<bestD: bestD=d; best=i
    if best is None:
        for i,a in enumerate(anchors):
            t=a['anchor']
            if t['meal']!=meal: continue
            d=rd(t)
            if d<bestD: bestD=d; best=i
    return best

recs=[]
for sex in ('m','f'):
  for cw in range(45,111,5):
    for h in range(155,196,5):
      for age in (20,30,40,50):
        for act in ('sedentary','light','moderate','active'):
          for goal,dtw in (('loss',-6),('maintain',0),('gain',6)):
            tw=cw+dtw
            if tw<30: continue
            k,p,f,c,meal=calc(sex,cw,tw,h,age,act)
            g=weight_group(sex,cw)
            ai=pick_anchor(k,p,f,c,meal,g)
            recs.append({'key':f'{sex}{cw}h{h}a{age}{act[:3]}{goal}',
                         'sex':sex,'cw':cw,'h':h,'age':age,'act':act,'goal':goal,
                         'k':k,'p':p,'f':f,'c':c,'meal':meal,'g':g,'anchor':ai,
                         'fatpct':round(f*9/k*100,1),'carbpct':round(c*4/k*100,1)})
json.dump({'fat_floor_pct':FAT_FLOOR_PCT,'n':len(recs),'recs':recs},
          open(OUT,'w',encoding='utf-8'), ensure_ascii=False)
print(f'[{TAG}] fat_floor_pct={FAT_FLOOR_PCT} · профилей={len(recs)} → {OUT}')

b='fingerprint_base.json'; cc='fingerprint_cand.json'
if os.path.exists(b) and os.path.exists(cc):
    B={r['key']:r for r in json.load(open(b))['recs']}
    C={r['key']:r for r in json.load(open(cc))['recs']}
    keys=set(B)&set(C)
    ch_t=ch_a=gain_n=fatfix=over35=0; moves=[]
    for kk in keys:
        rb,rc=B[kk],C[kk]
        if rb['goal']=='gain': gain_n+=1
        if (rb['k'],rb['p'],rb['f'],rb['c'])!=(rc['k'],rc['p'],rc['f'],rc['c']): ch_t+=1
        if rb['anchor']!=rc['anchor']: ch_a+=1; moves.append((kk,rb['anchor'],rc['anchor'],rb['fatpct'],rc['fatpct']))
        if rb['goal']=='gain' and rb['fatpct']<21 and rc['fatpct']>=21: fatfix+=1
        if rc['fatpct']>35: over35+=1
    bad=[kk for kk in keys if B[kk]['goal']!='gain' and (B[kk]['k'],B[kk]['p'],B[kk]['f'],B[kk]['c'])!=(C[kk]['k'],C[kk]['p'],C[kk]['f'],C[kk]['c'])]
    print(f'\n==== DIFF base vs cand(пол {json.load(open(cc))["fat_floor_pct"]}) ====')
    print(f'профилей: {len(keys)} · набор: {gain_n}')
    print(f'изменилась ЦЕЛЬ: {ch_t} ({ch_t/len(keys)*100:.1f}%)')
    print(f'сменился ЯКОРЬ: {ch_a} ({ch_a/len(keys)*100:.1f}%)')
    print(f'наборных подняты <21% → ≥21%: {fatfix}')
    print(f'профилей с жир>35% после (перебор верха): {over35}')
    print(f'⚠ изменились НЕ-наборные (ожид. 0): {len(bad)}')
    for kk,a0,a1,f0,f1 in moves[:10]:
        print(f'  {kk}: #{a0}→#{a1} | жир {f0}%→{f1}%')
