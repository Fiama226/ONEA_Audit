"""Comptes de démonstration : comptes locaux à mot de passe temporaire.

Les comptes passent par l'import CSV du service de provisionnement (acteur « demo » dans la
piste d'audit) : chacun reçoit un mot de passe temporaire (72 h, à changer à la première
connexion), sans courriel. Ceux des six comptes de test (`COMPTES_TEST`) sont affichés UNE
fois par la commande ; les autres ne le sont jamais (réinitialisation par l'administrateur).
Aucune copie n'est conservée : le fichier de mots de passe de l'import est lu puis détruit
aussitôt. Deux exceptions assumées : l'acteur système `demo` (inactif, jamais connectable)
et le compte `admin`, créé directement car un import ne donne jamais le rôle ADMIN.
"""

import csv
import io
from uuid import UUID

from auditlog.context import disable_auditlog
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.demo import ACTEUR, ContexteDemo
from apps.referentiel.models import Direction

from .auth_services import generer_mot_de_passe_temporaire
from .delegation import acteur_systeme
from .models import OrigineCompte, Role, User
from .provisioning import importer_csv, lire_fichier_mots_de_passe
from .services import _poser_mot_de_passe_temporaire, modifier_profil

# Comptes de test dont le mot de passe temporaire est affiché (profil volumetrie).
COMPTES_TEST = ("admin", "rai", "auditeur1", "auditeur2", "audite1", "dg")

PRENOMS = (
    "Awa", "Salif", "Mariam", "Issouf", "Fatoumata", "Boureima", "Aminata", "Adama",
    "Rasmata", "Moussa", "Estelle", "Ibrahim", "Clarisse", "Daouda", "Odette", "Harouna",
    "Pauline", "Lassané", "Edwige", "Souleymane", "Irène", "Abdoul", "Nadège", "Yacouba",
)  # fmt: skip
NOMS = (
    "Ouédraogo", "Traoré", "Sawadogo", "Kaboré", "Zongo", "Compaoré", "Sankara", "Ilboudo",
    "Barry", "Diallo", "Konaté", "Nikièma", "Tapsoba", "Zoungrana", "Savadogo", "Bationo",
    "Ouattara", "Sanou", "Kiemdé", "Yaméogo", "Belem", "Coulibaly", "Dabiré", "Kafando",
)  # fmt: skip
FONCTIONS = {
    Role.RAI: "Responsable de l'audit interne",
    Role.AUDITEUR: "Auditeur interne",
    Role.AUDITE: "Responsable de service",
    Role.DG: "Directeur général",
}


def _plan(ctx: ContexteDemo) -> list[tuple[str, Role]]:
    """(identifiant, rôle) à créer par l'import CSV, dans l'ordre."""
    if ctx.profil == "formation":
        return [
            ("formation.rai", Role.RAI),
            *[(f"formation.auditeur{i}", Role.AUDITEUR) for i in (1, 2, 3)],
            *[(f"formation.audite{i}", Role.AUDITE) for i in (1, 2)],
            ("formation.dg", Role.DG),
        ]
    plan: list[tuple[str, Role]] = [("rai", Role.RAI), ("dg", Role.DG)]
    plan += [(f"auditeur{i}", Role.AUDITEUR) for i in range(1, 11)]
    plan += [(f"audite{i}", Role.AUDITE) for i in range(1, 8)]
    n = ctx.volumes.comptes_charge
    nb_auditeurs = -(-n * 3 // 5)  # 60 % d'auditeurs, le reste d'audités
    for i in range(1, n + 1):
        role = Role.AUDITEUR if i <= nb_auditeurs else Role.AUDITE
        plan.append((f"charge{i:02d}", role))
    return plan


def _csv(ctx: ContexteDemo, plan: list[tuple[str, Role]]) -> bytes:
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie)
    ecrivain.writerow(
        ["identifiant", "email", "prenom", "nom", "matricule", "direction", "fonction", "role"]
    )
    for rang, (identifiant, role) in enumerate(plan, start=1):
        ecrivain.writerow(
            [
                identifiant,
                f"{identifiant}@example.org",
                ctx.rng.choice(PRENOMS),
                ctx.rng.choice(NOMS),
                f"DEMO-{rang:04d}",
                "",
                FONCTIONS[role],
                role.value,
            ]
        )
    return sortie.getvalue().encode("utf-8")


