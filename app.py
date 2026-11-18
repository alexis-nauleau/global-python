# ============================================================
# app.py : la fenêtre principale de la boîte à outils.
# Un MENU à gauche, des PAGES à droite. Chaque page contient des LIGNES (un outil = une ligne),
# et EN DESSOUS les résultats de l'outil.
#
# Pour ajouter un outil :
#   1. ajoute UNE ligne dans la liste PAGES ci-dessous ;
#   2. si le script a besoin d'un dossier ou d'une fenêtre à lui, précise-le dans LANCEMENT.
# ============================================================
import codecs                     # pour transformer les octets reçus d'un script en texte
import os                         # pour nettoyer les chemins de dossiers
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import subprocess                 # pour LANCER un autre programme (nos scripts)
import sys                        # sys.executable = le Python qui fait tourner CE programme
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk      # choix de dossier, messages, tableaux

from outils.gagner_de_la_place import caches         # la logique des caches (aucune fenêtre dedans)

PAGES = [
    # ===== Section "Gagner de la place" =====
    {
        # Cette page n'est pas une simple ligne : c'est une vraie page, construite par PageCaches
        # (plus bas), avec un tableau de résultats et un bouton pour supprimer.
        "cle": "caches",                      # chaque "cle" doit être UNIQUE
        "menu": "Analyser puis supprimer les caches",
        "titre": "Gagner de la place",
        "page": "caches",
    },
    {
        "cle": "projets",
        "menu": "Nettoyer un projet web",
        "titre": "Gagner de la place",
        "outils": [
            ("Nettoyer les projets dormants",
             "Supprime le dossier node_modules des projets web non modifiés depuis 60 jours.",
             "outils/gagner_de_la_place/nettoyer_projets.py"),
        ],
    },
    {
        "cle": "ranger_dossier",
        "menu": "Ranger un dossier",
        "titre": "Gagner de la place",
        "outils": [
            ("Ranger un dossier",
             "Trie un dossier en rangeant les fichiers par extension.",
             "outils/gagner_de_la_place/ranger.py"),
        ],
    },

    # ===== Section "Photos" =====
    {
        "cle": "images",
        "menu": "Optimiser les images",
        "titre": "Photos",
        "outils": [
            ("Optimiser les images",
             "Réduit le poids des images (WebP) ou les redimensionne pour un réseau social.",
             "outils/photos/optimiser_images.py"),
        ],
    },
    {
        "cle": "photos_annee",
        "menu": "Ranger les photos",
        "titre": "Photos",
        "outils": [
            ("Ranger les photos",
             "Trie les photos par année.",
             "outils/photos/ranger_photos.py"),
        ],
    },
    {
        "cle": "doublons",
        "menu": "Supprimer les doublons",
        "titre": "Photos",
        "outils": [
            ("Supprimer les doublons",
             "Supprime les fichiers dont le nom finit par (1), (2) ou (3).",
             "outils/photos/supprimer_doublons.py"),
        ],
    },
]

cles = [definition["cle"] for definition in PAGES]
if len(cles) != len(set(cles)):
    raise SystemExit("Erreur dans PAGES : deux pages ont la même 'cle'.")


# ------------------------------------------------------------
#  COMMENT LANCER CHAQUE SCRIPT
# ------------------------------------------------------------
# Les scripts ne se lancent pas tous de la même façon. Ce tableau le précise, script par script.
# La clé (à gauche) est le chemin du script, EXACTEMENT comme dans PAGES.
# (La page des caches n'est pas ici : elle n'utilise plus de script.)
#
#   "mode" :
#     "fenetre" -> le script a SA PROPRE fenêtre : on le lance simplement.
#     "console" -> le script écrit du texte : ce texte s'affiche dans la boîte "Résultat" sous la
#                  ligne de l'outil. Si le script pose une question (ex : "o/n"), tu réponds dans
#                  la zone "Réponse" sous la boîte, puis tu cliques sur "Envoyer" (ou Entrée).
#     "dossier" -> le script a besoin d'un DOSSIER : l'application te le demande, puis la ligne
#                  affiche deux boutons : "Simuler" (ne change rien) et "Appliquer" (agit pour de vrai).
#                  Le résultat s'affiche dans la boîte "Résultat".
#     "dossier_lecture" -> comme "dossier", mais pour un script qui ne fait que LIRE (il ne
#                  modifie ni ne supprime rien) : un seul bouton, qui te laisse choisir le dossier.
#     "chercher" -> en deux temps : "Chercher" (choisis le dossier, le script montre ce qu'il ferait,
#                  sans rien changer) puis "Appliquer" (grisé tant que la recherche n'est pas
#                  terminée) qui agit pour de vrai sur CE MÊME dossier.
#
#   Pour les modes "dossier" et "chercher" :
#     "simulation"   : les options ajoutées pour SIMULER ([] = le script simule déjà par défaut)
#     "reel"         : les options ajoutées pour AGIR POUR DE VRAI
#     "confirmation" : le message affiché avant d'agir pour de vrai
#
#   Pour les modes "dossier" et "dossier_lecture" (facultatifs) :
#     "titre_dialogue" : le titre de la fenêtre de choix du dossier
#     "dossier_depart" : le dossier ouvert au départ dans cette fenêtre
#
# Un script absent de ce tableau est lancé en mode "console", sans option.
LANCEMENT = {
    "outils/gagner_de_la_place/nettoyer_projets.py": {
        "mode": "dossier",
        "simulation": [],
        "reel": ["--appliquer"],
         "reponse": True,
        "confirmation": "Le dossier node_modules des projets dormants sera SUPPRIMÉ "
                        "(ton code n'est jamais touché).\n"
                        "Le script te demandera encore de taper OUI dans la zone Résultat.",
    },
    "outils/gagner_de_la_place/ranger.py": {
        "mode": "chercher",
        "simulation": [],
        "reel": ["--appliquer"],
        "confirmation": "Les fichiers du dossier seront DÉPLACÉS dans des sous-dossiers "
                        "(Images, Documents...).",
    },
    "outils/photos/optimiser_images.py": {
        "mode": "dossier",
        "simulation": [],
        "reel": ["--appliquer"],
        "confirmation": "Des images WebP optimisées seront créées dans un nouveau dossier "
                        "voisin. Tes originaux ne sont pas touchés.",
    },
    # Ce script propose déjà tout seul : choix du dossier, simulation, puis confirmation (o/n).
    # Ses questions s'affichent dans la boîte "Résultat" : réponds dans la zone "Réponse".
    "outils/photos/ranger_photos.py": {"mode": "console", "reponse": True},
    "outils/photos/supprimer_doublons.py": {
        "mode": "dossier",
        # ATTENTION : ce script SUPPRIME par défaut. Pour simuler, il faut lui ajouter --simulation.
        "simulation": ["--simulation"],
        "reel": [],
        "confirmation": "Les fichiers dont le nom finit par (1), (2) ou (3) seront "
                        "SUPPRIMÉS DÉFINITIVEMENT (pas de corbeille).",
    },
}

