#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt2mp3 — Petite interface web locale pour télécharger de la musique en MP3.

Accepte :
  - des liens YouTube (vidéo ou playlist) : téléchargés directement ;
  - des liens Spotify (playlist, album, titre) ou SoundCloud (set, artiste, titre) :
    chaque morceau est cherché sur YouTube puis téléchargé.

Lance ce fichier : il démarre un mini-serveur local et ouvre ton navigateur.
Aucune dépendance Python : juste yt-dlp + ffmpeg (installés via Homebrew).
Le serveur n'écoute que sur 127.0.0.1 (rien n'est accessible depuis l'extérieur).
"""

import os
import re
import json
import shutil
import subprocess
import threading
import webbrowser
import urllib.request
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WINDOWS = os.name == "nt"

# --- Rendre yt-dlp / ffmpeg trouvables (Homebrew sur Mac, winget sur Windows) ---
if WINDOWS:
    _extra = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")]
else:
    _extra = ["/opt/homebrew/bin", "/usr/local/bin"]
for p in _extra:
    if p and p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
# Sorties en UTF-8 partout (évite les plantages sur les titres accentués sous Windows)
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
TEXTE = {"text": True, "encoding": "utf-8", "errors": "replace"}

YTDLP = shutil.which("yt-dlp")
FFMPEG = shutil.which("ffmpeg")

DOSSIER_DEFAUT = os.path.join(os.path.expanduser("~"), "Downloads", "MP3")
HOST = "127.0.0.1"
# 0 = le système choisit un port libre automatiquement.
# On peut forcer un port avec la variable d'environnement YT2MP3_PORT.
PORT = int(os.environ.get("YT2MP3_PORT") or 0)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130 Safari/537.36")

# Résistance aux blocages passagers (HTTP 403) de YouTube
RETRY = ["--retries", "10", "--fragment-retries", "10", "--retry-sleep", "3"]
ENC = ["--encoding", "utf-8"]
MP3 = ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]

# Mots qui signalent une autre version que l'originale (pénalisés à la recherche)
MOTS_SUSPECTS = ["live", "remix", "cover", "karaoke", "instrumental", "sped up",
                 "slowed", "reverb", "nightcore", "8d", "1 hour", "acapella",
                 "a cappella", "extended", "drumless", "acoustic", "demo",
                 "bass boosted", "8 bit", "piano version", "slowed + reverb"]
ECART_MAX = 30   # secondes : au-delà, on considère que ce n'est pas le bon morceau
ECART_OK = 8     # secondes : en dessous, la correspondance est jugée sûre


class ClientParti(Exception):
    """Le navigateur a fermé la connexion : on arrête le travail."""


# ---------------------------------------------------------------- utilitaires

def nettoyer(nom):
    """Nom de fichier sûr pour macOS."""
    nom = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", nom).strip(" .")
    return (nom or "sans titre")[:180]


def duree_txt(s):
    s = int(round(s or 0))
    return f"{s // 60}:{s % 60:02d}"


def source_de(url):
    hote = urlparse(url).netloc.lower()
    if "spotify" in hote:
        return "spotify"
    if "soundcloud" in hote:
        return "soundcloud"
    return "direct"


def lancer_ytdlp(cmd, out, montrer_progression=True):
    """Lance yt-dlp et renvoie au navigateur les lignes utiles."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            bufsize=1, **TEXTE)
    try:
        for ligne in proc.stdout:
            ligne = ligne.rstrip()
            if ligne.startswith("ERROR"):
                out("   " + ligne)
            elif montrer_progression and (
                    ("[download]" in ligne and "%" in ligne)
                    or "[ExtractAudio]" in ligne
                    or "has already been downloaded" in ligne):
                out("   " + ligne)
    except ClientParti:
        proc.kill()
        raise
    return proc.wait()


# ---------------------------------------------------------------- YouTube direct

def telecharger_direct(url, dossier, out):
    cmd = [YTDLP, *ENC, "--newline", *MP3, "--embed-thumbnail", "--embed-metadata", *RETRY,
           "--output", os.path.join(dossier, "%(title)s.%(ext)s"), url]
    rc = lancer_ytdlp(cmd, out)
    out("   ✅ OK" if rc == 0 else f"   ❌ Échec (code {rc})")


# ---------------------------------------------------------------- Spotify

SPOTIFY_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-zA-Z-]+/)?(?:embed/)?(playlist|album|track)/([A-Za-z0-9]+)")


