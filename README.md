# Video Studio — FastAPI Backend

API locale pour envoyer des vidéos MP4, créer des extraits, extraire de l’audio et capturer les changements de scène.

## Prérequis et démarrage

- Python 3.12
- FFmpeg et FFprobe accessibles dans le `PATH`

Dans PowerShell, à la racine du projet :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002
```

Ouvre [l’interface](http://127.0.0.1:8002/) ou [la documentation interactive](http://127.0.0.1:8002/docs). Garde le terminal ouvert ; `Ctrl+C` arrête le serveur.

## Architecture

```text
Interface HTML / JavaScript
           | HTTP
           v
routers/   Requêtes, statuts HTTP et réponses fichiers
           |
           v
services/  Règles métier et opérations par domaine
           |                    |
           v                    v
core/storage.py          services/media.py
Fichiers et JSON          FFmpeg / FFprobe
```

```text
app/
  main.py          Assemble FastAPI, les routes et la gestion des erreurs
  schemas.py       Modèles Pydantic des requêtes
  routers/
    system.py      Accueil et health check
    videos.py      Envoi, liste, lecture et suppression des vidéos
    clips.py       Création, liste et suppression des extraits
    audio.py       Extraction MP3 / WAV
    frames.py      Extraction, lecture et suppression des captures
    files.py       Accès aux fichiers locaux
  services/
    videos.py      Logique des vidéos
    clips.py       Validation des temps et découpage
    audio.py       Conversion audio
    frames.py      Détection de scènes et gestion des captures
    files.py       Validation des fichiers demandés
    media.py       Exécution des commandes FFmpeg / FFprobe
  core/
    storage.py     Configuration du stockage et recherche de fichiers
    errors.py      Erreurs des services traduites en HTTP par main.py
  index.html       Interface locale
requirements.txt       Dépendances de l’application
requirements-dev.txt   Outils de développement et de test
tests/                 Tests automatisés
storage/               Fichiers locaux, ignorés par Git
```

Il n’y a pas de base de données : les MP4, MP3, WAV, images et métadonnées sont stockés localement. Les noms générés utilisent des identifiants uniques. Le contrôle à l’envoi vérifie l’extension, pas le contenu réel de la vidéo.

Les routes transmettent les opérations aux services. Les services appliquent les règles métier et utilisent le stockage commun ; ils ne créent pas de réponses HTTP. Le gestionnaire d’erreurs de `main.py` traduit leurs erreurs en réponses JSON.

Le dossier `storage/` est ancré à la racine du projet, indépendamment du répertoire courant. La variable d’environnement `VIDEO_STORAGE_DIR` permet de le remplacer. Swagger regroupe les endpoints par domaine.

## API

| Méthode | Route | Utilisation |
| --- | --- | --- |
| GET | `/health` | Vérifier que l’API répond. |
| GET | `/videos` | Lister les vidéos originales. |
| POST | `/videos` | Envoyer un MP4 dans le champ multipart `file`. |
| GET | `/videos/{video_id}` | Lire une vidéo. |
| DELETE | `/videos/{video_id}` | Supprimer la vidéo, ses extraits et leurs métadonnées de découpage. |
| GET | `/videos/{video_id}/clips` | Lister les extraits d’une vidéo. |
| POST | `/videos/{video_id}/clips` | Créer des extraits depuis des intervalles `MM:SS` ou `HH:MM:SS`. |
| DELETE | `/videos/{video_id}/clips/{clip_id}` | Supprimer un extrait. |
| POST | `/videos/{video_id}/audio` | Extraire l’audio d’une vidéo ou d’un extrait, avec `{"format": "mp3"}` ou `{"format": "wav"}`. |
| POST | `/videos/{video_id}/frames` | Capturer les changements de scène d’une vidéo ou d’un extrait. |
| GET | `/videos/{video_id}/frames` | Lister les lots de captures d’une source. |
| GET | `/frames/{batch_id}/{filename}` | Lire une capture. |
| DELETE | `/frames/{batch_id}/{filename}` | Supprimer une capture. |
| GET | `/files` et `/files/{filename}` | Lister ou lire les fichiers du stockage. |

Exemple de création d’extraits :

```json
{"clips": [{"start": "00:05", "end": "00:10"}]}
```

La suppression d’une vidéo ou d’un extrait ne supprime pas les fichiers audio et captures déjà extraits : ils restent dans `storage/`.

## Tests et qualité

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Les tests d’intégration média nécessitent FFmpeg et FFprobe. Sans les exécutables nécessaires, certains tests sont ignorés.
