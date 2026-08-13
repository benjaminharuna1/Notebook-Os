FROM python:3.12-slim

WORKDIR /app

# llama-cpp-python may need to build from source when no wheel is available
# (e.g. ARM); install the build toolchain up front.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
