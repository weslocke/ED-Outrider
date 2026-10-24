#!/bin/sh
# A Docker release bundle, made here and published nowhere: the built image saved into one .tgz with a compose file
# that runs it, so a server needs no checkout and no build. On the server:
#   tar xzf ed-outrider-docker-<version>-<arch>.tgz && cd ed-outrider-docker-<version>-<arch>
#   docker load -i ed-outrider-image.tar        then follow INSTALL.txt
# Usage: scripts/docker_bundle.sh   (PLATFORM=linux/arm64 for an ARM server, if this Docker can build for it)
# Output: dist/ (git-ignored). The image is built from this checkout as it is, uncommitted changes included: the
# bundle's revision says "-dirty" then.
set -eu
cd "$(dirname "$0")/.."

VER=$(python3 -c 'import outrider; print(outrider.__version__)')
REV=$(git describe --always --dirty 2>/dev/null || echo unknown)
IMAGE="ed-outrider:$VER"

echo "building $IMAGE ($REV)"
# CERTIFI_CHECKED: a new value each day, so the Dockerfile's certifi upgrade runs again instead of coming from the cache
docker build ${PLATFORM:+--platform "$PLATFORM"} \
  --build-arg CERTIFI_CHECKED="$(date +%F)" \
  --label org.opencontainers.image.title="ED Outrider" \
  --label org.opencontainers.image.version="$VER" \
  --label org.opencontainers.image.revision="$REV" \
  -t "$IMAGE" .
ARCH=$(docker image inspect -f '{{.Architecture}}' "$IMAGE")
NAME="ed-outrider-docker-$VER-$ARCH"
OUT="dist/$NAME"
rm -rf "$OUT" "dist/$NAME.tgz"
mkdir -p "$OUT/docker/data" "$OUT/docker/config" "$OUT/docker/journals"

echo "saving the image"
docker save -o "$OUT/ed-outrider-image.tar" "$IMAGE"

# the repository's compose file, running the saved image instead of building one (pull_policy never: an image of
# the same name on Docker Hub is not this one)
{
  echo "# ED Outrider $VER ($REV) as a server, from the saved image (see INSTALL.txt). From this folder:"
  echo "#   docker compose up -d      start"
  echo "#   docker compose logs -f    its log"
  echo "#   docker compose down       stop"
  echo "# Set JOURNALS (and UID/GID if yours are not 1000, PORT if not 8025) in .env beside this file."
  sed -n '/^name:/,$p' docker-compose.yml \
    | sed -e '/^    build: \.$/d' \
          -e "s|^    image: ed-outrider:local$|    image: $IMAGE\n    pull_policy: never|"
} > "$OUT/docker-compose.yml"
grep -q "image: $IMAGE" "$OUT/docker-compose.yml" && grep -q "^name: ed-outrider$" "$OUT/docker-compose.yml" \
  && ! grep -q "^    build:" "$OUT/docker-compose.yml" \
  || { echo "docker-compose.yml changed shape: update the image line's rewrite in $0" >&2; exit 1; }

cat > "$OUT/.env.example" <<EOF
# copy to .env and set at least JOURNALS
# the game's journal folder (an NFS or CIFS mount of the game PC's share), read-only.
# NFS: mount it with actimeo=1 (e.g. fstab options ro,actimeo=1). By default NFS caches a file's size for up to a
# minute, so the journal seems not to grow and the alerts arrive late and all at once; Outrider warns at start.
JOURNALS=/mnt/elite-journals
# your user and group on this computer: id -u, id -g
UID=1000
GID=1000
# the port the pages are on
PORT=8025
# your time zone, e.g. Europe/London (the History's days)
TZ=UTC
# the name other Outriders see when this one uploads (EDDN, EDSM): "Already uploading from ..."
# OUTRIDER_HOST=outrider-docker
EOF

cat > "$OUT/INSTALL.txt" <<EOF
ED Outrider $VER ($REV), $ARCH: running as a server in Docker
========================================================================

