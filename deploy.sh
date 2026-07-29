#!/bin/bash
# ============================================================
#  DEPLOY с защитой от промаха заливки
# ============================================================
#  Что делает:
#    1) делает бэкап файла в backups/ (с датой и временем)
#    2) заливает файл(ы) в Yandex Object Storage
#    3) СРАЗУ проверяет, что в бакете реально лежит новая версия
#       (сравнивает MD5 локального и залитого файла)
#    4) если что-то не сошлось — громко ругается ❌
#
#  Использование:
#    ./deploy.sh                 # зальёт index.html И cabinet.html
#    ./deploy.sh index.html      # зальёт только index.html
#    ./deploy.sh cabinet.html    # зальёт только cabinet.html
# ============================================================

cd "$(dirname "$0")" || exit 1

# ---------- НАСТРОЙКИ ----------
BUCKET="roman-nutrition-app"
ENDPOINT="https://storage.yandexcloud.net"
PROFILE="ycloud"          # профиль aws-cli с ключами Yandex
# -------------------------------

# Цвета для вывода
RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'; NC=$'\033[0m'

# Если файлы не переданы — берём оба основных html.
# './deploy.sh all'        → index.html + cabinet.html + recipes.json
# './deploy.sh recipes.json' → только рецепты
# Иначе берём аргументы, похожие на файлы (html/json/js/css),
# а мусор (комментарии после #, лишние слова) — молча игнорируем.
if [ $# -eq 0 ]; then
  FILES=("index.html" "cabinet.html")
elif [ "$1" = "all" ]; then
  FILES=("index.html" "cabinet.html" "recipes.json" "ingredients_kbju.json" "micronutrients.json" "anchors_seeds.json" "manifest.json")
else
  FILES=()
  for arg in "$@"; do
    # отсекаем всё после '#' (если комментарий прилип к команде)
    case "$arg" in \#*) break ;; esac
    # берём только осмысленные расширения
    case "$arg" in
      *.html|*.json|*.js|*.css|*.png|*.webp|*.jpg|*.jpeg|*.ico|*.svg) FILES+=("$arg") ;;
    esac
  done
  # если после фильтра ничего не осталось — заливаем оба html по умолчанию
  if [ ${#FILES[@]} -eq 0 ]; then
    FILES=("index.html" "cabinet.html")
  fi
fi

mkdir -p backups
STAMP=$(date +%Y-%m-%d_%H%M%S)
FAILED=0

for FILE in "${FILES[@]}"; do
  echo ""
  echo "============================================================"
  echo "  Деплою: $FILE"
  echo "============================================================"

  # --- 0. файл существует? ---
  if [ ! -f "$FILE" ]; then
    echo "${RED}❌ Файла $FILE нет в этой папке. Пропускаю.${NC}"
    FAILED=1
    continue
  fi

  # --- 1. БЭКАП ---
  BASE="${FILE%.*}"          # index   (без .html)
  EXT="${FILE##*.}"          # html
  BACKUP="backups/${BASE}_BACKUP_${STAMP}.${EXT}"
  mkdir -p "$(dirname "$BACKUP")"
  cp "$FILE" "$BACKUP"
  echo "${GRN}✓${NC} Бэкап: $BACKUP"

  # --- 1b. ТИХИЙ АПДЕЙТ: в html подставляем APP_VERSION = метка деплоя ---
  # Чтобы клиент с застрявшим в кэше старым html увидел, что вышла новая версия,
  # и сам перезагрузился. version.json (та же метка) заливаем после цикла.
  if [ "$EXT" = "html" ]; then
    sed -i '' "s/APP_VERSION = '[^']*'/APP_VERSION = '$STAMP'/" "$FILE"
    HTML_DEPLOYED=1
    echo "${GRN}✓${NC} APP_VERSION → $STAMP"
  fi

  # --- 2. ХЕШ локального файла (до заливки) ---
  LOCAL_MD5=$(md5 -q "$FILE" 2>/dev/null || md5sum "$FILE" | awk '{print $1}')

  # --- 3. ЗАЛИВКА ---
  # content-type по расширению + кэш.
  # HTML — no-cache (клиент всегда получает свежую версию правок).
  # Остальное (json/фото) можно кэшировать.
  CACHE="public, max-age=3600"
  case "$EXT" in
    html) CT="text/html; charset=utf-8"; CACHE="no-cache, no-store, must-revalidate" ;;
    json) CT="application/json"; CACHE="no-cache" ;;
    js)   CT="application/javascript; charset=utf-8" ;;
    css)  CT="text/css; charset=utf-8" ;;
    png)  CT="image/png" ;;
    webp) CT="image/webp" ;;
    jpg|jpeg) CT="image/jpeg" ;;
    *)    CT="application/octet-stream" ;;
  esac

  echo "  Заливаю в s3://$BUCKET/$FILE ..."
  if ! aws --endpoint-url "$ENDPOINT" --profile "$PROFILE" \
        s3 cp "$FILE" "s3://$BUCKET/$FILE" --content-type "$CT" --cache-control "$CACHE"; then
    echo "${RED}❌ ОШИБКА ЗАЛИВКИ $FILE — файл НЕ ушёл в бакет!${NC}"
    echo "${YEL}   Частые причины: нет ключей (Unable to locate credentials),${NC}"
    echo "${YEL}   нет сети, неверный бакет/профиль.${NC}"
    FAILED=1
    continue
  fi

  # --- 4. ПРОВЕРКА: качаем обратно и сравниваем хеши ---
  echo "  Проверяю, что новая версия легла в бакет..."
  REMOTE_TMP=$(mktemp)
  HTTP=$(curl -s -o "$REMOTE_TMP" -w "%{http_code}" \
         "$ENDPOINT/$BUCKET/$FILE")
  REMOTE_MD5=$(md5 -q "$REMOTE_TMP" 2>/dev/null || md5sum "$REMOTE_TMP" | awk '{print $1}')
  rm -f "$REMOTE_TMP"

  if [ "$HTTP" != "200" ]; then
    echo "${RED}❌ ПРОМАХ: бакет вернул HTTP $HTTP (файл недоступен).${NC}"
    FAILED=1
  elif [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
    echo "${GRN}✅ УСПЕХ: в бакете лежит ровно та версия, что у тебя локально.${NC}"
    echo "   MD5: $LOCAL_MD5"
  else
    echo "${RED}❌ ПРОМАХ: в бакете лежит ДРУГАЯ версия файла!${NC}"
    echo "${RED}   Локально: $LOCAL_MD5${NC}"
    echo "${RED}   В бакете: $REMOTE_MD5${NC}"
    echo "${YEL}   Возможно: заливка прошла, но мешает кэш CDN, или залилось не туда.${NC}"
    FAILED=1
  fi
done

# --- ТИХИЙ АПДЕЙТ: если заливали html — обновляем version.json (та же метка) ---
# Клиенты при следующем открытии увидят новую версию и тихо перезагрузятся.
if [ "${HTML_DEPLOYED:-0}" = "1" ]; then
  echo "{\"version\":\"$STAMP\"}" > version.json
  echo "  Заливаю version.json ($STAMP) ..."
  if aws --endpoint-url "$ENDPOINT" --profile "$PROFILE" \
        s3 cp version.json "s3://$BUCKET/version.json" \
        --content-type "application/json" --cache-control "no-cache, no-store, must-revalidate"; then
    echo "${GRN}✓${NC} version.json залит — клиенты получат тихий апдейт."
  else
    echo "${RED}❌ version.json не залился — тихий апдейт не сработает.${NC}"; FAILED=1
  fi
fi

echo ""
echo "============================================================"
if [ "$FAILED" -eq 0 ]; then
  echo "${GRN}  ВСЁ ЗАЛИТО И ПРОВЕРЕНО. Обнови сайт через Cmd+Shift+R.${NC}"
else
  echo "${RED}  ⚠️  БЫЛИ ПРОБЛЕМЫ — смотри ❌ выше. Сайт мог НЕ обновиться!${NC}"
fi
echo "============================================================"
exit $FAILED
