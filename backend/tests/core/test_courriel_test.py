from io import StringIO

import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import override_settings


def _lancer(*args: str) -> str:
    sortie = StringIO()
    call_command("envoyer_courriel_test", *args, stdout=sortie)
    return sortie.getvalue()


def test_envoie_un_message_en_francais() -> None:
    sortie = _lancer("rai@recette.test")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["rai@recette.test"]
    assert "essai" in message.subject.lower()
    assert "envoyé" in sortie.lower()
    assert "rai@recette.test" in sortie


SECRET = "mot-de-passe-secret"  # noqa: S105


@override_settings(EMAIL_HOST="smtp.onea.test", EMAIL_PORT=587, EMAIL_HOST_PASSWORD=SECRET)
def test_n_affiche_aucun_secret() -> None:
    sortie = _lancer("rai@recette.test")
    assert SECRET not in sortie
    assert SECRET not in mail.outbox[0].body
    assert "smtp.onea.test" in sortie


def test_refuse_une_adresse_invalide() -> None:
    with pytest.raises(CommandError, match="invalide"):
        _lancer("pas-une-adresse")
    assert mail.outbox == []


def test_echec_d_envoi_sans_fuite(monkeypatch: pytest.MonkeyPatch) -> None:
    def echec(*_a: object, **_k: object) -> int:
        raise OSError("connexion refusée")

    monkeypatch.setattr("django.core.mail.EmailMessage.send", echec)
    with override_settings(EMAIL_HOST_PASSWORD=SECRET):
        with pytest.raises(CommandError) as exc:
            _lancer("rai@recette.test")
    assert SECRET not in str(exc.value)
    assert "échec" in str(exc.value).lower()
