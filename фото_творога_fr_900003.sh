#!/usr/bin/env bash
# Фото для fr_900003 «Творог (порция белка)» — закрывает последнюю заглушку в деке.
# Пайплайн по правилам: PNG → webp (Pillow, quality 82) → dish_photos/<id>.webp → image_url.
set -euo pipefail
cd "$(dirname "$0")"
curl -fsSL "https://d8j0ntlcm91z4.cloudfront.net/user_3EYFzeIMBFYcZn6fKkhmqrweQkZ/hf_20260710_110118_3d96a614-f2f2-49f5-8c20-363fba991749.png" -o /tmp/fr_900003.png
python3 - <<'EOF'
from PIL import Image
import json
Image.open('/tmp/fr_900003.png').convert('RGB').save('dish_photos/fr_900003.webp','WEBP',quality=82)
recs=json.load(open('recipes.json',encoding='utf-8'))
for x in recs:
    if x['id']=='fr_900003': x['image_url']='dish_photos/fr_900003.webp'
json.dump(recs,open('recipes.json','w',encoding='utf-8'),ensure_ascii=False)
print('✅ dish_photos/fr_900003.webp создан, image_url проставлен')
EOF
echo "Не забудь при следующем деплое v2: фото уедет через «bash app-v2/deploy-v2.sh photos» или точечно:"
echo "aws --endpoint-url https://storage.yandexcloud.net s3 cp dish_photos/fr_900003.webp s3://roman-app-v2/dish_photos/fr_900003.webp --acl public-read --content-type image/webp"
