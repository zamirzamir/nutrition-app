#!/usr/bin/env bash
# Досбор недобранных якорей в ночной сборке (anchors_seeds_SUPER.json).
# Запуск из корня nutrition-app:  bash доделать_якоря.sh
#
# Что делает: билдер пропускает ПОЛНЫЕ чекпоинты (30 дней) и пересобирает только недобранные —
# сейчас их 30 из 238. Каждому даём 1800 сек вместо 120 (в 15 раз больше поиска).
# 30 якорей × 1800 сек ÷ 10 воркеров ≈ 90 минут.
#
# Боевой anchors_seeds.json НЕ трогается — правим только SUPER. Промоут будет отдельным шагом,
# после проверки.
#
# ⚠️ Unreal и прочее тяжёлое лучше закрыть: поиск ограничен ПО ВРЕМЕНИ, отнятый процессор =
#    меньше перебранных вариантов = хуже якоря.
set -e
cd "$(dirname "$0")"

echo "▶ Состояние ДО:"
python3 - <<'PY'
import json, glob
from collections import Counter
c=Counter(len(json.load(open(f,encoding='utf-8')).get('days') or []) for f in glob.glob('seeds_super/anchor_*.json'))
poor=sum(v for k,v in c.items() if k<30)
print(f"   чекпоинтов: {sum(c.values())} | полных (30 дн): {c.get(30,0)} | недобранных: {poor}")
PY

echo ""
echo "▶ Досбор (готовые 208 пропустятся автоматически, ~90 мин)…"
python3 build_super_presets.py 1800 --workers 10

echo ""
echo "▶ Состояние ПОСЛЕ:"
python3 - <<'PY'
import json, glob
from collections import Counter
files=glob.glob('seeds_super/anchor_*.json')
c=Counter(len(json.load(open(f,encoding='utf-8')).get('days') or []) for f in files)
poor=[(f.split('/')[-1], len(json.load(open(f,encoding='utf-8')).get('days') or []))
      for f in sorted(files) if len(json.load(open(f,encoding='utf-8')).get('days') or [])<30]
print(f"   полных (30 дн): {c.get(30,0)} из {sum(c.values())} | осталось недобранных: {len(poor)}")
for f,n in poor: print(f"      {f}: {n} дн")
PY

echo ""
echo "✅ Досбор завершён. НЕ промоутим автоматически — сначала проверка."
echo "   Скинь этот вывод — сверю качество (микро/разнообразие/дубли/UL),"
echo "   и если всё чисто, дам команды на промоут + добор остатка + деплой."
