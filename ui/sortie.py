# ============================================================
# sortie.py : la boîte "Résultat" (texte d'un script + zone de réponse).
# Elle lance un script en arrière-plan et en affiche le texte en direct, sous la ligne de l'outil.
# ============================================================
import codecs                     # pour transformer les octets reçus d'un script en texte
import os                         # os.environ : les variables de l'ordinateur
import queue                      # une "boîte aux lettres" pour passer des messages entre deux fils
import subprocess                 # pour LANCER un autre programme (nos scripts)
import threading                  # pour lire le résultat SANS bloquer la fenêtre
import tkinter as tk
from tkinter import messagebox

from ui.style import BLEU, FOND, FOND_SORTIE, GRIS, TEXTE_SORTIE


# ------------------------------------------------------------
#  LA BOÎTE "RÉSULTAT" : affiche le texte d'un script, sous sa ligne
# ------------------------------------------------------------

class Sortie(tk.Frame):
    """Une boîte de texte + une zone de réponse. Elle lance un script et en affiche le texte
    en direct (avant, ce texte s'affichait dans PowerShell)."""

    def __init__(self, parent, dossier_travail, avec_reponse=False):
        super().__init__(parent, bg=FOND)          # super().__init__ = "construis d'abord la boîte de base"
        self.dossier_travail = dossier_travail    # le dossier depuis lequel on lance les scripts
        self.processus = None             # le script en train de tourner (None = aucun)
        self.arret_demande = False        # vrai si TU as cliqué sur "Arrêter"
        self.reste_cr = ""                # un détail technique pour les lignes qui se réécrivent
        self.quand_fini = None            # une fonction à appeler quand le script se termine bien
        # La "boîte aux lettres" : le fil de lecture y dépose le texte du script,
        # et la fenêtre vient le chercher toutes les 100 ms (voir "surveiller").
        self.messages = queue.Queue()

        # --- La ligne du haut : le titre, l'état, et les boutons "Arrêter" / "Effacer" ---
        entete = tk.Frame(self, bg=FOND)
        entete.pack(fill="x", pady=(0, 6))

        tk.Label(entete, text="Résultat", font=("Arial", 12, "bold"),
                 bg=FOND).pack(side="left")

        # Ce petit texte indiquera "En cours..." pendant qu'un script tourne.
        self.etat = tk.Label(entete, text="", font=("Arial", 9), fg="#6B7280", bg=FOND)
        self.etat.pack(side="left", padx=10)

        tk.Button(entete, text="Effacer", font=("Arial", 9), relief="flat", bg=GRIS,
                  cursor="hand2", padx=10, command=self.effacer).pack(side="right")
        # state="disabled" : bouton grisé, impossible de cliquer (tant qu'aucun script ne tourne).
        self.bouton_arreter = tk.Button(entete, text="Arrêter", font=("Arial", 9), relief="flat",
                                        bg=GRIS, cursor="hand2", padx=10,
                                        state="disabled", command=self.arreter)
        self.bouton_arreter.pack(side="right", padx=(0, 6))

        # --- Le texte lui-même, avec une barre de défilement à droite ---
        corps = tk.Frame(self)
        corps.pack(fill="x")

        barre = tk.Scrollbar(corps)
        barre.pack(side="right", fill="y")

        # tk.Text = une zone de texte de plusieurs lignes.
        #   height=12 : 12 lignes visibles. font Consolas : police "machine à écrire".
        #   wrap="word" : les longues lignes passent à la ligne sans couper un mot.
        #   state="disabled" : tu ne peux pas écrire dedans à la main (seul le programme le fait).
        #   yscrollcommand : relie la zone à la barre de défilement.
        self.texte = tk.Text(corps, height=12, bg=FOND_SORTIE, fg=TEXTE_SORTIE,
                             font=("Consolas", 10), wrap="word", relief="flat",
                             padx=10, pady=8, state="disabled", yscrollcommand=barre.set)
        self.texte.pack(side="left", fill="x", expand=True)
        barre.config(command=self.texte.yview)

        # --- La ligne du bas : la zone de réponse (pour les scripts qui posent une question) ---
        saisie = tk.Frame(self, bg=FOND)
        if avec_reponse:                           # cachée (jamais rangée avec pack) si le script ne pose aucune question
            saisie.pack(fill="x", pady=(6, 0))

        tk.Label(saisie, text="Réponse :", font=("Arial", 9), bg=FOND).pack(side="left")

        # tk.Entry = une zone de saisie d'UNE ligne.
        self.champ = tk.Entry(saisie, font=("Consolas", 10), state="disabled")
        self.champ.pack(side="left", fill="x", expand=True, padx=6)
        # <Return> = la touche Entrée : elle fait la même chose que le bouton "Envoyer".
        self.champ.bind("<Return>", lambda evenement: self.envoyer())

        self.bouton_envoyer = tk.Button(saisie, text="Envoyer", font=("Arial", 9), relief="flat",
                                        bg=BLEU, fg="white", cursor="hand2", padx=12,
                                        state="disabled", command=self.envoyer)
        self.bouton_envoyer.pack(side="right")

        # Un petit message au départ.
        self.ecrire("Les résultats s'afficheront ici.\n")

    def ecrire(self, texte):
        """Ajoute du texte à la fin de la boîte et fait défiler vers le bas."""

        # Certains scripts écrivent "\r" pour RÉÉCRIRE la même ligne (ex : "12000 dossiers analysés...").
        # Si le morceau de texte se termine par "\r", on le garde de côté : le "\n" qui va avec
        # arrive peut-être dans le morceau suivant.
        texte = self.reste_cr + texte
        self.reste_cr = ""
        if texte.endswith("\r"):
            self.reste_cr = "\r"
            texte = texte[:-1]
        texte = texte.replace("\r\n", "\n")        # "\r\n" = simple retour à la ligne Windows

        # Une zone "disabled" refuse qu'on y écrive : on la débloque le temps d'écrire.
        self.texte.config(state="normal")
        # On coupe le texte à chaque "\r". Chaque "\r" efface la ligne en cours avant de réécrire.
        for i, morceau in enumerate(texte.split("\r")):
            if i > 0:
                # "end-1c linestart" = le début de la dernière ligne ; "end-1c" = sa fin.
                self.texte.delete("end-1c linestart", "end-1c")
            self.texte.insert("end", morceau)
        self.texte.see("end")                      # fait défiler jusqu'à la fin
        self.texte.config(state="disabled")

    def effacer(self):
        """Vide la boîte."""
        self.texte.config(state="normal")
        self.texte.delete("1.0", "end")            # "1.0" = ligne 1, caractère 0 : le tout début
        self.texte.config(state="disabled")
        self.reste_cr = ""

    def definir_etat(self, en_cours):
        """Active ou grise les boutons selon qu'un script tourne ou non."""
        etat = "normal" if en_cours else "disabled"
        self.bouton_arreter.config(state=etat)
        self.bouton_envoyer.config(state=etat)
        self.champ.config(state=etat)
        self.etat.config(text="En cours..." if en_cours else "")
        if en_cours:
            self.champ.focus_set()                 # le curseur se place dans la zone de réponse

    def executer(self, commande, titre, quand_fini=None):
        """Lance 'commande' (une liste) et affiche son texte ici. 'titre' est rappelé en haut.
        'quand_fini' (facultatif) : une fonction appelée avec le code de sortie quand le script
        se termine (sauf si tu cliques sur "Arrêter").
        Renvoie True si le script a démarré, False sinon."""
        # Un seul script à la fois dans cette boîte, sinon leurs textes se mélangeraient.
        if self.processus is not None:
            messagebox.showinfo("Déjà en cours",
                                "Un outil tourne déjà ici.\nAttends qu'il se termine, "
                                "ou clique sur « Arrêter ».")
            return False

        # Deux réglages pour que le texte arrive tout de suite et avec les accents :
        #   PYTHONUNBUFFERED : le script envoie son texte immédiatement (sans le garder en réserve)
        #   PYTHONIOENCODING : le script écrit en UTF-8, comme on le lit ici
        environnement = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")

        try:
            # stdout=PIPE : on RÉCUPÈRE ce que le script écrit (au lieu de l'afficher dans PowerShell).
            # stderr=STDOUT : les messages d'erreur arrivent au même endroit.
            # stdin=PIPE : on pourra lui ENVOYER nos réponses (ex : taper OUI).
            # CREATE_NO_WINDOW : aucune fenêtre noire ne s'ouvre (n'existe que sous Windows,
            # d'où le getattr : "0" = rien, ailleurs).
            self.processus = subprocess.Popen(
                commande, cwd=self.dossier_travail, env=environnement,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as erreur:
            messagebox.showerror("Lancement impossible", str(erreur))
            return False

        self.quand_fini = quand_fini
        self.arret_demande = False
        self.effacer()
        self.ecrire("▶ " + titre + "\n\n")
        self.definir_etat(True)

        # Un FIL séparé lit le texte du script : si on le lisait ici, la fenêtre se figerait.
        # daemon=True : ce fil s'arrête tout seul quand on ferme l'application.
        threading.Thread(target=self.lire_sortie, args=(self.processus,), daemon=True).start()
        # Et la fenêtre ira chercher ce texte toutes les 100 ms.
        self.after(100, self.surveiller)
        return True

    def lire_sortie(self, processus):
        """Tourne dans un FIL à part. Il NE TOUCHE PAS à la fenêtre : il dépose juste le texte
        dans la boîte aux lettres (self.messages). Seule la fenêtre elle-même a le droit
        de modifier l'écran."""
        # Le script envoie des octets ; le décodeur les transforme en texte (UTF-8).
        # Il sait gérer un accent coupé en deux entre deux morceaux.
        decodeur = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            morceau = processus.stdout.read(4096)      # attend du texte ; renvoie vide quand c'est fini
            if not morceau:
                break
            self.messages.put(("texte", decodeur.decode(morceau)))
        # Le script est terminé : wait() donne son "code de sortie" (0 = tout s'est bien passé).
        self.messages.put(("fin", processus.wait()))

    def surveiller(self):
        """Appelée toutes les 100 ms : affiche le texte arrivé depuis la dernière fois."""
        while True:
            try:
                genre, contenu = self.messages.get_nowait()   # prend un message, sans attendre
            except queue.Empty:                               # boîte vide : on arrête de lire
                break
            if genre == "texte":
                self.ecrire(contenu)
            else:                                             # "fin" : le script est terminé
                self.terminer(contenu)
                return                                        # plus besoin de surveiller
        self.after(100, self.surveiller)                      # on se rappelle dans 100 ms

    def terminer(self, code):
        """Appelée quand le script est fini : affiche le bilan et remet les boutons à zéro."""
        if self.arret_demande:
            self.ecrire("\n■ Arrêté.\n")
        elif code == 0:
            self.ecrire("\n✓ Terminé.\n")
        else:
            self.ecrire(f"\n✗ Le script s'est arrêté avec une erreur (code {code}).\n")
        try:
            self.processus.stdin.close()
        except OSError:
            pass
        self.processus = None
        self.definir_etat(False)
        # Un outil peut demander à être prévenu quand son script se termine (ex : le bouton "Appliquer").
        rappel, self.quand_fini = self.quand_fini, None
        if rappel is not None and not self.arret_demande:
            rappel(code)

    def envoyer(self):
        """Envoie au script ce que tu as tapé dans la zone "Réponse" (comme taper dans PowerShell)."""
        if self.processus is None:
            return
        texte = self.champ.get()
        self.champ.delete(0, "end")                # vide la zone de saisie
        self.ecrire(texte + "\n")                  # on l'affiche aussi (le script ne le répète pas)
        try:
            self.processus.stdin.write((texte + "\n").encode("utf-8"))
            self.processus.stdin.flush()
        except OSError:
            pass                                   # le script est déjà fini : rien à envoyer

    def arreter(self):
        """Interrompt le script en cours (attention : il s'arrête net, sans bilan final)."""
        if self.processus is not None:
            self.arret_demande = True
            self.processus.terminate()