# Le dossier où se trouve app.py : c'est à partir de lui qu'on retrouve les scripts.
RACINE = Path(__file__).resolve().parent

FOND = "#F4F5F7"
FOND_MENU = "#1F2937"
MENU_ACTIF = "#374151"
BLEU = "#2563EB"
ROUGE = "#DC2626"               # bouton "Appliquer" / "Supprimer" : une action qui modifie des fichiers
VERT = "#2EA043"                # "Vidé ✓"
ORANGE = "#D29922"              # "Partiel"
GRIS = "#E5E7EB"                # boutons secondaires
FOND_SORTIE = "#111827"         # fond de la boîte "Résultat" (sombre, comme un terminal)
TEXTE_SORTIE = "#E5E7EB"        # couleur du texte dans la boîte "Résultat"


# ------------------------------------------------------------
#  LA BOÎTE "RÉSULTAT" : affiche le texte d'un script, sous sa ligne
# ------------------------------------------------------------

class Sortie(tk.Frame):
    """Une boîte de texte + une zone de réponse. Elle lance un script et en affiche le texte
    en direct (avant, ce texte s'affichait dans PowerShell)."""

    def __init__(self, parent, avec_reponse=False):
        super().__init__(parent, bg=FOND)          # super().__init__ = "construis d'abord la boîte de base"
        self.processus = None             # le script en train de tourner (None = aucun)
        self.arret_demande = False        # vrai si TU as cliqué sur "Arrêter"
        self.reste_cr = ""                # un détail technique pour les lignes qui se réécrivent
        self.quand_fini = None            # une fonction à appeler quand le script se termine bien
        # La "boîte aux lettres" : le fil de lecture y dépose le texte du script,
        # et la fenêtre vient le chercher toutes les 100 ms (voir "surveiller").
        self.messages = queue.Queue()

        # --- La ligne du haut : le titre, l'état, et les boutons "Arrêter" / "Effacer" ---
        entete = tk.Frame(self, bg=FOND)
        entete.pack(fill="x", pady=(0, 6))

        tk.Label(entete, text="Résultat", font=("Arial", 12, "bold"),
                 bg=FOND).pack(side="left")

        # Ce petit texte indiquera "En cours..." pendant qu'un script tourne.
        self.etat = tk.Label(entete, text="", font=("Arial", 9), fg="#6B7280", bg=FOND)
        self.etat.pack(side="left", padx=10)

        tk.Button(entete, text="Effacer", font=("Arial", 9), relief="flat", bg=GRIS,
                  cursor="hand2", padx=10, command=self.effacer).pack(side="right")
        # state="disabled" : bouton grisé, impossible de cliquer (tant qu'aucun script ne tourne).
        self.bouton_arreter = tk.Button(entete, text="Arrêter", font=("Arial", 9), relief="flat",
                                        bg=GRIS, cursor="hand2", padx=10,
                                        state="disabled", command=self.arreter)
        self.bouton_arreter.pack(side="right", padx=(0, 6))

        # --- Le texte lui-même, avec une barre de défilement à droite ---
        corps = tk.Frame(self)
        corps.pack(fill="x")

        barre = tk.Scrollbar(corps)
        barre.pack(side="right", fill="y")

        # tk.Text = une zone de texte de plusieurs lignes.
        #   height=12 : 12 lignes visibles. font Consolas : police "machine à écrire".
        #   wrap="word" : les longues lignes passent à la ligne sans couper un mot.
        #   state="disabled" : tu ne peux pas écrire dedans à la main (seul le programme le fait).
        #   yscrollcommand : relie la zone à la barre de défilement.
        self.texte = tk.Text(corps, height=12, bg=FOND_SORTIE, fg=TEXTE_SORTIE,
                             font=("Consolas", 10), wrap="word", relief="flat",
                             padx=10, pady=8, state="disabled", yscrollcommand=barre.set)
        self.texte.pack(side="left", fill="x", expand=True)
        barre.config(command=self.texte.yview)

        # --- La ligne du bas : la zone de réponse (pour les scripts qui posent une question) ---
        saisie = tk.Frame(self, bg=FOND)
        if avec_reponse:                           # cachée (jamais rangée avec pack) si le script ne pose aucune question
            saisie.pack(fill="x", pady=(6, 0))

        tk.Label(saisie, text="Réponse :", font=("Arial", 9), bg=FOND).pack(side="left")

        # tk.Entry = une zone de saisie d'UNE ligne.
        self.champ = tk.Entry(saisie, font=("Consolas", 10), state="disabled")
        self.champ.pack(side="left", fill="x", expand=True, padx=6)
        # <Return> = la touche Entrée : elle fait la même chose que le bouton "Envoyer".
        self.champ.bind("<Return>", lambda evenement: self.envoyer())

        self.bouton_envoyer = tk.Button(saisie, text="Envoyer", font=("Arial", 9), relief="flat",
                                        bg=BLEU, fg="white", cursor="hand2", padx=12,
                                        state="disabled", command=self.envoyer)
        self.bouton_envoyer.pack(side="right")

        # Un petit message au départ.
        self.ecrire("Les résultats s'afficheront ici.\n")

    def ecrire(self, texte):
        """Ajoute du texte à la fin de la boîte et fait défiler vers le bas."""

        # Certains scripts écrivent "\r" pour RÉÉCRIRE la même ligne (ex : "12000 dossiers analysés...").
        # Si le morceau de texte se termine par "\r", on le garde de côté : le "\n" qui va avec
        # arrive peut-être dans le morceau suivant.
        texte = self.reste_cr + texte
        self.reste_cr = ""
        if texte.endswith("\r"):
            self.reste_cr = "\r"
            texte = texte[:-1]
        texte = texte.replace("\r\n", "\n")        # "\r\n" = simple retour à la ligne Windows

        # Une zone "disabled" refuse qu'on y écrive : on la débloque le temps d'écrire.
        self.texte.config(state="normal")
        # On coupe le texte à chaque "\r". Chaque "\r" efface la ligne en cours avant de réécrire.
        for i, morceau in enumerate(texte.split("\r")):
            if i > 0:
                # "end-1c linestart" = le début de la dernière ligne ; "end-1c" = sa fin.
                self.texte.delete("end-1c linestart", "end-1c")
            self.texte.insert("end", morceau)
        self.texte.see("end")                      # fait défiler jusqu'à la fin
        self.texte.config(state="disabled")

    def effacer(self):
        """Vide la boîte."""
        self.texte.config(state="normal")
        self.texte.delete("1.0", "end")            # "1.0" = ligne 1, caractère 0 : le tout début
        self.texte.config(state="disabled")
        self.reste_cr = ""

    def definir_etat(self, en_cours):
        """Active ou grise les boutons selon qu'un script tourne ou non."""
        etat = "normal" if en_cours else "disabled"
        self.bouton_arreter.config(state=etat)
        self.bouton_envoyer.config(state=etat)
        self.champ.config(state=etat)
        self.etat.config(text="En cours..." if en_cours else "")
        if en_cours:
            self.champ.focus_set()                 # le curseur se place dans la zone de réponse

    def executer(self, commande, titre, quand_fini=None):
        """Lance 'commande' (une liste) et affiche son texte ici. 'titre' est rappelé en haut.
        'quand_fini' (facultatif) : une fonction appelée avec le code de sortie quand le script
        se termine (sauf si tu cliques sur "Arrêter").
        Renvoie True si le script a démarré, False sinon."""
        # Un seul script à la fois dans cette boîte, sinon leurs textes se mélangeraient.
        if self.processus is not None:
            messagebox.showinfo("Déjà en cours",
                                "Un outil tourne déjà ici.\nAttends qu'il se termine, "
                                "ou clique sur « Arrêter ».")
            return False

        # Deux réglages pour que le texte arrive tout de suite et avec les accents :
        #   PYTHONUNBUFFERED : le script envoie son texte immédiatement (sans le garder en réserve)
        #   PYTHONIOENCODING : le script écrit en UTF-8, comme on le lit ici
        environnement = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")

        try:
            # stdout=PIPE : on RÉCUPÈRE ce que le script écrit (au lieu de l'afficher dans PowerShell).
            # stderr=STDOUT : les messages d'erreur arrivent au même endroit.
            # stdin=PIPE : on pourra lui ENVOYER nos réponses (ex : taper OUI).
            # CREATE_NO_WINDOW : aucune fenêtre noire ne s'ouvre (n'existe que sous Windows,
            # d'où le getattr : "0" = rien, ailleurs).
            self.processus = subprocess.Popen(
                commande, cwd=RACINE, env=environnement,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as erreur:
            messagebox.showerror("Lancement impossible", str(erreur))
            return False

        self.quand_fini = quand_fini
        self.arret_demande = False
        self.effacer()
        self.ecrire("▶ " + titre + "\n\n")
        self.definir_etat(True)

        # Un FIL séparé lit le texte du script : si on le lisait ici, la fenêtre se figerait.
        # daemon=True : ce fil s'arrête tout seul quand on ferme l'application.
        threading.Thread(target=self.lire_sortie, args=(self.processus,), daemon=True).start()
        # Et la fenêtre ira chercher ce texte toutes les 100 ms.
        self.after(100, self.surveiller)
        return True

    def lire_sortie(self, processus):
        """Tourne dans un FIL à part. Il NE TOUCHE PAS à la fenêtre : il dépose juste le texte
        dans la boîte aux lettres (self.messages). Seule la fenêtre elle-même a le droit
        de modifier l'écran."""
        # Le script envoie des octets ; le décodeur les transforme en texte (UTF-8).
        # Il sait gérer un accent coupé en deux entre deux morceaux.
        decodeur = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            morceau = processus.stdout.read(4096)      # attend du texte ; renvoie vide quand c'est fini
            if not morceau:
                break
            self.messages.put(("texte", decodeur.decode(morceau)))
        # Le script est terminé : wait() donne son "code de sortie" (0 = tout s'est bien passé).
        self.messages.put(("fin", processus.wait()))

    def surveiller(self):
        """Appelée toutes les 100 ms : affiche le texte arrivé depuis la dernière fois."""
        while True:
            try:
                genre, contenu = self.messages.get_nowait()   # prend un message, sans attendre
            except queue.Empty:                               # boîte vide : on arrête de lire
                break
            if genre == "texte":
                self.ecrire(contenu)
            else:                                             # "fin" : le script est terminé
                self.terminer(contenu)
                return                                        # plus besoin de surveiller
        self.after(100, self.surveiller)                      # on se rappelle dans 100 ms

    def terminer(self, code):
        """Appelée quand le script est fini : affiche le bilan et remet les boutons à zéro."""
        if self.arret_demande:
            self.ecrire("\n■ Arrêté.\n")
        elif code == 0:
            self.ecrire("\n✓ Terminé.\n")
        else:
            self.ecrire(f"\n✗ Le script s'est arrêté avec une erreur (code {code}).\n")
        try:
            self.processus.stdin.close()
        except OSError:
            pass
        self.processus = None
        self.definir_etat(False)
        # Un outil peut demander à être prévenu quand son script se termine (ex : le bouton "Appliquer").
        rappel, self.quand_fini = self.quand_fini, None
        if rappel is not None and not self.arret_demande:
            rappel(code)

    def envoyer(self):
        """Envoie au script ce que tu as tapé dans la zone "Réponse" (comme taper dans PowerShell)."""
        if self.processus is None:
            return
        texte = self.champ.get()
        self.champ.delete(0, "end")                # vide la zone de saisie
        self.ecrire(texte + "\n")                  # on l'affiche aussi (le script ne le répète pas)
        try:
            self.processus.stdin.write((texte + "\n").encode("utf-8"))
            self.processus.stdin.flush()
        except OSError:
            pass                                   # le script est déjà fini : rien à envoyer

    def arreter(self):
        """Interrompt le script en cours (attention : il s'arrête net, sans bilan final)."""
        if self.processus is not None:
            self.arret_demande = True
            self.processus.terminate()


# ------------------------------------------------------------
#  LA PAGE "ANALYSER PUIS SUPPRIMER LES CACHES"
# ------------------------------------------------------------

class PageCaches(tk.Frame):
    """Une vraie page : on choisit un dossier, l'analyse remplit un tableau en dessous,
    puis on sélectionne des lignes et on les supprime. Toute la logique (analyser, vérifier,
    vider) est dans outils/gagner_de_la_place/caches.py : ici, on ne s'occupe que de l'écran."""

    def __init__(self, zone, titre):
        super().__init__(zone, bg=FOND)
        # place() : la page occupe 100 % de la zone (toutes les pages sont empilées au même endroit).
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.racine = None                # le dossier analysé
        self.elements = []                # les dossiers trouvés (une "fiche" par ligne du tableau)
        self.liberes = 0                  # combien d'octets on a libérés au total
        self.occupe = False               # vrai pendant une analyse ou une suppression
        self.arret = threading.Event()    # l'interrupteur "Arrêter" (lu par le fil de travail)
        self.messages = queue.Queue()     # la boîte aux lettres du fil de travail vers la fenêtre

        # Le grand titre de la page.
        tk.Label(self, text=titre, font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # ----- La ligne de l'outil (la boîte blanche) -----
        ligne = tk.Frame(self, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        textes = tk.Frame(ligne, bg="white")
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)
        tk.Label(textes, text="Analyser les caches", font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
        tk.Label(textes, text="Cherche les caches et les dossiers reconstructibles d'un dossier "
                              "ou d'un disque. Tu choisis ensuite ce que tu supprimes.",
                 font=("Arial", 9), fg="#6B7280", bg="white", anchor="w", justify="left",
                 wraplength=340).pack(fill="x")

        # Le premier élément placé avec side="right" est celui tout à droite.
        self.bouton_analyser = tk.Button(ligne, text="Analyser un dossier", font=("Arial", 10, "bold"),
                                         bg=BLEU, fg="white", relief="flat", cursor="hand2",
                                         padx=14, command=self.choisir_et_analyser)
        self.bouton_analyser.pack(side="right", padx=(6, 15), ipady=4)
        self.bouton_arreter = tk.Button(ligne, text="Arrêter", font=("Arial", 10, "bold"),
                                        bg=GRIS, relief="flat", cursor="hand2", padx=14,
                                        state="disabled", command=self.arret.set)
        self.bouton_arreter.pack(side="right", ipady=4)

        # Une ligne de texte qui dit où on en est.
        self.statut = tk.Label(self, text="Clique sur « Analyser un dossier » pour commencer.",
                               font=("Arial", 9), fg="#6B7280", bg=FOND, anchor="w")
        self.statut.pack(fill="x", padx=32, pady=(2, 0))

        # ----- La barre du bas (rangée AVANT le tableau : elle reste visible même si la fenêtre rétrécit) -----
        bas = tk.Frame(self, bg=FOND)
        bas.pack(side="bottom", fill="x", padx=30, pady=(8, 20))

        self.label_totaux = tk.Label(bas, text="", font=("Arial", 10, "bold"), bg=FOND)
        self.label_totaux.pack(side="left")

        self.bouton_supprimer = tk.Button(bas, text="Supprimer la sélection", font=("Arial", 10, "bold"),
                                          bg=ROUGE, fg="white", relief="flat", cursor="hand2",
                                          padx=14, state="disabled", command=self.supprimer)
        self.bouton_supprimer.pack(side="right", ipady=4)
        self.bouton_tout = tk.Button(bas, text="Tout sélectionner", font=("Arial", 10), bg=GRIS,
                                     relief="flat", cursor="hand2", padx=10, state="disabled",
                                     command=self.tout_selectionner)
        self.bouton_tout.pack(side="right", padx=6, ipady=4)
        self.bouton_ouvrir = tk.Button(bas, text="Ouvrir le dossier", font=("Arial", 10), bg=GRIS,
                                       relief="flat", cursor="hand2", padx=10, state="disabled",
                                       command=self.ouvrir_dossier)
        self.bouton_ouvrir.pack(side="right", ipady=4)

        # ----- Les résultats : deux onglets, chacun avec un tableau -----
        ttk.Style(self).configure("Treeview", rowheight=24)      # des lignes un peu plus aérées
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=30, pady=(8, 0))

        # Onglet 1 : ce qu'on peut supprimer. selectmode="extended" = on peut en sélectionner plusieurs
        # (Ctrl + clic, ou Maj + clic).
        cadre1, self.tableau = self.creer_tableau(
            [("taille", "Taille", 90, "e", False), ("type", "Type", 120, "w", False),
             ("etat", "État", 90, "w", False), ("dossier", "Dossier", 400, "w", True)],
            "extended")
        self.onglets.add(cadre1, text="Caches et dossiers jetables")
        # Une "étiquette" (tag) colore les lignes : vert = vidé, orange = partiel.
        self.tableau.tag_configure("vide", foreground=VERT)
        self.tableau.tag_configure("partiel", foreground=ORANGE)
        self.tableau.tag_configure("refuse", foreground=ROUGE)
        # Quand la sélection change, on met à jour le total et les boutons.
        self.tableau.bind("<<TreeviewSelect>>", lambda evenement: self.maj_boutons())

        # Onglet 2 : les plus gros dossiers (pour information, rien à supprimer ici).
        cadre2, self.tableau_gros = self.creer_tableau(
            [("niveau", "Niveau", 70, "center", False), ("taille", "Taille", 90, "e", False),
             ("dossier", "Dossier", 400, "w", True)],
            "browse")
        self.onglets.add(cadre2, text="Plus gros dossiers")

        self.maj_boutons()

    def creer_tableau(self, colonnes, selectmode):
        """Fabrique un tableau (ttk.Treeview) avec une barre de défilement. Renvoie (cadre, tableau).
        Chaque colonne = (identifiant, titre, largeur, alignement, s'étire ?)."""
        cadre = tk.Frame(self.onglets)
        arbre = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings",
                             selectmode=selectmode)
        for identifiant, titre, largeur, alignement, s_etire in colonnes:
            arbre.heading(identifiant, text=titre)
            arbre.column(identifiant, width=largeur, anchor=alignement, stretch=s_etire)
        barre = ttk.Scrollbar(cadre, orient="vertical", command=arbre.yview)
        arbre.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        arbre.pack(side="left", fill="both", expand=True)
        return cadre, arbre

    # ------------------------------------------------------------
    # L'analyse
    # ------------------------------------------------------------
    def choisir_et_analyser(self):
        """Demande le dossier à analyser, puis lance l'analyse dans un fil de travail."""
        if self.occupe:
            return
        options = {"title": "Choisis le dossier ou le disque à analyser"}
        if os.path.isdir("C:\\"):
            options["initialdir"] = "C:\\"          # la fenêtre s'ouvre sur C:\ si ce disque existe
        dossier = filedialog.askdirectory(**options)
        if not dossier:                             # un texte vide compte pour "faux" : tu as annulé
            return
        # askdirectory renvoie des "/" ; normpath remet les "\" de Windows.
        self.racine = os.path.normpath(dossier)

        # On repart de zéro.
        self.elements = []
        self.liberes = 0
        self.tableau.delete(*self.tableau.get_children())            # vide les deux tableaux
        self.tableau_gros.delete(*self.tableau_gros.get_children())
        self.onglets.tab(0, text="Caches et dossiers jetables")
        self.arret.clear()                          # éteint l'interrupteur "Arrêter"
        self.definir_occupe(True)
        self.statut.config(text=f"Analyse de {self.racine} en cours (ça peut durer plusieurs minutes)...")

        # Le fil de travail : il analyse pendant que la fenêtre reste utilisable.
        threading.Thread(target=self.travail_analyse, args=(self.racine,), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_analyse(self, racine):
        """Tourne dans un FIL à part : il NE TOUCHE PAS à la fenêtre, il envoie des messages."""
        try:
            resultats = caches.analyser(
                racine, self.arret,
                progression=lambda compteur: self.messages.put(("progression", compteur)))
            self.messages.put(("fin_analyse", resultats))
        except Exception as erreur:                 # une erreur imprévue : on la montre, sans planter
            self.messages.put(("erreur", str(erreur)))

    def surveiller(self):
        """Appelée toutes les 100 ms : lit les messages du fil de travail et met l'écran à jour."""
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            genre = message[0]                      # message[0] = le 1er élément du message
            if genre == "progression":
                self.statut.config(text=f"Analyse en cours... {message[1]} dossiers parcourus")
            elif genre == "fin_analyse":
                self.afficher_resultats(message[1])
                return                              # c'est fini : on ne se reprogramme pas
            elif genre == "supprime":
                self.mettre_a_jour_ligne(*message[1:])
            elif genre == "fin_suppression":
                self.terminer_suppression(message[1])
                return
            else:                                   # "erreur"
                self.definir_occupe(False)
                self.statut.config(text="Une erreur est survenue.")
                messagebox.showerror("Erreur", message[1])
                return
        self.after(100, self.surveiller)

    def afficher_resultats(self, resultats):
        """Remplit les deux tableaux avec le résultat de l'analyse."""
        # Une "fiche" (dictionnaire) par dossier supprimable : temp, caches, puis dossiers jetables.
        for categorie in ("temp", "cache", "jetable"):
            for chemin, taille in resultats[categorie]:
                self.elements.append({"chemin": Path(chemin), "taille": taille,
                                      "categorie": categorie, "etat": ""})
        # Du plus gros au plus petit. key=... dit sur quoi on trie ; reverse=True : décroissant.
        self.elements.sort(key=lambda element: element["taille"], reverse=True)
        for numero, element in enumerate(self.elements):
            # iid = le numéro de la ligne : il permet de retrouver la fiche quand on sélectionne.
            self.tableau.insert("", "end", iid=str(numero), values=(
                caches.lisible(element["taille"]), caches.TYPES[element["categorie"]], "",
                str(element["chemin"])))
        self.onglets.tab(0, text=f"Caches et dossiers jetables ({len(self.elements)})")

        # Les plus gros dossiers : 10 de niveau 1 et 15 de niveau 2 (comme dans l'ancien script).
        for niveau, limite in ((1, 10), (2, 15)):
            plus_gros = sorted(resultats[niveau], key=lambda c: c[1], reverse=True)[:limite]
            for chemin, taille in plus_gros:
                self.tableau_gros.insert("", "end", values=(niveau, caches.lisible(taille), chemin))

        recuperable = caches.lisible(sum(e["taille"] for e in self.elements))
        if resultats["interrompu"]:
            self.statut.config(text=f"Analyse interrompue : résultats PARTIELS "
                                    f"({resultats['compteur']} dossiers parcourus).")
        elif self.elements:                         # une liste non vide compte pour "vrai"
            self.statut.config(text=f"Analyse terminée : {len(self.elements)} dossier(s), "
                                    f"{recuperable} récupérable(s). Sélectionne des lignes puis supprime.")
        else:
            self.statut.config(text="Analyse terminée : rien à supprimer dans ce dossier.")
        self.definir_occupe(False)

    # ------------------------------------------------------------
    # La suppression
    # ------------------------------------------------------------
    def supprimer(self):
        """Demande confirmation, puis vide les dossiers sélectionnés (dans un fil de travail)."""
        if self.occupe:
            return
        numeros = [int(iid) for iid in self.tableau.selection()]
        if not numeros:
            return
        choisis = [self.elements[n] for n in numeros]

        # Le message de confirmation : combien, quels dossiers, et ce que ça implique.
        total = caches.lisible(sum(e["taille"] for e in choisis))
        liste = "\n".join(str(e["chemin"]) for e in choisis[:6])
        if len(choisis) > 6:
            liste += f"\n... et {len(choisis) - 6} autre(s)"
        types = sorted({e["categorie"] for e in choisis})          # les catégories concernées, sans doublon
        consequences = "\n".join(caches.CONSEQUENCES[t] for t in types)
        if not messagebox.askyesno(
                "Confirmer la suppression",
                f"Vider {len(choisis)} dossier(s) ({total}) ?\n\n{liste}\n\n{consequences}\n\n"
                "Ferme Chrome, Edge et VS Code avant de vider leurs caches.\n"
                "La suppression est DÉFINITIVE (pas de corbeille)."):
            return

        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text="Suppression en cours...")
        threading.Thread(target=self.travail_suppression, args=(numeros,), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_suppression(self, numeros):
        """Tourne dans un FIL à part : vide les dossiers un par un et envoie un message à chaque fois."""
        for numero in numeros:
            if self.arret.is_set():                 # tu as cliqué sur "Arrêter" : on s'arrête là
                break
            element = self.elements[numero]
            chemin = element["chemin"]
            # Le garde-fou, AU MOMENT de supprimer : il refuse tout ce qui n'est pas un vrai cache.
            if not chemin.is_dir() or not caches.chemin_supprimable(chemin, element["categorie"],
                                                                    self.racine):
                self.messages.put(("supprime", numero, None, None))     # None = refusé
                continue
            avant = caches.taille_dossier(chemin)    # la taille avant nettoyage
            caches.vider_dossier(chemin)
            apres = caches.taille_dossier(chemin)    # après : parfois il reste des fichiers utilisés
            self.messages.put(("supprime", numero, avant, apres))
        self.messages.put(("fin_suppression", self.arret.is_set()))

    def mettre_a_jour_ligne(self, numero, avant, apres):
        """Met à jour une ligne du tableau après son nettoyage."""
        element = self.elements[numero]
        if avant is None:                           # le garde-fou a refusé
            element["etat"] = "Refusé"
            etiquette = "refuse"
        else:
            element["taille"] = apres
            self.liberes += avant - apres           # on ajoute ce qui a vraiment été libéré
            if apres > caches.SEUIL_PARTIEL:
                element["etat"] = "Partiel"         # il reste des fichiers utilisés par un programme
                etiquette = "partiel"
            else:
                element["etat"] = "Vidé ✓"
                etiquette = "vide"
        self.tableau.item(str(numero), tags=(etiquette,), values=(
            caches.lisible(element["taille"]), caches.TYPES[element["categorie"]],
            element["etat"], str(element["chemin"])))
        self.maj_boutons()

    def terminer_suppression(self, interrompu):
        """Appelée quand la suppression est finie."""
        self.statut.config(text="Suppression interrompue." if interrompu
                           else f"Suppression terminée : {caches.lisible(self.liberes)} libérés.")
        self.definir_occupe(False)

    # ------------------------------------------------------------
    # Les petits boutons et le total
    # ------------------------------------------------------------
    def tout_selectionner(self):
        self.tableau.selection_set(self.tableau.get_children())

    def ouvrir_dossier(self):
        """Ouvre dans l'Explorateur Windows le premier dossier sélectionné."""
        selection = self.tableau.selection()
        if not selection:
            return
        try:
            os.startfile(str(self.elements[int(selection[0])]["chemin"]))    # n'existe que sous Windows
        except (AttributeError, OSError) as erreur:
            messagebox.showerror("Ouverture impossible", str(erreur))

    def definir_occupe(self, occupe):
        """Pendant une analyse ou une suppression : on grise ce qui ne doit pas être cliqué."""
        self.occupe = occupe
        self.bouton_analyser.config(state="disabled" if occupe else "normal")
        self.bouton_arreter.config(state="normal" if occupe else "disabled")
        self.maj_boutons()

    def maj_boutons(self):
        """Met à jour le total affiché et active / grise les boutons du bas."""
        selection = [self.elements[int(iid)] for iid in self.tableau.selection()]
        taille_selection = caches.lisible(sum(e["taille"] for e in selection))
        self.label_totaux.config(
            text=f"Sélection : {len(selection)} dossier(s), {taille_selection}"
                 f"        Libéré : {caches.lisible(self.liberes)}")
        libre = "normal" if not self.occupe else "disabled"
        self.bouton_supprimer.config(state="normal" if selection and not self.occupe else "disabled")
        self.bouton_ouvrir.config(state="normal" if selection and not self.occupe else "disabled")
        self.bouton_tout.config(state=libre if self.elements else "disabled")


# ------------------------------------------------------------
#  LA CLASSE Application
# ------------------------------------------------------------

class Application:

    def __init__(self, fenetre):

        # On garde la fenêtre dans "self" (= cet objet), pour que toutes les méthodes s'en servent.
        self.fenetre = fenetre
        self.sorties = []                 # toutes les boîtes "Résultat" (une par page d'outil)
        self.page_caches = None           # la page des caches, si elle existe
        self.dossiers = {}                # pour les outils "chercher" : le dernier dossier cherché

        # ----- Réglages de la fenêtre -----
        fenetre.title("Boîte à outils")
        fenetre.geometry("1000x700")
        fenetre.minsize(920, 620)
        # Si tu fermes la fenêtre pendant qu'un script tourne, on l'arrête proprement.
        fenetre.protocol("WM_DELETE_WINDOW", self.fermer)

        # ---------- LE MENU  ----------

        # tk.Frame => "crée une boîte DANS la fenêtre (ci-dessus)".

        menu = tk.Frame(fenetre, bg=FOND_MENU, width=250)

        # pack()  C'est ce qui le rend VISIBLE :
        #   fill="y"     : étire-le sur toute la hauteur

        menu.pack(side="left", fill="y")
        # pack_propagate(False) dit : "garde ta largeur de 250, quoi qu'il y ait dedans".
        menu.pack_propagate(False)

        # Label = un texte affiché à l'écran:
        # fg =  couleur du texte
        # pady=(25, 20) (25 pixels au-dessus, 20 en dessous).

        tk.Label(menu, text="BOÎTE À OUTILS", font=("Arial", 13, "bold"),
                 bg=FOND_MENU, fg="white").pack(pady=(25, 20))

        # ---------- LA ZONE DES PAGES (à droite) ----------

        zone = tk.Frame(fenetre, bg=FOND)
        # fill="both" : étire en largeur ET en hauteur.
        # expand=True : prend tout l'espace libre qui reste.
        zone.pack(side="right", fill="both", expand=True)

        # ----- On prépare deux "carnets" -----

        self.pages = {}
        self.boutons_menu = {}

        # ---------- ON CONSTRUIT LE MENU ET LES PAGES ----------

        for definition in PAGES:

            cle = definition["cle"]

            #   relief="flat"  : bouton plat, sans bordure en relief
            #   anchor="w"     : texte aligné à gauche (w = west = ouest)
            #   padx=20        : espace horizontal à l'intérieur du bouton
            #   cursor="hand2" : le curseur devient une petite main au survol
            #   activebackground / activeforeground : couleurs pendant le clic
            #   wraplength=210 : un nom trop long passe à la ligne (justify="left" : alignée à gauche)
            #   command        : la fonction à exécuter QUAND on clique
            bouton = tk.Button(menu, text=definition["menu"], font=("Arial", 11),
                               bg=FOND_MENU, fg="white", relief="flat", anchor="w",
                               padx=20, cursor="hand2", activebackground=MENU_ACTIF,
                               activeforeground="white", wraplength=210, justify="left",
                               # "lambda" crée une mini-fonction sans nom, sur une seule ligne.
                               # Le "cle=cle" est un détail IMPORTANT : il fige la valeur de cle POUR CE bouton. Sans lui, tous les boutons afficheraient la dernière page (le piège classique des boucles).
                               command=lambda cle=cle: self.afficher(cle))

            # fill="x" : le bouton prend toute la largeur du menu.
            # ipady=8 : épaisseur supplémentaire À L'INTÉRIEUR
            bouton.pack(fill="x", ipady=8)

            # On range le bouton dans notre carnet
            self.boutons_menu[cle] = bouton

            self.pages[cle] = self.creer_page(zone, definition)

        # Au démarrage, on affiche la première page.
        self.afficher(PAGES[0]["cle"])

    # ------------------------------------------------------------
    # Construire UNE page
    # ------------------------------------------------------------

    def creer_page(self, zone, definition):
        """Construit une page : un titre, une ligne par outil, puis la boîte "Résultat"."""

        # Une page spéciale : on laisse la classe PageCaches la construire entièrement.
        if definition.get("page") == "caches":
            self.page_caches = PageCaches(zone, definition["titre"])
            return self.page_caches

        page = tk.Frame(zone, bg=FOND)

        # Ici on utilise place() au lieu de pack(). Il positionne l'élément à un endroit précis.
        # x=0, y=0 . relwidth=1 / relheight=1 : 100 %
        page.place(x=0, y=0, relwidth=1, relheight=1)

        # Le grand titre de la page. anchor="w" : aligné à gauche. padx : marge gauche/droite.
        tk.Label(page, text=definition["titre"], font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # La boîte "Résultat" est créée ICI (pour que les boutons des lignes puissent s'en servir),
        # mais rangée plus bas, APRÈS les lignes : elle s'affiche donc en dessous d'elles.
                # any(...) = "vrai si AU MOINS un des outils de la page pose des questions" (réglage "reponse").
        pose_des_questions = any(LANCEMENT.get(fichier, {}).get("reponse")
                                 for _nom, _description, fichier in definition["outils"])
        sortie = Sortie(page, avec_reponse=pose_des_questions)
        self.sorties.append(sortie)

        # Une boucle sur la liste "outils" de la fiche
        for nom, description, fichier in definition["outils"]:
            self.creer_ligne(page, nom, description, fichier, sortie)

        sortie.pack(fill="x", padx=30, pady=(12, 20))

        # Ici on rend la page construite, pour que __init__ puisse la ranger dans self.pages.
        return page

    # ------------------------------------------------------------
    # Construire UNE ligne (un outil)
    # ------------------------------------------------------------
    def creer_ligne(self, page, nom, description, fichier, sortie):
        """Une ligne = un outil : son nom, sa description, et ses boutons."""

        # Une boîte blanche avec une fine bordure grise.
        # highlightbackground = couleur de la bordure ; highlightthickness = son épaisseur (1 pixel).
        ligne = tk.Frame(page, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        # --- La partie texte, à gauche : le nom en dessous duquel se trouve la description ---
        textes = tk.Frame(ligne, bg="white")
        # expand=True : cette boîte prend tout l'espace libre, ce qui repousse les boutons à droite.
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)

        # Le nom de l'outil, en gras.
        tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")

        # La description, en plus petit et en gris.
        #   justify="left" : si le texte passe sur plusieurs lignes, elles sont alignées à gauche.
        #   wraplength=340 : au-delà de 340 pixels de large, le texte passe à la ligne tout seul.
        tk.Label(textes, text=description, font=("Arial", 9), fg="#6B7280", bg="white",
                 anchor="w", justify="left", wraplength=340).pack(fill="x")

        # --- Les boutons, à droite ---
        # On regarde dans LANCEMENT comment ce script se lance.
        # .get(clé, valeur_de_secours) : si le script n'est pas dans le tableau, on prend "console".
        reglage = LANCEMENT.get(fichier, {"mode": "console"})

        # Le premier élément placé avec side="right" est celui tout à droite.
        if reglage["mode"] == "dossier":
            # Un outil qui travaille sur un dossier : DEUX boutons.
            # "Appliquer" (rouge, tout à droite) agit pour de vrai ; "Simuler" ne change rien.
            tk.Button(ligne, text="Appliquer", font=("Arial", 10, "bold"), bg=ROUGE, fg="white",
                      relief="flat", cursor="hand2", padx=14,
                      command=lambda: self.lancer_avec_dossier(fichier, sortie, reel=True)
                      ).pack(side="right", padx=(6, 15), ipady=4)
            tk.Button(ligne, text="Simuler", font=("Arial", 10, "bold"), bg=BLEU, fg="white",
                      relief="flat", cursor="hand2", padx=14,
                      command=lambda: self.lancer_avec_dossier(fichier, sortie, reel=False)
                      ).pack(side="right", padx=(6, 0), ipady=4)
        elif reglage["mode"] == "dossier_lecture":
            # Un script qui ne fait que lire : un seul bouton, qui demande le dossier à analyser.
            tk.Button(ligne, text="Analyser un dossier", font=("Arial", 10, "bold"), bg=BLEU,
                      fg="white", relief="flat", cursor="hand2", padx=14,
                      command=lambda: self.lancer_avec_dossier(fichier, sortie, reel=False)
                      ).pack(side="right", padx=15, ipady=4)
        elif reglage["mode"] == "chercher":
            # Deux boutons : "Chercher" montre ce qui serait fait ; "Appliquer" le fait vraiment.
            # "Appliquer" est GRISÉ (state="disabled") tant qu'une recherche n'a pas réussi.
            bouton_appliquer = tk.Button(ligne, text="Appliquer", font=("Arial", 10, "bold"),
                                         bg=ROUGE, fg="white", relief="flat", cursor="hand2",
                                         padx=14, state="disabled")
            bouton_appliquer.pack(side="right", padx=(6, 15), ipady=4)
            # configure(command=...) donne sa fonction au bouton APRÈS sa création :
            # "Chercher" n'existait pas encore quand on a créé "Appliquer".
            bouton_appliquer.config(
                command=lambda: self.appliquer(fichier, sortie, bouton_appliquer))
            tk.Button(ligne, text="Chercher", font=("Arial", 10, "bold"), bg=BLEU, fg="white",
                      relief="flat", cursor="hand2", padx=14,
                      command=lambda: self.chercher(fichier, sortie, bouton_appliquer)
                      ).pack(side="right", padx=(6, 0), ipady=4)
        else:
            # Un seul bouton "Ouvrir".
            # Ici le lambda n'a pas besoin de "fichier=fichier" : il n'y a qu'un seul bouton par appel
            # de cette méthode, donc pas de piège de boucle.
            tk.Button(ligne, text="Ouvrir", font=("Arial", 10, "bold"), bg=BLEU, fg="white",
                      relief="flat", cursor="hand2", padx=18,
                      command=lambda: self.lancer(fichier, sortie)).pack(side="right", padx=15, ipady=4)

    # ------------------------------------------------------------
    # Changer de page
    # ------------------------------------------------------------
    def afficher(self, cle):
        """Met la page choisie au-dessus des autres et surligne son bouton dans le menu."""

        # tkraise() = "remonte cet élément au-dessus des autres".
        # Comme toutes les pages sont empilées au même endroit, celle-ci devient la visible.
        self.pages[cle].tkraise()

        # On parcourt le carnet des boutons du menu.
        # .items() donne, pour chaque entrée du dictionnaire, la paire (clé, valeur).
        for une_cle, bouton in self.boutons_menu.items():
            # Écriture condensée : "valeur_A if condition else valeur_B"
            # = si ce bouton est celui de la page choisie : couleur "active", sinon couleur normale.
            # .config(...) change une option d'un élément qui existe déjà.
            bouton.config(bg=MENU_ACTIF if une_cle == cle else FOND_MENU)

    # ------------------------------------------------------------
    # Lancer un script
    # ------------------------------------------------------------
    def lancer(self, fichier, sortie, arguments=(), quand_fini=None):
        """Lance le script 'fichier' (chemin relatif), avec des 'arguments' facultatifs.
        Son texte s'affiche dans la boîte 'sortie' de la page.
        Renvoie True si le script a démarré, False sinon."""
        script = RACINE / fichier                      # le "/" assemble les morceaux d'un chemin
        if not script.is_file():
            messagebox.showerror("Script introuvable", f"Je ne trouve pas ce fichier :\n{script}")
            return False

        reglage = LANCEMENT.get(fichier, {"mode": "console"})
        # La commande, sous forme de liste : [le Python utilisé, le script, ses options...]
        # sys.executable = le Python qui fait tourner app.py. Les scripts utilisent donc le MÊME
        # Python (et les mêmes bibliothèques installées, comme Pillow).
        # Le "*" devant arguments "déballe" la liste : ses éléments sont ajoutés un par un.
        commande = [sys.executable, str(script), *arguments]

        if reglage["mode"] == "fenetre":
            # Ce script a sa propre fenêtre : Popen le démarre SANS attendre,
            # l'application reste utilisable.
            # try / except : "essaie ceci ; si ça provoque une erreur, fais cela à la place".
            try:
                subprocess.Popen(commande, cwd=RACINE)
            except OSError as erreur:
                messagebox.showerror("Lancement impossible", str(erreur))
                return False
            return True

        # Pour tous les autres : le texte du script s'affiche dans la boîte "Résultat".
        # list2cmdline met les guillemets autour des chemins qui contiennent des espaces.
        return sortie.executer(commande, subprocess.list2cmdline([script.name, *arguments]),
                               quand_fini)

    def demander_dossier(self, reglage):
        """Ouvre la fenêtre de choix de dossier. Renvoie le dossier, ou None si tu annules."""
        # .get(clé, valeur_de_secours) lit un réglage facultatif.
        options_dialogue = {"title": reglage.get("titre_dialogue", "Choisis le dossier à traiter")}
        if os.path.isdir(reglage.get("dossier_depart", "")):
            options_dialogue["initialdir"] = reglage["dossier_depart"]    # dossier ouvert au départ
        dossier = filedialog.askdirectory(**options_dialogue)    # ** "déballe" le dictionnaire en options
        if not dossier:                    # un texte vide compte pour "faux" : l'utilisateur a annulé
            return None
        # askdirectory renvoie des "/" ; normpath remet les "\" de Windows.
        return os.path.normpath(dossier)

    def chercher(self, fichier, sortie, bouton_appliquer):
        """Étape 1 : choisis un dossier, le script montre ce qu'il ferait (sans rien changer).
        Si ça se passe bien, le bouton "Appliquer" devient cliquable."""
        reglage = LANCEMENT[fichier]
        dossier = self.demander_dossier(reglage)
        if dossier is None:
            return
        bouton_appliquer.config(state="disabled")      # pas d'application avant la fin de la recherche
        self.dossiers[fichier] = dossier               # on retient le dossier pour l'étape 2

        def recherche_finie(code):
            if code == 0:                              # 0 = le script s'est bien terminé
                bouton_appliquer.config(state="normal")

        self.lancer(fichier, sortie, [dossier, *reglage.get("simulation", [])], recherche_finie)

    def appliquer(self, fichier, sortie, bouton_appliquer):
        """Étape 2 : agit pour de vrai sur le dossier de la dernière recherche."""
        reglage = LANCEMENT[fichier]
        dossier = self.dossiers.get(fichier)
        if not dossier or not os.path.isdir(dossier):
            messagebox.showerror("Dossier introuvable", "Refais d'abord une recherche.")
            bouton_appliquer.config(state="disabled")
            return
        if not messagebox.askyesno(
                "Confirmer",
                f"Dossier :\n{dossier}\n\n{reglage['confirmation']}\n\nContinuer ?"):
            return
        bouton_appliquer.config(state="disabled")      # une seule application par recherche
        # Si le script n'a pas pu démarrer, on rend le bouton cliquable.
        if not self.lancer(fichier, sortie, [dossier, *reglage["reel"]]):
            bouton_appliquer.config(state="normal")

    def lancer_avec_dossier(self, fichier, sortie, reel):
        """Demande un dossier, puis lance le script en simulation (reel=False) ou pour de vrai."""
        reglage = LANCEMENT[fichier]

        dossier = self.demander_dossier(reglage)
        if dossier is None:                # tu as annulé
            return

        if reel:
            # Avant d'agir pour de vrai, on demande confirmation, avec ce que ça va faire.
            if not messagebox.askyesno(
                    "Confirmer",
                    f"Dossier :\n{dossier}\n\n{reglage['confirmation']}\n\n"
                    "As-tu d'abord fait une simulation ?\nContinuer pour de vrai ?"):
                return
            options = reglage["reel"]
        else:
            options = reglage.get("simulation", [])    # [] si le réglage n'existe pas

        self.lancer(fichier, sortie, [dossier, *options])

    def fermer(self):
        """Appelée quand tu fermes la fenêtre : on arrête ce qui tourne, puis on quitte."""
        for sortie in self.sorties:
            if sortie.processus is not None:
                sortie.processus.terminate()
        if self.page_caches is not None:
            self.page_caches.arret.set()           # arrête l'analyse / la suppression en cours
        self.fenetre.destroy()


# ------------------------------------------------------------
# LE POINT D'ENTRÉE : ce qui se passe quand on lance le programme
# ------------------------------------------------------------
def main():
    # tk.Tk() crée la fenêtre principale (vide pour l'instant).
    fenetre = tk.Tk()

    # On crée une Application et on lui donne la fenêtre : c'est là que __init__ s'exécute
    # et que tout l'écran (menu, pages, lignes) est construit.
    Application(fenetre)

    # Sous Windows, la fenêtre peut s'ouvrir DERRIÈRE VS Code. Ces trois lignes
    # la forcent à passer devant :
    fenetre.lift()                                  # remonte la fenêtre au premier plan
    fenetre.attributes("-topmost", True)            # la met "toujours au-dessus"...
    # after(500, ...) : "dans 500 millisecondes, exécute ceci".
    # On retire donc le "toujours au-dessus" au bout d'une demi-seconde,
    # sinon la fenêtre resterait devant tout, tout le temps.
    fenetre.after(500, lambda: fenetre.attributes("-topmost", False))

    # mainloop() garde la fenêtre OUVERTE et attend tes actions (clics, saisies...).
    fenetre.mainloop()

if __name__ == "__main__":
    main()