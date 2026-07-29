#!/usr/bin/env bash
# Ставит фото на «Творог (порция белка)» (fr_900003).
# У него УЖЕ есть своё фото (dish_photos/fr_900003.webp) — оно просто не было залито в бакет.
# Этот скрипт заливает его в бакет (точечно, быстро — не 171 МБ как «deploy-v2.sh photos»).
#
# Запуск:  bash ~/Claude/Projects/nutrition-app/залить_фото_творога.sh
set -euo pipefail
cd "$(dirname "$0")"

# --- ВАРИАНТ ПО УМОЛЧАНИЮ: залить СОБСТВЕННОЕ фото fr_900003 (рекомендую — уникальное) ---
FILE="dish_photos/fr_900003.webp"

# --- АЛЬТЕРНАТИВА (если хочешь, чтобы «порция белка» использовала фото «Творог 5%»): ---
#   раскомментируй следующую строку — она перезапишет фото fr_900003 фоткой tvorog5:
# cp dish_photos/tvorog5.webp dish_photos/fr_900003.webp

[ -f "$FILE" ] || { echo "❌ нет файла $FILE"; exit 1; }
echo "Заливаю $FILE в бакет…"
aws --endpoint-url https://storage.yandexcloud.net s3 cp "$FILE" \
  "s3://roman-app-v2/$FILE" --acl public-read --content-type "image/webp"

echo "✅ Готово. Обнови приложение (F5) — у «Творог (порция белка)» появится фото."
