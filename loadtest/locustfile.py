"""Test de charge de la plateforme ONEA (lot 9, tâche 26).

Scénario : utilisateurs virtuels répartis sur les comptes `chargeNN` du realm de recette,
jetons obtenus par le client `onea-charge` (accès direct par mot de passe, RECETTE SEULEMENT).

Répartition des tâches (poids = pourcentage) :
  30  listes de missions        10  référentiel          5  génération de document
  25  détail de mission/étapes  10  tableau de bord      5  téléchargements
  15  écritures courantes (compte rendu d'entretien, fiche de test)

Seuils D10 vérifiés à la fin (code de sortie 1 si un seul est dépassé) :
  p95 lecture <= 800 ms ; p95 écriture <= 1 500 ms ; génération de bout en bout p95 <= 20 s ;
  0 réponse 5xx ; taux d'erreur < 1 %.
Chaque seuil se surcharge par variable d'environnement (voir `Config`), mais un seuil relevé
doit être consigné dans le compte rendu de mesure.

Variables d'environnement :
  CHARGE_TOKEN_URL     URL du point d'accès jeton Keycloak
  CHARGE_CLIENT_ID     client OIDC (défaut onea-charge)
  CHARGE_COMPTES       fichier « utilisateur<TAB>mot de passe<TAB>rôle » (défaut .recette/comptes.txt)
  CHARGE_PREFIXE       préfixe des comptes retenus (défaut « charge » ; vide = tous)
  CHARGE_RESOLVE       « hote1,hote2=ip » : résolution locale sans DNS (recette)
  CHARGE_RESULTATS     dossier du résumé JSON (défaut loadtest/resultats)
L'hôte de l'API se donne avec l'option --host de Locust.
"""

from __future__ import annotations

import csv
import json
import os
import random
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from locust import HttpUser, between, events, task
from locust.env import Environment


def _flottant(nom: str, defaut: float) -> float:
    return float(os.environ.get(nom, defaut))


@dataclass(frozen=True)
class Config:
    p95_lecture_ms: float = _flottant("SEUIL_P95_LECTURE_MS", 800)
    p95_ecriture_ms: float = _flottant("SEUIL_P95_ECRITURE_MS", 1500)
    p95_generation_ms: float = _flottant("SEUIL_P95_GENERATION_MS", 20000)
    taux_erreur_max: float = _flottant("SEUIL_TAUX_ERREUR", 0.01)
    attente_generation_s: float = _flottant("CHARGE_ATTENTE_GENERATION_S", 60)
    client_id: str = os.environ.get("CHARGE_CLIENT_ID", "onea-charge")
    token_url: str = os.environ.get(
        "CHARGE_TOKEN_URL", "http://localhost:8180/realms/onea/protocol/openid-connect/token"
    )
    prefixe: str = os.environ.get("CHARGE_PREFIXE", "charge")
    comptes: str = os.environ.get("CHARGE_COMPTES", ".recette/comptes.txt")
    resultats: str = os.environ.get("CHARGE_RESULTATS", "loadtest/resultats")


CFG = Config()
API = "/api/v1"
ROLE_TABLEAU = {"RAI": "rai", "AUDITEUR": "auditor", "AUDITE": "auditee", "DG": "dg"}
# Statuts « de métier » admis sur les écritures : la donnée de départ peut ne plus s'y prêter
# (mission suspendue, entretien annulé, fiche soumise). Ils sont comptés à part et publiés, pas masqués.
REFUS_METIER = {400, 403, 404, 409, 422}
compteurs: dict[str, int] = {
    "refus_metier_ecriture": 0,
    "5xx": 0,
    "429": 0,
    "ecritures_sans_cible": 0,
    "generations_demandees": 0,
}

# --------------------------------------------------------------------------- résolution locale
_resolve = os.environ.get("CHARGE_RESOLVE", "")
if _resolve:
    _hotes, _, _ip = _resolve.partition("=")
    _table = {h.strip(): _ip.strip() for h in _hotes.split(",") if h.strip()}
    _getaddrinfo = socket.getaddrinfo

    def _getaddrinfo_local(host: Any, *args: Any, **kwargs: Any) -> Any:
        return _getaddrinfo(_table.get(host, host), *args, **kwargs)

    socket.getaddrinfo = _getaddrinfo_local  # type: ignore[assignment]


