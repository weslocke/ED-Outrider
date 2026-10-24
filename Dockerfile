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
# requirements.txt itself (review 2026-10-23 S7-S4: a hand copy missed a new package): every line but evdev (key presses
# on the game PC only) and, with WITH_PIPER=0, piper-tts; copied alone first, so the layer stays cached until it changes
COPY requirements.txt /tmp/requirements.txt
RUN grep -v -i -E '^(evdev|piper-tts)' /tmp/requirements.txt > /tmp/req-server.txt \
 && pip install --no-cache-dir -r /tmp/req-server.txt \
 && if [ "$WITH_PIPER" = "1" ]; then pip install --no-cache-dir "$(grep -i -E '^piper-tts' /tmp/requirements.txt | sed 's/[[:space:]]*#.*//')"; fi
# certifi (the root certificates every HTTPS request also trusts) as new as the build: the layer above stays in
# Docker's cache while this file and the base image are unchanged, keeping the certifi of the first build.
# scripts/docker_bundle.sh passes the day's date, so a release's build always asks for the newest
ARG CERTIFI_CHECKED=
RUN echo "certifi: the newest as of ${CERTIFI_CHECKED:-the first build}" && pip install --no-cache-dir --upgrade certifi

COPY . .
# runs as your user (compose's user:), so the shipped data it refreshes (the bio rules) and the defaults it needs must
# be writable by anyone; your own files live in the volumes
RUN chmod -R a+rwX /app/resources && mkdir -p /app/data /config && chmod a+rwx /app/data /config \
 && chmod a+rx docker/entrypoint.sh

EXPOSE 8025
STOPSIGNAL SIGTERM
# healthy as soon as Outrider answers: while it reads the journals (a while for years of them, the first start or a
# re-read) its starting page and /api/version answer already (S9), so the start period only covers Python starting
HEALTHCHECK --interval=60s --timeout=5s --start-period=2m --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8025/api/version', timeout=4)" || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
