#!/bin/bash
# Fabrique les deux zips à partager (Mac et PC).
# Usage : ./fabriquer-zips.sh [dossier_de_sortie]   (par défaut : dist/)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "${1:-dist}"
OUT="$(cd "${1:-dist}" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
NOM="YouTube en MP3"

# --- Mac
D="$TMP/mac/$NOM"; mkdir -p "$D"
ditto "YouTube en MP3.command" "$D/YouTube en MP3.command"
# Remet l'icône depuis icone.png (git ne conserve pas l'icône d'un fichier Mac)
cp icone.png "$TMP/icone.png"
sips -i "$TMP/icone.png" >/dev/null
DeRez -only icns "$TMP/icone.png" > "$TMP/icone.rsrc"
Rez -append "$TMP/icone.rsrc" -o "$D/YouTube en MP3.command"
SetFile -a C "$D/YouTube en MP3.command"
cp yt2mp3_app.py README.md "$D/"
rm -f "$OUT/YouTube-en-MP3-Mac.zip"
ditto -c -k --sequesterRsrc --keepParent "$D" "$OUT/YouTube-en-MP3-Mac.zip"

# --- PC : zip classique, sans fichiers spécifiques au Mac
D="$TMP/pc/$NOM"; mkdir -p "$D"
cp yt2mp3_app.py "windows/YouTube en MP3.bat" windows/icone.ico windows/LISEZMOI.txt "$D/"
rm -f "$OUT/YouTube-en-MP3-PC.zip"
(cd "$TMP/pc" && zip -rqX "$OUT/YouTube-en-MP3-PC.zip" "$NOM")

echo "Zips prêts dans $OUT :"
ls -lh "$OUT"/YouTube-en-MP3-*.zip