def titres_spotify(url):
    """Lit une playlist / un album / un titre via la page publique « embed ».
    Renvoie (nom, type, [(artiste, titre, durée_s), ...])."""
    m = SPOTIFY_RE.search(url)
    if not m:  # lien court (spotify.link…) : on suit la redirection
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        m = SPOTIFY_RE.search(urllib.request.urlopen(req, timeout=20).geturl())
    if not m:
        raise ValueError("Lien Spotify non reconnu (il faut une playlist, un album ou un titre).")
    genre, ident = m.groups()
    req = urllib.request.Request(f"https://open.spotify.com/embed/{genre}/{ident}",
                                 headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    bloc = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not bloc:
        raise ValueError("Impossible de lire cette page Spotify (playlist privée ?).")
    ent = json.loads(bloc.group(1))["props"]["pageProps"]["state"]["data"]["entity"]

    def propre(s):
        return (s or "").replace("\xa0", " ").strip()

    nom = propre(ent.get("name") or ent.get("title")) or "Spotify"
    if genre == "track":
        artistes = ", ".join(a.get("name", "") for a in ent.get("artists", []))
        return nom, genre, [(propre(artistes), propre(ent.get("title") or ent.get("name")),
                             (ent.get("duration") or 0) / 1000)]
    titres = [(propre(t.get("subtitle")), propre(t.get("title")), (t.get("duration") or 0) / 1000)
              for t in ent.get("trackList", []) if t.get("title")]
    return nom, genre, titres


# ---------------------------------------------------------------- SoundCloud

def titres_soundcloud(url, out):
    """Lit un set / une page d'artiste / un titre SoundCloud (sans rien télécharger).
    Renvoie (nom, [(artiste, titre, durée_s), ...])."""
    cmd = [YTDLP, *ENC, "--skip-download", "--ignore-errors", "--no-warnings",
           "--ignore-no-formats-error",
           "--print", "%(playlist_title|)s\t%(uploader|)s\t%(title|)s\t%(duration|0)s", url]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            bufsize=1, **TEXTE)
    nom, titres = None, []
    try:
        for ligne in proc.stdout:
            parts = ligne.rstrip("\n").split("\t")
            if len(parts) != 4 or not parts[2]:
                continue
            liste, artiste, titre, duree = parts
            nom = nom or liste or None
            # Beaucoup de titres SoundCloud sont déjà « Artiste - Titre »
            if " - " in titre:
                artiste, titre = titre.split(" - ", 1)
            try:
                duree = float(duree)
            except ValueError:
                duree = 0
            titres.append((artiste.strip(), titre.strip(), duree))
            out(f"   • {artiste.strip()} – {titre.strip()}")
    except ClientParti:
        proc.kill()
        raise
    proc.wait()
    return nom, titres


# ---------------------------------------------------------------- recherche YouTube

def recherche_youtube(requete):
    r = subprocess.run([YTDLP, *ENC, "--flat-playlist", "-J", "--no-warnings", f"ytsearch8:{requete}"],
                       capture_output=True, timeout=90, **TEXTE)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    return json.loads(r.stdout).get("entries") or []


def chercher_sur_youtube(artiste, titre, duree):
    """Renvoie (candidat, écart_s, suspect) pour la meilleure vidéo, ou None."""
    reference = f"{artiste} {titre}".lower()
    mots_titre = [w for w in re.findall(r"\w+", titre.lower()) if len(w) >= 3]
    premier_artiste = artiste.split(",")[0].strip().lower()
    meilleur = None

    for requete in (f"{artiste} - {titre}", f"{artiste} {titre} audio"):
        for c in recherche_youtube(requete):
            d = c.get("duration")
            if not d or not c.get("id"):
                continue
            t = (c.get("title") or "").lower()
            chaine = c.get("channel") or c.get("uploader") or ""
            ecart = abs(d - duree) if duree else 0
            penalite = 0
            for w in MOTS_SUSPECTS:
                if re.search(r"\b" + re.escape(w) + r"\b", t) and w not in reference:
                    penalite += 30
            if mots_titre and not any(w in t for w in mots_titre):
                penalite += 20
            bonus = 5 if chaine.endswith(" - Topic") else (
                2 if premier_artiste and premier_artiste in chaine.lower() else 0)
            score = ecart + penalite - bonus
            if meilleur is None or score < meilleur[0]:
                meilleur = (score, c, ecart, penalite > 0)
        # Correspondance sûre trouvée : inutile de lancer la 2e recherche
        if meilleur and meilleur[2] <= ECART_OK and not meilleur[3]:
            break

    if not meilleur or (duree and meilleur[2] > ECART_MAX):
        return None
    _, c, ecart, suspect = meilleur
    return c, ecart, suspect


