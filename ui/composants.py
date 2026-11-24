# ============================================================
# composants.py : les petits morceaux d'écran utilisés par PLUSIEURS pages.
# Avant, chaque page recopiait les mêmes lignes pour fabriquer un bouton, une carte, un tableau...
# Maintenant, elle appelle une fonction d'ici. Pour changer l'apparence de tous les boutons,
# par exemple, il suffit de modifier la fonction "bouton" : toutes les pages suivent.
#
# Ces fonctions ne font que FABRIQUER les éléments : c'est la page qui décide où les placer
# (avec pack) et ce qu'ils font quand on clique.
# ============================================================
import tkinter as tk
from tkinter import ttk

from ui.style import FOND, GRIS, TEXTE_DISCRET


def titre_page(parent, titre, pady=(25, 15)):
    """Le grand titre en haut d'une page."""
    etiquette = tk.Label(parent, text=titre, font=("Arial", 20, "bold"), bg=FOND)
    etiquette.pack(anchor="w", padx=30, pady=pady)
    return etiquette


def carte_outil(parent, nom, description, pady=6, wraplength=420):
    """La boîte blanche d'un outil : son nom, sa description, et de la place pour ses boutons.
    Renvoie (la boîte, la zone de texte) :
      - on range les BOUTONS dans la boîte, avec pack(side="right") ;
      - on range les RÉGLAGES (case à cocher, liste...) dans la zone de texte."""
    # highlightbackground / highlightthickness : une fine bordure grise de 1 pixel.
    ligne = tk.Frame(parent, bg="white", highlightbackground=GRIS, highlightthickness=1)
    ligne.pack(fill="x", padx=30, pady=pady)
    textes = tk.Frame(ligne, bg="white")
    textes.pack(side="left", fill="x", expand=True, padx=15, pady=12)
    tk.Label(textes, text=nom, font=("Arial", 12, "bold"), bg="white",
             anchor="w").pack(fill="x")
    # wraplength : un texte trop long passe à la ligne au lieu d'être coupé.
    tk.Label(textes, text=description, font=("Arial", 9), fg=TEXTE_DISCRET, bg="white",
             anchor="w", justify="left", wraplength=wraplength).pack(fill="x")
    return ligne, textes


def bouton(parent, texte, couleur, commande, gras=True, **options):
    """Un bouton plat de l'application.
    couleur : BLEU (action), ROUGE (action qui modifie des fichiers) ou GRIS (secondaire).
    gras    : False pour un bouton moins important.
    **options : n'importe quelle autre option de tk.Button, qui remplace la valeur par défaut
                (par exemple state="disabled" ou padx=10)."""
    reglages = {
        "text": texte, "bg": couleur, "command": commande,
        "font": ("Arial", 10, "bold" if gras else "normal"),
        "relief": "flat", "cursor": "hand2", "padx": 14,
    }
    if couleur != GRIS:
        reglages["fg"] = "white"           # texte blanc sur bleu et rouge
    reglages.update(options)               # ce que la page demande l'emporte
    return tk.Button(parent, **reglages)


def ligne_statut(parent, texte):
    """La ligne de texte qui dit où on en est ("Analyse en cours...").
    Un texte long passe à la ligne au lieu d'être coupé. Renvoie l'étiquette pour qu'on puisse
    changer son texte avec statut.config(text=...)."""
    etiquette = tk.Label(parent, text=texte, font=("Arial", 9), fg=TEXTE_DISCRET, bg=FOND,
                         anchor="w", justify="left", wraplength=600)
    etiquette.pack(fill="x", padx=32, pady=(2, 0))
    return etiquette


def barre_du_bas(parent, pady=(8, 20)):
    """La barre du bas d'une page (totaux et boutons). Elle est rangée AVANT le tableau :
    elle reste donc visible même si la fenêtre rétrécit."""
    cadre = tk.Frame(parent, bg=FOND)
    cadre.pack(side="bottom", fill="x", padx=30, pady=pady)
    return cadre


def tableau(parent, colonnes, selectmode="browse", hauteur=None):
    """Un tableau (ttk.Treeview) avec sa barre de défilement. Renvoie (cadre, tableau) :
    on range le CADRE dans la page (pack, ou onglets.add), et on remplit le TABLEAU.
    colonnes   : une liste de (identifiant, titre, largeur, alignement, s'étire ?)
    selectmode : "browse" = une ligne à la fois ; "extended" = plusieurs (Ctrl + clic, Maj + clic)
    hauteur    : nombre de lignes visibles au départ (facultatif)"""
    ttk.Style(parent).configure("Treeview", rowheight=24)          # des lignes un peu plus aérées
    cadre = tk.Frame(parent)
    options = {"height": hauteur} if hauteur else {}
    arbre = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings",
                         selectmode=selectmode, **options)
    for identifiant, titre, largeur, alignement, s_etire in colonnes:
        arbre.heading(identifiant, text=titre)
        arbre.column(identifiant, width=largeur, anchor=alignement, stretch=s_etire)
    barre = ttk.Scrollbar(cadre, orient="vertical", command=arbre.yview)
    arbre.configure(yscrollcommand=barre.set)
    barre.pack(side="right", fill="y")
    arbre.pack(side="left", fill="both", expand=True)
    return cadre, arbre