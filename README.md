# MySchool → Google Calendar (Music Rooms)

Ce repo génère des fichiers `.ics` pour des salles de musique MySchool CentraleSupélec, et les publie via GitHub Pages.
Google Calendar peut ensuite "s'abonner" à l'URL du `.ics`.

## 0) Structure du repo 

myschool-music-rooms-ics/
├─ README.md
├─ requirements.txt
├─ rooms.yaml
├─ generate.py
├─ calendars/              # fichiers .ics générés (committés)
│  ├─ ALL.ics
│  ├─ e090.ics
│  └─ ...
└─ .github/
   └─ workflows/
      └─ update.yml

## 1) Configurer les salles
Éditer `rooms.yaml` :
- ajouter les rooms (id, slug, name)
- choisir la fenêtre de synchro (`horizon_days`, `lookback_days`)

## 2) Générer en local
```bash
pip install -r requirements.txt
python generate.py
