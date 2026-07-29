# Правки бэкенда для v2 (применять вручную, когда решим)

Бэкенд ОДИН на обе версии (боевую и v2). Поэтому правки ниже не входят в deploy-v2.sh —
их применяет Замир сам, осознанно.

## 1. CORS: пустить v2-домен в API (нужно СРАЗУ для теста входа в кабинет v2)

Консоль Яндекса → API Gateway `nutrition-auth-api` → редактировать спеку →
блок `x-yc-apigateway.cors.origin` заменить на список:

```yaml
x-yc-apigateway:
  cors:
    origin:
      - 'https://roman-nutrition-app.website.yandexcloud.net'
      - 'https://roman-app-v2.website.yandexcloud.net'
    methods: 'GET, POST, OPTIONS'
    allowedHeaders: 'Content-Type, Authorization'
    credentials: true
    maxAge: 3600
```

Это безопасно для боевой версии: просто добавляется второй разрешённый домен.

## 2. Доступ 95 дней вместо 31 (ТОЛЬКО при боевом запуске v2!)

Cloud Function (yandex-backend/index.js), строка ~35:

```js
const ACCESS_DAYS = 95;   // было 31 (90 дней плана + 5 дней на раскачку)
```

⚠ После заливки ВСЕ новые оплаты будут давать 95 дней доступа —
применять одновременно со сменой тарифа на 90 дней / 1499₽.
