FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

# Install Node.js (for Tailwind/PostCSS build)
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Python deps first (layer caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything
COPY . /app/

# ── Build Tailwind / Node assets ──
# Uncomment/adjust based on your package.json setup:
COPY package.json package-lock.json /app/
RUN npm install
RUN npm run build

# ── Collect static files ──
RUN python manage.py collectstatic --no-input

# ── Entrypoint that runs migrations then starts Gunicorn ──
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]