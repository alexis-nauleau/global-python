# ============================================================
# page_projets.py : la page "Nettoyer un projet web".
# ============================================================
import os                         
import queue                      
import threading                  # pour travailler en arrière-plan SANS bloquer la fenêtre
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk      

from outils.gagner_de_la_place import projets       
from ui.composants import barre_du_bas, bouton, carte_outil, ligne_statut, tableau, titre_page
from ui.style import BLEU, FOND, GRIS, ORANGE, ROUGE, VERT


class PageProjets(tk.Frame):
    """Chercher, puis supprimer. Le garde-fou est revérifié projet par projet AU MOMENT de supprimer :
    si un projet a été modifié depuis la recherche, il est refusé."""

    def __init__(self, zone, titre):
        super().__init__(zone, bg=FOND)
        # place() : la page occupe 100 % de la zone (toutes les pages sont empilées au même endroit).
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.racine = None                # le dossier qui contient les projets
        self.jours = projets.JOURS_AVANT_DORMANT    # le réglage utilisé par la dernière recherche
        self.elements = []                # les projets dormants (une "fiche" par ligne du tableau)
        self.liberes = 0                  # combien d'octets on a libérés au total
        self.prete = False                # vrai si une recherche a réussi : la suppression est alors possible
        self.occupe = False               # vrai pendant une recherche ou une suppression
        self.dernier_dossier = None       # le dernier dossier choisi (la fenêtre s'y rouvre)
        self.arret = threading.Event()    # l'interrupteur "Arrêter" (lu par le fil de travail)
        self.messages = queue.Queue()     # la boîte aux lettres du fil de travail vers la fenêtre

        titre_page(self, titre)

        # ----- La ligne de l'outil (la boîte blanche) -----
        ligne, textes = carte_outil(
            self, "Nettoyer les projets dormants",
            f"Supprime le dossier {projets.DOSSIER_A_SUPPRIMER} des projets web qui n'ont pas "
            f"bougé depuis un certain temps. Le code n'est jamais touché : "
            f"« npm install » recrée le dossier.")
        # Le réglage : combien de jours sans modification avant qu'un projet soit "dormant".
        reglage = tk.Frame(textes, bg="white")
        reglage.pack(fill="x", pady=(6, 0))
        tk.Label(reglage, text="Dormant après (jours) :", font=("Arial", 9), bg="white").pack(side="left")
        self.var_jours = tk.StringVar(value=str(projets.JOURS_AVANT_DORMANT))
        ttk.Spinbox(reglage, from_=7, to=730, increment=7, width=6,
                    textvariable=self.var_jours).pack(side="left", padx=6)
        # trace_add("write", ...) = "appelle cette fonction dès que la valeur change".
        self.var_jours.trace_add("write", lambda *arguments: self.invalider())

        # Le premier élément placé avec side="right" est celui tout à droite.
        self.bouton_chercher = bouton(ligne, "Chercher", BLEU, self.choisir_et_chercher)
        self.bouton_chercher.pack(side="right", padx=(6, 15), ipady=4)
        self.bouton_arreter = bouton(ligne, "Arrêter", GRIS, self.arret.set, state="disabled")
        self.bouton_arreter.pack(side="right", ipady=4)

        self.statut = ligne_statut(self, "Clique sur « Chercher » pour commencer.")

        # ----- La barre du bas (rangée AVANT le tableau : elle reste visible même si la fenêtre rétrécit) -----
        bas = barre_du_bas(self)

        self.label_totaux = tk.Label(bas, text="", font=("Arial", 10, "bold"), bg=FOND)
        self.label_totaux.pack(side="left")

        # "Supprimer" : grisé tant qu'une recherche n'a pas réussi ET qu'aucune ligne n'est sélectionnée.
        self.bouton_supprimer = bouton(bas, f"Supprimer {projets.DOSSIER_A_SUPPRIMER}", ROUGE,
                                       self.appliquer, state="disabled")
        self.bouton_supprimer.pack(side="right", ipady=4)
        self.bouton_tout = bouton(bas, "Tout sélectionner", GRIS, self.tout_selectionner,
                                  gras=False, padx=10, state="disabled")
        self.bouton_tout.pack(side="right", padx=6, ipady=4)
        self.bouton_ouvrir = bouton(bas, "Ouvrir le dossier", GRIS, self.ouvrir_dossier,
                                    gras=False, padx=10, state="disabled")
        self.bouton_ouvrir.pack(side="right", ipady=4)

        # ----- Les résultats : deux onglets, chacun avec un tableau -----
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=30, pady=(8, 0))

        # Onglet 1 : les projets dormants (sélection multiple : Ctrl + clic, Maj + clic).
        cadre1, self.tableau = tableau(
            self.onglets,
            [("projet", "Projet", 220, "w", False), ("date", "Dernière modif.", 110, "w", False),
             ("jours", "Jours", 60, "e", False), ("taille", projets.DOSSIER_A_SUPPRIMER, 100, "e", False),
             ("etat", "État", 120, "w", True)], "extended")
        self.onglets.add(cadre1, text="Projets dormants")
        # Une "étiquette" (tag) colore les lignes : vert = supprimé, orange = partiel, rouge = refusé.
        self.tableau.tag_configure("fait", foreground=VERT)
        self.tableau.tag_configure("partiel", foreground=ORANGE)
        self.tableau.tag_configure("refuse", foreground=ROUGE)
        self.tableau.bind("<<TreeviewSelect>>", lambda evenement: self.maj_boutons())

        # Onglet 2 : les projets qu'on laisse en place, avec la raison.
        cadre2, self.tableau_laisses = tableau(
            self.onglets,
            [("projet", "Projet", 220, "w", False),
             ("raison", "Pourquoi on n'y touche pas", 400, "w", True)])
        self.onglets.add(cadre2, text="Laissés en place")

        self.maj_boutons()

    # ------------------------------------------------------------
    # Les réglages
    # ------------------------------------------------------------
    def lire_jours(self):
        """Lit le réglage et le vérifie. Renvoie un nombre, ou None (et affiche une erreur)."""
        try:
            jours = int(self.var_jours.get())
        except ValueError:
            messagebox.showerror("Réglage invalide", "Le nombre de jours doit être un nombre entier.")
            return None
        if jours < 7:
            messagebox.showerror("Réglage invalide", "Il faut au moins 7 jours : en dessous, "
                                 "tu supprimerais le dossier de projets sur lesquels tu travailles.")
            return None
        return jours

    def invalider(self):
        """Un réglage a changé : la recherche faite n'est plus valable. La suppression est regrisée,
        pour qu'on ne supprime jamais avec d'autres réglages que ceux qu'on a cherchés."""
        if self.occupe or not self.prete:
            return
        self.prete = False
        self.maj_boutons()
        self.statut.config(text="Réglage modifié : refais « Chercher » avant de supprimer.")

    # ------------------------------------------------------------
    # La recherche
    # ------------------------------------------------------------
    def choisir_et_chercher(self):
        """Vérifie le réglage, demande le dossier, puis lance la recherche dans un fil de travail."""
        if self.occupe:
            return
        jours = self.lire_jours()
        if jours is None:
            return
        options = {"title": "Choisis le dossier qui contient tes projets"}
        if self.dernier_dossier and os.path.isdir(self.dernier_dossier):
            options["initialdir"] = self.dernier_dossier
        dossier = filedialog.askdirectory(**options)
        if not dossier:                             # un texte vide compte pour "faux" : tu as annulé
            return
        dossier = os.path.normpath(dossier)         # askdirectory renvoie des "/" ; normpath remet les "\"
        raison = projets.dossier_interdit(dossier)  # le garde-fou : un disque ou un dossier système est refusé
        if raison:
            messagebox.showerror("Dossier refusé", f"{dossier}\n\n{raison}")
            return
        self.racine = dossier
        self.dernier_dossier = dossier
        self.jours = jours

        # On repart de zéro.
        self.elements = []
        self.liberes = 0
        self.prete = False
        self.tableau.delete(*self.tableau.get_children())
        self.tableau_laisses.delete(*self.tableau_laisses.get_children())
        self.onglets.tab(0, text="Projets dormants")
        self.onglets.tab(1, text="Laissés en place")
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text=f"Recherche dans {self.racine}...")

        threading.Thread(target=self.travail_recherche, args=(self.racine, jours), daemon=True).start()
        self.after(100, self.surveiller)

    def travail_recherche(self, racine, jours):
        """Tourne dans un FIL à part : il NE TOUCHE PAS à la fenêtre, il envoie des messages."""
        try:
            resultats = projets.chercher(
                racine, jours, self.arret,
                progression=lambda compteur: self.messages.put(("progression", compteur)))
            self.messages.put(("fin_recherche", resultats))
        except Exception as erreur:                 # une erreur imprévue : on la montre, sans planter
            self.messages.put(("erreur", str(erreur)))

    def afficher_resultats(self, resultats):
        """Remplit les deux tableaux avec le résultat de la recherche."""
        # Du plus gros au plus petit : les projets qui libèrent le plus de place en premier.
        self.elements = sorted(resultats["dormants"], key=lambda p: p["taille"], reverse=True)
        for numero, element in enumerate(self.elements):
            # iid = le numéro de la ligne : il permet de retrouver la fiche quand on sélectionne.
            self.tableau.insert("", "end", iid=str(numero), values=self.valeurs(element))
        self.onglets.tab(0, text=f"Projets dormants ({len(self.elements)})")
        for nom, raison in resultats["laisses"]:
            self.tableau_laisses.insert("", "end", values=(nom, raison))
        self.onglets.tab(1, text=f"Laissés en place ({len(resultats['laisses'])})")

        total = projets.lisible(sum(e["taille"] for e in self.elements))
        if resultats["interrompu"]:
            self.statut.config(text=f"Recherche interrompue : résultats PARTIELS, suppression impossible "
                                    f"({resultats['analyses']} projet(s) lus).")
        elif self.elements:                         # une liste non vide compte pour "vrai"
            self.statut.config(text=f"{resultats['analyses']} projet(s) analysé(s) : {len(self.elements)} dormant(s), "
                                    f"{total} récupérables. Ils sont sélectionnés : décoche ce que tu veux "
                                    "garder (Ctrl + clic), puis supprime.")
            self.prete = True
        else:
            self.statut.config(text=f"{resultats['analyses']} projet(s) analysé(s) : "
                                    f"rien à libérer (aucun projet dormant avec un lockfile).")
        self.definir_occupe(False)
        # On sélectionne tout par défaut : un seul clic ensuite.
        self.tout_selectionner()

    @staticmethod
    def valeurs(element, etat=""):
        """Les valeurs affichées dans une ligne du tableau (dans l'ordre des colonnes)."""
        return (element["nom"], datetime.fromtimestamp(element["derniere"]).strftime("%d/%m/%Y"),
                element["jours"], projets.lisible(element["taille"]), etat)

    # ------------------------------------------------------------
    # La suppression
    # ------------------------------------------------------------
    def selection_possible(self):
        """Les numéros des lignes sélectionnées qui ne sont pas déjà traitées."""
        return [int(iid) for iid in self.tableau.selection() if not self.elements[int(iid)]["etat"]]

    def appliquer(self):
        """Demande confirmation, puis supprime les node_modules sélectionnés (dans un fil de travail)."""
        if self.occupe or not self.prete:
            return
        numeros = self.selection_possible()
        if not numeros:
            return
        choisis = [self.elements[n] for n in numeros]
        total = projets.lisible(sum(e["taille"] for e in choisis))
        liste = "\n".join(str(e["cible"]) for e in choisis[:6])
        if len(choisis) > 6:
            liste += f"\n... et {len(choisis) - 6} autre(s)"
        if not messagebox.askyesno(
                "Confirmer la suppression",
                f"Supprimer {len(choisis)} dossier(s) {projets.DOSSIER_A_SUPPRIMER} ({total}) ?\n\n{liste}\n\n"
                "Ferme VS Code et les serveurs de développement de ces projets.\n"
                "Ton code n'est pas touché : « npm install » recrée le dossier.\n"
                "La suppression est DÉFINITIVE (pas de corbeille)."):
            return

        self.prete = False                          # une seule suppression par recherche
        self.arret.clear()
        self.definir_occupe(True)
        self.statut.config(text="Suppression en cours (un gros dossier peut prendre un moment)...")
        threading.Thread(target=self.travail_suppression, args=(numeros, self.jours),
                         daemon=True).start()
        self.after(100, self.surveiller)

    def travail_suppression(self, numeros, jours):
        """Tourne dans un FIL à part : supprime les dossiers un par un et prévient la fenêtre à chaque fois."""
        for numero in numeros:
            if self.arret.is_set():                 # tu as cliqué sur "Arrêter" : on s'arrête après celui-ci
                break
            cible = self.elements[numero]["cible"]
            # Le garde-fou, AU MOMENT de supprimer : c'est toujours un projet dormant ?
            if projets.verifier_avant_suppression(cible, jours):
                self.messages.put(("supprime", numero, None, None))      # None = refusé
                continue
            avant = projets.taille_dossier(cible)
            try:
                projets.supprimer(cible)
            except Exception:                       # un fichier utilisé par un programme, etc.
                pass
            apres = projets.taille_dossier(cible) if cible.exists() else 0
            self.messages.put(("supprime", numero, avant, apres))
        self.messages.put(("fin_suppression", self.arret.is_set()))

    def mettre_a_jour_ligne(self, numero, avant, apres):
        """Met à jour une ligne du tableau après son traitement."""
        element = self.elements[numero]
        if avant is None:                           # le garde-fou a refusé
            element["etat"] = "Refusé"
            etiquette = "refuse"
        else:
            self.liberes += avant - apres           # on ajoute ce qui a vraiment été libéré
            if apres:                               # il reste des fichiers (utilisés par un programme)
                element["etat"] = "Partiel"
                etiquette = "partiel"
                element["taille"] = apres
            else:
                element["etat"] = "Supprimé ✓"
                etiquette = "fait"
        self.tableau.item(str(numero), tags=(etiquette,), values=self.valeurs(element, element["etat"]))
        self.maj_boutons()

    def terminer_suppression(self, interrompu):
        """Appelée quand la suppression est finie."""
        refuses = sum(1 for e in self.elements if e["etat"] == "Refusé")
        partiels = sum(1 for e in self.elements if e["etat"] == "Partiel")
        texte = ("Suppression interrompue. " if interrompu else "Terminé. ") + \
                f"{projets.lisible(self.liberes)} libérés."
        if refuses:
            texte += f" {refuses} refusé(s) : le projet avait changé."
        if partiels:
            texte += f" {partiels} partiel(s) : un programme utilise encore des fichiers (ferme VS Code)."
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
            if genre == "progression":
                self.statut.config(text=f"Recherche en cours... {message[1]} projet(s) lus")
            elif genre == "fin_recherche":
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

    # ------------------------------------------------------------
    # Les petits boutons et le total
    # ------------------------------------------------------------
    def tout_selectionner(self):
        self.tableau.selection_set(self.tableau.get_children())

    def ouvrir_dossier(self):
        """Ouvre dans l'Explorateur Windows le dossier du premier projet sélectionné."""
        selection = self.tableau.selection()
        if not selection:
            return
        try:
            os.startfile(str(self.elements[int(selection[0])]["cible"].parent))   # n'existe que sous Windows
        except (AttributeError, OSError) as erreur:
            messagebox.showerror("Ouverture impossible", str(erreur))

    def definir_occupe(self, occupe):
        """Pendant un travail : on grise ce qui ne doit pas être cliqué."""
        self.occupe = occupe
        self.bouton_chercher.config(state="disabled" if occupe else "normal")
        self.bouton_arreter.config(state="normal" if occupe else "disabled")
        self.maj_boutons()

    def maj_boutons(self):
        """Met à jour le total affiché et active / grise les boutons."""
        selection = [self.elements[n] for n in self.selection_possible()]
        self.label_totaux.config(
            text=f"Sélection : {len(selection)} projet(s), "
                 f"{projets.lisible(sum(e['taille'] for e in selection))}"
                 f"        Libéré : {projets.lisible(self.liberes)}")
        # "Supprimer" : seulement après une recherche réussie, avec une sélection, jamais pendant un travail.
        self.bouton_supprimer.config(
            state="normal" if selection and self.prete and not self.occupe else "disabled")
        self.bouton_ouvrir.config(
            state="normal" if self.tableau.selection() and not self.occupe else "disabled")
        self.bouton_tout.config(state="normal" if self.elements and not self.occupe else "disabled")