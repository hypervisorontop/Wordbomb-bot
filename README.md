# 🚀 WordBot by Hypervisor

> Bot OCR rapide pour l'activité **Discord Word Bomb (FR)** avec interface **CustomTkinter**, mode ranked, vitesse réglable en temps réel et saisie automatique.

![Platform](https://img.shields.io/badge/Platform-Windows-0A66FF?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OCR](https://img.shields.io/badge/OCR-EasyOCR-1F2937?style=for-the-badge)
![Language](https://img.shields.io/badge/Dictionary-FR_Only-16A34A?style=for-the-badge)

> [!IMPORTANT]
> Le bot est optimisé pour la **vitesse** (jusqu'à `1 ms/char`) et inclut un **Ranked Mode** pour les layouts où le prompt est décalé vers la droite.

## ✨ Fonctionnalités

- ⚡ OCR du prompt (lettres / fragment) en français via `EasyOCR`
- 🇫🇷 Dictionnaire **français uniquement** (filtrage anti-mots anglais)
- 🎛️ Interface **CustomTkinter** compacte : `WordBot by Hypervisor`
- 🎚️ Slider de vitesse live de **`1` à `250` ms/char** (sans relancer)
- 🏎️ Mode turbo par défaut (ultra rapide)
- 🎯 Bouton **`Ranked Mode`** (décale la zone OCR vers la droite)
- 📌 Option **`Keep window on top`**
- 🔎 Option **`Require "YOUR TURN" text`**
- 🚫 Filtre de prénoms / mots bloqués (`blocked_names.txt`)
- ➕ Ajout de mots custom (`extra_words.txt`)
- ⌨️ Hotkeys : `F8` start/stop, `F9` quit

## 📦 Fichiers du projet

| Fichier | Rôle |
|---|---|
| `wordbomb_bot.py` | Script principal |
| `requirements.txt` | Dépendances Python |
| `blocked_names.txt` | Mots / prénoms à bloquer (1 ligne = 1 mot) |
| `extra_words.txt` | Mots custom à ajouter (1 ligne = 1 mot) |

## 🛠️ Installation

### ✅ Prérequis

- Windows
- Python `3.10+` (testé en `3.11`)

### 📥 Installer les dépendances

```powershell
py -m pip install -r requirements.txt
```

> [!NOTE]
> Au **premier lancement**, `EasyOCR` télécharge ses modèles (cela peut prendre quelques minutes selon ta connexion).

## ▶️ Lancement

```powershell
py wordbomb_bot.py
```

## 🎮 Utilisation (rapide)

1. Ouvre **Word Bomb** dans Discord.
2. Clique le **champ du jeu** (important pour la saisie automatique).
3. Lance le bot avec le bouton **Start** ou `F8`.
4. Régle la vitesse avec le **slider** (en live).
5. Active **Ranked Mode** si le prompt est décalé vers la droite.
6. Quitte avec `F9`.

> [!TIP]
> Si tu touches le slider ou un bouton pendant la partie, **re-clique le jeu** pour rendre le focus à Word Bomb.

## 🧰 Contrôles UI

| Contrôle | Description |
|---|---|
| `Start / Stop` | Active ou met en pause le bot |
| `Minimize` | Réduit la fenêtre |
| `Ranked Mode` | Décale la zone OCR pour le mode ranked |
| `Typing speed` | Vitesse de frappe (live) de `1` à `250` ms/char |
| `Require "YOUR TURN" text` | N'écrit que si le texte est détecté |
| `Keep window on top` | Garde la fenêtre au-dessus |

## ⚙️ Réglages utiles

### ⚡ Vitesse

- `1 ms/char` = vitesse max
- Monte vers `100-250 ms/char` si tu veux un comportement plus humain

### 🏆 Ranked Mode

- Active `Ranked Mode` si le bot ne lit plus le prompt en ranked
- Le bot **recalcule la zone OCR sans redémarrage**

### 🇫🇷 Dictionnaire FR

- Le bot utilise un dictionnaire français avec filtrage FR-only
- Si un mot manque, ajoute-le dans `extra_words.txt`

### 🚫 Blocage de mots / prénoms

- Ajoute des entrées dans `blocked_names.txt` (1 mot par ligne)

## 🩹 Dépannage

### ❌ Le bot trouve un mot mais n'écrit pas

- Clique à nouveau dans le jeu (focus)
- Évite de toucher l'UI pendant le tour (slider/boutons = focus UI)
- Lance Discord et le script avec le **même niveau de privilèges** (les deux normaux ou les deux admin)

### ❌ Le bot ne lit pas le prompt

- Active / désactive `Ranked Mode`
- Active `Require "YOUR TURN" text` uniquement si ton layout affiche vraiment ce texte

> [!TIP]
> En mode ranked, le prompt est souvent un peu plus à droite : utilise le bouton **Ranked Mode**.

## 📚 Dépendances

- `mss`
- `pillow`
- `easyocr`
- `wordfreq`
- `keyboard`
- `numpy`
- `customtkinter`

## ⚠️ Disclaimer

> [!WARNING]
> Utilise ce script à tes risques et en respectant les règles de ton serveur / plateforme.