def _rattacher_aux_directions(ctx: ContexteDemo) -> None:
    """Après le référentiel : direction d'appartenance de chaque compte (service de profil)."""
    directions = [d.code for d in Direction.objects.filter(type="DIRECTION").order_by("code")]
    autres = [c for c in directions if c != "DAI"] or directions
    # The inactive system actor only has rights inside this explicit block.
    with acteur_systeme(ctx.acteur):
        for compte in User.objects.exclude(username__in=[ACTEUR]).order_by("username"):
            if compte.role in (Role.AUDITE, Role.DG):
                code = ctx.rng.choice(autres) if compte.role == Role.AUDITE else "DAI"
            else:
                code = "DAI"
            if code in directions:
                modifier_profil(compte, changes={"direction_code": code}, by=ctx.acteur)


def _mots_de_passe(fichier_id: UUID | None, acteur: User) -> dict[str, str]:
    """Read (and so destroy) the import's password file: identifiant -> password."""
    if fichier_id is None:
        return {}
    texte = lire_fichier_mots_de_passe(fichier_id, par=acteur)
    lecteur = csv.DictReader(io.StringIO(texte.lstrip("\ufeff")), delimiter=";")
    return {ligne["identifiant"]: ligne["mot_de_passe_temporaire"] for ligne in lecteur}


def _afficher_comptes_de_test(ctx: ContexteDemo, mots_de_passe: dict[str, str]) -> None:
    affiches = [(c, mots_de_passe[c]) for c in COMPTES_TEST if c in mots_de_passe]
    if not affiches:
        return
    ctx.ecrire(
        "  Comptes de test, mot de passe temporaire affiché une seule fois (valable 72 h, "
        "à changer à la première connexion) :"
    )
    for identifiant, mot_de_passe in affiches:
        ctx.ecrire(f"    {identifiant} : {mot_de_passe}")


def peupler(ctx: ContexteDemo) -> None:
    # Acteur système : inactif, mot de passe inutilisable. Sa propre création ne peut pas
    # avoir d'acteur : c'est la seule écriture hors piste d'audit.
    with disable_auditlog():
        acteur = User(
            username=ACTEUR,
            first_name="Données de",
            last_name="démonstration",
            role=Role.ADMIN,
            is_active=False,
            origine=OrigineCompte.CSV,
        )
        acteur.set_unusable_password()
        acteur.save()
    ctx.acteur = acteur

    plan = _plan(ctx)
    # The inactive system actor only has rights inside this explicit block.
    with acteur_systeme(acteur):
        rapport = importer_csv(_csv(ctx, plan), by=acteur, dry_run=False, envoyer_courriel=False)
    if rapport.ignores:
        raise RuntimeError(f"Comptes de démonstration refusés : {rapport.ignores}")
    mots_de_passe = _mots_de_passe(rapport.fichier_mots_de_passe_id, acteur)

    if ctx.profil == "volumetrie":
        mot_de_passe = generer_mot_de_passe_temporaire()
        with actor_scope(acteur):
            admin = User(
                username="admin",
                email="admin@example.org",
                first_name=ctx.rng.choice(PRENOMS),
                last_name=ctx.rng.choice(NOMS),
                matricule="DEMO-ADMIN",
                role=Role.ADMIN,
                origine=OrigineCompte.CSV,
                fonction="Administrateur de la plateforme",
            )
            _poser_mot_de_passe_temporaire(admin, mot_de_passe, timezone.now())
            admin.save()
        mots_de_passe["admin"] = mot_de_passe
    _afficher_comptes_de_test(ctx, mots_de_passe)

    comptes = {u.username: u for u in User.objects.exclude(username=ACTEUR)}
    ctx.groupes["rai"] = [u for u in comptes.values() if u.role == Role.RAI]
    ctx.groupes["dg"] = [u for u in comptes.values() if u.role == Role.DG]
    ctx.groupes["auditeurs"] = sorted(
        (u for u in comptes.values() if u.role == Role.AUDITEUR), key=lambda u: u.username
    )
    ctx.groupes["audites"] = sorted(
        (u for u in comptes.values() if u.role == Role.AUDITE), key=lambda u: u.username
    )
    ctx.finaliseurs.append(lambda: _rattacher_aux_directions(ctx))
