# ============================================================
# Pour ajouter un outil : ajoute UNE ligne dans la liste PAGES ci-dessous.
# Pour ajouter une page : ajoute un bloc {...} dans PAGES.
# ============================================================

import tkinter as tk

# ------------------------------------------------------------
# LE CONTENU DE LA BOÎTE À OUTILS (c'est ici que tu modifies)

# ------------------------------------------------------------
PAGES = [
    {
        "cle": "gagner",
        "menu": "Gagner de la place",
        "titre": "Gagner de la place",
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


class Application:
    def __init__(self, fenetre):
        fenetre.title("Boîte à outils")
        fenetre.geometry("900x560")
        fenetre.minsize(760, 440)

        # ---------- LE MENU (colonne de gauche) ----------
        menu = tk.Frame(fenetre, bg=FOND_MENU, width=220)
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False)        # garde la largeur de 220 px quoi qu'il y ait dedans

        tk.Label(menu, text="BOÎTE À OUTILS", font=("Arial", 13, "bold"),
                 bg=FOND_MENU, fg="white").pack(pady=(25, 20))

        # ---------- LA ZONE DES PAGES (à droite) ----------
        zone = tk.Frame(fenetre, bg=FOND)
        zone.pack(side="right", fill="both", expand=True)

        self.pages = {}               # cle -> la page (Frame)
        self.boutons_menu = {}        # cle -> le bouton du menu

        # On construit un bouton de menu ET une page pour chaque bloc de PAGES
        for definition in PAGES:
            cle = definition["cle"]

            bouton = tk.Button(menu, text=definition["menu"], font=("Arial", 11),
                               bg=FOND_MENU, fg="white", relief="flat", anchor="w",
                               padx=20, cursor="hand2", activebackground=MENU_ACTIF,
                               activeforeground="white",
                               # lambda cle=cle : chaque bouton garde SA propre clé
                               command=lambda cle=cle: self.afficher(cle))
            bouton.pack(fill="x", ipady=8)
            self.boutons_menu[cle] = bouton

            self.pages[cle] = self.creer_page(zone, definition)

        # Au démarrage, on affiche la première page
        self.afficher(PAGES[0]["cle"])

    def creer_page(self, zone, definition):
        """Construit une page : un titre, puis une ligne par outil."""
        page = tk.Frame(zone, bg=FOND)
        # Toutes les pages occupent la MÊME place, empilées les unes sur les autres.
        # Afficher une page = la mettre au-dessus des autres (voir afficher()).
        page.place(x=0, y=0, relwidth=1, relheight=1)

        tk.Label(page, text=definition["titre"], font=("Arial", 20, "bold"),
                 bg=FOND).pack(anchor="w", padx=30, pady=(25, 15))

        for nom, description, fichier in definition["outils"]:
            self.creer_ligne(page, nom, description, fichier)
        return page

    def creer_ligne(self, page, nom, description, fichier):
        """Une ligne = un outil : son nom, sa description, un bouton Ouvrir."""
        ligne = tk.Frame(page, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        ligne.pack(fill="x", padx=30, pady=6)

        # La partie texte (nom + description), à gauche
        textes = tk.Frame(ligne, bg="white")
        textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)
        tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
                 anchor="w").pack(fill="x")
        tk.Label(textes, text=description, font=("Arial", 9), fg="#6B7280", bg="white",
                 anchor="w", justify="left", wraplength=470).pack(fill="x")

        # Le bouton, à droite
        tk.Button(ligne, text="Ouvrir", font=("Arial", 10, "bold"), bg=BLEU, fg="white",
                  relief="flat", cursor="hand2", padx=18,
                  command=lambda: self.pas_encore(fichier)).pack(side="right", padx=15, ipady=4)

    def afficher(self, cle):
        """Met la page choisie au-dessus des autres et surligne son bouton dans le menu."""
        self.pages[cle].tkraise()
        for une_cle, bouton in self.boutons_menu.items():
            bouton.config(bg=MENU_ACTIF if une_cle == cle else FOND_MENU)

    def pas_encore(self, fichier):
        # Étape suivante : ce bouton lancera vraiment l'outil.
        print(f"Ce bouton lancera : {fichier} (pas encore branché)")


def main():
    fenetre = tk.Tk()
    Application(fenetre)
    # Force la fenêtre au premier plan au lancement (sinon elle peut rester derrière VS Code)
    fenetre.lift()
    fenetre.attributes("-topmost", True)
    fenetre.after(500, lambda: fenetre.attributes("-topmost", False))
    fenetre.mainloop()


if __name__ == "__main__":
    main()