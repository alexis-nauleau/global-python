"""
Un fichier est un doublon CONFIRMÉ seulement si DEUX conditions sont vraies :
  1. son nom finit par (1), (2) ou (3), et le fichier d'origine existe dans le même dossier
     (photo (1).jpg  ->  photo.jpg) ;
  2. son contenu est IDENTIQUE à celui de l'original (comparé octet par octet).


Les doublons confirmés vont à la CORBEILLE (récupérables), 
"""
import filecmp
import os
import re
from pathlib import Path

from outils.gagner_de_la_place.caches import lisible      # "1536000" -> "1.5 Mo"

#   (?P<base>.*?) : le début du nom, c'est le nom de l'original ("photo" pour "photo (1)")
#   \s?           : un espace facultatif
#   \([1-3]\)$    : (1), (2) ou (3) tout à la fin
MOTIF = re.compile(r"^(?P<base>.*?)\s?\([1-3]\)$")


DOSSIERS_IGNORES = {".git", "node_modules", "$RECYCLE.BIN", "System Volume Information"}


STATUTS = {
    "doublon": "Doublon confirmé",
    "sans_original": "Original introuvable",
    "different": "Contenu différent",
    "erreur": "Illisible",
}


def corbeille_disponible():
    """Vrai si la bibliothèque send2trash est installée (pip install send2trash)."""
    try:
        import send2trash                                  # noqa: F401  (on teste juste sa présence)
        return True
    except ImportError:
        return False


def mettre_a_la_corbeille(chemin):
    """Envoie le fichier à la corbeille Windows (récupérable)."""
    from send2trash import send2trash
    send2trash(str(chemin))


def trouver_original(chemin):
    """Le chemin du fichier d'origine : photo (1).jpg -> photo.jpg, dans le même dossier.
    Renvoie None si le nom n'a pas de partie "origine" (par exemple un fichier nommé "(1).txt")."""
    reconnu = MOTIF.match(chemin.stem)
    if reconnu is None or not reconnu.group("base"):
        return None
    return chemin.with_name(reconnu.group("base") + chemin.suffix)


def original_valide(original):
    """L'original doit être un vrai fichier (pas un dossier, pas un lien)."""
    return original is not None and original.is_file() and not original.is_symlink()


def comparer(chemin, original):
    """Compare un fichier à son original. Renvoie un statut : "doublon", "sans_original",
    "different" ou "erreur"."""
    if not original_valide(original):
        return "sans_original"
    try:
        # shallow=False : on compare le CONTENU octet par octet (pas seulement la date et la taille).
        return "doublon" if filecmp.cmp(chemin, original, shallow=False) else "different"
    except OSError:
        return "erreur"


def verifier_avant_corbeille(chemin, original):
    """Le garde-fou, appelé JUSTE AVANT de supprimer (le dossier a pu changer depuis la
    recherche). Renvoie True seulement si c'est encore un vrai doublon."""
    if chemin.is_symlink() or not chemin.is_file() or not original_valide(original):
        return False
    filecmp.clear_cache()                  # on oublie les comparaisons mémorisées : on refait la vérification
    try:
        return filecmp.cmp(chemin, original, shallow=False)
    except OSError:
        return False


def analyser(racine, arret, progression=None):
    """Parcourt 'racine' et classe les fichiers dont le nom finit par (1), (2) ou (3).

    arret       : un threading.Event ; quand il est "allumé", on s'arrête proprement
    progression : une fonction appelée avec le nombre de fichiers parcourus (facultatif)

    Renvoie un dictionnaire :
      "doublons"   : la liste des doublons CONFIRMÉS (supprimables)
      "a_verifier" : la liste des autres (jamais supprimés)
      "compteur"   : combien de fichiers ont été parcourus
      "interrompu" : True si tu as cliqué sur "Arrêter"
    Chaque élément est un dictionnaire : chemin, original, taille, statut."""
    resultats = {"doublons": [], "a_verifier": [], "compteur": 0, "interrompu": False}
    est_jonction = getattr(os.path, "isjunction", lambda chemin: False)    # Python 3.12 et plus

    # os.walk parcourt le dossier et ses sous-dossiers. followlinks=False : on ne suit pas les liens.
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        if arret.is_set():
            resultats["interrompu"] = True
            break
        # On retire de la liste les dossiers à ignorer et les jonctions : os.walk n'y entrera pas.
        sous_dossiers[:] = [nom for nom in sous_dossiers
                            if nom not in DOSSIERS_IGNORES
                            and not est_jonction(os.path.join(dossier, nom))]
        for nom in fichiers:
            resultats["compteur"] += 1
            if progression and resultats["compteur"] % 200 == 0:
                progression(resultats["compteur"])
            chemin = Path(dossier) / nom
            if MOTIF.match(chemin.stem) is None or chemin.is_symlink():
                continue                              # le nom ne ressemble pas à un doublon
            original = trouver_original(chemin)
            statut = comparer(chemin, original)
            try:
                taille = chemin.stat().st_size
            except OSError:
                taille = 0
            element = {"chemin": chemin, "original": original, "taille": taille,
                       "statut": statut, "etat": ""}
            (resultats["doublons"] if statut == "doublon" else resultats["a_verifier"]).append(element)
    return resultats