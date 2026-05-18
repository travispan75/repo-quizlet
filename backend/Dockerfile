FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Default: API. Override start command for the worker service.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
