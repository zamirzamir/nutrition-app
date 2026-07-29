#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_poor_anchors.py — чинит якоря с БЕДНЫМ разнообразием (мало уникальных блюд).
Причина: экстремальный профиль Б/Ж/У почти не собирается из ФИКС-порций при ±3%.
Решение: для таких якорей расширяем коридор seed'а прогрессивно (±3→±5→±8%), пока
не наберётся достаточно РАЗНЫХ дней. Это безопасно: живой движок всё равно дотягивает
каждый день до ±3% под конкретного человека (rebalanceDayMacros, коридор порций ±20%).
UL и микро-скоринг сохраняются. Обычные якоря НЕ трогаем.

Пишет в anchors_seeds.json НА МЕСТЕ (бэкап делается перед запуском).
ПАРАЛЛЕЛЬНО: бедные якоря делятся между процессами-воркерами; воркеры НИЧЕГО не пишут
на диск — только возвращают результат. anchors_seeds.json и .poor_attempted.json пишет
РОДИТЕЛЬ один раз в конце (гонок записи нет). Прервали до конца — просто запусти заново.
Запуск: python3 fix_poor_anchors.py                    # 90 сек/якорь, воркеров = ядра−2
        python3 fix_poor_anchors.py 120 --workers 8    # 120 сек/якорь, 8 процессов
