
from outils.photos import rangement_photos           
from ui.page_ranger import PageRanger


class PageRangerPhotos(PageRanger):
    """Même fonctionnement que PageRanger."""

    NOM_OUTIL = "Ranger les photos par année"
    DESCRIPTION = ("Range les photos et vidéos d'un dossier dans un sous-dossier par année "
                   "(2019, 2020...), d'après leur date de prise de vue ou le nom WhatsApp. "
                   "Rien n'est supprimé ni écrasé, et tu peux annuler.")
    TEXTE_CASE = "À défaut de date, utiliser la date de modification du fichier"
    CASE_PAR_DEFAUT = False          # moins fiable : à toi de l'activer
    TITRE_DIALOGUE = "Choisis le dossier de photos à ranger"
    TITRE_ONGLET = "Photos à ranger"
    COLONNES = [("fichier", "Fichier", 200, "w", False), ("date", "Date", 90, "w", False),
                ("source", "Source de la date", 120, "w", False),
                ("cible", "Va dans", 200, "w", True), ("etat", "État", 100, "w", False)]


    def chercher_dans(self, racine, option):
        """La recherche des photos : elle lit les dates (ça peut prendre un moment)."""
        return rangement_photos.chercher(
            racine, option, self.arret,
            progression=lambda nombre: self.messages.put(("progression", nombre)))

    def valeurs(self, element, cible, etat):
        """Une ligne du tableau : le fichier, sa date, d'où elle vient, où il va, son état."""
        date = element["date"].strftime("%d/%m/%Y") if element["date"] else "-"
        return (element["source"].name, date, element["source_date"], cible, etat)

    def detail(self, resultats):
        """Un bilan des sources de date, ajouté sous le tableau."""
        sources = resultats["sources"]
        texte = (f" Dates : {sources[rangement_photos.EXIF]} EXIF, "
                 f"{sources[rangement_photos.WHATSAPP]} WhatsApp, "
                 f"{sources[rangement_photos.FICHIER]} date du fichier, "
                 f"{sources[rangement_photos.AUCUNE]} sans date (« Autre »).")
        if resultats["sans_date_illisible"]:
            # Sans pillow-heif, les .heic ne sont pas lisibles non plus : on le dit.
            quoi = "vidéo(s)" if rangement_photos.HEIF_DISPONIBLE else "vidéo(s) ou .heic (pillow-heif absent)"
            texte += (f" ⚠ {resultats['sans_date_illisible']} {quoi} sans date lisible : "
                      "coche la date de modification pour les classer.")
        if resultats["autres"]:
            texte += f" {resultats['autres']} autre(s) fichier(s) non touchés."
        return texte