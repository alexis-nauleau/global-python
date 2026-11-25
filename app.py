


import os                         
import subprocess                 # pour LANCER un autre programme (nos scripts)
import sys                        # sys.executable = le Python qui fait tourner CE programme
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox      

from ui.page_doublons import PageDoublons 
from ui.page_ranger import PageRanger                      
from ui.page_caches import PageCaches              
from ui.page_images import PageImages 
from ui.page_projets import PageProjets
from ui.page_ranger_photos import PageRangerPhotos  

from ui.sortie import Sortie  

from ui.style import BLEU, FOND, FOND_MENU, MENU_ACTIF, ROUGE   

PAGES = [

    {
        "cle": "caches",                      
        "menu": "Analyser puis supprimer les caches",
        "titre": "Gagner de la place",
        "page": "caches",
    },
    {
        "cle": "projets",
        "menu": "Nettoyer un projet web",
        "titre": "Gagner de la place",
        "page": "projets",
    },

    {
        "cle": "images",
        "menu": "Optimiser les images",
        "titre": "Photos",
        "page": "images",
    },
    {
        "cle": "ranger_dossier",
        "menu": "Ranger un dossier",
        "titre": "Gagner de la place",
        "page": "ranger",
    },
    {
        "cle": "doublons",
        "menu": "Supprimer les doublons",
        "titre": "Photos",
        "page": "doublons",
    },
        {
        "cle": "photos_annee",
        "menu": "Ranger les photos",
        "titre": "Photos",
        "page": "ranger_photos",
    },
]

cles = [definition["cle"] for definition in PAGES]
if len(cles) != len(set(cles)):
    raise SystemExit("Erreur dans PAGES : deux pages ont la même 'cle'.")

LANCEMENT = {
    "outils/photos/supprimer_doublons.py": {
        "mode": "dossier",
        "simulation": ["--simulation"],
        "reel": [],
        "confirmation": "Les fichiers dont le nom finit par (1), (2) ou (3) seront "
                        "SUPPRIMÉS DÉFINITIVEMENT (pas de corbeille).",
    },
}

# Le dossier où se trouve app.py 
RACINE = Path(__file__).resolve().parent


# ------------------------------------------------------------
#  LA CLASSE Application
# ------------------------------------------------------------

class Application:

    def __init__(self, fenetre):

        # On garde la fenêtre dans "self" , pour que toutes les méthodes s'en servent.
        self.fenetre = fenetre
        self.sorties = []                 # toutes les boîtes "Résultat" (une par page d'outil)
        self.page_caches = None           
        self.page_images = None          
        self.dossiers = {}                # pour les outils "chercher" : le dernier dossier cherché
        self.page_doublons = None        
        self.page_ranger = None   
        self.page_ranger_photos = None    
        self.page_projets = None          

        # ----- Réglages de la fenêtre -----
        fenetre.title("Boîte à outils")
        fenetre.geometry("1000x700")
        fenetre.minsize(920, 620)
        fenetre.protocol("WM_DELETE_WINDOW", self.fermer)# Si tu fermes la fenêtre pendant qu'un script tourne, on l'arrête proprement.

        # ---------- LE MENU  ----------

        # tk.Frame => "crée une boîte DANS la fenêtre".

        menu = tk.Frame(fenetre, bg=FOND_MENU, width=250)

        # pack()  C'est ce qui le rend VISIBLE :
        #   fill="y"     : étire-le sur toute la hauteur

        menu.pack(side="left", fill="y")
        # pack_propagate(False) dit : "garde ta largeur de 250, quoi qu'il y ait dedans".
        menu.pack_propagate(False)

        # Label = un texte affiché à l'écran:
        # fg =  couleur du texte
        # pady=(25, 20) (marge 25 pixels au-dessus, 20 en dessous).

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
            #   wraplength=210 : un nom trop long passe à la ligne 
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

        # Une page spéciale : on laisse une classe dédiée la construire entièrement.
        if definition.get("page") == "caches":
            self.page_caches = PageCaches(zone, definition["titre"])
            return self.page_caches
        if definition.get("page") == "images":
            self.page_images = PageImages(zone, definition["titre"])
            return self.page_images
        if definition.get("page") == "doublons":
            self.page_doublons = PageDoublons(zone, definition["titre"])
            return self.page_doublons
        if definition.get("page") == "ranger":
            self.page_ranger = PageRanger(zone, definition["titre"])
            return self.page_ranger
        if definition.get("page") == "ranger_photos":
            self.page_ranger_photos = PageRangerPhotos(zone, definition["titre"])
            return self.page_ranger_photos
        if definition.get("page") == "projets":
            self.page_projets = PageProjets(zone, definition["titre"])
            return self.page_projets

        page = tk.Frame(zone, bg=FOND)

        # Ici on utilise place() au lieu de pack(). Il positionne l'élément à un endroit précis.
        # x=0, y=0 . relwidth=1 / relheight=1 : 100 %
        page.place(x=0, y=0, relwidth=1, relheight=1)

        page.place(x=0, y=0, relwidth=1, relheight=1)

        # Le grand titre de la page. anchor="w" : aligné à gauche. padx : marge gauche/droite.
        tk.Label(page, text=definition["titre"], font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # La boîte "Résultat" est créée ICI 
        # any(...) = "vrai si AU MOINS un des outils de la page pose des questions" (réglage "reponse").
        pose_des_questions = any(LANCEMENT.get(fichier, {}).get("reponse")
                                 for _nom, _description, fichier in definition["outils"])
        sortie = Sortie(page, RACINE, avec_reponse=pose_des_questions)
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

        # highlightbackground = couleur de la bordure ; highlightthickness = son épaisseur (1 pixel).
        ligne = tk.Frame(page, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        textes = tk.Frame(ligne, bg="white")
        # expand=True : cette boîte prend tout l'espace libre, ce qui repousse les boutons à droite.
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)

        tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
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
       
        self.pages[cle].tkraise()

        # On parcourt le carnet des boutons du menu.
        # .items() donne, pour chaque entrée du dictionnaire, la paire (clé, valeur).
        for une_cle, bouton in self.boutons_menu.items():
            # .config(...) change une option d'un élément 
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
        for page in (self.page_caches, self.page_images, self.page_doublons, self.page_ranger,
                     self.page_ranger_photos, self.page_projets):
            if page is not None:
                page.arret.set()                   # arrête l'analyse / la suppression / l'optimisation en cours
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

    # mainloop() garde la fenêtre OUVERTE
    fenetre.mainloop()

if __name__ == "__main__":
    main()