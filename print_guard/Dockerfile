FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --no-install-recommends --assume-yes fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY print_guard.py .

ENV PRINT_GUARD_CONFIG=/config/config.json \
    PYTHONUNBUFFERED=1
VOLUME ["/config", "/data"]
EXPOSE 8098

CMD ["python", "print_guard.py"]
