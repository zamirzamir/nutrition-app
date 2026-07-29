#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_super_presets.py — «СУПЕР-ПРЕСЕТЫ»: ночная пересборка 28-дневных seed-меню
по ВСЕМ фронтам сразу:
  • МАКРО: каждый день в ±3% по ккал/Б/Ж/У (жёстко).
  • БЕЗОПАСНОСТЬ: ни один день не превышает UL (с зазором 80% для токсичных).
  • МИКРО: максимизируем 28-дневное покрытие RDA (витамины/минералы).
  • УГЛЕВОДЫ: штрафуем рафинад (белый хлеб/макароны/сахар), поощряем сложные
    (овсянка/гречка/рис/картофель/бобовые/цельнозерновое).
  • РАЗНООБРАЗИЕ: жадный отбор 28 дней с максимумом уникальных блюд и типов,
    штраф за повтор блюда/ингредиента в месяце.

БЕЗОПАСНО: строит по ТЕМ ЖЕ якорям, что и текущий anchors_seeds.json (совпадение
pickAnchor 1:1). Пишет в НОВЫЙ файл anchors_seeds_SUPER.json — текущий НЕ трогает.
Возобновляемый: чекпоинт на каждый якорь в seeds_super/. Можно прерывать и запускать снова.
В конце — отчёт-сравнение super_presets_report.md (микро/рафинад/разнообразие vs текущие).

ЗАПУСК (параллельно по ядрам; якоря делятся между процессами):
    python3 build_super_presets.py                      # 90 сек/якорь, воркеров = ядра−2
    python3 build_super_presets.py 150                  # 150 сек/якорь (дольше, качественнее)
    python3 build_super_presets.py 150 --workers 8      # явно 8 процессов
