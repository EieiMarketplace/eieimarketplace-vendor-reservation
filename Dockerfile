# Dockerfile
FROM python:3.11-slim

# Keep image lean and avoid full distro upgrade during build which slows rebuilds
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Make Python output unbuffered (easier logs) and avoid writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install Python deps first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# Copy application source
COPY ./app /app

# Expose FastAPI
EXPOSE 7003

# Start FastAPI
CMD ["python", "main.py"]