def ecrire_tags(chemin, artiste, titre, album):
    """Remplace les infos YouTube par les vraies (artiste / titre / album)."""
    tmp = chemin[:-4] + ".tags.mp3"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", chemin, "-map", "0", "-c", "copy",
           "-id3v2_version", "3", "-map_metadata", "-1",
           "-metadata", f"title={titre}", "-metadata", f"artist={artiste}"]
    if album:
        cmd += ["-metadata", f"album={album}"]
    cmd.append(tmp)
    if subprocess.run(cmd, capture_output=True).returncode == 0:
        os.replace(tmp, chemin)
    elif os.path.exists(tmp):
        os.remove(tmp)


NOMS_SOURCES = {"spotify": "Spotify", "soundcloud": "SoundCloud"}


def traiter_liste(source, url, dossier, out):
    out(f"🔎 Lecture du lien {NOMS_SOURCES[source]}…")
    if source == "spotify":
        nom, genre, titres = titres_spotify(url)
        if genre == "playlist" and len(titres) == 100:
            out("⚠️ Spotify ne montre que les 100 premiers titres d'une playlist publique.")
    else:
        nom, titres = titres_soundcloud(url, out)
        genre = "playlist"
    if not titres:
        out("❌ Aucun titre trouvé (liste privée, vide ou lien incorrect ?).")
        return

    album = nom if (source == "spotify" and genre == "album") else ""
    cible = os.path.join(dossier, nettoyer(nom)) if (nom and len(titres) > 1) else dossier
    os.makedirs(cible, exist_ok=True)
    out(f"📋 {nom or NOMS_SOURCES[source]} — {len(titres)} titre(s)")

    ok = deja = 0
    rates = []
    for i, (artiste, titre, duree) in enumerate(titres, 1):
        etiquette = f"{artiste} - {titre}" if artiste else titre
        out(f"\n[{i}/{len(titres)}] {etiquette}")
        fichier = os.path.join(cible, nettoyer(etiquette) + ".mp3")
        if os.path.exists(fichier):
            out("   ⏭️ déjà téléchargé")
            deja += 1
            continue
        try:
            res = chercher_sur_youtube(artiste, titre, duree)
            if not res:
                out("   ❌ pas trouvé sur YouTube")
                rates.append(etiquette)
                continue
            c, ecart, suspect = res
            info = f"   ↳ {c.get('title')} · {c.get('channel') or c.get('uploader') or '?'} · {duree_txt(c.get('duration'))}"
            if suspect:
                info += "  ⚠️ version peut-être différente"
            elif duree and ecart > ECART_OK:
                info += f"  ⚠️ écart de {int(ecart)} s"
            out(info)
            base = nettoyer(etiquette).replace("%", "%%")
            cmd = [YTDLP, *ENC, "--newline", "--no-playlist", *MP3, "--embed-thumbnail", *RETRY,
                   "--output", os.path.join(cible, base + ".%(ext)s"),
                   f"https://www.youtube.com/watch?v={c['id']}"]
            rc = lancer_ytdlp(cmd, out, montrer_progression=False)
            if rc == 0 and os.path.exists(fichier):
                ecrire_tags(fichier, artiste, titre, album)
                out("   ✅ OK")
                ok += 1
            else:
                out(f"   ❌ Échec du téléchargement (code {rc})")
                rates.append(etiquette)
        except ClientParti:
            raise
        except Exception as e:
            out(f"   ❌ Erreur : {e}")
            rates.append(etiquette)

    out(f"\n📊 {ok} téléchargé(s), {deja} déjà là, {len(rates)} raté(s).")
    if rates:
        out("Ratés :\n" + "\n".join(f"   - {r}" for r in rates))
    out(f"📁 {cible}")


# ---------------------------------------------------------------- page web

PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube → MP3</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background:#141414; color:#eee;
         margin:0; padding:32px 16px; display:flex; justify-content:center; }
  .card { width:100%; max-width:680px; }
  h1 { font-size:20px; margin:0 0 4px; }
  p.sub { color:#888; margin:0 0 20px; font-size:13px; line-height:1.5; }
  label { display:block; font-size:13px; color:#bbb; margin:16px 0 6px; }
  textarea, input[type=text] { width:100%; background:#1f1f1f; border:1px solid #333;
         color:#eee; border-radius:8px; padding:10px; font-size:14px; font-family:inherit; }
  textarea { height:90px; resize:vertical; }
  button { background:#e0245e; color:#fff; border:0; border-radius:8px; padding:12px 18px;
           font-size:15px; font-weight:600; cursor:pointer; margin-top:20px; width:100%; }
  button:disabled { opacity:.5; cursor:default; }
  #log { margin-top:20px; background:#0e0e0e; border:1px solid #2a2a2a; border-radius:8px;
         padding:12px; height:340px; overflow:auto; font-family:ui-monospace,Menlo,monospace;
         font-size:12.5px; white-space:pre-wrap; color:#cfcfcf; }
  .warn { background:#3a2a00; border:1px solid #6b5200; color:#ffd479; padding:10px;
          border-radius:8px; font-size:13px; margin-bottom:16px; }
</style>
</head>
<body>
<div class="card">
  <h1>🎵 YouTube → MP3</h1>
  <p class="sub">Colle un ou plusieurs liens (un par ligne).<br>
  YouTube : téléchargé directement. Spotify ou SoundCloud : chaque titre est cherché sur YouTube.</p>
  __WARN__
  <label>Liens YouTube, Spotify ou SoundCloud</label>
  <textarea id="urls" placeholder="https://www.youtube.com/watch?v=...&#10;https://open.spotify.com/playlist/...&#10;https://soundcloud.com/.../sets/..." autofocus></textarea>
  <label>Dossier de destination</label>
  <input type="text" id="dossier" value="__DOSSIER__">
  <button id="go">⬇  Télécharger en MP3</button>
  <div id="log">Prêt.</div>
</div>
<script>
const $ = s => document.querySelector(s);
const log = $("#log");
function write(t){ log.textContent += "\\n" + t; log.scrollTop = log.scrollHeight; }

$("#go").addEventListener("click", async () => {
  const urls = $("#urls").value.split("\\n").map(s=>s.trim()).filter(Boolean);
  const dossier = $("#dossier").value.trim();
  if (!urls.length){ alert("Colle au moins un lien."); return; }
  $("#go").disabled = true;
  log.textContent = "Démarrage…";
  try {
    const res = await fetch("/download", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({urls, dossier})
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while(true){
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      const parts = buf.split("\\n");
      buf = parts.pop();
      for (const line of parts) write(line);
    }
    if (buf) write(buf);
  } catch(e){ write("❌ Connexion perdue avec l'appli (fenêtre de terminal fermée ?) : " + e); }
  $("#go").disabled = false;
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        warn = ""
        if not YTDLP or not FFMPEG:
            manquant = "yt-dlp" if not YTDLP else "ffmpeg"
            warn = (f'<div class="warn">⚠️ {manquant} introuvable. '
                    f'Installe-le : <code>brew install yt-dlp ffmpeg</code></div>')
        html = PAGE.replace("__DOSSIER__", DOSSIER_DEFAUT).replace("__WARN__", warn)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/download":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        urls = [u.strip() for u in data.get("urls", []) if u.strip()]
        dossier = os.path.expanduser((data.get("dossier") or DOSSIER_DEFAUT).strip())

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

        def out(ligne):
            try:
                self.wfile.write((ligne + "\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise ClientParti()

        try:
            if not YTDLP or not FFMPEG:
                out("❌ yt-dlp ou ffmpeg introuvable. brew install yt-dlp ffmpeg")
                return
            os.makedirs(dossier, exist_ok=True)
            for i, url in enumerate(urls, 1):
                source = source_de(url)
                out(f"🎵 ({i}/{len(urls)}) {url}")
                try:
                    if source == "direct":
                        telecharger_direct(url, dossier, out)
                    else:
                        traiter_liste(source, url, dossier, out)
                except ClientParti:
                    raise
                except Exception as e:
                    out(f"   ❌ Erreur : {e}")
            out(f"\n📁 Fichiers dans : {dossier}")
            out("✅ Terminé.")
        except ClientParti:
            pass  # onglet fermé : on arrête simplement


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    port = srv.server_address[1]
    url = f"http://{HOST}:{port}/"
    print(f"Interface ouverte sur {url}", flush=True)
    print("Ferme cette fenêtre de terminal pour quitter.", flush=True)
    if not os.environ.get("YT2MP3_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
