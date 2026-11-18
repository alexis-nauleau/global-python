"""La LOGIQUE des caches : analyser un dossier, vérifier qu'on a le droit de supprimer, vider.

Ce fichier ne dessine AUCUNE fenêtre (pas de tkinter) : il ne fait que des calculs et des
suppressions. C'est app.py qui s'occupe de l'affichage et qui appelle les fonctions d'ici.
Avantage : on pourrait changer toute l'interface sans toucher à ce fichier.
"""
import os                           # parcourir les dossiers rapidement, variables d'environnement
import shutil                       # supprimer des dossiers
from pathlib import Path            # manipuler des chemins de dossiers et de fichiers

# ------------------------------------------------------------
#  RÉGLAGES
# ------------------------------------------------------------

# Le dossier "AppData\Local" de ton compte Windows.
# os.environ.get(...) lit une variable de Windows ; si elle n'existe pas, on prend la valeur de secours.
LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

# Les noms de dossiers considérés comme des CACHES (reconstruits tout seuls par les applications).
NOMS_CACHE = {"cache", "code cache", "gpucache", "dawncache", "grshadercache",
              "shadercache", "d3dscache", "npm-cache", "crashdumps"}

# Les noms de dossiers JETABLES : on peut les reconstruire (npm install, pip install...).
NOMS_JETABLES = {"__pycache__", "node_modules", ".venv", "target", ".next", "dist"}

SEUIL = 1024 * 1024              # on n'affiche pas les dossiers de moins de 1 Mo
SEUIL_PARTIEL = 1024 * 1024      # s'il reste plus de 1 Mo après nettoyage : "partiel"

# Les textes affichés dans l'interface.
TYPES = {"cache": "Cache", "jetable": "Reconstructible", "temp": "Temporaire"}
CONSEQUENCES = {
    "cache": "Les caches sont reconstruits automatiquement par les applications.",
    "jetable": "Les dossiers reconstructibles (node_modules, .venv...) devront être recréés "
               "(npm install, pip install -r requirements.txt...).\n"
               "Le projet ne fonctionnera plus tant que tu ne l'auras pas reconstruit.",
    "temp": "Fichiers temporaires. Ceux utilisés par un programme seront ignorés.",
}


def dossiers_proteges():
    """Les dossiers où l'on NE PROPOSE JAMAIS de supprimer quoi que ce soit.
    Leur taille est comptée dans l'analyse, mais rien de ce qu'ils contiennent n'est proposé :
    supprimer un node_modules dans 'Program Files' casserait un programme installé."""
    return [
        Path(os.environ.get("SystemRoot", r"C:\Windows")),                  # Windows lui-même
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("ProgramData", r"C:\ProgramData")),
        LOCAL / "Programs",                                                 # applications installées
        LOCAL / "Packages",                                                 # applications du Store
        LOCAL / "Temp",                                                     # géré à part (voir analyser)
    ]


# ------------------------------------------------------------
#  OUTILS DE BASE
# ------------------------------------------------------------

def lisible(octets):
    """Transforme 1536000 en '1.5 Mo'."""
    for unite in ("o", "Ko", "Mo"):
        if octets < 1024:
            return f"{octets:.1f} {unite}"
        octets /= 1024         # /= 1024 veut dire "divise par 1024" : on passe à l'unité du dessus
    return f"{octets:.1f} Go"


def taille_dossier(chemin):
    """Additionne la taille de tous les fichiers d'un dossier, en octets."""
    total = 0
    for racine, _dossiers, fichiers in os.walk(chemin):
        for nom in fichiers:
            try:
                total += os.path.getsize(os.path.join(racine, nom))
            except OSError:
                pass  # fichier verrouillé ou disparu : on l'ignore
    return total


# ------------------------------------------------------------
#  L'ANALYSE
# ------------------------------------------------------------

def scanner(chemin, profondeur, ctx, dans_trouve=False):
    """Parcourt 'chemin' et renvoie sa taille totale en octets.

    'ctx' est un dictionnaire qui sert de "carnet de notes" partagé (voir analyser) :
    on y range ce qu'on trouve, et on y lit l'interrupteur d'arrêt.
    'dans_trouve' vaut True quand on est DÉJÀ dans un dossier repéré ou protégé :
    on n'y cherche plus rien de nouveau (on compte seulement la taille)."""
    total = 0        # la taille cumulée de ce dossier
    try:
        with os.scandir(chemin) as entrees:
            for entree in entrees:
                if ctx["arret"].is_set():              # on a cliqué sur "Arrêter" : on rend ce qu'on a
                    return total
                try:
                    if entree.is_symlink() or entree.is_junction():
                        continue                       # évite les boucles et les doublons
                    if entree.is_file(follow_symlinks=False):
                        total += entree.stat(follow_symlinks=False).st_size
                    elif entree.is_dir(follow_symlinks=False):
                        chemin_minuscules = entree.path.lower()     # minuscules : comparer sans souci
                        if chemin_minuscules in ctx["ignores"]:
                            continue
                        categorie = None               # None = "rien" : on ne sait pas encore ce que c'est
                        if not dans_trouve:
                            nom = entree.name.lower()
                            if nom in NOMS_CACHE:
                                categorie = "cache"
                            elif nom in NOMS_JETABLES:
                                categorie = "jetable"

                        # On compte les dossiers parcourus, pour montrer que ça avance.
                        ctx["compteur"] += 1
                        # % est le "reste de la division" : vrai tous les 2000 dossiers.
                        if ctx["compteur"] % 2000 == 0 and ctx["progression"]:
                            ctx["progression"](ctx["compteur"])

                        # Dans un dossier repéré ou protégé, on ne cherche plus de nouvelles catégories.
                        interdit = (dans_trouve or categorie is not None
                                    or chemin_minuscules in ctx["proteges"])
                        # LA RÉCURSIVITÉ : la fonction s'appelle elle-même pour ce sous-dossier.
                        taille = scanner(entree.path, profondeur + 1, ctx, interdit)
                        total += taille

                        if ctx["arret"].is_set():
                            return total               # taille incomplète : on ne la note pas
                        if categorie:
                            ctx[categorie].append((entree.path, taille))
                        if profondeur in (1, 2):
                            ctx[profondeur].append((entree.path, taille))
                except OSError:
                    pass                               # fichier ou dossier inaccessible : on passe
    except OSError:
        pass                                           # dossier illisible (droits) : on passe
    return total