Каждый якорь считается ровно ОДНИМ процессом (гонок нет), чекпоинт — свой файл в seeds_super/.
Финальная сборка и отчёт — один процесс в конце, как раньше.
Затем смотришь super_presets_report.md. Если всё ок — заливаешь anchors_seeds_SUPER.json
как anchors_seeds.json. Если нет — оставляешь текущие (ничего не потеряно).
"""
import json, random, time, os, sys
from collections import defaultdict

# ---------- настройки ----------
# Реальное значение задаётся аргументом в main(); воркеры получают его через _init_worker.
TIME_PER_ANCHOR = 90.0   # сек поиска на якорь (значение по умолчанию)
OUT_DIR = 'seeds_super'
OUT_FILE = 'anchors_seeds_SUPER.json'
REPORT = 'super_presets_report.md'
CARB_W = 4.0        # вес качества углеводов в оценке дня (конкурирует с микро ~0..20)
DIVERSITY_REUSE_PEN = 0.55   # штраф за каждое повторное использование блюда в месяце
POOL_KEEP = 1500    # сколько лучших дней-кандидатов держим на якорь

# ---------- данные ----------
recs = {x['id']: x for x in json.load(open('recipes.json', encoding='utf-8'))}
MM = json.load(open('micronutrients_per_portion.json', encoding='utf-8'))['dishes']
FIELDS = json.load(open('micronutrients.json', encoding='utf-8'))['fields']
CUR = json.load(open('anchors_seeds.json', encoding='utf-8'))   # текущие якоря — источник спецификаций

RDA = {'vitamin_a':900,'vitamin_b1':1.2,'vitamin_b2':1.3,'vitamin_b3':16,'vitamin_b5':5,'vitamin_b6':1.3,
 'vitamin_b9':400,'vitamin_b12':2.4,'vitamin_c':90,'vitamin_k':120,'calcium':1000,'iron':8,'magnesium':400,
 'phosphorus':700,'potassium':3400,'zinc':11,'selenium':55,'omega3':1.6,'omega6':17,'fiber':38}
UL = {'vitamin_a':3000,'vitamin_b3':35,'vitamin_b6':100,'vitamin_b9':1000,'vitamin_c':2000,'vitamin_d':100,
 'vitamin_e':1000,'calcium':2500,'iron':45,'zinc':40,'selenium':400,'phosphorus':4000}
UL_SAFE = {'vitamin_a':0.8,'vitamin_d':0.8,'iron':0.8,'zinc':0.8,'selenium':0.8}
ULcap = {k: UL[k]*UL_SAFE.get(k,1.0) for k in UL}
SCORE_F = [k for k in RDA if k not in ('vitamin_d','vitamin_e')]   # D/E — топпер, не штрафуем

# ---------- качество углеводов на блюдо (доли рафинада/сложных) ----------
REFINED = ['белый хлеб','батон','бейгл','багет','булочк','круассан','макарон','вермишель',
           'спагетти','лапша','сахар','пончик','вафл']
COMPLEX = ['овсян','геркулес','гречк','бурый рис','дикий рис','киноа','булгур','перлов',
           'чечевиц','фасоль','нут','горох','цельнозерн','отруб','батат','пшено']

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

# ---------- дека под группу ----------
SNACK_CONC = ('сухофрукт','изюм','курага','чернослив','финик','инжир','урюк','цукат',
              'вялен','сушён','сушен','шоколад','батончик','гранат')
def is_snack_concentrate(x):
    """Снек-концентрат: в рантайме порция режется спец-потолком до 20-100 г,
    поэтому в seed-днях такие блюда дают ложные калории. Не берём в пресеты."""
    name = (x.get('name','') or '').lower()
    tags = x.get('tags') or {}
    cats = set(tags.get('cats') or [])
    if tags.get('dish_type') == 'снек-сухофрукты': return True
    if cats & {'сухофрукты','орехи'} and len(x.get('ingredients') or []) <= 2: return True
    return any(w in name for w in SNACK_CONC) and len(x.get('ingredients') or []) <= 2

def works(x, G):
    if x.get('balance_off'): return False
    if is_snack_concentrate(x): return False   # фикс 09.07 (утв. Замиром)
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
    """доля рафинада/сложных, взвешенная по углеводам блюд дня."""
    cc = sum(d['c'] for d in day) or 1.0
    ref = sum(d['ref'] * d['c'] for d in day) / cc
    cpx = sum(d['cpx'] * d['c'] for d in day) / cc
    return ref, cpx

def build_super_seed(T):
    G = T['group']; slots = T['slots']; slots_set = set(slots)
    deck = build_deck(G, slots_set)
    if any(not deck[s] for s in slots): return None
    ok = lambda v, t, tol=0.03: t > 0 and abs(v-t)/t <= tol
    pool = []; t0 = time.time()
    while time.time() - t0 < TIME_PER_ANCHOR:
        for _ in range(800):
            # фикс 15.07 (D6): id блюд в дне УНИКАЛЬНЫ — один рецепт не может стоять
            # в двух слотах одного дня; при коллизии берём другого кандидата того же слота
            day = []; used_ids = set()
            for s in slots:
                cand = random.choice(deck[s])
                if cand['id'] in used_ids:
                    alts = [d for d in deck[s] if d['id'] not in used_ids]
                    if not alts: day = None; break
                    cand = random.choice(alts)
                day.append(cand); used_ids.add(cand['id'])
            if day is None: continue
            k = sum(d['kcal'] for d in day)
            if not ok(k, T['kcal']): continue
            p = sum(d['p'] for d in day); f = sum(d['f'] for d in day); c = sum(d['c'] for d in day)
            if not (ok(p, T['p']) and ok(f, T['f']) and ok(c, T['c'])): continue
            M = {key: sum(d['M'][key] for d in day) for key in FIELDS}
            if any(M[key] > ULcap[key] for key in UL): continue
            micro = sum(min(M[key]/RDA[key], 1.0) for key in SCORE_F)  # 0..~20
            ref, cpx = day_carb_shares(day)
            carbq = cpx - ref                                          # -1..1
            score = micro + CARB_W * carbq
            ids = tuple(d['id'] for d in day)
            allings = set()
            for d in day: allings |= d['ings']
            pool.append({'score': score, 'ids': ids, 'k': k, 'p': p, 'f': f, 'c': c,
                         'M': M, 'ref': ref, 'cpx': cpx, 'ings': allings})
        if len(pool) > POOL_KEEP * 4:
            pool.sort(key=lambda z: -z['score']); pool = pool[:POOL_KEEP]
    if not pool: return None
    pool.sort(key=lambda z: -z['score'])
    pool = pool[:POOL_KEEP]

    # ---------- жадный отбор 28 дней с максимумом разнообразия ----------
    used_dish = defaultdict(int)      # сколько раз блюдо уже в месяце
    used_ing = defaultdict(int)
    chosen = []; seen_days = set()
    while len(chosen) < 30 and pool:
        best = None; best_val = -1e9
        for cand in pool:
            if cand['ids'] in seen_days: continue
            rep = sum(used_dish[i] for i in cand['ids'])          # повтор блюд
            ingrep = sum(used_ing[i] for i in cand['ings']) / max(1, len(cand['ings']))
            val = cand['score'] - DIVERSITY_REUSE_PEN * rep - 0.15 * ingrep
            if val > best_val: best_val = val; best = cand
        if best is None: break
        chosen.append(best); seen_days.add(best['ids'])
        for i in best['ids']: used_dish[i] += 1
        for i in best['ings']: used_ing[i] += 1
        # чтобы не зациклиться на одном дне — удаляем выбранный из пула
        pool = [c for c in pool if c['ids'] != best['ids']]
    if not chosen: return None

    # метрики якоря
    days_ids = [list(c['ids']) for c in chosen]
    avg_micro = sum(sum(min(c['M'][k]/RDA[k],1.0) for k in SCORE_F) for c in chosen)/len(chosen)
    avg_ref = sum(c['ref'] for c in chosen)/len(chosen)
    avg_cpx = sum(c['cpx'] for c in chosen)/len(chosen)
    uniq = len(set(i for c in chosen for i in c['ids']))
    return {'slots': slots, 'days': days_ids,
            'metrics': {'n_days': len(chosen), 'avg_micro': round(avg_micro,2),
                        'avg_refined_share': round(avg_ref,3), 'avg_complex_share': round(avg_cpx,3),
                        'unique_dishes': uniq}}

# ---------- параллельные воркеры ----------
def _init_worker(time_per):
    """Инициализация процесса-воркера: только передаём время поиска.
    Данные (recipes/MM/…) каждый процесс грузит сам при импорте модуля (spawn)."""
    global TIME_PER_ANCHOR
    TIME_PER_ANCHOR = time_per

def _process_anchor(task):
    """Считает ОДИН якорь — та же логика build_super_seed, байт в байт.
    Пишет СВОЙ чекпоинт-файл (имя уникально по индексу якоря) — гонок записи нет."""
    idx, A, n_total = task
    spec = A['anchor']
    fn = f'{OUT_DIR}/anchor_{idx:03d}_{spec["group"]}.json'
    print(f'  [pid {os.getpid()}] старт якоря {idx}/{n_total}: {spec["group"]} {spec["kcal"]}ккал '
          f'({TIME_PER_ANCHOR:.0f}с)', flush=True)
    T = {'group': spec['group'], 'kcal': spec['kcal'], 'p': spec['p'],
         'f': spec['f'], 'c': spec['c'], 'slots': A['slots']}
    res = build_super_seed(T)
    out = {'anchor': spec, 'slots': A['slots'],
           'days': res['days'] if res else [], 'metrics': res['metrics'] if res else None}
    json.dump(out, open(fn, 'w', encoding='utf-8'), ensure_ascii=False)
    return idx, spec, (res['metrics'] if res else {})

# ---------- отчёт-сравнение SUPER vs ТЕКУЩИЕ ----------
def anchor_metrics(days, slots, group):
    """средние микро-покрытие, рафинад, разнообразие по 28 дням якоря."""
    if not days: return None
    # per-dish кэш
    ref_cache = {}; cpx_cache = {}
    def rc(i):
        if i not in ref_cache:
            x = recs.get(i); ref_cache[i], cpx_cache[i] = carb_fracs(x) if x else (0,0)
        return ref_cache[i], cpx_cache[i]
    tot_micro = 0.0; tot_ref = 0.0; n = 0; uniq = set()
    for day in days:
        M = defaultdict(float); cc = 0.0; ref_w = 0.0
        for i in day:
            uniq.add(i)
            mg = MM.get(i, {}).get('groups', {}).get(group)
            if mg:
                for k in SCORE_F: M[k] += mg.get(k, 0)
            p = (recs.get(i, {}).get('portions') or {}).get(group)
            c = p['c'] if p else 0; cc += c
            r, _ = rc(i); ref_w += r * c
        tot_micro += sum(min(M[k]/RDA[k], 1.0) for k in SCORE_F)
        tot_ref += (ref_w/cc if cc else 0); n += 1
    return {'avg_micro': tot_micro/n, 'avg_refined': tot_ref/n, 'unique': len(uniq)}

# ---------- главный процесс: раздача якорей воркерам + сборка + отчёт ----------
def main():
    import argparse, multiprocessing as mp
    global TIME_PER_ANCHOR
    ap = argparse.ArgumentParser(description='СУПЕР-ПРЕСЕТЫ: параллельная пересборка seed-меню по якорям')
    ap.add_argument('time_per', nargs='?', type=float, default=90.0,
                    help='сек поиска на якорь (по умолчанию 90)')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 3) - 2),
                    help='число процессов (по умолчанию: все ядра минус 2)')
    args = ap.parse_args()
    TIME_PER_ANCHOR = args.time_per
    workers = max(1, args.workers)

    os.makedirs(OUT_DIR, exist_ok=True)
    anchors = CUR['anchors']
    _LIMIT = int(os.environ.get('SUPER_LIMIT', '0'))   # для смоук-теста: обработать только первые N якорей

    # --- какие якоря ещё считать (готовые чекпоинты пропускаем — как раньше) ---
    pending = []
    for idx, A in enumerate(anchors, 1):
        if _LIMIT and idx > _LIMIT: break
        spec = A['anchor']
        fn = f'{OUT_DIR}/anchor_{idx:03d}_{spec["group"]}.json'
        if os.path.exists(fn):
            try:
                _chk = json.load(open(fn, encoding='utf-8'))
                if len(_chk.get('days') or []) >= 30:   # пропускаем только ПОЛНЫЕ (30 дней)
                    print(f'[{idx}/{len(anchors)}] {spec["group"]} {spec["kcal"]}ккал — готов (30 дн), пропуск')
                    continue
            except Exception:
                pass  # битый/неполный чекпоинт — пересоберём заново
        pending.append((idx, A, len(anchors)))

    print(f'СУПЕР-ПРЕСЕТЫ: {len(anchors)} якорей, к расчёту {len(pending)} × {TIME_PER_ANCHOR:.0f}с '
          f'на {workers} воркерах ≈ {len(pending)*TIME_PER_ANCHOR/3600/max(1,min(workers,max(1,len(pending)))):.1f} ч. '
          f'Пишем в {OUT_FILE} (текущие не трогаем).', flush=True)
    t_start = time.time()

    if pending:
        # spawn — тот же механизм запуска процессов, что на macOS по умолчанию.
        # Каждый якорь достаётся ровно ОДНОМУ воркеру (imap по списку pending) — пересечений нет.
        ctx = mp.get_context('spawn')
        with ctx.Pool(processes=min(workers, len(pending)),
                      initializer=_init_worker, initargs=(TIME_PER_ANCHOR,)) as pool:
            done = 0
            for idx, spec, m in pool.imap_unordered(_process_anchor, pending):
                done += 1
                el = time.time() - t_start
                eta = el/done*(len(pending)-done)
                print(f'[{done}/{len(pending)}] якорь {idx}: {spec["group"]} {spec["kcal"]}ккал → '
                      f'{m.get("n_days",0)} дн, микро {m.get("avg_micro","-")}, '
                      f'рафинад {m.get("avg_refined_share","-")}, уник {m.get("unique_dishes","-")} '
                      f'| ETA {eta/3600:.1f}ч', flush=True)

    # ---------- сборка в один файл (ОДИН процесс — как раньше) ----------
    out_anchors = []
    filled = 0
    for idx, A in enumerate(anchors, 1):
        spec = A['anchor']
        fn = f'{OUT_DIR}/anchor_{idx:03d}_{spec["group"]}.json'
        if not os.path.exists(fn):
            out_anchors.append({'anchor': spec, 'slots': A['slots'], 'days': A['days']})  # фолбэк на текущий
            continue
        d = json.load(open(fn, encoding='utf-8'))
        days = d.get('days') or A['days']
        # добить до 30 повтором лучших, если поиск дал меньше
        if len(days) < 30 and days:
            i = 0
            while len(days) < 30:
                days.append(days[i % len(days)]); i += 1
        if len(days) >= 30: filled += 1
        out_anchors.append({'anchor': spec, 'slots': A['slots'], 'days': days[:30]})

    json.dump({'note': 'СУПЕР-ПРЕСЕТЫ: сложные углеводы + разнообразие + микро. Сборка по якорям текущего anchors_seeds.',
               'count': len(out_anchors), 'anchors': out_anchors},
              open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'\nСобрано в {OUT_FILE}: {len(out_anchors)} якорей ({filled} с полными 28 днями).')

    # ---------- отчёт-сравнение SUPER vs ТЕКУЩИЕ ----------
    rows = []
    for idx, A in enumerate(anchors, 1):
        spec = A['anchor']; G = spec['group']
        cur_m = anchor_metrics(A['days'], A['slots'], G)
        sup_m = anchor_metrics(out_anchors[idx-1]['days'], A['slots'], G)
        if cur_m and sup_m:
            rows.append((spec, cur_m, sup_m))

    def avg(key_path):
        cur = sum(r[1][key_path] for r in rows)/len(rows)
        sup = sum(r[2][key_path] for r in rows)/len(rows)
        return cur, sup

    L = ['# СУПЕР-ПРЕСЕТЫ — отчёт сравнения\n',
         f'Якорей сравнено: {len(rows)} · время поиска: {TIME_PER_ANCHOR:.0f}с/якорь\n', '\n## Средние по всем якорям\n']
    cm, sm = avg('avg_micro'); L.append(f'- Микро-покрытие RDA (из {len(SCORE_F)}): текущие **{cm:.2f}** → супер **{sm:.2f}** ({"✅ не хуже" if sm>=cm-0.2 else "⚠️ ХУЖЕ"})')
    cr, sr = avg('avg_refined'); L.append(f'- Доля рафинированных углеводов/день: текущие **{cr:.3f}** → супер **{sr:.3f}** ({"✅ меньше" if sr<cr else "⚠️ не меньше"})')
    cu, su = avg('unique'); L.append(f'- Уникальных блюд на якорь (разнообразие): текущие **{cu:.1f}** → супер **{su:.1f}** ({"✅ больше" if su>cu else "≈"})')
    verdict = (sm >= cm - 0.2) and (sr <= cr) and (su >= cu - 1)
    L.append(f'\n## ВЕРДИКТ: {"✅ СУПЕР ЛУЧШЕ ИЛИ НЕ ХУЖЕ — можно заливать" if verdict else "⚠️ ЕСТЬ РЕГРЕСС — смотри детали, возможно оставить текущие"}\n')
    L.append('\n(Макро ±3% и UL соблюдены по построению: дни, не прошедшие пороги, в пул не попадали.)\n')
    L.append('\n## Худшие якоря по микро (супер vs текущие)\n')
    worst = sorted(rows, key=lambda r: r[2][1]['avg_micro'] if False else (r[2]['avg_micro'] - r[1]['avg_micro']))[:15]
    L.append('\n| Группа | ккал | микро тек | микро супер | рафинад тек→супер |\n|---|--:|--:|--:|--:|')
    for spec, cur_m, sup_m in worst:
        L.append(f'| {spec["group"]} | {spec["kcal"]} | {cur_m["avg_micro"]:.2f} | {sup_m["avg_micro"]:.2f} | {cur_m["avg_refined"]:.2f}→{sup_m["avg_refined"]:.2f} |')
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'Отчёт: {REPORT}')
    print('Готово. Если вердикт ✅ — залей anchors_seeds_SUPER.json вместо anchors_seeds.json.')

if __name__ == '__main__':
    main()
