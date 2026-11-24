FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Paris \
    COPILOTE_HOST=0.0.0.0 \
    COPILOTE_PORT=8765 \
    COPILOTE_MISSIONS=/data/missions \
    COPILOTE_MODELES=/data/modeles

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd --uid 1000 --create-home copilote \
    && mkdir -p /data/missions /data/modeles \
    && chown -R copilote:copilote /data
USER copilote

VOLUME /data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['COPILOTE_PORT'] + '/', timeout=4)"]

CMD ["python", "server.py"]
