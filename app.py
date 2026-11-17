# ============================================================
# Pour ajouter un outil : ajoute UNE ligne dans la liste PAGES ci-dessous.
# Pour ajouter une page : ajoute un bloc {...} dans PAGES.
# ============================================================
import tkinter as tk

PAGES = [
    {
        "cle": "gagner",                 # un identifiant interne, pour que le code s'y retrouve
        "menu": "Gagner de la place",    # le texte du bouton dans le menu de gauche
        "titre": "Gagner de la place",   # le grand titre affiché en haut de la page
        # "outils" est la liste des lignes de la page.
        # Chaque ligne est un TUPLE de 3 éléments : (nom, description, chemin du script)
        "outils": [
            ("Analyser les caches",
             "Affiche les caches qui prennent de la place et leur taille (rien n'est supprimé).",
             "outils/gagner_de_la_place/analyser_caches.py"),
        ],
    },
    {
        "cle": "photos",
        "menu": "Photos",
        "titre": "Photos",
        "outils": [
            ("Optimiser les images",
             "Réduit le poids des images (WebP) ou les redimensionne pour un réseau social.",
             "outils/photos/optimiser_images.py"),
        ],
    },
]

FOND = "#F4F5F7"           
FOND_MENU = "#1F2937"       
MENU_ACTIF = "#374151"      
BLEU = "#2563EB"            

# ------------------------------------------------------------
# 4. LA CLASSE Application
# ------------------------------------------------------------