def charger_comptes() -> list[tuple[str, str, str]]:
    chemin = Path(CFG.comptes)
    if not chemin.exists():
        raise SystemExit(f"Fichier de comptes introuvable : {chemin}")
    lignes = []
    with chemin.open(newline="", encoding="utf-8") as f:
        for ligne in csv.reader(f, delimiter="\t"):
            if len(ligne) >= 3 and ligne[0].startswith(CFG.prefixe):
                lignes.append((ligne[0], ligne[1], ligne[2]))
    if not lignes:
        raise SystemExit(f"Aucun compte « {CFG.prefixe}* » dans {chemin}")
    return lignes


COMPTES = charger_comptes()
_prochain = 0


def _compte_suivant() -> tuple[str, str, str]:
    global _prochain  # noqa: PLW0603
    compte = COMPTES[_prochain % len(COMPTES)]
    _prochain += 1
    return compte


def _classer(reponse: Any) -> None:
    if reponse.status_code >= 500:  # noqa: PLR2004
        compteurs["5xx"] += 1
    elif reponse.status_code == 429:  # noqa: PLR2004
        compteurs["429"] += 1


class Utilisateur(HttpUser):
    wait_time = between(1, 3)
    # Les AUDITE et DG sont en lecture seule : les tâches d'écriture et de génération
    # sont sans effet pour eux (leur part de poids n'émet aucune requête).

    def on_start(self) -> None:
        self.login, self.mdp, self.role = _compte_suivant()
        self.jeton = ""
        self.jeton_expire = 0.0
        self.missions: list[str] = []
        self.entretiens: list[str] = []
        self.fiches: list[str] = []
        self.versions: list[str] = []
        ca = os.environ.get("REQUESTS_CA_BUNDLE")
        if ca:
            self.client.verify = ca
        self._authentifier()
        self._decouvrir()

    # ------------------------------------------------------------------ jeton
    def _authentifier(self) -> None:
        # Keycloak refuse parfois des connexions simultanées d'un MÊME compte (401 transitoire) :
        # jusqu'à 3 essais espacés. Avec 40 comptes distincts (recette) cela n'arrive pas.
        for essai in range(3):
            reponse = self.client.post(
                CFG.token_url,
                data={
                    "grant_type": "password",
                    "client_id": CFG.client_id,
                    "username": self.login,
                    "password": self.mdp,
                    "scope": "openid",
                },
                name="[AUTH] jeton",
            )
            if reponse.status_code == 200:  # noqa: PLR2004
                break
            time.sleep(0.5 + random.random() * (essai + 1))  # noqa: S311
        else:
            self.jeton = ""
            self.jeton_expire = time.time() + 5
            return
        corps = reponse.json()
        self.jeton = corps["access_token"]
        self.jeton_expire = time.time() + float(corps.get("expires_in", 60)) - 15

    def _entetes(self) -> dict[str, str]:
        if time.time() >= self.jeton_expire:
            self._authentifier()
        return {"Authorization": f"Bearer {self.jeton}"}

    # ------------------------------------------------------------------ appels
    def lire(self, chemin: str, nom: str) -> Any:
        """GET compté en lecture : seul 200 est un succès."""
        with self.client.get(
            chemin, headers=self._entetes(), name=f"[R] {nom}", catch_response=True
        ) as r:
            _classer(r)
            if r.status_code == 200:  # noqa: PLR2004
                r.success()
                try:
                    return r.json()
                except ValueError:
                    return None
            r.failure(f"HTTP {r.status_code}")
        return None

    def ecrire(self, methode: str, chemin: str, corps: dict[str, Any], nom: str) -> Any:
        """Écriture : 2xx = succès ; refus de métier (400/403/404/409/422) comptés à part."""
        with self.client.request(
            methode,
            chemin,
            json=corps,
            headers=self._entetes(),
            name=f"[W] {nom}",
            catch_response=True,
        ) as r:
            _classer(r)
            if 200 <= r.status_code < 300:  # noqa: PLR2004
                r.success()
                try:
                    return r.json()
                except ValueError:
                    return None
            if r.status_code in REFUS_METIER:
                compteurs["refus_metier_ecriture"] += 1
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")
        return None

    # ------------------------------------------------------------------ données de départ
    def _decouvrir(self) -> None:
        page = self.lire(f"{API}/missions/?page_size=25", "missions (découverte)")
        self.missions = [m["id"] for m in (page or {}).get("results", [])]
        if self.role in ("RAI", "AUDITEUR"):
            ent = self.lire(f"{API}/interviews/?page_size=25", "entretiens (découverte)")
            self.entretiens = [e["id"] for e in (ent or {}).get("results", [])]
            for mission in self.missions[:6]:
                fic = self.lire(
                    f"{API}/test-sheets/?mission={mission}&page_size=25", "fiches (découverte)"
                )
                self.fiches += [f["id"] for f in (fic or {}).get("results", [])]
        if self.role not in ("RAI", "AUDITEUR"):  # téléchargements : équipe d'audit seulement
            return
        docs = self.lire(f"{API}/documents/?page_size=25", "documents (découverte)")
        for d in (docs or {}).get("results", []):
            v = d.get("derniere_version") or {}
            if v.get("statut") == "PRETE":
                self.versions.append(v["id"])

    # ------------------------------------------------------------------ tâches (poids = %)
    @task(30)
    def listes_missions(self) -> None:
        choix = [(f"{API}/notifications/unread-count/", "notifications non lues")]
        if self.role == "DG":  # le DG n'a pas accès aux missions : synthèses de suivi
            choix += [
                (f"{API}/follow-up/recommendations/", "recommandations (suivi)"),
                (f"{API}/follow-up/actions/", "actions (suivi)"),
                (f"{API}/reports/", "rapports"),
            ]
        else:
            choix += [
                (f"{API}/missions/?page_size=25", "missions liste"),
                (f"{API}/missions/?page_size=50&ordering=-created_at", "missions liste p50"),
                (f"{API}/follow-up/recommendations/", "recommandations (suivi)"),
            ]
            choix.append((f"{API}/documents/?page_size=25", "documents liste"))
            if self.role == "RAI":
                choix.append((f"{API}/follow-up/missions/", "suivi missions"))
        chemin, nom = random.choice(choix)  # noqa: S311
        self.lire(chemin, nom)

    @task(25)
    def detail_mission_etapes(self) -> None:
        if not self.missions:
            return
        mission = random.choice(self.missions)  # noqa: S311
        self.lire(f"{API}/missions/{mission}/", "mission détail")
        if self.role != "AUDITE":  # 403 attendu : l'audité ne consulte pas les étapes
            self.lire(f"{API}/mission-steps/?mission={mission}", "étapes de mission")

    @task(10)
    def referentiel(self) -> None:
        choix = [(f"{API}/directions/", "directions"), (f"{API}/processes/", "processus")]
        if self.role in ("RAI", "AUDITEUR"):
            choix.append((f"{API}/risks/?page_size=25", "risques"))
        chemin, nom = random.choice(choix)  # noqa: S311
        self.lire(chemin, nom)

    @task(10)
    def tableau_de_bord(self) -> None:
        self.lire(f"{API}/dashboards/{ROLE_TABLEAU[self.role]}/", f"tableau de bord {self.role}")

    @task(15)
    def ecritures(self) -> None:
        if self.role not in ("RAI", "AUDITEUR"):
            return
        cibles: list[tuple[str, str]] = [("entretien", i) for i in self.entretiens]
        cibles += [("fiche", i) for i in self.fiches]
        if not cibles:
            compteurs["ecritures_sans_cible"] += 1
            return
        type_, ident = random.choice(cibles)  # noqa: S311
        horodatage = time.strftime("%H:%M:%S")
        if type_ == "entretien":
            self.ecrire(
                "PATCH",
                f"{API}/interviews/{ident}/",
                {"compte_rendu": f"Compte rendu de charge {self.login} {horodatage}."},
                "compte rendu d'entretien",
            )
        else:
            self.ecrire(
                "PATCH",
                f"{API}/test-sheets/{ident}/",
                {"travaux_realises": f"Travaux de charge {self.login} {horodatage}."},
                "fiche de test",
            )

    @task(5)
    def generation(self) -> None:
        """Demande de génération puis attente de l'état PRETE : durée de bout en bout."""
        if self.role not in ("RAI", "AUDITEUR") or not self.missions:
            return
        mission = random.choice(self.missions)  # noqa: S311
        dispo = self.lire(f"{API}/documents/available/?mission={mission}", "documents disponibles")
        candidats = [d for d in (dispo or []) if d.get("peut_generer") and not d.get("en_cours")]
        if not candidats:
            return
        choix = random.choice(candidats)  # noqa: S311
        debut = time.perf_counter()
        version = self.ecrire(
            "POST",
            f"{API}/documents/generate/",
            {"type_document": choix["type_document"], "objet": choix["objet_id"]},
            "génération (demande)",
        )
        if not version or "id" not in version:
            return
        compteurs["generations_demandees"] += 1
        statut = ""
        limite = debut + CFG.attente_generation_s
        while time.perf_counter() < limite:
            time.sleep(1)
            lu = self.lire(f"{API}/document-versions/{version['id']}/", "génération (suivi)")
            statut = (lu or {}).get("statut", "")
            if statut in ("PRETE", "ECHEC"):
                break
        duree_ms = (time.perf_counter() - debut) * 1000
        erreur = None
        if statut == "PRETE":
            self.versions.append(version["id"])
        else:
            erreur = Exception(f"génération non prête ({statut or 'sans réponse'})")
        self.environment.events.request.fire(
            request_type="E2E",
            name="[G] génération de bout en bout",
            response_time=duree_ms,
            response_length=0,
            exception=erreur,
            context={},
        )

    @task(5)
    def telechargements(self) -> None:
        if not self.versions:
            return
        version = random.choice(self.versions)  # noqa: S311
        self.lire(f"{API}/document-versions/{version}/download/?format=docx", "téléchargement docx")


