#!/usr/bin/env bash
# Деплой v2 на ОБЕ ссылки-зеркала (боевая + запасная) одной командой.
#   bash deploy-v2.sh          — залить на ОБА бакета (roman-nutrition-app + roman-app-v2)
#   bash deploy-v2.sh photos   — то же + синк фото блюд (171 МБ, долго, нужно 1 раз)
#   BUCKET=xxx bash deploy-v2.sh — залить ТОЛЬКО в один бакет xxx (если надо точечно)
set -euo pipefail
cd "$(dirname "$0")"

export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
export AWS_DEFAULT_REGION=ru-central1

ENDPOINT="https://storage.yandexcloud.net"
AWSCMD=(aws --endpoint-url "$ENDPOINT")   # ключи: профиль по умолчанию

# 25.07 (Замир): держим ДВЕ одинаковые ссылки. По умолчанию льём в ОБА бакета.
# Переопределить одним: BUCKET=roman-nutrition-app bash deploy-v2.sh
if [ -n "${BUCKET:-}" ]; then BUCKETS=("$BUCKET"); else BUCKETS=(roman-nutrition-app roman-app-v2); fi
echo "▶ Целевые бакеты: ${BUCKETS[*]}"

# ── ВЕРСИЯ (один раз): бампаем APP_VERSION → PWA/браузер подхватят свежий html ──
TS=$(date +%Y-%m-%d_%H%M%S)
echo "{\"version\":\"$TS\"}" > ../version.json
echo "▶ Версия сборки: $TS"

# ── temp html с подставленным APP_VERSION (один раз) ──
TMPH=$(mktemp -d)
# 25.07: версию подставляем И в APP_VERSION, И в адрес каждого JS (?v=$TS). Второе — пуленепробиваемо
# против цепкого кэша iOS-Safari: новый деплой = новый URL скрипта = принудительная свежая загрузка.
for f in index.html cabinet.html admin.html; do
  [ -f "$f" ] && sed \
    -e "s/var APP_VERSION = '[^']*'/var APP_VERSION = '$TS'/" \
    -e "s#src=\"v2-app.js\"#src=\"v2-app.js?v=$TS\"#" \
    -e "s#src=\"v2-ui.js\"#src=\"v2-ui.js?v=$TS\"#" \
    -e "s#src=\"workouts.js\"#src=\"workouts.js?v=$TS\"#" \
    "$f" > "$TMPH/$f"
done

# ── temp json с gzip (один раз) ──
TMP=$(mktemp -d)
for f in recipes.json demo-recipes.json ingredients_kbju.json micronutrients.json anchors_seeds.json; do
  src="../$f"; [ -f "$src" ] || { echo "⚠ нет $src — пропуск"; continue; }
  gzip -9 -c "$src" > "$TMP/$f"
done

# ── ЗАЛИВКА В КАЖДЫЙ БАКЕТ ──────────────────────────────────
for BUCKET in "${BUCKETS[@]}"; do
  echo ""
  echo "═══════════ Бакет: $BUCKET ═══════════"
  # бакет + режим статик-сайта
  if ! "${AWSCMD[@]}" s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
    "${AWSCMD[@]}" s3 mb "s3://$BUCKET"
  fi
  "${AWSCMD[@]}" s3 website "s3://$BUCKET" --index-document index.html

  # HTML (no-cache, с APP_VERSION)
  for f in index.html cabinet.html admin.html; do
    [ -f "$TMPH/$f" ] && "${AWSCMD[@]}" s3 cp "$TMPH/$f" "s3://$BUCKET/$f" --acl public-read \
      --content-type "text/html; charset=utf-8" --cache-control "no-cache"
  done

  # JS (no-cache)
  for j in v2-ui.js v2-app.js workouts.js; do
    [ -f "$j" ] && "${AWSCMD[@]}" s3 cp "$j" "s3://$BUCKET/$j" --acl public-read \
      --content-type "application/javascript; charset=utf-8" --cache-control "no-cache"
  done

  # фото + видео упражнений (кэш на год)
  # --delete: чистим старые AI-фото и старые имена видео на бакете (зеркало локальной папки)
  [ -d workout_photos ] && "${AWSCMD[@]}" s3 sync workout_photos/ "s3://$BUCKET/workout_photos/" \
    --acl public-read --content-type "image/webp" --cache-control "public, max-age=31536000" \
    --delete --exclude "*.csv" --exclude "*.sh"
  [ -d workout_videos ] && "${AWSCMD[@]}" s3 sync workout_videos/ "s3://$BUCKET/workout_videos/" \
    --acl public-read --content-type "video/mp4" --cache-control "public, max-age=31536000" --delete

  # JSON (gzip, public)
  for f in recipes.json demo-recipes.json ingredients_kbju.json micronutrients.json anchors_seeds.json; do
    [ -f "$TMP/$f" ] && "${AWSCMD[@]}" s3 cp "$TMP/$f" "s3://$BUCKET/$f" --acl public-read \
      --content-type "application/json" --content-encoding gzip --cache-control "no-cache"
  done

  # прочее
  for f in ../manifest.json ../manifest-index.json ../version.json; do
    [ -f "$f" ] && "${AWSCMD[@]}" s3 cp "$f" "s3://$BUCKET/$(basename "$f")" --acl public-read \
      --content-type "application/json" --cache-control "no-cache"
  done
  [ -d ../design ] && "${AWSCMD[@]}" s3 sync ../design/ "s3://$BUCKET/design/" --acl public-read

  # фото блюд (только по запросу: deploy-v2.sh photos)
  if [ "${1:-}" = "photos" ]; then
    echo "… синк фото блюд (171 МБ — надолго)"
    "${AWSCMD[@]}" s3 sync ../dish_photos/ "s3://$BUCKET/dish_photos/" --acl public-read \
      --content-type "image/webp" --cache-control "public, max-age=31536000"
  fi
  echo "✓ $BUCKET готов: https://$BUCKET.website.yandexcloud.net"
done

rm -rf "$TMPH" "$TMP"
echo ""
echo "✅ Готово на ОБЕ ссылки: ${BUCKETS[*]}"
[ "${1:-}" != "photos" ] && echo "   ⚠ Фото блюд отдельно: «bash deploy-v2.sh photos» (один раз на каждый бакет)"
