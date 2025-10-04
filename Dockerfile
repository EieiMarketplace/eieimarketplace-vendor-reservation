# Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app:/app/grpc_generated:${PYTHONPATH}"

# install system deps (optional)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY app/ ./ 


# Expose FastAPI and gRPC ports
EXPOSE 7003

# Start FastAPI + gRPC together
# CMD ["python", "main.py"]
CMD ["bash", "-c", "python main.py"]
