FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir mutagen

WORKDIR /data

COPY cuetoflac.py /usr/local/bin/cuetoflac
RUN chmod +x /usr/local/bin/cuetoflac

ENTRYPOINT ["python", "/usr/local/bin/cuetoflac"]