# --------------------------------------------------------------------------- seuils D10
def _p95(env: Environment, prefixe: str) -> tuple[float | None, int]:
    """p95 le plus défavorable des routes du groupe (borne haute, aucune moyenne qui masque)."""
    groupe = [s for (nom, _m), s in env.stats.entries.items() if nom.startswith(prefixe)]
    groupe = [s for s in groupe if s.num_requests]
    if not groupe:
        return None, 0
    return max(s.get_response_time_percentile(0.95) for s in groupe), sum(
        s.num_requests for s in groupe
    )


@events.quitting.add_listener
def verifier_seuils(environment: Environment, **_: Any) -> None:
    total = environment.stats.total
    taux = total.num_failures / total.num_requests if total.num_requests else 1.0
    lecture, n_lecture = _p95(environment, "[R] ")
    ecriture, n_ecriture = _p95(environment, "[W] ")
    generation, n_generation = _p95(environment, "[G] ")
    regles: list[dict[str, Any]] = [
        {
            "seuil": f"p95 lecture (pire route) <= {CFG.p95_lecture_ms:g} ms",
            "mesure": lecture,
            "n": n_lecture,
            "ok": lecture is not None and lecture <= CFG.p95_lecture_ms,
        },
        {
            "seuil": f"p95 écriture (pire route) <= {CFG.p95_ecriture_ms:g} ms",
            "mesure": ecriture,
            "n": n_ecriture,
            "ok": ecriture is not None and ecriture <= CFG.p95_ecriture_ms,
        },
        {
            "seuil": f"p95 génération de bout en bout <= {CFG.p95_generation_ms:g} ms",
            "mesure": generation,
            "n": n_generation,
            "ok": generation is not None and generation <= CFG.p95_generation_ms,
        },
        {
            "seuil": "0 réponse 5xx",
            "mesure": compteurs["5xx"],
            "n": total.num_requests,
            "ok": compteurs["5xx"] == 0,
        },
        {
            "seuil": f"taux d'erreur < {CFG.taux_erreur_max * 100:g} %",
            "mesure": round(taux * 100, 3),
            "n": total.num_requests,
            "ok": taux < CFG.taux_erreur_max,
        },
    ]
    dossier = Path(CFG.resultats)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "resume.json").write_text(
        json.dumps(
            {"regles": regles, "compteurs": compteurs, "comptes": len(COMPTES)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n=== Seuils D10 ===")
    for r in regles:
        etat = "OK   " if r["ok"] else "ECHEC"
        print(f"{etat} {r['seuil']} -> mesure {r['mesure']} (n={r['n']})")
    print(f"Compteurs : {compteurs}")
    # Code explicite dans les deux cas : sinon Locust sortirait en 1 dès qu'une requête a échoué,
    # même sous les seuils (le taux d'erreur est jugé par la règle ci-dessus).
    environment.process_exit_code = 0 if all(r["ok"] for r in regles) else 1
