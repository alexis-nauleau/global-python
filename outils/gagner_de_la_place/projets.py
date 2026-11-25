# ============================================================
# projets.py : la LOGIQUE de "Nettoyer un projet web" 
# ============================================================
import os                        
import shutil                   
import stat                      
import time
from pathlib import Path

DOSSIER_A_SUPPRIMER = "node_modules"
JOURS_AVANT_DORMANT = 60
FICHIER_PROJET = "package.json"
DOSSIERS_IGNORES = {DOSSIER_A_SUPPRIMER, ".git", ".next", ".nuxt", ".venv", "venv",
                    "dist", "build", "__pycache__", ".turbo", ".cache"}
FICHIERS_LOCK = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")
SECONDES_PAR_JOUR = 86400

# Dossiers qu'on refuse comme point de départ (trop larges ou système).
DOSSIERS_SYSTEME = ("windows", "program files", "program files (x86)", "programdata")


def lisible(octets):
    """4300000 -> '4.1 Mo'"""
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024:
            return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} To"


def dossier_interdit(dossier):
    """Renvoie la RAISON du refus (texte), ou '' si le dossier est accepté."""
    chemin = Path(dossier)
    if chemin.parent == chemin:                       # la racine d'un disque : C:\ n'a pas de parent
        return "C'est la racine d'un disque : choisis le dossier qui contient tes projets."
    morceaux = [m.lower() for m in chemin.parts]
    if any(m in DOSSIERS_SYSTEME for m in morceaux):
        return "C'est un dossier système."
    return ""


def est_lien(chemin):
    """Vrai pour un raccourci (lien symbolique ou "junction" Windows) : on ne les suit JAMAIS."""
    return os.path.islink(chemin) or os.path.isjunction(chemin)


def a_un_lockfile(projet):
    """Un lockfile fige les versions exactes : sans lui, "npm install" peut installer d'autres versions."""
    return any((Path(projet) / nom).is_file() for nom in FICHIERS_LOCK)


def derniere_activite(projet):
    """Renvoie la date (en secondes) du fichier le plus récemment modifié du projet.
    On saute les dossiers de DOSSIERS_IGNORES et les raccourcis."""
    plus_recent = 0.0
    a_visiter = [str(projet)]            # liste de dossiers à explorer
    while a_visiter:
        courant = a_visiter.pop()
        try:
            with os.scandir(courant) as entrees:
                for entree in entrees:
                    if entree.is_dir(follow_symlinks=False):
                        if entree.name not in DOSSIERS_IGNORES and not est_lien(entree.path):
                            a_visiter.append(entree.path)
                    else:
                        plus_recent = max(plus_recent, entree.stat(follow_symlinks=False).st_mtime)
        except OSError:
            pass                          # dossier illisible : on l'ignore
    if plus_recent == 0.0:                # projet sans fichier : on prend la date du dossier
        plus_recent = Path(projet).stat().st_mtime
    return plus_recent


def taille_dossier(dossier):
    """Additionne la taille de tous les fichiers d'un dossier (sans suivre les liens)."""
    total = 0
    a_visiter = [str(dossier)]
    while a_visiter:
        courant = a_visiter.pop()
        try:
            with os.scandir(courant) as entrees:
                for entree in entrees:
                    if entree.is_symlink():
                        continue
                    if entree.is_dir(follow_symlinks=False):
                        a_visiter.append(entree.path)
                    else:
                        total += entree.stat(follow_symlinks=False).st_size
        except OSError:
            pass
    return total


def chercher(racine, jours, arret, progression=None):
    """Cherche les projets dormants SANS rien supprimer. Renvoie un dictionnaire :
      "dormants"  : les projets à nettoyer (avec lockfile), un dictionnaire chacun
      "laisses"   : liste de (nom du projet, raison) : on n'y touche pas
      "analyses"  : combien de projets ont été regardés
      "interrompu": True si tu as cliqué sur "Arrêter"
    'arret' est un threading.Event ; 'progression' est une fonction appelée avec le nombre de projets lus."""
    racine = Path(racine)
    limite = time.time() - jours * SECONDES_PAR_JOUR      # tout ce qui est plus vieux = dormant
    dormants, laisses = [], []
    analyses = 0
    interrompu = False

    for dossier in sorted(racine.iterdir()):
        if arret.is_set():
            interrompu = True
            break
        # Un "projet" = un sous-dossier direct (pas un raccourci) qui contient package.json
        if est_lien(dossier) or not dossier.is_dir() or not (dossier / FICHIER_PROJET).is_file():
            continue
        analyses += 1
        if progression:
            progression(analyses)

        cible = dossier / DOSSIER_A_SUPPRIMER             # ex : F:\Projets\mon-site\node_modules
        if not cible.is_dir() or est_lien(cible):
            continue                                      # rien à libérer ici

        derniere = derniere_activite(dossier)
        if derniere >= limite:
            laisses.append((dossier.name, "Projet encore actif (modifié récemment)"))
            continue
        if not a_un_lockfile(dossier):
            laisses.append((dossier.name, "Pas de lockfile : on ne pourrait pas recréer les mêmes versions"))
            continue

        # La taille est lente à calculer : on ne le fait que pour les projets dormants
        dormants.append({
            "nom": dossier.name,
            "cible": cible,
            "derniere": derniere,
            "jours": int((time.time() - derniere) / SECONDES_PAR_JOUR),
            "taille": taille_dossier(cible),
            "etat": "",
        })
    return {"dormants": dormants, "laisses": laisses, "analyses": analyses, "interrompu": interrompu}


def verifier_avant_suppression(cible, jours):
    """Le garde-fou, revérifié AU MOMENT de supprimer (le dossier a pu changer depuis la recherche).
    Renvoie '' si tout est bon, sinon la raison du refus."""
    cible = Path(cible)
    if cible.name != DOSSIER_A_SUPPRIMER:
        return f"Ce dossier ne s'appelle pas « {DOSSIER_A_SUPPRIMER} »."
    if est_lien(cible):
        return "C'est un raccourci, pas un vrai dossier."
    if not cible.is_dir():
        return "Le dossier n'existe plus."
    projet = cible.parent
    if not (projet / FICHIER_PROJET).is_file():
        return f"Pas de {FICHIER_PROJET} à côté : ce n'est pas un projet web."
    if not a_un_lockfile(projet):
        return "Pas de lockfile dans ce projet."
    if derniere_activite(projet) >= time.time() - jours * SECONDES_PAR_JOUR:
        return "Le projet a été modifié depuis la recherche."
    return ""


def rendre_modifiable(fonction, chemin, _info):
    """Appelée quand la suppression échoue : on rend le fichier modifiable et on réessaie.
    (Beaucoup de fichiers de node_modules sont en lecture seule sous Windows.)"""
    os.chmod(chemin, stat.S_IWRITE)
    fonction(chemin)


def supprimer(cible):
    """Supprime le dossier node_modules d'un projet, et RIEN d'autre. Définitif (pas de corbeille) :
    node_modules se recrée avec "npm install", et la corbeille ne libérerait pas la place."""
    cible = Path(cible)
    if cible.name != DOSSIER_A_SUPPRIMER or est_lien(cible):      # dernier garde-fou
        raise ValueError(f"Refus : ce n'est pas un vrai dossier '{DOSSIER_A_SUPPRIMER}'")
    # Le préfixe \\?\ autorise les chemins de plus de 260 caractères sous Windows
    chemin = "\\\\?\\" + str(cible.resolve()) if os.name == "nt" else str(cible)
    shutil.rmtree(chemin, onexc=rendre_modifiable)