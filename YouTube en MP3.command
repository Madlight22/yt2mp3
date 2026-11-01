#!/bin/bash
# Double-clique ce fichier pour ouvrir l'interface YouTube → MP3
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Première utilisation : installer yt-dlp et ffmpeg si besoin
if ! command -v yt-dlp >/dev/null 2>&1 || ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Première utilisation : installation de yt-dlp et ffmpeg…"
  if command -v brew >/dev/null 2>&1; then
    brew install yt-dlp ffmpeg || { echo "❌ L'installation a échoué."; read -rp "Appuie sur Entrée pour fermer."; exit 1; }
  else
    echo ""
    echo "Il manque Homebrew (l'outil qui installe yt-dlp et ffmpeg)."
    echo "1. Sur la page https://brew.sh qui vient de s'ouvrir, copie la commande d'installation."
    echo "2. Colle-la dans l'app Terminal et suis les instructions (mot de passe du Mac demandé)."
    echo "3. Relance ce fichier."
    open "https://brew.sh"
    read -rp "Appuie sur Entrée pour fermer."
    exit 1
  fi
fi

/usr/bin/python3 yt2mp3_app.py
