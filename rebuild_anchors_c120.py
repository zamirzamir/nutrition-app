#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_anchors_c120.py — пересборка якорей под новое правило «минимум углеводов 120 г»
(п.8б, утверждено Замиром и Романом 10.07.2026).

Что делает:
  • Берёт из anchors_seeds.json якоря с углеводами < 120 г (~44 шт).
  • Пересчитывает их цели ТОЧНО по правилу п.8б: kcal' = 4·Б + 9·Ж + 480, У' = 120
    (белок и жир не меняются — правило их не трогает).
  • Собирает под новые цели 30 seed-дней тем же алгоритмом, что build_super_presets.py
    (та же дека: без balance_off, без снек-концентратов, Б ≥ 1.2·Ж).
  • Чекпоинты — в СВОЮ папку seeds_super_c120/ (не конфликтует с идущей ночной сборкой).
  • Итог: anchors_seeds_C120.json (только пересобранные якоря, с обновлёнными спеками).

Запуск (можно ПАРАЛЛЕЛЬНО ночной сборке):
    python3 rebuild_anchors_c120.py 600      # 600 сек/якорь · 44 якоря ≈ 7.3 ч
Возобновляемый: прерывание безопасно, готовые чекпоинты пропускаются.

После окончания ОБЕИХ сборок собери финал:
    python3 merge_presets_final.py
