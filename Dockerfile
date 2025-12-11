# Minimal container for Cloud Run / Functions Framework
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Functions Framework HTTP target slack_notify
CMD ["functions-framework", "--target=slack_notify", "--port=8080"]