class Application:

    def __init__(self, fenetre):

        # ----- Réglages de la fenêtre -----
        fenetre.title("Boîte à outils")      # le texte de la barre de titre
        fenetre.geometry("900x560")          # taille de départ : largeur x hauteur, en pixels
        fenetre.minsize(760, 440)            # taille minimale : on ne peut pas la réduire en dessous

        # ---------- LE MENU (la colonne de gauche) ----------
        
        # tk.Frame => "crée une boîte DANS la fenêtre (ci-dessus)".
        
        menu = tk.Frame(fenetre, bg=FOND_MENU, width=220)

        # pack()  C'est ce qui le rend VISIBLE :
        #   side="left"  : colle-le sur le côté gauche
        #   fill="y"     : étire-le sur toute la hauteur 

        menu.pack(side="left", fill="y")
        # pack_propagate(False) dit : "garde ta largeur de 220, quoi qu'il y ait dedans".
        menu.pack_propagate(False)

        # Label = un texte affiché à l'écran.
        # font=("Arial", 13, "bold") :
        # fg =  couleur du texte 
        # pady=(25, 20) (25 pixels au-dessus, 20 en dessous).

        tk.Label(menu, text="BOÎTE À OUTILS", font=("Arial", 13, "bold"),
                 bg=FOND_MENU, fg="white").pack(pady=(25, 20))

        # ---------- LA ZONE DES PAGES (à droite) ----------
        # Une autre boîte, qui prend toute la place restante : c'est là que les pages s'afficheront.
        zone = tk.Frame(fenetre, bg=FOND)
        # fill="both" : étire en largeur ET en hauteur.
        # expand=True : prend tout l'espace libre qui reste.
        zone.pack(side="right", fill="both", expand=True)

        # ----- On prépare deux "carnets" pour retrouver nos éléments plus tard -----
        # Un dictionnaire VIDE : on le remplit au fur et à mesure dans la boucle ci-dessous.
        # self.pages["photos"] donnera la page des photos, par exemple.
        self.pages = {}            # clé de la page  ->  la page elle-même
        self.boutons_menu = {}     # clé de la page  ->  son bouton dans le menu

        # ---------- ON CONSTRUIT LE MENU ET LES PAGES ----------

        for definition in PAGES:

            cle = definition["cle"]

            # Button = un bouton cliquable. Quelques options importantes :
            #   text           : le texte écrit dessus
            #   relief="flat"  : bouton plat, sans bordure en relief
            #   anchor="w"     : texte aligné à gauche (w = west = ouest)
            #   padx=20        : espace horizontal à l'intérieur du bouton
            #   cursor="hand2" : le curseur devient une petite main au survol
            #   activebackground / activeforeground : couleurs pendant le clic
            #   command        : la fonction à exécuter QUAND on clique
            bouton = tk.Button(menu, text=definition["menu"], font=("Arial", 11),
                               bg=FOND_MENU, fg="white", relief="flat", anchor="w",
                               padx=20, cursor="hand2", activebackground=MENU_ACTIF,
                               activeforeground="white",
                               # "lambda" crée une mini-fonction sans nom, sur une seule ligne.
                               # Ici : "quand on clique, appelle self.afficher(cle)".
                               # Le "cle=cle" est un détail IMPORTANT : il fige la valeur de
                               # cle POUR CE bouton. Sans lui, tous les boutons afficheraient
                               # la dernière page (le piège classique des boucles).
                               command=lambda cle=cle: self.afficher(cle))

            # fill="x" : le bouton prend toute la largeur du menu.
            # ipady=8 : épaisseur supplémentaire À L'INTÉRIEUR du bouton (le rend plus haut).
            bouton.pack(fill="x", ipady=8)

            # On range le bouton dans notre carnet, pour le retrouver plus tard
            # (afin de changer sa couleur quand on change de page).
            self.boutons_menu[cle] = bouton

            # On construit la page (voir la méthode creer_page plus bas) et on la range aussi.
            self.pages[cle] = self.creer_page(zone, definition)

        # Au démarrage, on affiche la première page.
        # PAGES[0] = le premier élément de la liste (en programmation, on compte à partir de 0).
        self.afficher(PAGES[0]["cle"])

    # ------------------------------------------------------------
    # Construire UNE page
    # ------------------------------------------------------------
    # "zone" : la boîte dans laquelle on met la page. "definition" : sa fiche.
    def creer_page(self, zone, definition):
        """Construit une page : un titre, puis une ligne par outil."""
        # (Le texte entre triples guillemets juste au-dessus s'appelle une "docstring" :
        #  c'est la description de la fonction, que Python garde en mémoire.)

        page = tk.Frame(zone, bg=FOND)

        # Ici on utilise place() au lieu de pack(). Il positionne l'élément à un endroit précis.
        # x=0, y=0 : en haut à gauche. relwidth=1 / relheight=1 : 100 % de la largeur / hauteur.
        # RÉSULTAT : toutes les pages occupent exactement la MÊME place, empilées comme des
        # feuilles de papier les unes sur les autres. On verra celle qui est au-dessus.
        page.place(x=0, y=0, relwidth=1, relheight=1)

        # Le grand titre de la page. anchor="w" : aligné à gauche. padx : marge gauche/droite.
        tk.Label(page, text=definition["titre"], font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        # Une boucle sur la liste "outils" de la fiche : une ligne par outil.
        # Chaque outil est un tuple de 3 valeurs. Python permet de les "déballer" directement
        # dans trois variables : nom, description, fichier.
        for nom, description, fichier in definition["outils"]:
            self.creer_ligne(page, nom, description, fichier)

        # "return" renvoie un résultat à celui qui a appelé la fonction.
        # Ici on rend la page construite, pour que __init__ puisse la ranger dans self.pages.
        return page

    # ------------------------------------------------------------
    # Construire UNE ligne (un outil)
    # ------------------------------------------------------------
    def creer_ligne(self, page, nom, description, fichier):
        """Une ligne = un outil : son nom, sa description, un bouton Ouvrir."""

        # Une boîte blanche avec une fine bordure grise.
        # highlightbackground = couleur de la bordure ; highlightthickness = son épaisseur (1 pixel).
        ligne = tk.Frame(page, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        # --- La partie texte, à gauche : le nom en dessous duquel se trouve la description ---
        textes = tk.Frame(ligne, bg="white")
        # expand=True : cette boîte prend tout l'espace libre, ce qui repousse le bouton à droite.
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)

        # Le nom de l'outil, en gras.
        tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")

        # La description, en plus petit et en gris.
        #   justify="left" : si le texte passe sur plusieurs lignes, elles sont alignées à gauche.
        #   wraplength=470 : au-delà de 470 pixels de large, le texte passe à la ligne tout seul.
        tk.Label(textes, text=description, font=("Arial", 9), fg="#6B7280", bg="white",
                 anchor="w", justify="left", wraplength=470).pack(fill="x")

        # --- Le bouton "Ouvrir", à droite ---
        # Ici le lambda n'a pas besoin de "fichier=fichier" : il n'y a qu'un seul bouton par appel
        # de cette méthode, donc pas de piège de boucle.
        tk.Button(ligne, text="Ouvrir", font=("Arial", 10, "bold"), bg=BLEU, fg="white",
                  relief="flat", cursor="hand2", padx=18,
                  command=lambda: self.pas_encore(fichier)).pack(side="right", padx=15, ipady=4)

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
    # Ce que font les boutons "Ouvrir" (pour l'instant)
    # ------------------------------------------------------------
    def pas_encore(self, fichier):
        # À l'étape suivante, cette méthode lancera vraiment l'outil.
        # Pour l'instant, elle affiche juste un message dans le terminal.
        # Le f devant les guillemets ("f-string") permet d'insérer une variable dans le texte,
        # en l'écrivant entre accolades : {fichier} sera remplacé par sa valeur.
        print(f"Ce bouton lancera : {fichier} (pas encore branché)")


# ------------------------------------------------------------
# 5. LE POINT D'ENTRÉE : ce qui se passe quand on lance le programme
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
    # Le programme reste bloqué sur cette ligne jusqu'à ce que tu fermes la fenêtre.
    fenetre.mainloop()


# Cette condition est une habitude de tous les programmes Python.
# __name__ vaut "__main__" quand on lance CE fichier directement (python app.py).
# Si un autre fichier fait un jour "import app", ce bloc ne s'exécutera PAS,
# ce qui évite d'ouvrir une fenêtre par accident.
if __name__ == "__main__":
    main()