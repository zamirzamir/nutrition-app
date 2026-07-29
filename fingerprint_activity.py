#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fingerprint_activity.py — отпечаток мотора КБЖУ ДО/ПОСЛЕ перенастройки активности (11.07).
Сравнивает СТАРУЮ модель (множители 1.20/1.375/1.55/1.725, БЕЗ тренировочных калорий) с
НОВОЙ (NEAT-множители 1.20/1.35/1.45/1.60 + EAT-калории по частоте). Для каждого профиля сетки
считает цель КБЖУ и выбранный якорь обеими моделями, затем сколько профилей сдвинулось.

Пол жира набора 21% — в ОБЕИХ моделях (уже live), чтобы мерить ТОЛЬКО эффект активности.
EAT для новой модели считается при частоте FREQ (по умолчанию 3 = дефолт приложения);
дополнительно печатается разброс сдвига якоря по частотам 1..5.

Запуск:  python3 fingerprint_activity.py [FREQ]
"""
import json, sys

FREQ = int(sys.argv[1]) if len(sys.argv) > 1 else 3
anchors = json.load(open('anchors_seeds.json', encoding='utf-8'))['anchors']

OLD_MULT = {'sedentary':1.20,'light':1.375,'moderate':1.55,'active':1.725}
NEW_MULT = {'sedentary':1.20,'light':1.35,'moderate':1.45,'active':1.60}
EAT_MET, EAT_HOURS = 5.0, 1.0

def eat_per_day(cw, freq):
    f = freq if 1 <= freq <= 5 else 3
    return round((EAT_MET-1)*cw*EAT_HOURS*f/7)

def weight_group(sex, w):
    if sex=='m': return 'm70' if w<70 else ('m90' if w<=90 else 'm90p')
    return 'f60' if w<60 else ('f80' if w<=80 else 'f80p')

def calc(sex, cw, tw, h, age, act, mult, eat):
    isMale = sex=='m'
    bmr = 10*cw + 6.25*h - 5*age + (5 if isMale else -161)
    tdee = bmr*mult[act]
    isLoss = tw<cw; isGain = tw>cw
    lf = 0.80 if tdee>=2200 else 0.85
    kcal = tdee*lf if isLoss else (tdee*1.10 if isGain else tdee)
    kcal = round(kcal)
    kcal += eat                       # EAT добавляется после дефицита/профицита (eat-back)
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
    if isGain:                        # пол жира набора 21% (live в обеих моделях)
        fl = round(0.21*kcal/9)
        if fat<fl: fat=fl
    carbs = round((kcal - protein*4 - fat*9)/4)
    if carbs<130:
        coef=pc
        while carbs<130 and coef>1.6:
            coef=round((coef-0.1)*10)/10; protein=round(pbw*coef)
            if protein>220: protein=220
            carbs=round((kcal-protein*4-fat*9)/4)
        if carbs<0: carbs=0
    if carbs<120:                     # минимум углеводов 120 (поднимаем калораж)
        kcal = protein*4 + fat*9 + 120*4
        carbs = 120
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

def run(freq):
    ch_t=ch_a=n=0; deltas=[]; moves=[]
    for sex in ('m','f'):
      for cw in range(45,111,5):
        for h in range(155,196,5):
          for age in (20,30,40,50):
            for act in ('sedentary','light','moderate','active'):
              for goal,dtw in (('loss',-6),('maintain',0),('gain',6)):
                tw=cw+dtw
                if tw<30: continue
                n+=1
                g=weight_group(sex,cw)
                ok=calc(sex,cw,tw,h,age,act,OLD_MULT,0)
                ek=eat_per_day(cw,freq)
                nk=calc(sex,cw,tw,h,age,act,NEW_MULT,ek)
                ai_o=pick_anchor(*ok[:4],ok[4],g)
                ai_n=pick_anchor(*nk[:4],nk[4],g)
                if ok[:4]!=nk[:4]: ch_t+=1
                deltas.append(nk[0]-ok[0])
                if ai_o!=ai_n:
                    ch_a+=1
                    moves.append((sex,cw,h,age,act,goal,ok[0],nk[0],ai_o,ai_n))
    return n,ch_t,ch_a,deltas,moves

n,ch_t,ch_a,deltas,moves=run(FREQ)
deltas.sort()
med=deltas[len(deltas)//2]
print(f"==== ОТПЕЧАТОК активности: старая vs новая (частота={FREQ}) ====")
print(f"профилей в сетке: {n}")
print(f"изменилась ЦЕЛЬ КБЖУ: {ch_t} ({ch_t/n*100:.1f}%)")
print(f"сменился ЯКОРЬ: {ch_a} ({ch_a/n*100:.1f}%)")
print(f"Δкалорий (новая−старая): min {deltas[0]}  медиана {med}  max {deltas[-1]}  среднее {sum(deltas)/len(deltas):.0f}")
print("примеры смены якоря:")
for m in moves[:12]:
    sex,cw,h,age,act,goal,ko,kn,ao,an=m
    print(f"  {sex}{cw} h{h} a{age} {act[:3]} {goal}: {ko}→{kn} ккал | якорь #{ao}→#{an}")
print("\n--- разброс смены якоря по частоте 1..5 ---")
for fr in range(1,6):
    _,_,ca,_,_=run(fr)
    print(f"  частота {fr}: сменился якорь у {ca} ({ca/n*100:.1f}%)")
