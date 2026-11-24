# ============================================================

# Tu cliques sur "Chercher" : un tableau liste les DOUBLONS CONFIRMÉS (même contenu que l'original)
# et, dans un 2e onglet, les fichiers à vérifier à la main (jamais supprimés).
# Puis "Mettre à la corbeille" envoie la sélection à la corbeille (récupérable).
# La logique est dans outils/photos/doublons.py : ici, on ne s'occupe que de l'écran.
# ============================================================
import os                         # os.path : vérifier qu'un dossier existe, os.startfile : l'Explorateur
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from tkinter import filedialog, messagebox, ttk      # choix de dossier, messages, tableaux

from outils.photos import doublons                   # la logique (aucune fenêtre dedans)
from ui.style import BLEU, FOND, GRIS, ROUGE, VERT


class PageDoublons(tk.Frame):
    """Chercher, puis envoyer à la corbeille. Le garde-fou est revérifié fichier par fichier
    AU MOMENT d'envoyer : si un fichier a changé depuis la recherche, il est refusé."""

    def __init__(self, zone, titre):
        super().__init__(zone, bg=FOND)
        # place() : la page occupe 100 % de la zone (toutes les pages sont empilées au même endroit).
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.racine = None                # le dossier cherché
        self.elements = []                # les doublons confirmés (une "fiche" par ligne du tableau)
        self.envoyes = 0                  # combien de fichiers sont partis à la corbeille
        self.octets = 0                   # et leur taille totale
        self.occupe = False               # vrai pendant une recherche ou un envoi
        self.dernier_dossier = None       # le dernier dossier cherché (la fenêtre s'y rouvre)
        self.arret = threading.Event()    # l'interrupteur "Arrêter" (lu par le fil de travail)
        self.messages = queue.Queue()     # la boîte aux lettres du fil de travail vers la fenêtre

        tk.Label(self, text=titre, font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # ----- La ligne de l'outil (la boîte blanche) -----
        ligne = tk.Frame(self, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        textes = tk.Frame(ligne, bg="white")
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)
        tk.Label(textes, text="Supprimer les doublons", font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
        tk.Label(textes, text="Cherche les fichiers dont le nom finit par (1), (2) ou (3) ET dont le "
                              "contenu est identique à l'original. Les autres sont listés, jamais "
                              "supprimés. Les doublons vont à la corbeille.",
                 font=("Arial", 9), fg="#6B7280", bg="white", anchor="w", justify="left",
                 wraplength=420).pack(fill="x")

        self.bouton_chercher = tk.Button(ligne, text="Chercher", font=("Arial", 10, "bold"),
                                         bg=BLEU, fg="white", relief="flat", cursor="hand2",
                                         padx=14, command=self.choisir_et_chercher)
        self.bouton_chercher.pack(side="right", padx=(6, 15), ipady=4)
        self.bouton_arreter = tk.Button(ligne, text="Arrêter", font=("Arial", 10, "bold"),
                                        bg=GRIS, relief="flat", cursor="hand2", padx=14,
                                        state="disabled", command=self.arret.set)
        self.bouton_arreter.pack(side="right", ipady=4)

                # wraplength : un texte trop long passe à la ligne au lieu d'être coupé.
        self.statut = tk.Label(self, text="Clique sur « Chercher » pour commencer.",
                               font=("Arial", 9), fg="#6B7280", bg=FOND, anchor="w",
                               justify="left", wraplength=600)
        self.statut.pack(fill="x", padx=32, pady=(2, 0))

        # ----- La barre du bas (rangée AVANT le tableau : elle reste visible même si la fenêtre rétrécit) -----
        bas = tk.Frame(self, bg=FOND)
        bas.pack(side="bottom", fill="x", padx=30, pady=(8, 20))

        self.label_totaux = tk.Label(bas, text="", font=("Arial", 10, "bold"), bg=FOND)
        self.label_totaux.pack(side="left")

        # "Appliquer" : grisé tant qu'une recherche n'a pas réussi ET qu'aucune ligne n'est sélectionnée.
        self.bouton_appliquer = tk.Button(bas, text="Mettre à la corbeille", font=("Arial", 10, "bold"),
                                          bg=ROUGE, fg="white", relief="flat", cursor="hand2",
                                          padx=14, state="disabled", command=self.appliquer)
        self.bouton_appliquer.pack(side="right", ipady=4)
        self.bouton_tout = tk.Button(bas, text="Tout sélectionner", font=("Arial", 10), bg=GRIS,
                                     relief="flat", cursor="hand2", padx=10, state="disabled",
                                     command=self.tout_selectionner)
        self.bouton_tout.pack(side="right", padx=6, ipady=4)
        self.bouton_ouvrir = tk.Button(bas, text="Ouvrir le dossier", font=("Arial", 10), bg=GRIS,
                                       relief="flat", cursor="hand2", padx=10, state="disabled",
                                       command=self.ouvrir_dossier)
        self.bouton_ouvrir.pack(side="right", ipady=4)

        # ----- Les résultats : deux onglets, chacun avec un tableau -----
        ttk.Style(self).configure("Treeview", rowheight=24)
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=30, pady=(8, 0))

        # Onglet 1 : les doublons confirmés (sélection multiple : Ctrl + clic, Maj + clic).
        cadre1, self.tableau = self.creer_tableau(
            [("taille", "Taille", 80, "e", False), ("fichier", "Doublon", 200, "w", False),
             ("original", "Original", 170, "w", False), ("etat", "État", 110, "w", False),
             ("dossier", "Dossier", 300, "w", True)], "extended")
        self.onglets.add(cadre1, text="Doublons confirmés")
        self.tableau.tag_configure("envoye", foreground=VERT)
        self.tableau.tag_configure("refuse", foreground=ROUGE)
        self.tableau.bind("<<TreeviewSelect>>", lambda evenement: self.maj_boutons())

        # Onglet 2 : à vérifier à la main (rien n'est supprimé ici).
        cadre2, self.tableau_verifier = self.creer_tableau(
            [("raison", "Raison", 150, "w", False), ("fichier", "Fichier", 220, "w", False),
             ("dossier", "Dossier", 400, "w", True)], "browse")
        self.onglets.add(cadre2, text="À vérifier à la main")

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
    # La recherche
    # ------------------------------------------------------------
    def choisir_et_chercher(self):
        """Demande le dossier, puis lance la recherche dans un fil de travail."""
        if self.occupe:
            return
        options = {"title": "Choisis le dossier où chercher les doublons"}
        if self.dernier_dossier and os.path.isdir(self.dernier_dossier):
            options["initialdir"] = self.dernier_dossier
        dossier = filedialog.askdirectory(**options)
        if not dossier:                             # un texte vide compte pour "faux" : tu as annulé
            return
        self.racine = os.path.normpath(dossier)     # askdirectory renvoie des "/" ; normpath remet les "\"
        self.dernier_dossier = self.racine

        # On repart de zéro.
        self.elements = []
        self.envoyes = 0
        self.octets = 0
        self.tableau.delete(*self.tableau.get_children())
        self.tableau_verifier.delete(*self.tableau_verifier.get_children())
        self.onglets.tab(0, text="Doublons confirmés")
        self.onglets.tab(1, text="À vérifier à la main")
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text=f"Recherche dans {self.racine} en cours...")

        threading.Thread(target=self.travail_recherche, args=(self.racine,), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_recherche(self, racine):
        """Tourne dans un FIL à part : il NE TOUCHE PAS à la fenêtre, il envoie des messages."""
        try:
            resultats = doublons.analyser(
                racine, self.arret,
                progression=lambda compteur: self.messages.put(("progression", compteur)))
            self.messages.put(("fin_recherche", resultats))
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
                self.statut.config(text=f"Recherche en cours... {message[1]} fichiers parcourus")
            elif genre == "fin_recherche":
                self.afficher_resultats(message[1])
                return                              # c'est fini : on ne se reprogramme pas
            elif genre == "corbeille":
                self.mettre_a_jour_ligne(*message[1:])
            elif genre == "fin_corbeille":
                self.terminer_envoi(message[1])
                return
            else:                                   # "erreur"
                self.definir_occupe(False)
                self.statut.config(text="Une erreur est survenue.")
                messagebox.showerror("Erreur", message[1])
                return
        self.after(100, self.surveiller)

    def afficher_resultats(self, resultats):
        """Remplit les deux tableaux avec le résultat de la recherche."""
        # Du plus gros au plus petit : les doublons les plus lourds en premier.
        self.elements = sorted(resultats["doublons"], key=lambda e: e["taille"], reverse=True)
        for numero, element in enumerate(self.elements):
            # iid = le numéro de la ligne : il permet de retrouver la fiche quand on sélectionne.
            self.tableau.insert("", "end", iid=str(numero), values=(
                doublons.lisible(element["taille"]), element["chemin"].name,
                element["original"].name, "", str(element["chemin"].parent)))
        self.onglets.tab(0, text=f"Doublons confirmés ({len(self.elements)})")

        for element in resultats["a_verifier"]:
            self.tableau_verifier.insert("", "end", values=(
                doublons.STATUTS[element["statut"]], element["chemin"].name,
                str(element["chemin"].parent)))
        self.onglets.tab(1, text=f"À vérifier à la main ({len(resultats['a_verifier'])})")

        total = doublons.lisible(sum(e["taille"] for e in self.elements))
        if resultats["interrompu"]:
            self.statut.config(text=f"Recherche interrompue : résultats PARTIELS "
                                    f"({resultats['compteur']} fichiers parcourus).")
        elif self.elements:                         # une liste non vide compte pour "vrai"
            self.statut.config(text=f"{len(self.elements)} doublon(s) confirmé(s), {total}. "
                                    "Ils sont sélectionnés : décoche ce que tu veux garder "
                                    "(Ctrl + clic), puis envoie à la corbeille.")
        else:
            self.statut.config(text=f"Aucun doublon confirmé ({resultats['compteur']} fichiers parcourus).")
        self.definir_occupe(False)
        # On sélectionne tout par défaut : un seul clic ensuite.
        self.tout_selectionner()

    # ------------------------------------------------------------
    # L'envoi à la corbeille
    # ------------------------------------------------------------
    def appliquer(self):
        """Demande confirmation, puis envoie la sélection à la corbeille (dans un fil de travail)."""
        if self.occupe:
            return
        if not doublons.corbeille_disponible():
            messagebox.showerror("Corbeille indisponible",
                                 "La bibliothèque send2trash n'est pas installée.\n\n"
                                 "Dans le terminal, tape :\n    pip install send2trash\n\n"
                                 "Rien n'a été supprimé.")
            return
        # On garde seulement les lignes sélectionnées qui ne sont pas déjà traitées.
        numeros = [int(iid) for iid in self.tableau.selection()
                   if not self.elements[int(iid)]["etat"]]
        if not numeros:
            return
        choisis = [self.elements[n] for n in numeros]
        total = doublons.lisible(sum(e["taille"] for e in choisis))
        liste = "\n".join(str(e["chemin"]) for e in choisis[:6])
        if len(choisis) > 6:
            liste += f"\n... et {len(choisis) - 6} autre(s)"
        if not messagebox.askyesno(
                "Confirmer",
                f"Envoyer {len(choisis)} doublon(s) ({total}) à la corbeille ?\n\n{liste}\n\n"
                "Chaque fichier est revérifié juste avant (original présent, contenu identique).\n"
                "Tu pourras les restaurer depuis la corbeille."):
            return

        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text="Envoi à la corbeille en cours...")
        threading.Thread(target=self.travail_corbeille, args=(numeros,), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_corbeille(self, numeros):
        """Tourne dans un FIL à part : envoie les fichiers un par un et prévient la fenêtre à chaque fois."""
        for numero in numeros:
            if self.arret.is_set():                 # tu as cliqué sur "Arrêter" : on s'arrête là
                break
            element = self.elements[numero]
            # Le garde-fou, AU MOMENT d'envoyer : c'est toujours un vrai doublon ?
            if not doublons.verifier_avant_corbeille(element["chemin"], element["original"]):
                self.messages.put(("corbeille", numero, False))      # False = refusé
                continue
            try:
                doublons.mettre_a_la_corbeille(element["chemin"])
                self.messages.put(("corbeille", numero, True))
            except Exception:                                       # fichier ouvert ailleurs, etc.
                self.messages.put(("corbeille", numero, False))
        self.messages.put(("fin_corbeille", self.arret.is_set()))

    def mettre_a_jour_ligne(self, numero, reussi):
        """Met à jour une ligne du tableau après son traitement."""
        element = self.elements[numero]
        if reussi:
            element["etat"] = "Corbeille ✓"
            self.envoyes += 1
            self.octets += element["taille"]
            etiquette = "envoye"
        else:
            element["etat"] = "Refusé"
            etiquette = "refuse"
        self.tableau.item(str(numero), tags=(etiquette,), values=(
            doublons.lisible(element["taille"]), element["chemin"].name,
            element["original"].name, element["etat"], str(element["chemin"].parent)))
        self.maj_boutons()

    def terminer_envoi(self, interrompu):
        """Appelée quand l'envoi est fini."""
        refuses = sum(1 for e in self.elements if e["etat"] == "Refusé")
        texte = ("Envoi interrompu. " if interrompu else "Terminé. ") + \
                f"{self.envoyes} fichier(s) à la corbeille ({doublons.lisible(self.octets)})."
        if refuses:
            texte += f" {refuses} refusé(s) : le fichier avait changé ou est ouvert ailleurs."
        texte += " Vide la corbeille pour libérer la place."
        self.statut.config(text=texte)
        self.definir_occupe(False)

    # ------------------------------------------------------------
    # Les petits boutons et le total
    # ------------------------------------------------------------
    def tout_selectionner(self):
        self.tableau.selection_set(self.tableau.get_children())

    def ouvrir_dossier(self):
        """Ouvre dans l'Explorateur Windows le dossier du premier doublon sélectionné."""
        selection = self.tableau.selection()
        if not selection:
            return
        try:
            os.startfile(str(self.elements[int(selection[0])]["chemin"].parent))   # n'existe que sous Windows
        except (AttributeError, OSError) as erreur:
            messagebox.showerror("Ouverture impossible", str(erreur))

    def definir_occupe(self, occupe):
        """Pendant une recherche ou un envoi : on grise ce qui ne doit pas être cliqué."""
        self.occupe = occupe
        self.bouton_chercher.config(state="disabled" if occupe else "normal")
        self.bouton_arreter.config(state="normal" if occupe else "disabled")
        self.maj_boutons()

    def maj_boutons(self):
        """Met à jour le total affiché et active / grise les boutons du bas."""
        # On ne compte que les lignes sélectionnées pas encore traitées.
        selection = [self.elements[int(iid)] for iid in self.tableau.selection()
                     if not self.elements[int(iid)]["etat"]]
        self.label_totaux.config(
            text=f"Sélection : {len(selection)} fichier(s), "
                 f"{doublons.lisible(sum(e['taille'] for e in selection))}"
                 f"        Envoyés : {self.envoyes}")
        self.bouton_appliquer.config(state="normal" if selection and not self.occupe else "disabled")
        self.bouton_ouvrir.config(
            state="normal" if self.tableau.selection() and not self.occupe else "disabled")
        self.bouton_tout.config(state="normal" if self.elements and not self.occupe else "disabled")