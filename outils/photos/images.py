"""La LOGIQUE de la page "Optimiser les images" (SANS aucune fenêtre).

Ce fichier choisit le dossier de sortie, traite les photos une par une et fabrique le bilan.
Le travail sur UNE image (redimensionner, convertir en WebP ou en JPEG) est fait par les
fonctions de optimiser_images.py ; les dimensions des réseaux sociaux sont dans formats.py.
La page (page_images.py) ne fait qu'afficher ce que renvoient ces fonctions.
"""
from pathlib import Path

from outils.photos.optimiser_images import (EXTENSIONS, destination_libre, lisible,
                                            optimiser_en_memoire, preparer_pour_reseau)


def filtrer_images(chemins):
    """Garde seulement les images (jpg, jpeg, png), triées par nom."""
    photos = [Path(chemin) for chemin in chemins]
    return sorted(photo for photo in photos if photo.suffix.lower() in EXTENSIONS)


def dossier_sortie(photos, mode):
    """Le dossier où seront écrites les images optimisées : un nouveau dossier À CÔTÉ de celui
    des photos, jamais dedans. Exemple : D:\\Vacances -> D:\\Vacances_webp (ou _reseau)."""
    source = photos[0].parent
    suffixe = "_webp" if mode == "reduire" else "_reseau"
    return source.parent / (source.name + suffixe)


def traiter(photos, mode, largeur, qualite, taille, sortie, ecrire, arret, a_chaque_image):
    """Traite les photos une par une.

    mode           : "reduire" (WebP, largeur max) ou "reseau" (JPEG, taille exacte)
    largeur        : la largeur max en pixels (mode "reduire")
    taille         : (largeur, hauteur) du réseau (mode "reseau")
    ecrire         : False = SIMULATION (on calcule les tailles, on n'écrit rien) ; True = on écrit
    arret          : un threading.Event ; quand il est "allumé", on s'arrête proprement
    a_chaque_image : une fonction appelée après chaque photo avec
                     (numero, total, nom, avant, apres, gain, etiquette)

    Renvoie le bilan : un dictionnaire de compteurs (voir plus bas)."""
    sortie = Path(sortie)
    # Sécurité : on n'écrit JAMAIS dans le dossier des originaux.
    if sortie.resolve() == photos[0].parent.resolve():
        raise ValueError("Le dossier de sortie doit être différent du dossier des photos.")

    bilan = {"traitees": 0, "ignorees": 0, "erreurs": 0, "ecrites": 0,
             "total_avant": 0, "total_apres": 0, "interrompu": False}
    total = len(photos)

    for numero, chemin in enumerate(photos, start=1):
        if arret.is_set():                         # on a cliqué sur "Arrêter"
            bilan["interrompu"] = True
            break
        try:
            avant = chemin.stat().st_size          # le poids de la photo d'origine
            if mode == "reduire":
                donnees = optimiser_en_memoire(chemin, largeur, qualite)    # l'image WebP, en mémoire
                extension = ".webp"
            else:
                donnees = preparer_pour_reseau(chemin, taille, qualite)     # l'image JPEG, en mémoire
                extension = ".jpg"
            apres = len(donnees)                   # son poids

            if mode == "reduire" and apres >= avant:
                # Le WebP serait plus lourd que l'original : on ne touche pas à cette photo.
                bilan["ignorees"] += 1
                a_chaque_image(numero, total, chemin.name, lisible(avant), "-",
                               "Ignorée (déjà optimisée)", "ignoree")
            else:
                if ecrire:
                    sortie.mkdir(parents=True, exist_ok=True)
                    # destination_libre ajoute un numéro si le fichier existe déjà : jamais d'écrasement.
                    destination = destination_libre(sortie / (chemin.stem + extension))
                    destination.write_bytes(donnees)
                    bilan["ecrites"] += 1
                bilan["traitees"] += 1
                bilan["total_avant"] += avant
                bilan["total_apres"] += apres
                gain = (apres - avant) / avant * 100 if avant else 0
                a_chaque_image(numero, total, chemin.name, lisible(avant), lisible(apres),
                               f"{gain:+.0f} %", "")
        except Exception as erreur:                # une photo illisible ne doit pas tout arrêter
            bilan["erreurs"] += 1
            a_chaque_image(numero, total, chemin.name, "-", "-", f"Erreur : {erreur}", "erreur")
    return bilan


def resume(bilan, ecrire):
    """La phrase de bilan affichée sous le tableau."""
    if bilan["traitees"]:
        gain = ((bilan["total_apres"] - bilan["total_avant"]) / bilan["total_avant"] * 100
                if bilan["total_avant"] else 0)
        texte = (f"{bilan['traitees']} image(s) : {lisible(bilan['total_avant'])} → "
                 f"{lisible(bilan['total_apres'])} ({gain:+.0f} %)")
    else:
        texte = "Aucune image traitée"
    if bilan["ignorees"]:
        texte += f" · {bilan['ignorees']} ignorée(s)"
    if bilan["erreurs"]:
        texte += f" · {bilan['erreurs']} erreur(s)"
    if bilan["interrompu"]:
        texte += " · INTERROMPU"
    if not ecrire:
        texte = "SIMULATION, rien n'a été écrit. " + texte
    return texte