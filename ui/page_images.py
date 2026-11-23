
import os                         # os.startfile : ouvrir un dossier dans l'Explorateur
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from tkinter import filedialog, messagebox, ttk      # choix de photos, messages, tableau

from outils.photos import images                     # la logique 
from outils.photos.formats import FORMATS            # les dimensions 
from ui.style import BLEU, FOND, GRIS, ROUGE


class PageImages(tk.Frame):
    """La page des images. Les photos choisies à la simulation sont retenues : "Appliquer"
    traite EXACTEMENT les mêmes photos avec EXACTEMENT les mêmes réglages."""

    def __init__(self, zone, titre):
        super().__init__(zone, bg=FOND)
        # place() : la page occupe 100 % de la zone (toutes les pages sont empilées au même endroit).
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.occupe = False               # vrai pendant une simulation ou une optimisation
        self.simulation = None            # les réglages de la dernière simulation réussie (None = aucune)
        self.dossier_ecrit = None         # le dossier où l'on a écrit (pour le bouton "Ouvrir")
        self.dernier_dossier = None       # le dernier dossier de photos (la fenêtre s'y rouvre)
        self.arret = threading.Event()    # l'interrupteur "Arrêter" (lu par le fil de travail)
        self.messages = queue.Queue()     # la boîte aux lettres du fil de travail vers la fenêtre
        self.boutons = {}                 # mode -> (bouton Simuler, bouton Appliquer)

        tk.Label(self, text=titre, font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(20, 6))

        # ----- Bloc 1 : réduire le poids (WebP) -----
        ligne, textes = self.creer_carte(
            "Optimiser les images",
            "Réduit le poids des photos (WebP), pour un site web. Les proportions sont conservées.")
        reglage = tk.Frame(textes, bg="white")
        reglage.pack(fill="x", pady=(6, 0))
        tk.Label(reglage, text="Largeur max (px) :", font=("Arial", 9), bg="white").pack(side="left")
        self.var_largeur = tk.StringVar(value="1920")
        # ttk.Spinbox = une zone de nombre avec deux petites flèches ; textvariable la relie à var_largeur.
        ttk.Spinbox(reglage, from_=200, to=8000, increment=100, width=8,
                    textvariable=self.var_largeur).pack(side="left", padx=6)
        # trace_add("write", ...) = "appelle cette fonction dès que la valeur change".
        self.var_largeur.trace_add("write", lambda *arguments: self.invalider())
        self.creer_boutons(ligne, "reduire")

        # ----- Bloc 2 : réseaux sociaux (JPEG) -----
        ligne, textes = self.creer_carte(
            "Optimiser pour les réseaux sociaux",
            "Recadre au centre à la taille exacte du réseau choisi, en JPEG "
            "(Instagram et Facebook refusent le WebP).")
        reglage = tk.Frame(textes, bg="white")
        reglage.pack(fill="x", pady=(6, 0))
        # state="readonly" : on choisit dans la liste, on ne peut pas taper n'importe quoi.
        self.format = ttk.Combobox(reglage, values=list(FORMATS), state="readonly", width=26)
        self.format.current(0)            # le premier de la liste est sélectionné au départ
        self.format.pack(side="left")
        self.format.bind("<<ComboboxSelected>>", self.changer_format)
        self.info_format = tk.Label(reglage, font=("Arial", 9, "bold"), fg=BLEU, bg="white")
        self.info_format.pack(side="left", padx=10)
        tk.Label(textes, text="⚠ Les dimensions des réseaux changent souvent : à corriger dans "
                              "outils/photos/formats.py.",
                 font=("Arial", 8), fg="#B45309", bg="white", anchor="w").pack(fill="x", pady=(4, 0))
        self.creer_boutons(ligne, "reseau")

        # ----- La qualité (commune aux deux blocs) -----
        cadre_qualite = tk.Frame(self, bg=FOND)
        cadre_qualite.pack(fill="x", padx=32, pady=(4, 0))
        tk.Label(cadre_qualite, text="Qualité :", font=("Arial", 9), bg=FOND).pack(side="left")
        self.qualite = tk.Scale(cadre_qualite, from_=1, to=100, orient="horizontal",
                                length=220, bg=FOND, highlightthickness=0)
        self.qualite.set(80)              # AVANT de brancher "command" : sinon set() la déclencherait
        self.qualite.config(command=lambda valeur: self.invalider())
        self.qualite.pack(side="left", padx=8)
        tk.Label(cadre_qualite, text="80 = bon compromis", font=("Arial", 8), fg="#6B7280",
                 bg=FOND).pack(side="left")

        # ----- Les résultats -----
        self.progression = ttk.Progressbar(self, mode="determinate")
        self.progression.pack(fill="x", padx=30, pady=(6, 0))

        # Le bas est rangé AVANT le tableau : il reste visible même si la fenêtre rétrécit.
        bas = tk.Frame(self, bg=FOND)
        bas.pack(side="bottom", fill="x", padx=30, pady=(6, 18))
        self.resume = tk.Label(bas, text="Choisis des photos avec « Simuler » : rien n'est écrit.",
                               font=("Arial", 10, "bold"), fg="#666666", bg=FOND, anchor="w")
        self.resume.pack(side="left")
        self.bouton_ouvrir = tk.Button(bas, text="Ouvrir le dossier de sortie", font=("Arial", 9),
                                       bg=GRIS, relief="flat", cursor="hand2", padx=10,
                                       state="disabled", command=self.ouvrir_sortie)
        self.bouton_ouvrir.pack(side="right", ipady=2)
        self.bouton_arreter = tk.Button(bas, text="Arrêter", font=("Arial", 9), bg=GRIS,
                                        relief="flat", cursor="hand2", padx=10,
                                        state="disabled", command=self.arret.set)
        self.bouton_arreter.pack(side="right", padx=6, ipady=2)

        cadre_tableau = tk.Frame(self)
        cadre_tableau.pack(fill="both", expand=True, padx=30, pady=(8, 0))
        colonnes = ("nom", "avant", "apres", "gain")
        self.tableau = ttk.Treeview(cadre_tableau, columns=colonnes, show="headings", height=4)
        for colonne, titre_colonne, largeur, s_etire in (("nom", "Image", 300, True),
                                                         ("avant", "Avant", 90, False),
                                                         ("apres", "Après", 90, False),
                                                         ("gain", "Gain", 190, False)):
            self.tableau.heading(colonne, text=titre_colonne)
            self.tableau.column(colonne, width=largeur, anchor="w", stretch=s_etire)
        # Les "tags" colorent certaines lignes : gris = ignorée, rouge = erreur.
        self.tableau.tag_configure("ignoree", foreground="#999999")
        self.tableau.tag_configure("erreur", foreground=ROUGE)
        barre = ttk.Scrollbar(cadre_tableau, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        self.tableau.pack(side="left", fill="both", expand=True)

        self.changer_format()             # affiche la taille du réseau choisi au départ

    # ------------------------------------------------------------
    # Construire les blocs
    # ------------------------------------------------------------
    def creer_carte(self, nom, description):
        """Une boîte blanche avec un nom et une description. Renvoie (la boîte, la zone de texte)."""
        ligne = tk.Frame(self, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=5)
        textes = tk.Frame(ligne, bg="white")
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=10)
        tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
        tk.Label(textes, text=description, font=("Arial", 9), fg="#6B7280", bg="white",
                 anchor="w", justify="left", wraplength=430).pack(fill="x")
        return ligne, textes

    def creer_boutons(self, ligne, mode):
        """Les boutons "Simuler" et "Appliquer" d'un bloc. "Appliquer" est GRISÉ tant qu'une
        simulation n'a pas réussi."""
        appliquer = tk.Button(ligne, text="Appliquer", font=("Arial", 10, "bold"), bg=ROUGE,
                              fg="white", relief="flat", cursor="hand2", padx=14,
                              state="disabled", command=lambda: self.appliquer(mode))
        appliquer.pack(side="right", padx=(6, 15), ipady=4)
        simuler = tk.Button(ligne, text="Simuler", font=("Arial", 10, "bold"), bg=BLEU,
                            fg="white", relief="flat", cursor="hand2", padx=14,
                            command=lambda: self.simuler(mode))
        simuler.pack(side="right", padx=(6, 0), ipady=4)
        self.boutons[mode] = (simuler, appliquer)

    # ------------------------------------------------------------
    # Les réglages
    # ------------------------------------------------------------
    def changer_format(self, evenement=None):
        """Affiche la taille du réseau choisi (lue dans formats.py)."""
        largeur, hauteur = FORMATS[self.format.get()]
        self.info_format.config(text=f"→ {largeur} x {hauteur} px, JPEG, recadré au centre")
        self.invalider()

    def invalider(self):
        """Un réglage a changé : la simulation faite n'est plus valable. "Appliquer" est regrisé,
        pour qu'on n'applique jamais d'autres réglages que ceux qu'on a simulés."""
        if self.occupe or self.simulation is None:
            return
        self.simulation = None
        self.maj_boutons()
        self.resume.config(text="Réglages modifiés : refais une simulation avant d'appliquer.")

    def maj_boutons(self):
        """Active ou grise les boutons selon l'état."""
        for mode, (simuler, appliquer) in self.boutons.items():
            simuler.config(state="disabled" if self.occupe else "normal")
            # "Appliquer" : seulement pour le bloc simulé, et jamais pendant un travail.
            actif = (not self.occupe and self.simulation is not None
                     and self.simulation["mode"] == mode)
            appliquer.config(state="normal" if actif else "disabled")
        self.bouton_arreter.config(state="normal" if self.occupe else "disabled")

    # ------------------------------------------------------------
    # Simuler, appliquer
    # ------------------------------------------------------------
    def simuler(self, mode):
        """Étape 1 : choisis des photos ; on calcule les tailles SANS rien écrire."""
        if self.occupe:
            return

        # --- On vérifie les réglages AVANT d'ouvrir la fenêtre de choix ---
        largeur, taille = None, None
        if mode == "reduire":
            try:
                largeur = int(self.var_largeur.get())
            except ValueError:
                messagebox.showerror("Largeur invalide", "La largeur doit être un nombre.")
                return
            if largeur < 50:
                messagebox.showerror("Largeur invalide", "La largeur doit être d'au moins 50 pixels.")
                return
        else:
            taille = FORMATS[self.format.get()]

        # --- Le choix des photos : une ou plusieurs (Ctrl + clic, Maj + clic, ou Ctrl+A pour tout) ---
        options = {"title": "Choisis une ou plusieurs photos (Ctrl+A : toutes celles du dossier)",
                   "filetypes": [("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]}
        if self.dernier_dossier and os.path.isdir(self.dernier_dossier):
            options["initialdir"] = self.dernier_dossier
        chemins = filedialog.askopenfilenames(**options)    # renvoie la liste des fichiers choisis
        if not chemins:                                     # liste vide : tu as annulé
            return
        photos = images.filtrer_images(chemins)             # on garde seulement jpg, jpeg, png
        if not photos:
            messagebox.showerror("Aucune photo", "Aucun fichier JPG ou PNG dans ta sélection.")
            return
        self.dernier_dossier = str(photos[0].parent)

        self.demarrer({"mode": mode, "photos": photos, "largeur": largeur, "taille": taille,
                       "qualite": self.qualite.get(), "ecrire": False,
                       "sortie": images.dossier_sortie(photos, mode)})

    def appliquer(self, mode):
        """Étape 2 : écrit les images optimisées, avec les photos et les réglages de la simulation."""
        if self.occupe or self.simulation is None or self.simulation["mode"] != mode:
            return
        reglages = dict(self.simulation, ecrire=True)       # une copie de la simulation, en mode "écriture"
        if not messagebox.askyesno(
                "Confirmer",
                f"{len(reglages['photos'])} photo(s) seront optimisées et écrites dans :\n"
                f"{reglages['sortie']}\n\n"
                "Tes originaux ne sont pas touchés.\nContinuer ?"):
            return
        self.demarrer(reglages)

    def demarrer(self, reglages):
        """Lance le travail dans un fil et prépare l'écran."""
        self.arret.clear()                                  # éteint l'interrupteur "Arrêter"
        self.tableau.delete(*self.tableau.get_children())   # vide le tableau
        self.progression["value"] = 0
        self.progression["maximum"] = len(reglages["photos"])
        self.resume.config(text="Optimisation en cours..." if reglages["ecrire"]
                           else "Simulation en cours...")
        self.bouton_ouvrir.config(state="disabled")
        self.dossier_ecrit = None
        self.occupe = True
        self.maj_boutons()
        threading.Thread(target=self.travail, args=(reglages,), daemon=True).start()
        self.after(100, self.surveiller)

    def travail(self, reglages):
        """Tourne dans un FIL à part : il NE TOUCHE PAS à la fenêtre, il envoie des messages."""
        try:
            bilan = images.traiter(
                reglages["photos"], reglages["mode"], reglages["largeur"], reglages["qualite"],
                reglages["taille"], reglages["sortie"], reglages["ecrire"], self.arret,
                # "*donnees" récupère tous les morceaux d'un coup, et ("ligne", *donnees) les remet à la suite.
                lambda *donnees: self.messages.put(("ligne", *donnees)))
            self.messages.put(("fin", reglages, bilan))
        except Exception as erreur:                         # une erreur imprévue : on la montre, sans planter
            self.messages.put(("erreur", str(erreur)))

    def surveiller(self):
        """Appelée toutes les 100 ms : lit les messages du fil de travail et met l'écran à jour."""
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            genre = message[0]                              # message[0] = le 1er élément du message
            if genre == "ligne":
                _, numero, _total, nom, avant, apres, gain, etiquette = message
                ligne = self.tableau.insert("", "end", values=(nom, avant, apres, gain),
                                            tags=(etiquette,) if etiquette else ())
                self.tableau.see(ligne)                     # fait défiler jusqu'à la dernière ligne
                self.progression["value"] = numero
            elif genre == "fin":
                self.terminer(message[1], message[2])
                return                                      # c'est fini : on ne se reprogramme pas
            else:                                           # "erreur"
                self.occupe = False
                self.simulation = None
                self.maj_boutons()
                self.resume.config(text="Une erreur est survenue.")
                messagebox.showerror("Erreur", message[1])
                return
        self.after(100, self.surveiller)

    def terminer(self, reglages, bilan):
        """Appelée quand le travail est fini : affiche le bilan et décide si "Appliquer" s'active."""
        self.resume.config(text=images.resume(bilan, reglages["ecrire"]))
        if reglages["ecrire"]:
            self.simulation = None                          # une seule application par simulation
            if bilan["ecrites"]:
                self.dossier_ecrit = reglages["sortie"]
                self.bouton_ouvrir.config(state="normal")
        elif not bilan["interrompu"] and bilan["traitees"] > 0:
            self.simulation = reglages                      # simulation réussie : "Appliquer" devient possible
        else:
            self.simulation = None                          # interrompue, ou rien à faire
        self.occupe = False
        self.maj_boutons()

    def ouvrir_sortie(self):
        """Ouvre le dossier de sortie dans l'Explorateur Windows."""
        if self.dossier_ecrit and self.dossier_ecrit.exists():
            try:
                os.startfile(str(self.dossier_ecrit))       # n'existe que sous Windows
            except (AttributeError, OSError) as erreur:
                messagebox.showerror("Ouverture impossible", str(erreur))