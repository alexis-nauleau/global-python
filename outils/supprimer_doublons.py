import re
import sys
from pathlib import Path

racine = Path(sys.argv[1])
simulation = "--simulation" in sys.argv
motif = re.compile(r"\([1-4]\)")

total = 0
for fichier in racine.rglob("*"):
    if fichier.is_file() and motif.search(fichier.name):
        if not simulation:
            fichier.unlink()
        print("SUPPRIMÉ :", fichier)
        total += 1

print(total, "fichier(s).")