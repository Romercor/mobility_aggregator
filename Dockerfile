FROM python:3.11-slim

WORKDIR /app

# System dependencies für Playwright
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]