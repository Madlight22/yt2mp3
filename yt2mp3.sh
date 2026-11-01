#!/bin/bash
#
# yt2mp3 — Télécharge une ou plusieurs vidéos YouTube en MP3
#
# Usage :
#   ./yt2mp3.sh <url> [url2 ...]
#   ./yt2mp3.sh                (te demande l'URL)
#
# Les fichiers sont enregistrés dans le dossier ./mp3/
#

set -euo pipefail

# Dossier de sortie (à côté du script)
DOSSIER="$(cd "$(dirname "$0")" && pwd)/mp3"
mkdir -p "$DOSSIER"

# Vérifie que yt-dlp est installé
if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "❌ yt-dlp n'est pas installé. Lance : brew install yt-dlp ffmpeg"
  exit 1
fi

# Si aucune URL passée en argument, on la demande
if [ "$#" -eq 0 ]; then
  read -rp "Colle l'URL YouTube : " url
  set -- "$url"
fi

for url in "$@"; do
  echo "🎵 Téléchargement : $url"
  yt-dlp \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    --embed-thumbnail \
    --embed-metadata \
    --retries 10 \
    --fragment-retries 10 \
    --retry-sleep 3 \
    --output "$DOSSIER/%(title)s.%(ext)s" \
    "$url"
done

echo "✅ Terminé. Fichiers dans : $DOSSIER"
