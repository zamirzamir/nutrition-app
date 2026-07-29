#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_fractions_measures.py — ПОИСК (только чтение) в ШАГАХ: дроби, ложки, ч.л./ст.л.,
стаканы, щепотки, граммы/мл/литры, штучные количества. Показывает, где остались меры.
Запуск:  python3 scan_fractions_measures.py
"""
import json, re
R = json.load(open('recipes.json', encoding='utf-8'))

PATTERNS = {
    'дроби (½ ¼ ⅓ 1/3)':        re.compile(r'[½¼¾⅓⅔⅛⅜⅝⅞]|\b\d+\s*/\s*\d+\b'),
    'чайная ложка / ч.л.':      re.compile(r'\bч\.?\s?л\.?\b|чайн\w*\s+ложк', re.I),
    'столовая ложка / ст.л.':   re.compile(r'\bст\.?\s?л\.?\b|\bс\.?\s?л\.?\b|столов\w*\s+ложк', re.I),
    'ложка (общая)':            re.compile(r'\bложк\w*\b', re.I),
    'стакан / пол стакана':     re.compile(r'стакан\w*|пол\s*-?\s*стакана', re.I),
    'щепотка / горсть':         re.compile(r'щепот\w*|горст\w*', re.I),
    'граммы в шагах':           re.compile(r'\b\d+[.,]?\d*\s*(?:г|гр|грамм\w*)\b', re.I),
    'мл / литры':               re.compile(r'\b\d+[.,]?\d*\s*(?:мл|миллилитр\w*|л|литр\w*)\b', re.I),
    'штук / шт':                re.compile(r'\b\d+\s*(?:шт\b|штук\w*)', re.I),
    'зубчик / долька':          re.compile(r'\b\d+[\s-]*\d*\s*(?:зубч\w*|дольк\w*)', re.I),
    'число + продукт':          re.compile(r'\b\d+\s*[-–]?\s*\d*\s*(?:яйц|яблок|банан|луковиц|морков|помидор|огурц|картофелин|лимон|апельсин|ломт)', re.I),
}

for label, pat in PATTERNS.items():
    hits = []
    for r in R:
        for n, s in enumerate(r.get('instructions') or []):
            if pat.search(s):
                hits.append((r['id'], r['name'], n + 1, s))
    print(f'\n=== {label} — {len(hits)} шагов ===')
    for rid, nm, step, s in hits[:60]:
        m = pat.search(s)
        frag = s[max(0, m.start() - 25):m.start() + 35]
        print(f'   {rid} | {nm[:34]:34} | шаг {step}: …{frag}…')
    if len(hits) > 60:
        print(f'   … ещё {len(hits) - 60}')

# сводка: сколько рецептов вообще имеют хоть одну меру
allpat = re.compile('|'.join(p.pattern for p in PATTERNS.values()))
recs = sum(1 for r in R if any(allpat.search(s) for s in (r.get('instructions') or [])))
print(f'\n\nИТОГО рецептов с любой мерой/числом в шагах: {recs} из {len(R)}')
