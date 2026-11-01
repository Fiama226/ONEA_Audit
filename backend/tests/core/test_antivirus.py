"""Point d'extension antivirus : moteur `aucun` et client clamd (serveur simulé sur socket)."""

import io
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from apps.core import antivirus
from apps.core.antivirus import AntivirusIndisponibleError
from apps.core.fichiers import FichierRefuseError

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@contextmanager
def faux_clamd(repondre: Callable[[bytes], bytes]) -> Iterator[tuple[int, list[bytes]]]:
    """Serveur INSTREAM minimal : lit le flux, répond `repondre(contenu)` puis ferme."""
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)
    recus: list[bytes] = []

    def servir() -> None:
        conn, _ = serveur.accept()
        with conn:
            commande = b""
            while not commande.endswith(b"\x00"):
                commande += conn.recv(1)
            assert commande == b"zINSTREAM\x00"
            contenu = b""
            while True:
                taille = struct.unpack("!I", _lire(conn, 4))[0]
                if taille == 0:
                    break
                contenu += _lire(conn, taille)
            recus.append(contenu)
            conn.sendall(repondre(contenu))

    fil = threading.Thread(target=servir, daemon=True)
    fil.start()
    try:
        yield serveur.getsockname()[1], recus
    finally:
        fil.join(timeout=5)
        serveur.close()


def _lire(conn: socket.socket, n: int) -> bytes:
    donnees = b""
    while len(donnees) < n:
        morceau = conn.recv(n - len(donnees))
        assert morceau
        donnees += morceau
    return donnees


@pytest.fixture
def clamd(settings: Any) -> Any:
    settings.ANTIVIRUS_MOTEUR = "clamd"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    return settings


def test_moteur_aucun_accepte_sans_rien_lire(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "aucun"
    flux = io.BytesIO(EICAR)
    antivirus.analyser(flux)
    assert flux.tell() == 0


def test_clamd_fichier_sain_accepte(clamd: Any) -> None:
    contenu = b"%PDF-1.7 " + b"x" * 200_000  # plusieurs blocs
    with faux_clamd(lambda c: b"stream: OK\x00") as (port, recus):
        clamd.ANTIVIRUS_CLAMD_PORT = port
        flux = io.BytesIO(contenu)
        antivirus.analyser(flux)
    assert recus == [contenu]
    assert flux.tell() == 0


def test_clamd_eicar_refuse_400(clamd: Any) -> None:
    def reponse(contenu: bytes) -> bytes:
        return b"stream: Eicar-Signature FOUND\x00" if b"EICAR" in contenu else b"stream: OK\x00"

    with faux_clamd(reponse) as (port, _):
        clamd.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(FichierRefuseError) as exc:
            antivirus.analyser(io.BytesIO(EICAR))
    assert exc.value.status_http == 400
    assert exc.value.message == "Le fichier a été refusé par l'analyse antivirus."


def test_clamd_injoignable_503(clamd: Any) -> None:
    with socket.socket() as s:  # port libre puis fermé : connexion refusée
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    clamd.ANTIVIRUS_CLAMD_PORT = port
    with pytest.raises(AntivirusIndisponibleError) as exc:
        antivirus.analyser(io.BytesIO(b"x"))
    assert exc.value.status_http == 503
    assert exc.value.message == "Analyse antivirus indisponible : réessayez plus tard."


def test_clamd_reponse_erreur_503(clamd: Any) -> None:
    with faux_clamd(lambda c: b"UNKNOWN COMMAND. ERROR\x00") as (port, _):
        clamd.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(AntivirusIndisponibleError):
            antivirus.analyser(io.BytesIO(b"x"))


def test_clamd_connexion_coupee_503(clamd: Any) -> None:
    with faux_clamd(lambda c: b"") as (port, _):  # ferme sans répondre
        clamd.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(AntivirusIndisponibleError):
            antivirus.analyser(io.BytesIO(b"x"))


def test_clamd_delai_depasse_503(clamd: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(antivirus, "DELAI_SECONDES", 0.3)
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)  # accepte au niveau du noyau mais ne répond jamais
    try:
        clamd.ANTIVIRUS_CLAMD_PORT = serveur.getsockname()[1]
        with pytest.raises(AntivirusIndisponibleError):
            antivirus.analyser(io.BytesIO(b"x"))
    finally:
        serveur.close()


# --- SEC-04 : production (moteur clamav, échec fermé, taille) -------------------------------


def test_moteur_clamav_synonyme_de_clamd(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    with faux_clamd(lambda c: b"stream: Eicar-Signature FOUND\x00") as (port, _):
        settings.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(FichierRefuseError):
            antivirus.analyser(io.BytesIO(EICAR))


def _port_ferme() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_echec_ferme_par_defaut_refuse_si_injoignable(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_CLAMD_PORT = _port_ferme()
    assert settings.ANTIVIRUS_ECHEC_FERME is True
    with pytest.raises(AntivirusIndisponibleError) as exc:
        antivirus.analyser(io.BytesIO(b"x"))
    assert exc.value.status_http == 503


def test_echec_ouvert_explicite_accepte_si_injoignable(
    settings: Any, caplog: pytest.LogCaptureFixture
) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_CLAMD_PORT = _port_ferme()
    settings.ANTIVIRUS_ECHEC_FERME = False
    flux = io.BytesIO(b"x")
    antivirus.analyser(flux)  # ne lève pas
    assert flux.tell() == 0
    assert "échec ouvert" in caplog.text


def test_echec_ouvert_refuse_quand_meme_un_virus(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_ECHEC_FERME = False
    with faux_clamd(lambda c: b"stream: Eicar-Signature FOUND\x00") as (port, _):
        settings.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(FichierRefuseError):
            antivirus.analyser(io.BytesIO(EICAR))


@pytest.mark.parametrize("echec_ferme", [True, False])
def test_fichier_trop_gros_refuse_sans_contacter_clamd(settings: Any, echec_ferme: bool) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_CLAMD_PORT = _port_ferme()  # toute connexion échouerait
    settings.ANTIVIRUS_ECHEC_FERME = echec_ferme
    settings.ANTIVIRUS_TAILLE_MAX_OCTETS = 10
    with pytest.raises(FichierRefuseError) as exc:
        antivirus.analyser(io.BytesIO(b"x" * 11))
    assert exc.value.status_http == 400
    assert "trop volumineux" in exc.value.message


def test_fichier_a_la_limite_est_analyse(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_TAILLE_MAX_OCTETS = 10
    with faux_clamd(lambda c: b"stream: OK\x00") as (port, recus):
        settings.ANTIVIRUS_CLAMD_PORT = port
        antivirus.analyser(io.BytesIO(b"x" * 10))
    assert recus == [b"x" * 10]


def test_limite_par_defaut_alignee_sur_nginx(settings: Any) -> None:
    assert settings.ANTIVIRUS_TAILLE_MAX_OCTETS == settings.PIECE_TAILLE_MAX_OCTETS == 50 * 2**20


def test_clamd_depasse_sa_propre_limite_refuse_400(settings: Any) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamav"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    with faux_clamd(lambda c: b"INSTREAM size limit exceeded. ERROR\x00") as (port, _):
        settings.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(FichierRefuseError):
            antivirus.analyser(io.BytesIO(b"x"))
