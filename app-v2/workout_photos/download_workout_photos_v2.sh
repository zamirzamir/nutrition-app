#!/usr/bin/env bash
#
# download_workout_photos_v2.sh
# ------------------------------------------------------------------
# Скачивает 116 сгенерированных фото упражнений (Higgsfield) по манифесту
# и конвертирует их в .webp под нужными именами в ТЕКУЩЕЙ папке.
#
# Запуск (из app-v2/workout_photos/):
#     bash download_workout_photos_v2.sh          # обычный прогон (пропускает уже скачанные)
#     bash download_workout_photos_v2.sh --force  # перекачать всё заново
#
# Конверт: cwebp -q 82 (если установлен), иначе Python Pillow (quality=82).
# Идемпотентно: существующие .webp пропускаются, если не задан --force.
# ------------------------------------------------------------------
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MANIFEST="_photos_manifest.csv"
QUALITY=82
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ ! -f "$MANIFEST" ]; then
  echo "ОШИБКА: не найден манифест $MANIFEST рядом со скриптом." >&2
  exit 1
fi

# --- выбираем конвертер webp -------------------------------------
CONVERTER=""
if command -v cwebp >/dev/null 2>&1; then
  CONVERTER="cwebp"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import PIL" >/dev/null 2>&1; then
  CONVERTER="pillow"
else
  echo "ОШИБКА: нет ни cwebp, ни Python Pillow." >&2
  echo "  Установи один из вариантов:" >&2
  echo "    brew install webp        # даст cwebp (рекомендуется)" >&2
  echo "    pip3 install pillow      # даст Python Pillow" >&2
  exit 1
fi
echo "Конвертер webp: $CONVERTER"
echo "Папка назначения: $SCRIPT_DIR"
[ $FORCE -eq 1 ] && echo "Режим: --force (перекачиваю всё)"
echo "------------------------------------------------------------"

TMP_PNG="$(mktemp -t wpv2.XXXXXX).png"
trap 'rm -f "$TMP_PNG"' EXIT

TOTAL=0        # всего строк в манифесте (с url)
OK=0           # успешно на диске после прогона
SKIP=0         # пропущено (уже было)
DL=0           # реально скачано в этот прогон
FAIL=0
declare -a FAILED_FILES=()

convert_to_webp() {
  # $1 = исходный png, $2 = целевой webp
  if [ "$CONVERTER" = "cwebp" ]; then
    cwebp -quiet -q "$QUALITY" "$1" -o "$2" >/dev/null 2>&1
  else
    python3 - "$1" "$2" "$QUALITY" <<'PY'
import sys
from PIL import Image
src, dst, q = sys.argv[1], sys.argv[2], int(sys.argv[3])
im = Image.open(src).convert("RGB")
im.save(dst, "WEBP", quality=q, method=6)
PY
  fi
}

# --- читаем манифест (пропускаем заголовок) ----------------------
# столбцы: filename,exercise_id,pose,job_id,raw_url
while IFS=, read -r filename exercise_id pose job_id raw_url; do
  [ "$filename" = "filename" ] && continue          # заголовок
  [ -z "${filename// }" ] && continue               # пустая строка
  raw_url="${raw_url%$'\r'}"                         # убрать возможный CR
  if [ -z "${raw_url// }" ]; then
    echo "  ПРОПУСК (нет url в манифесте): $filename"
    FAIL=$((FAIL+1)); FAILED_FILES+=("$filename (нет url)")
    continue
  fi
  TOTAL=$((TOTAL+1))

  if [ $FORCE -eq 0 ] && [ -f "$filename" ]; then
    SKIP=$((SKIP+1)); OK=$((OK+1))
    echo "  [$TOTAL] есть, пропуск: $filename"
    continue
  fi

  # скачать
  if ! curl -fsSL --retry 3 --retry-delay 2 -o "$TMP_PNG" "$raw_url"; then
    echo "  [$TOTAL] ОШИБКА загрузки: $filename" >&2
    FAIL=$((FAIL+1)); FAILED_FILES+=("$filename (curl)")
    continue
  fi
  # конверт
  if convert_to_webp "$TMP_PNG" "$filename" && [ -s "$filename" ]; then
    DL=$((DL+1)); OK=$((OK+1))
    echo "  [$TOTAL] OK: $filename"
  else
    echo "  [$TOTAL] ОШИБКА конверта: $filename" >&2
    FAIL=$((FAIL+1)); FAILED_FILES+=("$filename (webp)")
    rm -f "$filename"
  fi
done < "$MANIFEST"

echo "------------------------------------------------------------"
echo "Скачано (новых) в этот прогон: $DL"
echo "Пропущено (уже были):         $SKIP"
echo "Ошибок:                       $FAIL"
echo "ИТОГО на диске: $OK из $TOTAL"
if [ ${#FAILED_FILES[@]} -gt 0 ]; then
  echo "Не удалось:"
  for f in "${FAILED_FILES[@]}"; do echo "   - $f"; done
  echo "Повтори прогон позже: bash download_workout_photos_v2.sh"
  exit 2
fi
echo "Готово. Дальше: запусти deploy-v2.sh"
