import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("Usage : python supprimer_doublons.py <dossier> [--simulation]")

racine = Path(sys.argv[1])
if not racine.is_dir():
    raise SystemExit(f"Dossier introuvable : {racine}")

simulation = "--simulation" in sys.argv
motif = re.compile(r"\([1-3]\)$")
motif_proche = re.compile(r"\(\d+\)")

analyses = 0
trouves = 0
supprimes = 0
erreurs = []
proches = []
exemples = []

for chemin in racine.rglob("*"):
    if not chemin.is_file():
        continue
    analyses += 1
    if len(exemples) < 3:
        exemples.append(chemin.name)
    if motif.search(chemin.stem):
        trouves += 1
        if simulation:
            print(f"A supprimer : {chemin}")
        else:
            try:
                chemin.unlink()
                supprimes += 1
                print(f"Supprimé : {chemin}")
            except OSError as erreur:
                erreurs.append(f"{chemin.name} ({erreur})")
    elif motif_proche.search(chemin.stem):
        proches.append(chemin.name)

print()
print(f"Dossier : {racine}")
print(f"{analyses} fichier(s) analysé(s), {trouves} doublon(s) trouvé(s), {supprimes} supprimé(s).")

if analyses == 0:
    print(" le dossier est vide.")
elif trouves == 0:
    print(" aucun nom de fichier ne finit par (1), (2) ou (3).")
    if proches:
        print(f"  {len(proches)} fichier(s) ont un numéro entre parenthèses, mais pas à la fin du nom ou autre que 1 à 3, par exemple :")
        for nom in proches[:3]:
            print("   -", nom)
    else:
        print("  Exemples  analysés :")
        for nom in exemples:
            print("   -", nom)
elif simulation:
    print(" mode simulation.")

if erreurs:
    print(f" {len(erreurs)} fichier(s) n'ont pas pu être supprimés  :")
    for ligne in erreurs[:5]:
        print("   -", ligne)