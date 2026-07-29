#!/usr/bin/env bash
# P0 — закрыть платный контент: перевести бакет roman-app-v2 на ПООБЪЕКТНЫЙ доступ.
# Итог: все ассеты остаются публичными, recipes.json становится приватным
#        (доступ только по подписанной ссылке /recipes-url для оплативших).
# Запуск из папки app-v2:  bash p0-privatize.sh
# Разовая операция. Данные НЕ перезаливаются — меняются только права (ACL).
set -euo pipefail
cd "$(dirname "$0")"

export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
export AWS_DEFAULT_REGION=ru-central1

BUCKET="roman-app-v2"
ENDPOINT="https://storage.yandexcloud.net"
AWSCMD=(aws --endpoint-url "$ENDPOINT")

echo "▶ 1/3 Всем объектам — публичное чтение (кроме recipes.json)…"
"${AWSCMD[@]}" s3api list-objects-v2 --bucket "$BUCKET" \
  --query 'Contents[].Key' --output text | tr '\t' '\n' | while read -r KEY; do
  [ -z "$KEY" ] && continue
  if [ "$KEY" = "recipes.json" ]; then continue; fi
  "${AWSCMD[@]}" s3api put-object-acl --bucket "$BUCKET" --key "$KEY" --acl public-read
  echo "  public  ✓ $KEY"
done

echo "▶ 2/3 recipes.json — приватно…"
"${AWSCMD[@]}" s3api put-object-acl --bucket "$BUCKET" --key recipes.json --acl private
echo "  private ✓ recipes.json"

echo "▶ 3/3 Снимаю публичный доступ на уровне всего бакета…"
"${AWSCMD[@]}" s3api put-bucket-acl --bucket "$BUCKET" --acl private
echo "  bucket  ✓ private"

echo ""
echo "✅ Готово. Проверка ниже (без ключей):"
echo "   • recipes.json напрямую → ожидаем 403:"
curl -s -o /dev/null -w "     %{http_code}\n" "https://$BUCKET.website.yandexcloud.net/recipes.json" || true
echo "   • index.html → ожидаем 200:"
curl -s -o /dev/null -w "     %{http_code}\n" "https://$BUCKET.website.yandexcloud.net/index.html" || true
echo "   • demo-recipes.json → ожидаем 200:"
curl -s -o /dev/null -w "     %{http_code}\n" "https://$BUCKET.website.yandexcloud.net/demo-recipes.json" || true
