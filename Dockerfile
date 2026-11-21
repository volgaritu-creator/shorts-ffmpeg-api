FROM python:3.11-slim

# Install FFmpeg and Noto Sans Devanagari font for Hindi text rendering
RUN apt-get update && \
    apt-get install -y ffmpeg fonts-noto-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]
