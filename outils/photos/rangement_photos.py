"""La page Ranger les photos range les photos et vidéos d'un dossier dans un sous-dossier par ANNÉE (2019, 2020...).

Attention : la bibliothèque Pillow lit l'EXIF des photos JPEG et PNG, mais PAS celui des vidéos
(.mp4, .mov) ni des photos .heic (le format des iPhone). Ces fichiers n'ont donc une date que
par leur nom (WhatsApp) ou, si tu l'actives, par leur date de modification.

Le déplacement et l'annulation sont ceux de "Ranger un dossier" (outils/gagner_de_la_place/
rangement.py) : jamais d'écrasement, revérification au moment de déplacer, annulation possible.
"""
import re
from datetime import datetime
from pathlib import Path

from PIL import Image                        # lit les images et leurs informations EXIF (Pillow)

from outils.gagner_de_la_place import rangement      # raison_de_laisser, nom_libre


EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".heic"}

EXTENSIONS_SANS_EXIF = {".mp4", ".mov", ".heic"}

SANS_DATE = "Autre"               
ANNEE_MIN = 1990                   

# Les deux façons dont WhatsApp écrit la date dans le nom d'un fichier.
#   \d{4} = exactement 4 chiffres (l'année)   \d{2} = exactement 2 chiffres   ( ) = "retiens ce morceau"
MOTIFS_WHATSAPP = [
    re.compile(r"-(\d{4})(\d{2})(\d{2})-WA\d+"),                      
    re.compile(r"WhatsApp (?:Image|Video) (\d{4})-(\d{2})-(\d{2})"),  
]


EXIF, WHATSAPP, FICHIER, AUCUNE = "EXIF", "nom WhatsApp", "date du fichier", "aucune date"


def date_plausible(date):
    """Vrai si l'année est crédible (entre 1990 et l'année prochaine)."""
    return date is not None and ANNEE_MIN <= date.year <= datetime.now().year + 1


def date_prise_de_vue(chemin):
    """Date de prise de vue lue dans l'EXIF, ou None."""
    try:
        with Image.open(chemin) as image:           # "with" referme l'image tout seul à la fin
            exif = image.getexif()                  # les métadonnées de la photo
            # 36867 = date de prise de vue ; 306 = date de modification EXIF (secours)
            date = exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if date:
                return datetime.strptime(str(date).strip(), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass            # vidéo, image abîmée, date mal formée... : on continue sans date
    return None


def date_whatsapp(nom):
    """Date écrite dans un nom de fichier WhatsApp, ou None."""
    for motif in MOTIFS_WHATSAPP:
        trouve = motif.search(nom)
        if trouve:
            annee, mois, jour = (int(x) for x in trouve.groups())
            try:
                return datetime(annee, mois, jour)
            except ValueError:
                return None     # date impossible (par exemple mois 13)
    return None


def date_du_fichier(informations):
    """La date de dernière modification du fichier, ou None."""
    try:
        return datetime.fromtimestamp(informations.st_mtime)
    except (OSError, OverflowError, ValueError):
        return None


def trouver_date(chemin, informations, utiliser_date_fichier):
    """Renvoie (date, source). La source dit d'où vient la date : EXIF, nom WhatsApp, date du fichier,
    ou "aucune date". Une date dont l'année n'est pas plausible est ignorée."""
    # L'EXIF n'est tenté que pour les photos : Pillow ne lit pas les vidéos ni les .heic.
    if chemin.suffix.lower() not in EXTENSIONS_SANS_EXIF:
        date = date_prise_de_vue(chemin)
        if date_plausible(date):
            return date, EXIF
    date = date_whatsapp(chemin.name)
    if date_plausible(date):
        return date, WHATSAPP
    if utiliser_date_fichier:
        date = date_du_fichier(informations)
        if date_plausible(date):
            return date, FICHIER
    return None, AUCUNE


def chercher(dossier, utiliser_date_fichier, arret, progression=None):
    """Prépare le rangement par année SANS rien déplacer.

    utiliser_date_fichier : True = à défaut d'autre date, on prend la date de modification du fichier
    arret                 : un threading.Event ; quand il est "allumé", on s'arrête proprement
    progression           : une fonction appelée avec le nombre de fichiers lus (facultatif)

    Renvoie le même dictionnaire que rangement.chercher, avec en plus :
      "sources"      : combien de fichiers pour chaque source de date
      "sans_date_illisible" : combien de vidéos / .heic sont restés sans date
      "autres"       : combien de fichiers ne sont pas des photos ou vidéos (ils ne sont pas touchés)
    Chaque élément à ranger a aussi "date" (datetime ou None) et "source_date"."""
    dossier = Path(dossier)
    resultats = {"deplacements": [], "laisses": [], "sous_dossiers": 0, "interrompu": False,
                 "sources": {EXIF: 0, WHATSAPP: 0, FICHIER: 0, AUCUNE: 0},
                 "sans_date_illisible": 0, "autres": 0}
    lus = 0
    for chemin in sorted(dossier.iterdir(), key=lambda c: c.name.lower()):
        if arret.is_set():
            resultats["interrompu"] = True
            break
        if chemin.is_dir() and not chemin.is_symlink():
            resultats["sous_dossiers"] += 1
            continue
        if chemin.suffix.lower() not in EXTENSIONS:
            resultats["autres"] += 1             # ni photo ni vidéo : on n'y touche pas
            continue
        try:
            informations = chemin.lstat()
        except OSError:
            resultats["laisses"].append((chemin.name, "illisible"))
            continue
        raison = rangement.raison_de_laisser(chemin, informations)
        if raison is None and not chemin.is_file():
            raison = "ni fichier ni dossier"
        if raison is not None:
            resultats["laisses"].append((chemin.name, raison))
            continue

        date, source = trouver_date(chemin, informations, utiliser_date_fichier)
        resultats["sources"][source] += 1
        if date is None and chemin.suffix.lower() in EXTENSIONS_SANS_EXIF:
            resultats["sans_date_illisible"] += 1
        sous_dossier = str(date.year) if date else SANS_DATE
        if (dossier / sous_dossier).exists() and not (dossier / sous_dossier).is_dir():
            resultats["laisses"].append((chemin.name, f"un fichier s'appelle déjà « {sous_dossier} »"))
            continue
        resultats["deplacements"].append({
            "source": chemin, "categorie": sous_dossier, "taille": informations.st_size,
            "cible": rangement.nom_libre(dossier / sous_dossier / chemin.name), "etat": "",
            "date": date, "source_date": source})
        lus += 1
        if progression and lus % 25 == 0:
            progression(lus)
    return resultats