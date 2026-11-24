
import os                         # os.path : vérifier qu'un dossier existe, os.startfile : l'Explorateur
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from tkinter import filedialog, messagebox, ttk      # choix de dossier, messages, tableaux

from outils.gagner_de_la_place import rangement      
from ui.style import BLEU, FOND, GRIS, ROUGE, VERT


class PageRanger(tk.Frame):
    """Chercher, appliquer, annuler. Le garde-fou est revérifié fichier par fichier AU MOMENT
    de déplacer : si un fichier a changé depuis la recherche, il est refusé."""

    def __init__(self, zone, titre):
        super().__init__(zone, bg=FOND)
        # place() : la page occupe 100 % de la zone (toutes les pages sont empilées au même endroit).
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.racine = None                # le dossier cherché
        self.elements = []                # les fichiers à ranger (une "fiche" par ligne du tableau)
        self.generation = 0               # change à chaque recherche (pour ne pas confondre deux recherches)
        self.journal = []                 # tout ce qui a été déplacé : de quoi ANNULER
        self.remis = set()                # les numéros du journal déjà remis pendant une annulation
        self.prete = False                # vrai si une recherche a réussi : "Appliquer" est alors possible
        self.occupe = False               # vrai pendant une recherche, un déplacement ou une annulation
        self.dernier_dossier = None       # le dernier dossier choisi (la fenêtre s'y rouvre)
        self.arret = threading.Event()    # l'interrupteur "Arrêter" (lu par le fil de travail)
        self.messages = queue.Queue()     # la boîte aux lettres du fil de travail vers la fenêtre

        tk.Label(self, text=titre, font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # ----- La ligne de l'outil (la boîte blanche) -----
        ligne = tk.Frame(self, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        textes = tk.Frame(ligne, bg="white")
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)
        tk.Label(textes, text="Ranger un dossier", font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
        tk.Label(textes, text="Range les fichiers d'un dossier dans des sous-dossiers selon leur "
                              "extension (Images, Documents, Archives...). Rien n'est supprimé "
                              "ni écrasé, et tu peux annuler.",
                 font=("Arial", 9), fg="#6B7280", bg="white", anchor="w", justify="left",
                 wraplength=420).pack(fill="x")
        # La case à cocher : que faire des fichiers dont l'extension est inconnue ?
        self.var_inconnus = tk.BooleanVar(value=True)
        tk.Checkbutton(textes, text="Mettre les fichiers inconnus dans « Autres »",
                       variable=self.var_inconnus, font=("Arial", 9), bg="white",
                       activebackground="white", anchor="w", cursor="hand2"
                       ).pack(anchor="w", pady=(4, 0))
        # trace_add("write", ...) = "appelle cette fonction dès que la valeur change".
        self.var_inconnus.trace_add("write", lambda *arguments: self.invalider())

        # Le premier élément placé avec side="right" est celui tout à droite.
        self.bouton_appliquer = tk.Button(ligne, text="Appliquer", font=("Arial", 10, "bold"),
                                          bg=ROUGE, fg="white", relief="flat", cursor="hand2",
                                          padx=14, state="disabled", command=self.appliquer)
        self.bouton_appliquer.pack(side="right", padx=(6, 15), ipady=4)
        self.bouton_chercher = tk.Button(ligne, text="Chercher", font=("Arial", 10, "bold"),
                                         bg=BLEU, fg="white", relief="flat", cursor="hand2",
                                         padx=14, command=self.choisir_et_chercher)
        self.bouton_chercher.pack(side="right", padx=(6, 0), ipady=4)

        self.statut = tk.Label(self, text="Clique sur « Chercher » pour commencer.",
                               font=("Arial", 9), fg="#6B7280", bg=FOND, anchor="w")
        self.statut.pack(fill="x", padx=32, pady=(2, 0))


        bas = tk.Frame(self, bg=FOND)
        bas.pack(side="bottom", fill="x", padx=30, pady=(8, 20))

        self.label_totaux = tk.Label(bas, text="", font=("Arial", 10, "bold"), bg=FOND)
        self.label_totaux.pack(side="left")

        self.bouton_arreter = tk.Button(bas, text="Arrêter", font=("Arial", 10), bg=GRIS,
                                        relief="flat", cursor="hand2", padx=10, state="disabled",
                                        command=self.arret.set)
        self.bouton_arreter.pack(side="right", ipady=4)
        self.bouton_annuler = tk.Button(bas, text="Annuler le rangement", font=("Arial", 10, "bold"),
                                        bg=GRIS, relief="flat", cursor="hand2", padx=10,
                                        state="disabled", command=self.annuler)
        self.bouton_annuler.pack(side="right", padx=6, ipady=4)
        self.bouton_ouvrir = tk.Button(bas, text="Ouvrir le dossier", font=("Arial", 10), bg=GRIS,
                                       relief="flat", cursor="hand2", padx=10, state="disabled",
                                       command=self.ouvrir_dossier)
        self.bouton_ouvrir.pack(side="right", ipady=4)

        # ----- Les résultats : deux onglets, chacun avec un tableau -----
        ttk.Style(self).configure("Treeview", rowheight=24)
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=30, pady=(8, 0))

        cadre1, self.tableau = self.creer_tableau(
            [("fichier", "Fichier", 230, "w", False), ("taille", "Taille", 80, "e", False),
             ("cible", "Va dans", 260, "w", True), ("etat", "État", 110, "w", False)])
        self.onglets.add(cadre1, text="À ranger")
        self.tableau.tag_configure("fait", foreground=VERT)
        self.tableau.tag_configure("refuse", foreground=ROUGE)
        self.tableau.tag_configure("annule", foreground="#6B7280")

        cadre2, self.tableau_laisses = self.creer_tableau(
            [("fichier", "Fichier", 280, "w", False), ("raison", "Pourquoi on n'y touche pas", 300, "w", True)])
        self.onglets.add(cadre2, text="Laissés en place")

        self.maj_boutons()

    def creer_tableau(self, colonnes):
        """Fabrique un tableau (ttk.Treeview) avec une barre de défilement. Renvoie (cadre, tableau).
        Chaque colonne = (identifiant, titre, largeur, alignement, s'étire ?)."""
        cadre = tk.Frame(self.onglets)
        arbre = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings",
                             selectmode="browse")
        for identifiant, titre, largeur, alignement, s_etire in colonnes:
            arbre.heading(identifiant, text=titre)
            arbre.column(identifiant, width=largeur, anchor=alignement, stretch=s_etire)
        barre = ttk.Scrollbar(cadre, orient="vertical", command=arbre.yview)
        arbre.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        arbre.pack(side="left", fill="both", expand=True)
        return cadre, arbre

    # ------------------------------------------------------------
    # Les réglages
    # ------------------------------------------------------------
    def invalider(self):
        """Un réglage a changé : la recherche faite n'est plus valable. "Appliquer" est regrisé,
        pour qu'on n'applique jamais d'autres réglages que ceux qu'on a cherchés."""
        if self.occupe or not self.prete:
            return
        self.prete = False
        self.maj_boutons()
        self.statut.config(text="Réglage modifié : refais « Chercher » avant d'appliquer.")

    # ------------------------------------------------------------
    # La recherche
    # ------------------------------------------------------------
    def choisir_et_chercher(self):
        """Demande le dossier, vérifie qu'on a le droit de le ranger, puis lance la recherche."""
        if self.occupe:
            return
        options = {"title": "Choisis le dossier à ranger"}
        if self.dernier_dossier and os.path.isdir(self.dernier_dossier):
            options["initialdir"] = self.dernier_dossier
        dossier = filedialog.askdirectory(**options)
        if not dossier:                             # un texte vide compte pour "faux" : tu as annulé
            return
        dossier = os.path.normpath(dossier)         # askdirectory renvoie des "/" ; normpath remet les "\"
        # Le garde-fou : certains dossiers (un disque, Windows, un projet...) sont refusés.
        raison = rangement.dossier_interdit(dossier)
        if raison:
            messagebox.showerror("Dossier refusé", f"{dossier}\n\n{raison}")
            return
        self.racine = dossier
        self.dernier_dossier = dossier

        # On repart de zéro.
        self.generation += 1
        self.elements = []
        self.prete = False
        self.tableau.delete(*self.tableau.get_children())
        self.tableau_laisses.delete(*self.tableau_laisses.get_children())
        self.onglets.tab(0, text="À ranger")
        self.onglets.tab(1, text="Laissés en place")
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text=f"Recherche dans {self.racine}...")

        threading.Thread(target=self.travail_recherche,
                         args=(self.racine, self.var_inconnus.get()), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_recherche(self, racine, inconnus):
        """Tourne dans un FIL à part : il NE TOUCHE PAS à la fenêtre, il envoie des messages."""
        try:
            self.messages.put(("fin_recherche", rangement.chercher(racine, inconnus, self.arret)))
        except Exception as erreur:                 # une erreur imprévue : on la montre, sans planter
            self.messages.put(("erreur", str(erreur)))

    def afficher_resultats(self, resultats):
        """Remplit les deux tableaux avec le résultat de la recherche."""
        self.elements = resultats["deplacements"]
        for numero, element in enumerate(self.elements):
            # iid = le numéro de la ligne : il permet de retrouver la fiche.
            self.tableau.insert("", "end", iid=str(numero), values=(
                element["source"].name, rangement.lisible(element["taille"]),
                self.nom_cible(element), ""))
        self.onglets.tab(0, text=f"À ranger ({len(self.elements)})")
        for nom, raison in resultats["laisses"]:
            self.tableau_laisses.insert("", "end", values=(nom, raison))
        self.onglets.tab(1, text=f"Laissés en place ({len(resultats['laisses'])})")

        reste = f" ({resultats['sous_dossiers']} sous-dossier(s) ignoré(s))" if resultats["sous_dossiers"] else ""
        if resultats["interrompu"]:
            self.statut.config(text="Recherche interrompue : résultats PARTIELS, applique impossible.")
        elif self.elements:                         # une liste non vide compte pour "vrai"
            total = rangement.lisible(sum(e["taille"] for e in self.elements))
            self.statut.config(text=f"{len(self.elements)} fichier(s) à ranger ({total}){reste}. "
                                    "Rien n'est déplacé : clique sur « Appliquer » si ça te convient.")
            self.prete = True
        else:
            self.statut.config(text=f"Rien à ranger dans ce dossier{reste}.")
        self.definir_occupe(False)

    @staticmethod
    def nom_cible(element):
        """Le nom de destination affiché : Images/photo.jpg"""
        return f"{element['cible'].parent.name}/{element['cible'].name}"

    # ------------------------------------------------------------
    # Le déplacement
    # ------------------------------------------------------------
    def appliquer(self):
        """Demande confirmation, puis déplace les fichiers (dans un fil de travail)."""
        if self.occupe or not self.prete:
            return
        if not messagebox.askyesno(
                "Confirmer le rangement",
                f"Dossier :\n{self.racine}\n\n"
                f"{len(self.elements)} fichier(s) seront DÉPLACÉS dans des sous-dossiers "
                "(Images, Documents...).\n"
                "Rien n'est supprimé ni écrasé. Tant que l'application reste ouverte, "
                "tu peux annuler avec « Annuler le rangement ».\n\nContinuer ?"):
            return
        self.prete = False                          # une seule application par recherche
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text="Rangement en cours...")
        threading.Thread(target=self.travail_deplacement, args=(list(self.elements),),
                         daemon=True).start()
        self.after(100, self.surveiller)

    def travail_deplacement(self, elements):
        """Tourne dans un FIL à part : déplace les fichiers un par un et prévient la fenêtre à chaque fois."""
        for numero, element in enumerate(elements):
            if self.arret.is_set():                 # tu as cliqué sur "Arrêter" : on s'arrête là
                break
            try:
                resultat = rangement.deplacer(element)    # (cible, dossier_cree) ou None (refusé)
            except Exception:
                resultat = None
            self.messages.put(("deplace", numero, resultat))
        self.messages.put(("fin_deplacement", self.arret.is_set()))

    def mettre_a_jour_ligne(self, numero, resultat):
        """Met à jour une ligne du tableau après son déplacement, et note le déplacement dans le journal."""
        element = self.elements[numero]
        if resultat is None:
            element["etat"] = "Refusé"
            etiquette, cible = "refuse", self.nom_cible(element)
        else:
            cible_reelle, dossier_cree = resultat
            element["etat"] = "Déplacé ✓"
            etiquette = "fait"
            cible = f"{cible_reelle.parent.name}/{cible_reelle.name}"
            # Le journal : de quoi remettre le fichier à sa place (avec la génération de la recherche).
            self.journal.append({"origine": element["source"], "cible": cible_reelle,
                                 "cree": dossier_cree, "generation": self.generation,
                                 "numero": numero})
        self.tableau.item(str(numero), tags=(etiquette,), values=(
            element["source"].name, rangement.lisible(element["taille"]), cible, element["etat"]))
        self.maj_boutons()

    def terminer_deplacement(self, interrompu):
        faits = sum(1 for e in self.elements if e["etat"] == "Déplacé ✓")
        refuses = sum(1 for e in self.elements if e["etat"] == "Refusé")
        texte = ("Rangement interrompu. " if interrompu else "Terminé. ") + f"{faits} fichier(s) déplacé(s)."
        if refuses:
            texte += f" {refuses} refusé(s) : le fichier avait changé ou est ouvert ailleurs."
        if faits:
            texte += " Tu peux annuler avec « Annuler le rangement »."
        self.statut.config(text=texte)
        self.definir_occupe(False)

    # ------------------------------------------------------------
    # L'annulation
    # ------------------------------------------------------------
    def annuler(self):
        """Remet à leur place les fichiers déplacés (dans un fil de travail)."""
        if self.occupe or not self.journal:
            return
        if not messagebox.askyesno(
                "Annuler le rangement",
                f"Remettre {len(self.journal)} fichier(s) à leur place d'origine ?\n\n"
                "Un fichier qui a été modifié ou déplacé depuis le rangement, ou dont "
                "l'ancienne place est déjà prise, ne sera pas touché."):
            return
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text="Annulation en cours...")
        # On remet les fichiers dans l'ordre INVERSE : le dernier rangé est le premier remis.
        threading.Thread(target=self.travail_annulation, args=(list(enumerate(self.journal))[::-1],),
                         daemon=True).start()
        self.after(100, self.surveiller)

    def travail_annulation(self, entrees):
        """Tourne dans un FIL à part : remet les fichiers un par un."""
        for indice, entree in entrees:
            if self.arret.is_set():
                break
            try:
                reussi = rangement.annuler(entree["origine"], entree["cible"], entree["cree"])
            except Exception:
                reussi = False
            self.messages.put(("annule", indice, reussi))
        self.messages.put(("fin_annulation", self.arret.is_set()))

    def terminer_annulation(self, remis, interrompu):
        """Appelée quand l'annulation est finie : on retire du journal ce qui a été remis."""
        for indice in remis:
            entree = self.journal[indice]
            # Si le tableau affiche toujours la même recherche, on met la ligne à jour.
            if entree["generation"] == self.generation:
                element = self.elements[entree["numero"]]
                element["etat"] = "Annulé"
                self.tableau.item(str(entree["numero"]), tags=("annule",), values=(
                    element["source"].name, rangement.lisible(element["taille"]),
                    self.nom_cible(element), "Annulé"))
        self.journal = [e for i, e in enumerate(self.journal) if i not in remis]
        reste = len(self.journal)
        texte = ("Annulation interrompue. " if interrompu else "Terminé. ") + \
                f"{len(remis)} fichier(s) remis à leur place."
        if reste and not interrompu:
            texte += f" Non remis : {reste} (modifié, déplacé, ou ancienne place déjà prise)."
        self.statut.config(text=texte)
        self.definir_occupe(False)

    # ------------------------------------------------------------
    # Surveiller le fil de travail
    # ------------------------------------------------------------
    def surveiller(self):
        """Appelée toutes les 100 ms : lit les messages du fil de travail et met l'écran à jour."""
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            genre = message[0]                      # message[0] = le 1er élément du message
            if genre == "fin_recherche":
                self.afficher_resultats(message[1])
                return                              # c'est fini : on ne se reprogramme pas
            elif genre == "deplace":
                self.mettre_a_jour_ligne(*message[1:])
            elif genre == "fin_deplacement":
                self.terminer_deplacement(message[1])
                return
            elif genre == "annule":
                if message[2]:
                    self.remis.add(message[1])
            elif genre == "fin_annulation":
                self.terminer_annulation(self.remis, message[1])
                self.remis = set()
                return
            else:                                   # "erreur"
                self.definir_occupe(False)
                self.statut.config(text="Une erreur est survenue.")
                messagebox.showerror("Erreur", message[1])
                return
        self.after(100, self.surveiller)

    # ------------------------------------------------------------
    # Les petits boutons
    # ------------------------------------------------------------
    def ouvrir_dossier(self):
        """Ouvre dans l'Explorateur Windows le dossier rangé."""
        if not self.racine:
            return
        try:
            os.startfile(self.racine)               # n'existe que sous Windows
        except (AttributeError, OSError) as erreur:
            messagebox.showerror("Ouverture impossible", str(erreur))

    def definir_occupe(self, occupe):
        """Pendant un travail : on grise ce qui ne doit pas être cliqué."""
        self.occupe = occupe
        self.bouton_arreter.config(state="normal" if occupe else "disabled")
        self.maj_boutons()

    def maj_boutons(self):
        """Met à jour le total affiché et active / grise les boutons."""
        libre = not self.occupe
        self.bouton_chercher.config(state="normal" if libre else "disabled")
        # "Appliquer" : seulement après une recherche réussie, et jamais pendant un travail.
        self.bouton_appliquer.config(state="normal" if libre and self.prete and self.elements else "disabled")
        self.bouton_annuler.config(state="normal" if libre and self.journal else "disabled")
        self.bouton_ouvrir.config(state="normal" if libre and self.racine else "disabled")
        self.label_totaux.config(text=f"Annulable : {len(self.journal)} fichier(s)" if self.journal else "")