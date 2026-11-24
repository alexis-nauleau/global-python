""" la page Ranger un dossier range les fichiers d'un dossier dans des sous-dossiers selon leur EXTENSION


Les garde-fous (ce que cette logique REFUSE de faire) :
  - ranger un disque entier, un dossier système, ton dossier personnel ou un dossier de projet ;
  - déplacer un fichier caché, un fichier système ou un téléchargement en cours ;
  - écraser un fichier : si le nom existe déjà à l'arrivée, on ajoute (1), (2)...
Chaque déplacement peut être ANNULÉ (voir annuler).
"""
import os
import shutil
from pathlib import Path

from outils.gagner_de_la_place.caches import lisible      # "1536000" -> "1.5 Mo"


CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Documents": {".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".md"},
    "Archives": {".zip", ".rar", ".7z"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json"},
    "Installateurs": {".exe", ".msi"},
}
AUTRES = "Autres"    


EXTENSIONS_EN_COURS = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}
NOMS_SYSTEME = {"desktop.ini", "thumbs.db", ".ds_store"}


MARQUEURS_PROJET = {".git", "package.json", "pyproject.toml", "setup.py", "requirements.txt"}

FILE_ATTRIBUTE_HIDDEN = 0x2       # l'attribut "caché" de Windows


def dossier_interdit(dossier):
    """Renvoie la RAISON pour laquelle on refuse de ranger ce dossier, ou None s'il est permis."""
    dossier = Path(dossier).resolve()
    if dossier.parent == dossier:
        return "C'est la racine d'un disque : range plutôt un dossier précis."
    # Les dossiers de Windows et des programmes (les variables n'existent que sous Windows).
    for variable in ("WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"):
        valeur = os.environ.get(variable)
        if valeur and (dossier == Path(valeur).resolve() or Path(valeur).resolve() in dossier.parents):
            return "C'est un dossier système ou de programmes."
    if dossier == Path.home().resolve():
        return "C'est ton dossier personnel : choisis un sous-dossier (Téléchargements, Bureau...)."
    try:
        presents = {element.name.lower() for element in dossier.iterdir()}
    except OSError as erreur:
        return f"Ce dossier n'est pas lisible ({erreur})."
    trouves = sorted(MARQUEURS_PROJET & presents)
    if trouves:
        return ("Ce dossier ressemble à un PROJET (il contient " + ", ".join(trouves) + ") : "
                "le ranger casserait son code.")
    return None


def categorie(fichier, inconnus=True):
    """Le nom du sous-dossier pour ce fichier. Si l'extension est inconnue : "Autres",
    ou None si inconnus=False (le fichier reste alors en place)."""
    extension = fichier.suffix.lower()           # ".PDF" -> ".pdf" : "photo.JPG" et "photo.jpg" sont traités pareil
    for nom, extensions in CATEGORIES.items():
        if extension in extensions:
            return nom
    return AUTRES if inconnus else None


def nom_libre(destination):
    """Si le fichier existe déjà, ajoute (1), (2)... plutôt que d'écraser."""
    if not destination.exists() and not destination.is_symlink():
        return destination
    numero = 1
    while True:
        essai = destination.with_name(f"{destination.stem} ({numero}){destination.suffix}")
        if not essai.exists() and not essai.is_symlink():
            return essai
        numero += 1


def raison_de_laisser(fichier, informations):
    """Pourquoi on ne touche PAS à ce fichier (ou None s'il peut être rangé)."""
    if fichier.is_symlink():
        return "lien"
    if fichier.name.startswith("."):
        return "fichier caché"
    if getattr(informations, "st_file_attributes", 0) & FILE_ATTRIBUTE_HIDDEN:
        return "fichier caché"
    if fichier.name.lower() in NOMS_SYSTEME:
        return "fichier système"
    if fichier.suffix.lower() in EXTENSIONS_EN_COURS:
        return "téléchargement en cours ?"
    return None


def chercher(dossier, inconnus, arret):
    """Prépare le rangement SANS rien déplacer.

    inconnus : True = les fichiers inconnus vont dans "Autres" ; False = ils restent en place
    arret    : un threading.Event ; quand il est "allumé", on s'arrête proprement

    Renvoie un dictionnaire :
      "deplacements" : la liste des fichiers à ranger (chaque élément : source, cible, categorie, taille, etat)
      "laisses"      : la liste des (nom, raison) des fichiers qu'on ne touche pas
      "sous_dossiers": combien de sous-dossiers sont ignorés
      "interrompu"   : True si tu as cliqué sur "Arrêter" """
    dossier = Path(dossier)
    resultats = {"deplacements": [], "laisses": [], "sous_dossiers": 0, "interrompu": False}
    for chemin in sorted(dossier.iterdir(), key=lambda c: c.name.lower()):
        if arret.is_set():
            resultats["interrompu"] = True
            break
        if chemin.is_dir() and not chemin.is_symlink():
            resultats["sous_dossiers"] += 1
            continue
        try:
            informations = chemin.lstat()
        except OSError:
            resultats["laisses"].append((chemin.name, "illisible"))
            continue
        raison = raison_de_laisser(chemin, informations)
        if raison is None and not chemin.is_file():
            raison = "ni fichier ni dossier"
        if raison is None:
            sous_dossier = categorie(chemin, inconnus)
            if sous_dossier is None:
                raison = "type inconnu, laissé en place"
            elif (dossier / sous_dossier).exists() and not (dossier / sous_dossier).is_dir():
                raison = f"un fichier s'appelle déjà « {sous_dossier} »"
        if raison is not None:
            resultats["laisses"].append((chemin.name, raison))
            continue
        resultats["deplacements"].append({
            "source": chemin, "categorie": sous_dossier, "taille": informations.st_size,
            "cible": nom_libre(dossier / sous_dossier / chemin.name), "etat": ""})
    return resultats


def deplacer(element):
    """Déplace UN fichier, après avoir revérifié que rien n'a changé depuis la recherche.
    Renvoie (cible réelle, dossier_cree) si c'est fait, ou None si le fichier est refusé.
    Le garde-fou est ICI, au moment de déplacer : le dossier a pu changer entre-temps."""
    source = element["source"]
    if source.is_symlink() or not source.is_file():
        return None                                  # le fichier a disparu ou a changé de nature
    sous_dossier = source.parent / element["categorie"]
    cree = False
    if sous_dossier.exists():
        if not sous_dossier.is_dir():
            return None                              # un fichier porte le nom du sous-dossier
    else:
        sous_dossier.mkdir()
        cree = True
    cible = nom_libre(sous_dossier / source.name)   # on recalcule : un fichier a pu apparaître à l'arrivée
    try:
        shutil.move(str(source), str(cible))
    except OSError:
        if cree:
            try:
                sous_dossier.rmdir()                 # on ne laisse pas un dossier vide créé pour rien
            except OSError:
                pass
        return None
    return cible, cree


def annuler(origine, cible, dossier_cree):
    """Remet UN fichier à sa place d'origine. Renvoie True si c'est fait.
    Refuse si le fichier n'est plus là, ou si l'emplacement d'origine est déjà pris
    (on n'écrase jamais). Si on avait créé le sous-dossier et qu'il est maintenant vide, on le retire."""
    if cible.is_symlink() or not cible.is_file() or origine.exists() or origine.is_symlink():
        return False
    try:
        shutil.move(str(cible), str(origine))
    except OSError:
        return False
    if dossier_cree:
        try:
            cible.parent.rmdir()                     # rmdir échoue si le dossier n'est pas vide : sans danger
        except OSError:
            pass
    return True