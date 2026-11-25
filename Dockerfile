# Cable-N - single container: builds the website, serves it and the API on :8000.
FROM node:22-alpine AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_SITE_URL=https://cable-n.onrender.com
ARG VITE_ADS_ENABLED=false
ARG VITE_ADSENSE_CLIENT=
ARG VITE_ADSENSE_SLOT_RAIL=
ARG VITE_ADSENSE_SLOT_INLINE=
ARG VITE_ADSENSE_CMP=own
ARG VITE_CONTACT_EMAIL=
ENV VITE_SITE_URL=$VITE_SITE_URL VITE_ADS_ENABLED=$VITE_ADS_ENABLED VITE_ADSENSE_CLIENT=$VITE_ADSENSE_CLIENT \
    VITE_ADSENSE_SLOT_RAIL=$VITE_ADSENSE_SLOT_RAIL VITE_ADSENSE_SLOT_INLINE=$VITE_ADSENSE_SLOT_INLINE \
    VITE_ADSENSE_CMP=$VITE_ADSENSE_CMP VITE_CONTACT_EMAIL=$VITE_CONTACT_EMAIL
RUN npx vite build && node scripts/postbuild.mjs

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY reference /app/reference
COPY --from=web /src/frontend/dist /app/frontend/dist
COPY frontend/public/brand /app/frontend/public/brand
RUN useradd -r -u 10001 cablen && chown -R cablen /app
USER cablen
# Render (and most hosts) set $PORT; one worker keeps memory under 512 MB (free tier).
ENV PORT=8000 WEB_CONCURRENCY=1 TRUST_PROXY_HEADERS=true
EXPOSE 8000
HEALTHCHECK CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/v1/health')"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips '*'"]