"""
import json, random, time, os, sys
from collections import defaultdict

TIME_PER_ANCHOR = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
OUT_DIR = 'seeds_super_c120'
OUT_FILE = 'anchors_seeds_C120.json'
CARB_W = 4.0
DIVERSITY_REUSE_PEN = 0.55
POOL_KEEP = 1500
C_MIN = 120   # новое правило

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
SNACK_CONC = ('сухофрукт','изюм','курага','чернослив','финик','инжир','урюк','цукат',
              'вялен','сушён','сушен','шоколад','батончик','гранат')

def is_snack_concentrate(x):
    name = (x.get('name','') or '').lower()
    tags = x.get('tags') or {}
    cats = set(tags.get('cats') or [])
    if tags.get('dish_type') == 'снек-сухофрукты': return True
    if cats & {'сухофрукты','орехи'} and len(x.get('ingredients') or []) <= 2: return True
    return any(w in name for w in SNACK_CONC) and len(x.get('ingredients') or []) <= 2

def carb_fracs(x):
    ings = x.get('ingredients') or []
    tot = ref = cpx = 0.0
    for i in ings:
        g = float(i.get('amount_g', 0) or 0)
        if g <= 0: continue
        tot += g; n = (i.get('id','') or '').lower()
        if any(w in n for w in REFINED): ref += g
        if any(w in n for w in COMPLEX): cpx += g
    if tot <= 0: return 0.0, 0.0
    return ref/tot, cpx/tot

def works(x, G):
    if x.get('balance_off'): return False
    if is_snack_concentrate(x): return False
    p = (x.get('portions') or {}).get(G)
    return bool(p and p.get('p') and p.get('f') and p['p'] >= 1.2*p['f'])

def build_deck(G, slots_set):
    deck = {s: [] for s in slots_set}
    for i, x in recs.items():
        if not works(x, G) or i not in MM: continue
        mt = x.get('meal_type') or []
        p = x['portions'][G]; mg = MM[i]['groups'].get(G)
        if not mg: continue
        ref, cpx = carb_fracs(x)
        rec = {'id': i, 'kcal': p['kcal'], 'p': p['p'], 'f': p['f'], 'c': p['c'],
               'M': {k: mg.get(k, 0) for k in FIELDS}, 'ref': ref, 'cpx': cpx,
               'ings': set((ii.get('id','') or '') for ii in (x.get('ingredients') or []))}
        for s in slots_set:
            if s in mt: deck[s].append(rec)
    return deck

def day_carb_shares(day):
    cc = sum(d['c'] for d in day) or 1.0
    return (sum(d['ref']*d['c'] for d in day)/cc, sum(d['cpx']*d['c'] for d in day)/cc)

def build_super_seed(T):
    G = T['group']; slots = T['slots']; slots_set = set(slots)
    deck = build_deck(G, slots_set)
    if any(not deck[s] for s in slots): return None
    ok = lambda v, t, tol=0.03: t > 0 and abs(v-t)/t <= tol
    pool = []; t0 = time.time()
    while time.time() - t0 < TIME_PER_ANCHOR:
        for _ in range(800):
            day = [random.choice(deck[s]) for s in slots]
            k = sum(d['kcal'] for d in day)
            if not ok(k, T['kcal']): continue
            p = sum(d['p'] for d in day); f = sum(d['f'] for d in day); c = sum(d['c'] for d in day)
            if not (ok(p, T['p']) and ok(f, T['f']) and ok(c, T['c'])): continue
            M = {key: sum(d['M'][key] for d in day) for key in FIELDS}
            if any(M[key] > ULcap[key] for key in UL): continue
            micro = sum(min(M[key]/RDA[key], 1.0) for key in SCORE_F)
            ref, cpx = day_carb_shares(day)
            score = micro + CARB_W * (cpx - ref)
            allings = set()
            for d in day: allings |= d['ings']
            pool.append({'score': score, 'ids': tuple(d['id'] for d in day), 'M': M,
                         'ref': ref, 'cpx': cpx, 'ings': allings})
        if len(pool) > POOL_KEEP * 4:
            pool.sort(key=lambda z: -z['score']); pool = pool[:POOL_KEEP]
    if not pool: return None
    pool.sort(key=lambda z: -z['score']); pool = pool[:POOL_KEEP]
    used_dish = defaultdict(int); used_ing = defaultdict(int)
    chosen = []; seen_days = set()
    while len(chosen) < 30 and pool:
        best = None; best_val = -1e9
        for cand in pool:
            if cand['ids'] in seen_days: continue
            rep = sum(used_dish[i] for i in cand['ids'])
            ingrep = sum(used_ing[i] for i in cand['ings']) / max(1, len(cand['ings']))
            val = cand['score'] - DIVERSITY_REUSE_PEN * rep - 0.15 * ingrep
            if val > best_val: best_val = val; best = cand
        if best is None: break
        chosen.append(best); seen_days.add(best['ids'])
        for i in best['ids']: used_dish[i] += 1
        for i in best['ings']: used_ing[i] += 1
        pool = [c for c in pool if c['ids'] != best['ids']]
    if not chosen: return None
    return {'days': [list(c['ids']) for c in chosen],
            'metrics': {'n_days': len(chosen),
                        'unique_dishes': len(set(i for c in chosen for i in c['ids']))}}

# ---------- пересчёт целей и прогон ----------
os.makedirs(OUT_DIR, exist_ok=True)
targets = []
for idx, A in enumerate(CUR['anchors'], 1):
    s = A['anchor']
    if s.get('c', 999) >= C_MIN: continue
    new_kcal = round(4*s['p'] + 9*s['f'] + 4*C_MIN)
    targets.append((idx, A, dict(s, kcal=new_kcal, c=C_MIN)))

print(f'Пересборка {len(targets)} якорей под правило У≥{C_MIN} '
      f'({TIME_PER_ANCHOR:.0f}с/якорь ≈ {len(targets)*TIME_PER_ANCHOR/3600:.1f} ч). '
      f'Папка {OUT_DIR}/ — с ночной сборкой не конфликтует.')
t0 = time.time()
for n, (idx, A, spec) in enumerate(targets, 1):
    fn = f'{OUT_DIR}/anchor_{idx:03d}_{spec["group"]}.json'
    if os.path.exists(fn):
        try:
            if len(json.load(open(fn, encoding='utf-8')).get('days') or []) >= 30:
                print(f'[{n}/{len(targets)}] #{idx} готов — пропуск'); continue
        except Exception: pass
    T = {'group': spec['group'], 'kcal': spec['kcal'], 'p': spec['p'],
         'f': spec['f'], 'c': spec['c'], 'slots': A['slots']}
    res = build_super_seed(T)
    json.dump({'anchor': spec, 'slots': A['slots'],
               'days': res['days'] if res else [], 'metrics': res['metrics'] if res else None},
              open(fn, 'w', encoding='utf-8'), ensure_ascii=False)
    m = (res or {}).get('metrics') or {}
    el = time.time()-t0; eta = el/n*(len(targets)-n)
    print(f'[{n}/{len(targets)}] #{idx} {spec["group"]} {spec["kcal"]}ккал/У{C_MIN} → '
          f'{m.get("n_days",0)} дн, уник {m.get("unique_dishes","-")} | ETA {eta/3600:.1f}ч')

# ---------- сборка своего файла ----------
out = []
for idx, A, spec in targets:
    fn = f'{OUT_DIR}/anchor_{idx:03d}_{spec["group"]}.json'
    d = json.load(open(fn, encoding='utf-8')) if os.path.exists(fn) else {}
    days = d.get('days') or []
    if days and len(days) < 30:
        i = 0
        while len(days) < 30: days.append(days[i % len(days)]); i += 1
    out.append({'index': idx, 'anchor': spec, 'slots': A['slots'], 'days': days[:30]})
json.dump({'note': f'Якоря, пересчитанные под правило У≥{C_MIN} (п.8б). Слить: merge_presets_final.py',
           'count': len(out), 'anchors': out},
          open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n✅ {OUT_FILE}: {len(out)} якорей. После окончания ночной сборки: python3 merge_presets_final.py')
