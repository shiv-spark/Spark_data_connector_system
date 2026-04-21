FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project files
COPY connectors/  ./connectors/
COPY utils/       ./utils/
COPY loaders/     ./loaders/
COPY main.py      .
COPY run.py       .

# Required folders
RUN mkdir -p dags data backups

EXPOSE 8000

CMD ["python", "run.py"]