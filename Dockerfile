# ED Outrider as a server: Outrider running 24/7 on another computer, reading the game's journals from a share.
# Away from the game PC, what needs it is off ([server] game_pc = auto: off inside this container): auto honk,
# auto-target, the tablet's rail, the co-pilot button, the clipboard, sound played on the PC. See docs/guide/install.md,
# "Running as a server (Docker)". Built where it runs (x86-64 or arm64): docker compose up -d --build
FROM python:3.12-slim
# published as ghcr.io/weslocke/ed-outrider (these labels link the package to the repository)
LABEL org.opencontainers.image.source="https://github.com/weslocke/ED-Outrider" \
      org.opencontainers.image.description="ED Outrider: an exploration companion for Elite Dangerous, as a server (the game-PC automation is off in Docker)" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OUTRIDER_CONTAINER=1
WORKDIR /app

# Piper (the voice, about 100 MB with onnxruntime) is in by default; --build-arg WITH_PIPER=0 leaves it out (the
# pages then speak with the browser's voice)
ARG WITH_PIPER=1
RUN pip install --no-cache-dir "aiohttp>=3.9" \
 && if [ "$WITH_PIPER" = "1" ]; then pip install --no-cache-dir "piper-tts>=1.3"; fi

COPY . .
# runs as your user (compose's user:), so the shipped data it refreshes (the bio rules) and the defaults it needs must
# be writable by anyone; your own files live in the volumes
RUN chmod -R a+rwX /app/resources && mkdir -p /app/data /config && chmod a+rwx /app/data /config \
 && chmod a+rx docker/entrypoint.sh

EXPOSE 8025
STOPSIGNAL SIGTERM
# start-period: the first start reads every journal before the server answers (a while for years of them); a success
# ends the start period at once, so a quick start is not held back
HEALTHCHECK --interval=60s --timeout=5s --start-period=30m --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8025/api/version', timeout=4)" || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
