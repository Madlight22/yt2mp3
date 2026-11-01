# YouTube en MP3

Petit outil pour récupérer de la musique en MP3, depuis des liens YouTube, Spotify ou SoundCloud.

## Installation sur Mac
1. Double-clic sur le `.zip` pour l'extraire, puis range le dossier où tu veux (ex. Documents).
2. Double-clic sur **YouTube en MP3.command**.
   - Si macOS refuse de l'ouvrir (« Apple ne peut pas vérifier… ») : **Réglages Système → Confidentialité et sécurité**,
     tout en bas, clique sur **Ouvrir quand même**. À faire une seule fois.
3. Première fois : il installe yt-dlp et ffmpeg via Homebrew. Si Homebrew manque, la page https://brew.sh s'ouvre :
   copie la commande d'installation dans l'app Terminal, puis relance le fichier.
4. L'interface s'ouvre dans le navigateur. Pour quitter : fermer la fenêtre de Terminal.

Sur PC : voir le fichier `LISEZMOI.txt` du zip PC.

## Liens acceptés
- **YouTube** (vidéo ou playlist) : téléchargé directement.
- **Spotify** (playlist publique, album, titre) : chaque titre est cherché sur YouTube.
  Limite : seuls les 100 premiers titres d'une playlist sont lus.
- **SoundCloud** (set, page d'artiste, titre) : chaque titre est cherché sur YouTube.

Les MP3 vont dans `Téléchargements/MP3`, avec un sous-dossier par playlist ou album.
Les titres déjà présents sont sautés : relancer une playlist ne récupère que les nouveaux.

## Dépannage
Erreur 403 ou titres introuvables : `brew upgrade yt-dlp` (PC : `winget upgrade yt-dlp.yt-dlp`),
attendre 1–2 min, puis relancer.

## Pour le développeur
- `yt2mp3_app.py` : l'appli (serveur local + page web), sans dépendance Python, Mac et Windows.
- `YouTube en MP3.command` : lanceur Mac. `windows/` : lanceur `.bat`, icône `.ico` et notice PC.
- `yt2mp3.sh` : version ligne de commande, YouTube uniquement.
- `./fabriquer-zips.sh` : refait les deux zips à partager dans `dist/`.
