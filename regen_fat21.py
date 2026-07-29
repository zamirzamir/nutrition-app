#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regen_fat21.py — перегенерация seed-дней у 14 якорей, чья цель жира была < 21%
калорий, под НОВОЕ правило «пол жира для набора = 21% калорий».

Спеки якорей (f и c) уже обновлены в anchors_seeds.json отдельным шагом:
  f_new = round(0.21*kcal/9),  c_new = round((kcal - p*4 - f_new*9)/4),  p и kcal без изменений.
Здесь берём эти НОВЫЕ цели (spec['f'], spec['c']) и пересобираем 30 дней ровно как
build_super_presets.py (та же дека, ±3% по 4 макро, UL-безопасность, максимизация
микро-покрытия RDA + сложные углеводы + разнообразие жадным отбором).

Если ±3% для якоря структурно недостижим (как #84) — best-effort: 30 лучших достижимых
(минимум макс-макро-отклонения), как в fix_anchor84.py. Не падаем.

ВОЗОБНОВЛЯЕМЫЙ: чекпоинт на якорь в seeds_fat21/. Готовые (30 дней) пропускаются.
Бюджеты через env:
  REGEN_BUDGET   — сек поиска на якорь (по умолч. 15)
  REGEN_WALL     — сек общего бюджета на ЭТОТ вызов (по умолч. 38), после — стоп
Запускать несколько раз, пока все 14 не готовы. Затем merge (см. --merge).

    python3 regen_fat21.py            # прогон (несколько раз)
    python3 regen_fat21.py --merge    # влить готовые дни в anchors_seeds.json
"""
import json, random, time, os, sys
from collections import defaultdict

BUDGET = float(os.environ.get('REGEN_BUDGET', '15'))
WALL   = float(os.environ.get('REGEN_WALL', '38'))
OUT_DIR = 'seeds_fat21'
CARB_W = 4.0
MACRO_W = 200.0
DIVERSITY_REUSE_PEN = 0.55
POOL_KEEP = 1500
TARGET_IDX = [43, 84, 92, 93, 104, 109, 120, 128, 132, 139, 145, 159, 211, 230]

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
    ings=x.get('ingredients') or []; tot=ref=cpx=0.0
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

def build_deck(G, slots_set):
    deck={s:[] for s in slots_set}
    for i,x in recs.items():
        if not works(x,G) or i not in MM: continue
        mt=x.get('meal_type') or []; p=x['portions'][G]; mg=MM[i]['groups'].get(G)
        if not mg: continue
        ref,cpx=carb_fracs(x)
        rec={'id':i,'kcal':p['kcal'],'p':p['p'],'f':p['f'],'c':p['c'],
             'M':{k:mg.get(k,0) for k in FIELDS},'ref':ref,'cpx':cpx,
             'ings':set((ii.get('id','') or '') for ii in (x.get('ingredients') or []))}
        for s in slots_set:
            if s in mt: deck[s].append(rec)
    return deck

def regen_anchor(A):
    spec=A['anchor']; slots=A['slots']; G=spec['group']; slots_set=set(slots)
    tk,tp,tf,tc=spec['kcal'],spec['p'],spec['f'],spec['c']
    deck=build_deck(G, slots_set)
    if any(not deck[s] for s in slots_set):
        return None
    id2rec={}
    for s in slots_set:
        for d in deck[s]: id2rec[d['id']]=d
    def macro_dev(k,p,f,c):
        return max(abs(k-tk)/tk,abs(p-tp)/tp,abs(f-tf)/tf,abs(c-tc)/tc)

    def feats(day):
        """полные признаки дня (micro/carbq/M/ings) — считаем лениво только для кандидатов."""
        M={key:sum(d['M'][key] for d in day) for key in FIELDS}
        micro=sum(min(M[key]/RDA[key],1.0) for key in SCORE_F)
        cc=sum(d['c'] for d in day) or 1.0
        ref=sum(d['ref']*d['c'] for d in day)/cc
        cpx=sum(d['cpx']*d['c'] for d in day)/cc
        allings=set()
        for d in day: allings|=d['ings']
        return M,micro,cpx-ref,ref,cpx,allings

    def climb(day, k,p,f,c):
        """координатный спуск по md: в каждом слоте берём блюдо, минимизирующее md."""
        md=macro_dev(k,p,f,c)
        improved=True; passes=0
        while improved and passes<6:
            improved=False; passes+=1
            for si,s in enumerate(slots):
                cur=day[si]
                bestd=cur; bestmd=md; bk,bp,bf,bc=k,p,f,c
                for cand in deck[s]:
                    nk=k-cur['kcal']+cand['kcal']; np_=p-cur['p']+cand['p']
                    nf=f-cur['f']+cand['f']; nc=c-cur['c']+cand['c']
                    nmd=macro_dev(nk,np_,nf,nc)
                    if nmd<bestmd-1e-12:
                        bestmd=nmd; bestd=cand; bk,bp,bf,bc=nk,np_,nf,nc
                if bestd is not cur:
                    day[si]=bestd; k,p,f,c=bk,bp,bf,bc; md=bestmd; improved=True
        return day,k,p,f,c,md

    strict_ids=set(); strict_days=[]; best_pool=[]; tried=0; best_md=1e9
    t0=time.time()
    while time.time()-t0 < BUDGET:
        for _ in range(400):
            tried+=1
            day=[random.choice(deck[s]) for s in slots]
            k=sum(d['kcal'] for d in day); p=sum(d['p'] for d in day)
            f=sum(d['f'] for d in day); c=sum(d['c'] for d in day)
            day,k,p,f,c,md=climb(day,k,p,f,c)
            if md<best_md: best_md=md
            ids=tuple(d['id'] for d in day)
            # UL-безопасность жёстко
            M={key:sum(d['M'][key] for d in day) for key in FIELDS}
            if any(M[key]>ULcap[key] for key in UL): continue
            if md<=0.03+1e-9:
                if ids not in strict_ids:
                    strict_ids.add(ids); strict_days.append((ids,day))
            else:
                best_pool.append((md,ids,day))
        if len(best_pool)>4000:
            best_pool.sort(key=lambda z:z[0]); best_pool=best_pool[:POOL_KEEP]
        if len(strict_ids)>=200:   # достаточно строгих для качественного отбора 30 с разнообразием
            break

    # собрать уникальный пул кандидатов с полными признаками
    def mk(ids,day,md):
        M,micro,carbq,ref,cpx,allings=feats(day)
        return {'md':md,'ids':ids,'micro':micro,'carbq':carbq,'M':M,
                'ref':ref,'cpx':cpx,'ings':allings}
    strict=[mk(ids,day,macro_dev(sum(d['kcal'] for d in day),sum(d['p'] for d in day),
              sum(d['f'] for d in day),sum(d['c'] for d in day))) for ids,day in strict_days]
    best_pool.sort(key=lambda z:z[0])
    seen=set(ids for ids,_ in strict_days); be=[]
    for md,ids,day in best_pool:
        if ids in seen: continue
        seen.add(ids); be.append(mk(ids,day,md))
        if len(be)>=POOL_KEEP: break
    uniq_pool=strict+be
    if not uniq_pool:
        return None

    used=defaultdict(int); usedi=defaultdict(int); chosen=[]; picked=set()
    if len(strict)>=30:
        mode='strict'
        cand_pool=strict
        # жадный отбор как в build_super_presets: макс микро + сложные − повторы
        while len(chosen)<30 and cand_pool:
            best=None; bv=-1e18
            for c in cand_pool:
                if c['ids'] in picked: continue
                rep=sum(used[i] for i in c['ids'])
                ingrep=sum(usedi[i] for i in c['ings'])/max(1,len(c['ings']))
                score=c['micro']+CARB_W*c['carbq']
                val=score - DIVERSITY_REUSE_PEN*rep - 0.15*ingrep
                if val>bv: bv=val; best=c
            if best is None: break
            chosen.append(best); picked.add(best['ids'])
            for i in best['ids']: used[i]+=1
            for i in best['ings']: usedi[i]+=1
            cand_pool=[c for c in cand_pool if c['ids']!=best['ids']]
    else:
        mode='best-effort'
        cand_pool=uniq_pool
        # приоритет — макро-близость (md), микро/разнообразие как мягкий тайбрейк
        while len(chosen)<30 and cand_pool:
            best=None; bv=-1e18
            for c in cand_pool:
                if c['ids'] in picked: continue
                rep=sum(used[i] for i in c['ids'])
                ingrep=sum(usedi[i] for i in c['ings'])/max(1,len(c['ings']))
                val=-100.0*c['md'] + 0.5*c['micro'] - 0.4*rep - 0.1*ingrep
                if val>bv: bv=val; best=c
            if best is None: break
            chosen.append(best); picked.add(best['ids'])
            for i in best['ids']: used[i]+=1
            for i in best['ings']: usedi[i]+=1
            cand_pool=[c for c in cand_pool if c['ids']!=best['ids']]

    if len(chosen)<30 and chosen:
        i=0
        while len(chosen)<30: chosen.append(chosen[i%len(chosen)]); i+=1
    if not chosen:
        return None
    mds=sorted(c['md'] for c in chosen)
    mics=[c['micro'] for c in chosen]
    days=[list(c['ids']) for c in chosen]
    metrics={'n_days':len(days),'mode':mode,'tried':tried,'best_md_seen':round(best_md*100,2),
             'md_min':round(mds[0]*100,2),'md_med':round(mds[len(mds)//2]*100,2),
             'md_max':round(mds[-1]*100,2),'avg_micro':round(sum(mics)/len(mics),2),
             'strict_unique':len(strict)}
    return {'anchor':spec,'slots':slots,'days':days,'metrics':metrics}

def do_merge():
    n=0; report=[]
    for idx in TARGET_IDX:
        spec=CUR['anchors'][idx]['anchor']; G=spec['group']
        fn=f'{OUT_DIR}/anchor_{idx:03d}_{G}.json'
        if not os.path.exists(fn):
            report.append((idx,G,'НЕТ чекпоинта',None)); continue
        d=json.load(open(fn,encoding='utf-8'))
        days=d.get('days') or []
        if len(days)<30:
            report.append((idx,G,f'НЕПОЛНЫЙ ({len(days)})',None)); continue
        CUR['anchors'][idx]['days']=days[:30]
        n+=1
        report.append((idx,G,d.get('metrics',{}).get('mode','?'),d.get('metrics',{})))
    json.dump(CUR, open('anchors_seeds.json','w',encoding='utf-8'), ensure_ascii=False)
    print(f'ВЛИТО якорей: {n}/{len(TARGET_IDX)}')
    for idx,G,mode,m in report:
        if m: print(f'  #{idx} {G}: {mode} · md min/med/max {m.get("md_min")}/{m.get("md_med")}/{m.get("md_max")}% · микро {m.get("avg_micro")}')
        else: print(f'  #{idx} {G}: {mode}')

if __name__=='__main__':
    if '--merge' in sys.argv:
        do_merge(); sys.exit(0)
    os.makedirs(OUT_DIR, exist_ok=True)
    wall0=time.time()
    for idx in TARGET_IDX:
        spec=CUR['anchors'][idx]['anchor']; G=spec['group']
        fn=f'{OUT_DIR}/anchor_{idx:03d}_{G}.json'
        if os.path.exists(fn):
            try:
                _c=json.load(open(fn,encoding='utf-8'))
                if len(_c.get('days') or [])>=30:
                    continue
            except Exception:
                pass
        if time.time()-wall0 > WALL:
            print('WALL-бюджет исчерпан, стоп. Запусти скрипт снова.'); break
        random.seed(1000+idx)
        res=regen_anchor(CUR['anchors'][idx])
        if res is None:
            print(f'#{idx} {G}: пул пуст / дека неполна — ПРОПУЩЕН (проверь)'); continue
        json.dump(res, open(fn,'w',encoding='utf-8'), ensure_ascii=False)
        m=res['metrics']
        print(f'#{idx} {G} kcal{spec["kcal"]} → {m["n_days"]}дн [{m["mode"]}] '
              f'md {m["md_min"]}/{m["md_med"]}/{m["md_max"]}% микро {m["avg_micro"]} '
              f'strict_uniq {m["strict_unique"]} tried {m["tried"]}')
    # статус готовности
    done=sum(1 for idx in TARGET_IDX
             if os.path.exists(f'{OUT_DIR}/anchor_{idx:03d}_{CUR["anchors"][idx]["anchor"]["group"]}.json')
             and len(json.load(open(f'{OUT_DIR}/anchor_{idx:03d}_{CUR["anchors"][idx]["anchor"]["group"]}.json',encoding='utf-8')).get('days') or [])>=30)
    print(f'ГОТОВО {done}/{len(TARGET_IDX)} якорей. ' + ('ВСЕ — запусти --merge.' if done==len(TARGET_IDX) else 'Запусти скрипт снова для остальных.'))
