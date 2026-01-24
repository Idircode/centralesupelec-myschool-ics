# MySchool → Google Calendar (Music Rooms)

Ce repo génère des fichiers `.ics` pour des salles de musique MySchool CentraleSupélec, et les publie via GitHub Pages.
Google Calendar peut ensuite "s'abonner" à l'URL du `.ics`.

## 1) Configurer les salles
Éditer `rooms.yaml` :
- ajouter les rooms (id, slug, name)
- choisir la fenêtre de synchro (`horizon_days`, `lookback_days`)

## 2) Générer en local
```bash
pip install -r requirements.txt
python generate.py
