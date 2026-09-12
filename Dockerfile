# Production Dockerfile for Outside Bubble Scraper Service
FROM mcr.microsoft.com/playwright/python:v1.46.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser dependencies
RUN playwright install chromium

# Copy application source code
COPY . .

# Expose HTTP port
EXPOSE 8000

# Run FastAPI service
CMD ["uvicorn", "apps.scraper_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