"""
import json, random, time, os, sys
from collections import defaultdict

UNIQUE_THRESH = 40      # якоря с уникальных БЛЮД < этого — чиним
# 15.07: второй критерий. Бывает, что блюд у якоря МНОГО (>40), но из них не складывается
# 30 РАЗНЫХ дней под жёсткие макросы — тогда месяц крутит мало комбинаций (напр. #189: 120 блюд,
# но 12 уникальных дней). Такие тоже чиним расширенным коридором.
DAYS_THRESH = 28        # якоря с уникальных ДНЕЙ < этого — чиним
TARGET_DISTINCT = 26    # сколько разных дней хотим найти, прежде чем сузить коридор обратно
TOLS = [0.03, 0.05, 0.08]
# сек на якорь. Реальное значение задаётся аргументом в main(); воркеры получают через _init_worker.
TIME_PER = 90.0
CARB_W = 4.0
DIV_PEN = 0.55

recs = {x['id']: x for x in json.load(open('recipes.json', encoding='utf-8'))}
MM = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))['dishes']
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
doc = json.load(open('anchors_seeds.json', encoding='utf-8'))
anchors = doc['anchors']

RDA = {'vitamin_a':900,'vitamin_b1':1.2,'vitamin_b2':1.3,'vitamin_b3':16,'vitamin_b5':5,'vitamin_b6':1.3,
 'vitamin_b9':400,'vitamin_b12':2.4,'vitamin_c':90,'vitamin_k':120,'calcium':1000,'iron':8,'magnesium':400,
 'phosphorus':700,'potassium':3400,'zinc':11,'selenium':55,'omega3':1.6,'omega6':17,'fiber':38}
UL = {'vitamin_a':3000,'vitamin_b3':35,'vitamin_b6':100,'vitamin_b9':1000,'vitamin_c':2000,'vitamin_d':100,
 'vitamin_e':1000,'calcium':2500,'iron':45,'zinc':40,'selenium':400,'phosphorus':4000}
UL_SAFE = {'vitamin_a':0.8,'vitamin_d':0.8,'iron':0.8,'zinc':0.8,'selenium':0.8}
ULcap = {k: UL[k]*UL_SAFE.get(k,1.0) for k in UL}
SCORE_F = [k for k in RDA if k not in ('vitamin_d','vitamin_e')]
REFINED = ['белый хлеб','батон','бейгл','багет','булочк','круассан','макарон','вермишель','спагетти','лапша','сахар','пончик','вафл']
COMPLEX = ['овсян','геркулес','гречк','бурый рис','дикий рис','киноа','булгур','перлов','чечевиц','фасоль','нут','горох','цельнозерн','отруб','батат','пшено']

def carb_fr(x):
    ings=x.get('ingredients') or []; tot=ref=cpx=0.0
    for i in ings:
        g=float(i.get('amount_g',0) or 0)
        if g<=0: continue
        tot+=g; n=(i.get('id','') or '').lower()
        if any(w in n for w in REFINED): ref+=g
        if any(w in n for w in COMPLEX): cpx+=g
    return (ref/tot,cpx/tot) if tot else (0,0)

def works(x,G):
    if x.get('balance_off'): return False
    p=(x.get('portions') or {}).get(G); return bool(p and p.get('p') and p.get('f') and p['p']>=1.2*p['f'])

def rebuild(an):
    spec=an['anchor']; G=spec['group']; T=spec; slots=an['slots']; ss=set(slots)
    deck={s:[] for s in ss}
    for i,x in recs.items():
        if not works(x,G) or i not in MM: continue
        mt=x.get('meal_type') or []; p=x['portions'][G]; mg=MM[i]['groups'].get(G)
        if not mg: continue
        ref,cpx=carb_fr(x)
        rec={'id':i,'kcal':p['kcal'],'p':p['p'],'f':p['f'],'c':p['c'],'M':{k:mg.get(k,0) for k in FIELDS},'ref':ref,'cpx':cpx}
        for s in ss:
            if s in mt: deck[s].append(rec)
    if any(not deck[s] for s in slots): return None
    ok=lambda v,t,tol: t>0 and abs(v-t)/t<=tol
    # прогрессивный коридор
    pool={}; used_tol=TOLS[0]
    for tol in TOLS:
        t0=time.time()
        while time.time()-t0<TIME_PER/len(TOLS):
            for _ in range(2000):
                # фикс 15.07: id блюд в дне УНИКАЛЬНЫ (тот же запрет, что в build_super_presets).
                # Раньше fix_poor собирал день через random.choice БЕЗ проверки → возвращал дубли
                # (одно блюдо в двух слотах дня), вычищенные ранее фиксом D6.
                day=[]; _uid=set()
                for s in slots:
                    cand=random.choice(deck[s])
                    if cand['id'] in _uid:
                        alts=[d for d in deck[s] if d['id'] not in _uid]
                        if not alts: day=None; break
                        cand=random.choice(alts)
                    day.append(cand); _uid.add(cand['id'])
                if day is None: continue
                k=sum(d['kcal'] for d in day)
                if not ok(k,T['kcal'],tol): continue
                p=sum(d['p'] for d in day); f=sum(d['f'] for d in day); c=sum(d['c'] for d in day)
                if not (ok(p,T['p'],tol) and ok(f,T['f'],tol) and ok(c,T['c'],tol)): continue
                M={key:sum(d['M'][key] for d in day) for key in FIELDS}
                if any(M[key]>ULcap[key] for key in UL): continue
                ids=tuple(d['id'] for d in day)
                if ids in pool: continue
                micro=sum(min(M[key]/RDA[key],1.0) for key in SCORE_F)
                cc=sum(d['c'] for d in day) or 1
                carbq=sum(d['cpx']*d['c'] for d in day)/cc - sum(d['ref']*d['c'] for d in day)/cc
                dev=max(abs(k-T['kcal'])/T['kcal'],abs(p-T['p'])/T['p'],abs(f-T['f'])/T['f'],abs(c-T['c'])/T['c'])
                pool[ids]={'score':micro+CARB_W*carbq,'dev':dev}
        used_tol=tol
        if len(pool)>=TARGET_DISTINCT: break
    if not pool: return None
    cands=sorted(pool.items(), key=lambda kv:-kv[1]['score'])
    # жадный отбор 28 с разнообразием
    used=defaultdict(int); chosen=[]
    while len(chosen)<28 and cands:
        best=None; bv=-1e9
        for ids,meta in cands:
            rep=sum(used[i] for i in ids)
            val=meta['score']-DIV_PEN*rep
            if val>bv: bv=val; best=(ids,meta)
        chosen.append(best);
        for i in best[0]: used[i]+=1
        cands=[c for c in cands if c[0]!=best[0]]
        if not cands and len(chosen)<28:  # мало дней — доберём повтором лучших
            cands=sorted(pool.items(), key=lambda kv:-kv[1]['score'])
    days=[list(ids) for ids,_ in chosen][:28]
    while len(days)<28 and days: days.append(days[len(days)%len(days)])
    maxdev=max(pool[tuple(d)]['dev'] for d in days if tuple(d) in pool)
    return days, used_tol, maxdev, len(set(i for d in days for i in d)), len(pool)

def uniq(an): return len(set(i for d in an['days'] for i in d))
def uniq_days(an): return len({tuple(d) for d in an['days']})   # 15.07: уникальных ДНЕЙ (комбинаций)

ATT_FILE='.poor_attempted.json'

# ---------- параллельные воркеры ----------
def _init_worker(time_per):
    """Инициализация воркера: только время поиска. Данные каждый процесс грузит сам (spawn)."""
    global TIME_PER
    TIME_PER = time_per

def _fix_one(task):
    """Воркер: пересобирает ОДИН якорь (логика rebuild — байт в байт та же) и
    ВОЗВРАЩАЕТ результат родителю. Файлы НЕ пишет — писать может только родитель."""
    i, an = task
    print(f'  [pid {os.getpid()}] старт #{i} {an["anchor"]["group"]} {an["anchor"]["kcal"]}ккал '
          f'(уник сейчас {uniq(an)}, {TIME_PER:.0f}с)', flush=True)
    return i, rebuild(an)

def main():
    import argparse, multiprocessing as mp
    global TIME_PER
    ap = argparse.ArgumentParser(description='Починка бедных якорей (параллельно по процессам)')
    ap.add_argument('time_per', nargs='?', type=float, default=90.0,
                    help='сек поиска на якорь (по умолчанию 90)')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 3) - 2),
                    help='число процессов (по умолчанию: все ядра минус 2)')
    args = ap.parse_args()
    TIME_PER = args.time_per
    workers = max(1, args.workers)

    attempted=set()
    if os.path.exists(ATT_FILE):
        try: attempted=set(json.load(open(ATT_FILE)))
        except Exception: attempted=set()
    # 15.07: берём якорь, если беден ПО БЛЮДАМ (<40) ИЛИ по КОМБИНАЦИЯМ ДНЕЙ (<28) —
    # второе ловит случаи вроде #189 (120 блюд, но всего 12 разных дней на месяц).
    poor=[(i,an) for i,an in enumerate(anchors)
          if (uniq(an)<UNIQUE_THRESH or uniq_days(an)<DAYS_THRESH) and i not in attempted]
    print(f'Якорей бедных (блюд < {UNIQUE_THRESH} или уник. дней < {DAYS_THRESH}), не пробованных: {len(poor)}. '
          f'Чиним на {min(workers, max(1,len(poor)))} воркер(ах); каждый якорь — ровно одному процессу. '
          f'anchors_seeds.json будет записан ОДИН раз в конце.', flush=True)
    report=[]; processed=[]
    if poor:
        # spawn — тот же механизм запуска процессов, что на macOS по умолчанию
        ctx = mp.get_context('spawn')
        with ctx.Pool(processes=min(workers, len(poor)),
                      initializer=_init_worker, initargs=(TIME_PER,)) as pool:
            for i, res in pool.imap_unordered(_fix_one, poor):
                an = anchors[i]            # родительская копия документа — её и обновляем
                before = uniq(an)
                processed.append(i)
                if not res:
                    print(f'  #{i} {an["anchor"]["group"]} — не удалось, оставляю как есть', flush=True)
                    continue
                days,tol,maxdev,after,npool=res
                # ЗАЩИТА «НЕ УХУДШАТЬ»: заменяем якорь ТОЛЬКО если новых уникальных блюд СТРОГО больше.
                if after <= before:
                    print(f'  #{i} {an["anchor"]["group"]} {an["anchor"]["kcal"]}ккал: новый вариант '
                          f'{after} ≤ текущего {before} — ОСТАВЛЯЮ старый (не ухудшаю)', flush=True)
                    continue
                an['days']=days
                report.append((i,an['anchor'],before,after,tol,round(maxdev*100,1),npool))
                print(f'  #{i} {an["anchor"]["group"]} {an["anchor"]["kcal"]}ккал: уник {before}→{after} '
                      f'(коридор ±{int(tol*100)}%, макс. откл {round(maxdev*100,1)}%, пул дней {npool}) [принято ✅]', flush=True)

    # --- запись на диск: ТОЛЬКО родитель, ОДИН раз, после завершения всех воркеров ---
    if report:
        json.dump(doc, open('anchors_seeds.json','w',encoding='utf-8'), ensure_ascii=False)
    if processed:
        attempted |= set(processed)
        json.dump(sorted(attempted), open(ATT_FILE,'w'))

    print(f'\nОбновлено якорей: {len(report)}. ' +
          ('Записано в anchors_seeds.json.' if report else 'anchors_seeds.json НЕ менялся (улучшений нет).'))
    print('Эти якоря используют более широкий seed-коридор; движок дотянет до ±3% под человека.')

if __name__ == '__main__':
    main()
