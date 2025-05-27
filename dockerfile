# Use Python with Playwright pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-focal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (only Chromium for smaller size)
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]