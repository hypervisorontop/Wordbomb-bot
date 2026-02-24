# WordBot by Hypervisor

Bot OCR rapide pour l'activite Discord Word Bomb (FR) avec interface `CustomTkinter`, mode ranked, vitesse reglable en temps reel et saisie automatique.

## Fonctionnalites

- OCR du prompt (lettres/fragment) en francais avec `EasyOCR`
- Dictionnaire **francais uniquement** (filtrage anti-mots anglais)
- UI `CustomTkinter` compacte (`WordBot by Hypervisor`)
- Slider de vitesse live (`1` a `250` ms/char) sans relancer
- Mode turbo (tres rapide) par defaut
- Bouton `Ranked Mode` (decale la zone OCR vers la droite)
- Option `Require "YOUR TURN" text`
- Option `Keep window on top`
- Filtre de prenoms/mots bloques (`blocked_names.txt`)
- Ajout de mots custom (`extra_words.txt`)
- Hotkeys : `F8` start/stop, `F9` quit

## Fichiers

- `wordbomb_bot.py` : script principal
- `requirements.txt` : dependances Python
- `blocked_names.txt` : mots/prenoms a bloquer (1 mot par ligne)
- `extra_words.txt` : mots custom a ajouter (1 mot par ligne)

## Installation

Prerequis :

- Windows
- Python 3.10+ (teste en Python 3.11)

Installer les dependances :

```powershell
py -m pip install -r requirements.txt
```

Note :

- Au premier lancement, `EasyOCR` telecharge ses modeles (quelques minutes selon la connexion).

## Lancement

```powershell
py wordbomb_bot.py
```

## Utilisation

1. Ouvre Word Bomb dans Discord.
2. Clique le champ du jeu (important pour que la saisie parte au bon endroit).
3. Lance le bot avec le bouton `Start` ou `F8`.
4. Regle la vitesse avec le slider (live).
5. Active `Ranked Mode` si le prompt est decale vers la droite (mode ranked).
6. Quitte avec `F9`.

## Reglages utiles

### Vitesse

- `1 ms/char` = mode ultra rapide
- Tu peux monter jusqu'a `250 ms/char` pour paraitre plus humain

### Ranked Mode

- Active `Ranked Mode` si le bot ne lit plus le prompt en ranked
- Le bot recalcule la zone OCR sans redemarrage

### Dictionnaire FR

- Le bot utilise un dictionnaire francais avec filtrage FR-only
- Si un mot manque, ajoute-le dans `extra_words.txt`

### Blocage de mots/prenoms

- Ajoute des mots dans `blocked_names.txt` (1 par ligne)

## Depannage

### Le bot trouve un mot mais n'ecrit pas

- Clique a nouveau dans le jeu (focus)
- Evite de toucher l'UI pendant le tour (slider/boutons = focus UI)
- Lance Discord et le script avec le meme niveau de privileges (les deux normaux, ou les deux admin)

### Le bot ne lit pas le prompt

- Active/desactive `Ranked Mode`
- Active `Require "YOUR TURN" text` uniquement si ton layout affiche vraiment ce texte

## Dependances

Le projet utilise :

- `mss`
- `pillow`
- `easyocr`
- `wordfreq`
- `keyboard`
- `numpy`
- `customtkinter`

## Disclaimer

Utilise ce script a tes risques et en respectant les regles de ton serveur / plateforme.

