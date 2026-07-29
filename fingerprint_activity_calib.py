#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fingerprint_activity_calib.py — отпечаток УМНОЙ ПЕРЕКАЛИБРОВКИ мини-мотора активности (11.07).

Множители TDEE (1.20/1.375/1.55/1.725) и формула calculate() НЕ меняются. Меняется ТОЛЬКО
маппинг «ответы анкеты → один из 4 уровней»: баллы тайлов (work/steps/freq), пороги scoreToLevel.
Комбинация та же: level = scoreToLevel( max(ptsWork,ptsSteps) + ptsFreq ).

Скрипт:
 1) печатает матрицу base(work/steps) × freq(0..7) → уровень для СТАРОЙ и НОВОЙ схемы;
 2) гоняет демографическую сетку × все анкетные комбо, считает цель КБЖУ и якорь обеими
    схемами (live-множители, без EAT) и печатает, у скольких профилей сменился уровень/цель/якорь,
    + распределение по 4 уровням ДО/ПОСЛЕ.

Запуск: python3 fingerprint_activity_calib.py
"""
import json

anchors = json.load(open('anchors_seeds.json', encoding='utf-8'))['anchors']
MULT = {'sedentary':1.20,'light':1.375,'moderate':1.55,'active':1.725}   # LIVE, не меняем

# ---- СТАРАЯ схема маппинга ----
OLD_WORK  = [4, 18, 30, 44]
OLD_STEPS = [2, 16, 30, 44]
OLD_FREQ  = [0, 8, 10, 12, 14, 16, 18, 20]
def old_level(pts):
    if pts < 12: return 'sedentary'
    if pts < 26: return 'light'
    if pts < 44: return 'moderate'
    return 'active'

# ---- НОВАЯ схема маппинга ----
NEW_WORK  = [0, 15, 30, 45]
NEW_STEPS = [0, 15, 30, 45]
NEW_FREQ  = [0, 5, 10, 15, 20, 24, 28, 32]
def new_level(pts):
    if pts < 15: return 'sedentary'
    if pts < 30: return 'light'
    if pts < 45: return 'moderate'
    return 'active'

LRU = {'sedentary':'Низкая ', 'light':'Лёгкая ', 'moderate':'Средняя', 'active':'Высокая'}
BASE_LBL = ['сидит/≤3k', 'стоя/3-6k', 'ноги/6-10k', 'физтр/10k+']

def matrix(WORK, FREQ, lvlfn, title):
    print(f"\n==== {title} ====")
    print("           freq: " + "  ".join(f"{i}" for i in range(8)))
    for bi in range(4):
        cells = []
        for fi in range(8):
            pts = WORK[bi] + FREQ[fi]
            cells.append(LRU[lvlfn(pts)][:3])
        print(f"  {BASE_LBL[bi]:>11}: " + "  ".join(cells))

matrix(OLD_WORK, OLD_FREQ, old_level, "СТАРАЯ схема: base(work) × freq → уровень")
matrix(NEW_WORK, NEW_FREQ, new_level, "НОВАЯ схема: base(work) × freq → уровень")

# ---------- расчёт КБЖУ (реплика live calculate(), множители 1.20/1.375/1.55/1.725, без EAT) ----------
def weight_group(sex, w):
    if sex=='m': return 'm70' if w<70 else ('m90' if w<=90 else 'm90p')
    return 'f60' if w<60 else ('f80' if w<=80 else 'f80p')

def calc(sex, cw, tw, h, age, act):
    isMale = sex=='m'
    bmr = 10*cw + 6.25*h - 5*age + (5 if isMale else -161)
    tdee = bmr*MULT[act]
    isLoss = tw<cw; isGain = tw>cw
    lf = 0.80 if tdee>=2200 else 0.85
    kcal = round(tdee*lf if isLoss else (tdee*1.10 if isGain else tdee))
    kmin = 1500 if isMale else 1200
    if kcal<kmin: kcal=kmin
    bmi = cw/((h/100)**2); isObese = bmi>30; avgW=(cw+tw)/2
    below = act in ('sedentary','light')
    if isLoss: pc = 1.6 if below else (1.8 if act=='moderate' else 2.0)
    elif isGain: pc = 1.8 if below else 2.0
    else: pc = 1.6 if below else (1.8 if act=='moderate' else 2.0)
    pbw = avgW if isObese else cw
    if pc>2.0: pc=2.0
    protein = min(round(pbw*pc), 220)
    fc = (0.8 if isLoss else 0.9) if isMale else (0.9 if isLoss else 1.0)
    if isGain: fc = 1.0
    fmin = 60 if isMale else 55
    if isObese:
        fat = min(round(fc*tw), 100 if isMale else 90)
    else:
        fat = round(cw*fc)
    if fat<fmin: fat=fmin
    if isGain:
        fl = round(0.21*kcal/9)
        if fat<fl: fat=fl
    carbs = round((kcal - protein*4 - fat*9)/4)
    if carbs<130:
        coef=pc
        while carbs<130 and coef>1.6:
            coef=round((coef-0.1)*10)/10; protein=min(round(pbw*coef),220)
            carbs=round((kcal-protein*4-fat*9)/4)
        if carbs<0: carbs=0
    if carbs<120:
        kcal = protein*4 + fat*9 + 120*4; carbs = 120
    meal = 5 if isGain else 4
    return kcal, protein, fat, carbs, meal

def pick_anchor(kcal, p, f, c, meal, g):
    if not kcal: return None, 1e18
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
    return best, bestD

# ---------- популяционный отпечаток: демо-сетка × анкетные комбо ----------
ch_lvl=ch_t=ch_a=n=0
dist_old={k:0 for k in MULT}; dist_new={k:0 for k in MULT}
examples=[]
sumD_o=sumD_n=0.0; bad_o=bad_n=0; maxD_o=maxD_n=0.0
for sex in ('m','f'):
  for cw in range(45,111,5):
    for h in range(155,196,5):
      for age in (20,30,40,50):
        g=weight_group(sex,cw)
        for goal,dtw in (('loss',-6),('maintain',0),('gain',6)):
          tw=cw+dtw
          if tw<30: continue
          for bi in range(4):                 # 4 тира base (work≡steps параллельны)
            for fi in range(8):               # freq 0..7
              n+=1
              lo=old_level(OLD_WORK[bi]+OLD_FREQ[fi])
              ln=new_level(NEW_WORK[bi]+NEW_FREQ[fi])
              dist_old[lo]+=1; dist_new[ln]+=1
              if lo!=ln: ch_lvl+=1
              ok=calc(sex,cw,tw,h,age,lo)
              nk=calc(sex,cw,tw,h,age,ln)
              if ok[:4]!=nk[:4]: ch_t+=1
              ao,do=pick_anchor(*ok[:4],ok[4],g)
              an,dn=pick_anchor(*nk[:4],nk[4],g)
              sumD_o+=do; sumD_n+=dn
              if do>0.06: bad_o+=1
              if dn>0.06: bad_n+=1
              if do>maxD_o: maxD_o=do
              if dn>maxD_n: maxD_n=dn
              if ao!=an:
                  ch_a+=1
                  if len(examples)<12:
                      examples.append((sex,cw,age,BASE_LBL[bi],fi,lo,ln,ok[0],nk[0],ao,an))

print(f"\n==== ПОПУЛЯЦИОННЫЙ ОТПЕЧАТОК (демо-сетка × 4 base × 8 freq) ====")
print(f"анкетных профилей: {n}")
print(f"сменился УРОВЕНЬ активности: {ch_lvl} ({ch_lvl/n*100:.1f}%)")
print(f"изменилась ЦЕЛЬ КБЖУ:        {ch_t} ({ch_t/n*100:.1f}%)")
print(f"сменился ЯКОРЬ:              {ch_a} ({ch_a/n*100:.1f}%)")
print("\nраспределение по 4 уровням (доля анкетных профилей):")
print("  уровень     СТАРАЯ      НОВАЯ")
for k in ('sedentary','light','moderate','active'):
    print(f"  {LRU[k]}  {dist_old[k]/n*100:6.1f}%   {dist_new[k]/n*100:6.1f}%")
print("\nкачество матча профиль↔якорь (дистанция по долям Б/Ж/У; меньше = лучше):")
print(f"  средняя дистанция:  СТАРАЯ {sumD_o/n:.4f}   НОВАЯ {sumD_n/n:.4f}")
print(f"  «плохих» матчей >0.06:  СТАРАЯ {bad_o/n*100:.1f}%   НОВАЯ {bad_n/n*100:.1f}%")
print(f"  макс дистанция:     СТАРАЯ {maxD_o:.3f}    НОВАЯ {maxD_n:.3f}")
print("\nпримеры смены якоря:")
for e in examples:
    sex,cw,age,bl,fi,lo,ln,ko,kn,ao,an=e
    print(f"  {sex}{cw} a{age} [{bl} +{fi}трен] {lo[:3]}→{ln[:3]}: {ko}→{kn} ккал | якорь #{ao}→#{an}")
