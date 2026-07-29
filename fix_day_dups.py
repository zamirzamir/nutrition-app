#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_day_dups.py — точечный ремонт дублей-в-дне в anchors_seeds.json (D6, 15.07.2026).
79 дней в 54 якорях содержат одно блюдо в двух слотах дня. Заменяем ВТОРОЕ вхождение
на альтернативный рецепт по логике build_super_presets.py / фикса якоря #189:
  слот ∈ meal_type, не balance_off, не снек-концентрат, дека Б≥1.2Ж, есть в
  micronutrients_per_portion, id нет в этом дне, все 4 макроса дня в ±3% якоря,
  суточные микро < UL-кэпов билдера (буфер 0.8 по A/D/Fe/Zn/Se).
Выбор кандидата детерминированный: score = микро-покрытие + 4·(сложные−рафинад)
− 0.55·(повторы блюда в этом якоре) − 2·(сумма |отклонений| макросов дня).
Бэкап уже сделан: _АРХИВ/anchors_seeds_20260715_v2.json. Пишем НА МЕСТО.
"""
import json
from collections import defaultdict

recs = {x['id']: x for x in json.load(open('recipes.json', encoding='utf-8'))}
MM = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))['dishes']
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
DATA = json.load(open('anchors_seeds.json', encoding='utf-8'))

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

def is_snack_concentrate(x):
    name = (x.get('name','') or '').lower()
    tags = x.get('tags') or {}
    cats = set(tags.get('cats') or [])
    if tags.get('dish_type') == 'снек-сухофрукты': return True
    if cats & {'сухофрукты','орехи'} and len(x.get('ingredients') or []) <= 2: return True
    return any(w in name for w in SNACK_CONC) and len(x.get('ingredients') or []) <= 2

def works(x, G):
    if x.get('balance_off'): return False
    if is_snack_concentrate(x): return False
    p = (x.get('portions') or {}).get(G)
    return bool(p and p.get('p') and p.get('f') and p['p'] >= 1.2*p['f'])

_deck_cache = {}
def build_deck(G):
    if G in _deck_cache: return _deck_cache[G]
    deck = defaultdict(list)
    for i, x in recs.items():
        if not works(x, G) or i not in MM: continue
        mg = MM[i]['groups'].get(G)
        if not mg: continue
        p = x['portions'][G]
        ref, cpx = carb_fracs(x)
        rec = {'id': i, 'kcal': p['kcal'], 'p': p['p'], 'f': p['f'], 'c': p['c'],
               'M': {k: mg.get(k, 0) for k in FIELDS}, 'ref': ref, 'cpx': cpx}
        for s in (x.get('meal_type') or []):
            deck[s].append(rec)
    _deck_cache[G] = deck
    return deck

def port(i, G):
    p = (recs.get(i, {}).get('portions') or {}).get(G)
    return p or {'kcal':0,'p':0,'f':0,'c':0}

def micro_of(i, G):
    mg = MM.get(i, {}).get('groups', {}).get(G) or {}
    return {k: mg.get(k, 0) for k in FIELDS}

def day_stats(day, G):
    k=p=f=c=0.0; M=defaultdict(float)
    for i in day:
        pp = port(i, G); k+=pp['kcal']; p+=pp['p']; f+=pp['f']; c+=pp['c']
        for kk, v in micro_of(i, G).items(): M[kk]+=v
    return k,p,f,c,M

def devs(k,p,f,c,spec):
    return [(k-spec['kcal'])/spec['kcal'], (p-spec['p'])/spec['p'],
            (f-spec['f'])/spec['f'], (c-spec['c'])/spec['c']]

log = []      # успешные замены
failed = []   # не подобрали
for ai, A in enumerate(DATA['anchors'], 1):
    spec = A['anchor']; G = spec['group']; slots = A['slots']
    for di, day in enumerate(A['days']):
        if len(set(day)) == len(day): continue
        deck = build_deck(G)
        # использование блюд в остальном месяце (для штрафа за повтор)
        month_use = defaultdict(int)
        for dj, dd in enumerate(A['days']):
            if dj == di: continue
            for i in dd: month_use[i] += 1
        changed = True
        while changed and len(set(day)) < len(day):
            changed = False
            seen = set(); dup_slot = None
            for si, i in enumerate(day):
                if i in seen: dup_slot = si; break   # ВТОРОЕ вхождение
                seen.add(i)
            # пробуем заменить второе вхождение; если не выйдет — первое
            try_slots = [dup_slot, day.index(day[dup_slot])]
            fixed = False
            for si in try_slots:
                s = slots[si]; old = day[si]
                others = [day[j] for j in range(len(day)) if j != si]
                bk,bp,bf,bc,BM = day_stats(others, G)
                best = None; best_score = -1e9
                for cand in deck.get(s, []):
                    if cand['id'] in others or cand['id'] == old: continue
                    k = bk+cand['kcal']; p = bp+cand['p']; f = bf+cand['f']; c = bc+cand['c']
                    dv = devs(k,p,f,c,spec)
                    if any(abs(d) > 0.03 for d in dv): continue
                    M = {kk: BM[kk]+cand['M'].get(kk,0) for kk in FIELDS}
                    if any(M[kk] > ULcap[kk] for kk in UL): continue
                    micro = sum(min(M[kk]/RDA[kk], 1.0) for kk in SCORE_F)
                    score = (micro + 4.0*(cand['cpx']-cand['ref'])
                             - 0.55*month_use[cand['id']] - 2.0*sum(abs(d) for d in dv))
                    if score > best_score or (score == best_score and (best is None or cand['id'] < best['id'])):
                        best_score = score; best = cand
                if best:
                    o = port(old, G)
                    ok0,op0,of0,oc0,_ = day_stats(day, G)
                    day[si] = best['id']
                    nk,np_,nf,nc,_ = day_stats(day, G)
                    log.append({'anchor': ai, 'group': G, 'kcal': spec['kcal'], 'day': di,
                        'slot': si, 'slot_name': s, 'old': old,
                        'old_name': recs.get(old,{}).get('name','?'),
                        'new': best['id'], 'new_name': recs.get(best['id'],{}).get('name','?'),
                        'dev_before': max(abs(d) for d in devs(ok0,op0,of0,oc0,spec)),
                        'dev_after': max(abs(d) for d in devs(nk,np_,nf,nc,spec))})
                    fixed = True; changed = True; break
            if not fixed:
                failed.append({'anchor': ai, 'group': G, 'day': di, 'day_ids': list(day)})
                break

# ---------- запись и ревалидация ----------
if not failed:
    json.dump(DATA, open('anchors_seeds.json', 'w', encoding='utf-8'), ensure_ascii=False)
else:
    # пишем только если все дубли устранены хотя бы там, где нашлись кандидаты
    json.dump(DATA, open('anchors_seeds.json', 'w', encoding='utf-8'), ensure_ascii=False)

chk = json.load(open('anchors_seeds.json', encoding='utf-8'))
ref = json.load(open('_АРХИВ/anchors_seeds_20260715_v2.json', encoding='utf-8'))
assert len(chk['anchors']) == len(ref['anchors']) == 238
same_struct = all(
    a['anchor'] == b['anchor'] and a['slots'] == b['slots'] and
    len(a['days']) == len(b['days']) and
    all(len(x) == len(y) for x, y in zip(a['days'], b['days']))
    for a, b in zip(chk['anchors'], ref['anchors']))
dup_left = sum(1 for A in chk['anchors'] for day in A['days'] if len(set(day)) < len(day))
print(f'replacements: {len(log)}  failed: {len(failed)}')
print(f'structure identical (anchors/slots/days/lengths): {same_struct}')
print(f'days with duplicate after fix: {dup_left}')
json.dump({'log': log, 'failed': failed}, open('_АУДИТ_14.07/fix_dups_log.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
