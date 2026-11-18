# ============================================================
# page_caches.py : la page "Analyser puis supprimer les caches".
# La logique (analyser, vérifier, vider) est dans outils/gagner_de_la_place/caches.py :
# ici, on ne s'occupe que de l'écran.
# ============================================================
import os                         # os.path : vérifier qu'un dossier existe, os.startfile : l'Explorateur
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk      # choix de dossier, messages, tableaux

from outils.gagner_de_la_place import caches         # la logique des caches (aucune fenêtre dedans)
from style import BLEU, FOND, GRIS, ORANGE, ROUGE, VERT


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