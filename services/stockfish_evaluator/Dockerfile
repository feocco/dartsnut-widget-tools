FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/feocco/dartsnut-widget-tools"

RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir chess==1.11.2
COPY app.py /app/app.py

ENV SERVICE_HOST=0.0.0.0
ENV SERVICE_PORT=8096
ENV STOCKFISH_PATH=/usr/games/stockfish

EXPOSE 8096
CMD ["python", "app.py"]
