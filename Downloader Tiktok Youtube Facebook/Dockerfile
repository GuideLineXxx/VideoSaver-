# Gunakan base image Python yang ringan
FROM python:3.10-slim

# Install FFmpeg (wajib untuk menggabungkan video & audio kualitas tinggi)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory di dalam container
WORKDIR /app

# Salin file requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi
COPY . .

# Buat folder downloads jika belum ada
RUN mkdir -p downloads

# Ekspos port 5000 (port yang digunakan Flask/Gunicorn)
EXPOSE 5000

# Jalankan aplikasi menggunakan Gunicorn untuk production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]