def analyser(racine, arret, progression=None):
    """Analyse le dossier 'racine'. Ne supprime RIEN.

    arret       : un threading.Event ; quand il est "allumé", l'analyse s'arrête proprement.
    progression : une fonction facultative, appelée avec le nombre de dossiers parcourus.

    Renvoie un dictionnaire :
      "temp", "cache", "jetable" : listes de (chemin, taille) proposées à la suppression
      1, 2                       : les dossiers de niveau 1 et 2 (pour voir ce qui est gros)
      "compteur"                 : nombre de dossiers parcourus
      "interrompu"               : True si l'analyse a été arrêtée (résultats partiels)"""
    racine = Path(racine)
    proteges = dossiers_proteges()

    ctx = {
        "cache": [], "jetable": [], 1: [], 2: [], "compteur": 0,
        "arret": arret, "progression": progression,
        # Windows n'est jamais analysé (très long, et rien à y supprimer).
        "ignores": {str(proteges[0]).lower()},
        "proteges": {str(p).lower() for p in proteges},
    }
    scanner(str(racine), 1, ctx)

    # Le dossier Temp est proposé à part, s'il se trouve dans le dossier analysé.
    temp = []
    dossier_temp = LOCAL / "Temp"
    if not arret.is_set() and dossier_temp.is_dir():
        temp_resolu = dossier_temp.resolve()
        if racine.resolve() == temp_resolu or racine.resolve() in temp_resolu.parents:
            temp.append((str(dossier_temp), taille_dossier(dossier_temp)))

    return {
        "temp": temp,
        # On ne garde que les dossiers d'au moins 1 Mo.
        "cache": [(c, t) for c, t in ctx["cache"] if t >= SEUIL],
        "jetable": [(c, t) for c, t in ctx["jetable"] if t >= SEUIL],
        1: ctx[1], 2: ctx[2],
        "compteur": ctx["compteur"],
        "interrompu": arret.is_set(),
    }


# ------------------------------------------------------------
#  LA SUPPRESSION
# ------------------------------------------------------------

def chemin_supprimable(chemin, categorie, racine):
    """Garde-fou appliqué AU MOMENT de supprimer (même si l'analyse s'est trompée).
    Renvoie True seulement si TOUTES ces conditions sont vraies :
      - ce n'est pas un raccourci de dossier ;
      - son nom est bien celui d'un cache (ou d'un dossier jetable, selon sa catégorie) ;
      - il se trouve dans le dossier qui a été analysé ;
      - il n'est dans aucun dossier protégé (Windows, Program Files...)."""
    chemin = Path(chemin)
    try:
        if chemin.is_symlink() or chemin.is_junction():
            return False
        resolu = chemin.resolve()                     # le vrai chemin, sans détour
        if categorie == "temp":
            return resolu == (LOCAL / "Temp").resolve()
        if categorie == "cache":
            noms = NOMS_CACHE
        elif categorie == "jetable":
            noms = NOMS_JETABLES
        else:
            return False
        if resolu.name.lower() not in noms:
            return False
        if Path(racine).resolve() not in resolu.parents:    # .parents = tous les dossiers au-dessus
            return False
        for protege in dossiers_proteges():
            protege = protege.resolve()
            if protege == resolu or protege in resolu.parents:
                return False
    except OSError:
        return False
    return True       # toutes les vérifications sont passées


def vider_dossier(chemin):
    """Supprime tout ce qui est DANS le dossier. Ignore ce qui est utilisé par un programme."""
    try:
        elements = list(chemin.iterdir())             # list(...) transforme le contenu en liste
    except OSError:
        return                                        # dossier illisible : on arrête là
    for element in elements:
        try:
            if element.is_symlink() or element.is_junction():
                continue                              # on ne touche jamais aux raccourcis de dossier
            if element.is_dir():
                shutil.rmtree(element, ignore_errors=True)
            else:
                element.unlink()                      # unlink() supprime un fichier
        except OSError:
            pass