Away from the game PC, what needs it is off and left out of the pages: auto honk, auto-target, the tablet's control
rail, the co-pilot button, the clipboard and sound played on the PC. Everything else works.

1. Load the image (once per release):
     docker load -i ed-outrider-image.tar

2. Make the game's journal folder reachable here, read-only: share it from the game PC over NFS or CIFS and mount
   it. NFS: mount it with actimeo=1, or NFS shows the journal's growth up to a minute late and the alerts come late
   and all at once (Outrider warns at start). The guide's "Running as a server (Docker)" has the export and mount
   lines: https://github.com/weslocke/ED-Outrider/blob/main/docs/guide/install.md

3. Settings:
     cp .env.example .env      then set JOURNALS to that mount (and UID/GID: id -u, id -g)

4. Start it, as the user who owns this folder:
     docker compose up -d
     docker compose logs -f    (the first start imports every journal: a while for years of them)

5. Open http://<this computer>:\${PORT:-8025}/ then Settings > Server settings: set a password (every device signs
   in here, your own browser too) and add this computer's name to allowed hosts if you open it by name (with the
   port when PORT is not 8025, e.g. nas:8030: the refusal page names the exact text). Then:
     docker compose restart

Uploads (EDDN, EDSM, off unless switched on): to let another Outrider see that this one uploads, give it a writable
folder in the journal share: mkdir -p "\$JOURNALS/.outrider" (on the share, as its owner), then uncomment the
.outrider line in docker-compose.yml. The guide's Uploads page explains.

Your database, backups and voices stay in docker/data/, the config in docker/config/. If the container says it
cannot write them: sudo chown -R \$(id -u):\$(id -g) docker/   then docker compose restart

Updating from an earlier bundle: extract this one beside the old one's folder, then from this folder:
     OLD=../ed-outrider-docker-<old version>-$ARCH          the old bundle's folder
     (cd "\$OLD" && docker compose down)                   stop it first, so its database is closed
     rm -rf docker && cp -a "\$OLD/docker" "\$OLD/.env" .
     docker load -i ed-outrider-image.tar
     docker compose up -d
   Your database, backups, voices and config come along in docker/; without them it starts as a new install. Every
   bundle uses the project name ed-outrider, so the new one takes the old one's place. Keep the old folder until
   the new one runs, then delete it and its image (docker rmi ed-outrider:<old version>).
Removing: docker compose down && docker rmi $IMAGE

Do not expose Outrider to the internet: for access away from home, use a VPN into your network.
EOF

tar -C dist -czf "dist/$NAME.tgz" "$NAME"

# for a GitHub release, beside the bundle: the compose file for the published image (GitHub's container registry:
# no download or docker load, and `docker compose pull` updates it), and the .env template
REG=ghcr.io/weslocke/ed-outrider
{
  echo "# ED Outrider as a server, from the image published on GitHub ($REG). In a folder of its own, with .env beside"
  echo "# this file (copied from env.example: set JOURNALS, and UID/GID if yours are not 1000):"
  echo "#   mkdir -p docker/data docker/config && docker compose up -d   start (the first time it downloads the image)"
  echo "#   docker compose pull && docker compose up -d                   update to the latest release"
  echo "#   docker compose logs -f                                        its log"
  echo "#   docker compose down                                           stop"
  sed -n '/^name:/,$p' docker-compose.yml \
    | sed -e '/^    build: \.$/d' -e "s|^    image: ed-outrider:local$|    image: $REG:latest|"
} > dist/docker-compose.yml
grep -q "image: $REG:latest" dist/docker-compose.yml && ! grep -q "^    build:" dist/docker-compose.yml \
  || { echo "docker-compose.yml changed shape: update the registry compose rewrite in $0" >&2; exit 1; }
cp "$OUT/.env.example" dist/env.example
rm -rf "$OUT"
echo "dist/$NAME.tgz ($(du -h "dist/$NAME.tgz" | cut -f1)): $IMAGE, $REV"
echo "dist/docker-compose.yml and dist/env.example: release files for $REG (push $IMAGE there as :$VER and :latest)"
