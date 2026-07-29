#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_presets_final.py — финальная сборка пресетов:
  anchors_seeds_SUPER.json (ночная пересборка всех 238)
+ anchors_seeds_C120.json  (44 якоря, пересчитанные под правило У≥120)
= anchors_seeds_FINAL.json (боевой файл: заменить им anchors_seeds.json)

Для якорей из C120 берутся И новая спека (kcal/У), И новые дни.
Запуск: python3 merge_presets_final.py   (после окончания ОБЕИХ сборок)
"""
import json, sys

SUP = json.load(open('anchors_seeds_SUPER.json', encoding='utf-8'))
C120 = json.load(open('anchors_seeds_C120.json', encoding='utf-8'))

by_idx = {a['index']: a for a in C120['anchors'] if a.get('days')}
skipped = [a['index'] for a in C120['anchors'] if not a.get('days')]

out = []
replaced = 0
for idx, A in enumerate(SUP['anchors'], 1):
    if idx in by_idx:
        c = by_idx[idx]
        out.append({'anchor': c['anchor'], 'slots': c['slots'], 'days': c['days']})
        replaced += 1
    else:
        out.append(A)

json.dump({'note': 'ФИНАЛ: супер-пресеты (сложные углеводы+разнообразие+микро) '
                   '+ якоря, пересчитанные под минимум углеводов 120 г (п.8б, 10.07.2026).',
           'count': len(out), 'anchors': out},
          open('anchors_seeds_FINAL.json', 'w', encoding='utf-8'), ensure_ascii=False)

print(f'✅ anchors_seeds_FINAL.json: {len(out)} якорей, из них {replaced} заменены на У≥120-версии.')
if skipped:
    print(f'⚠ без дней (не пересобрались, остались как в SUPER): якоря #{skipped}')
print('Дальше: python3 validate_presets.py (если совместим) и передай файл Клоду на проверку.')
