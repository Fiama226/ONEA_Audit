"""Certificat autosigné de DÉVELOPPEMENT et de test pour la signature PAdES.

Jamais utilisé en production : le certificat réel est fourni par l'ONEA (voir
`docs/exploitation/signature-electronique.md`). Aucune clé n'est versionnée.
"""

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


def generer_pkcs12(
    phrase: str, *, nom_commun: str = "ONEA Audit Interne (certificat de DEVELOPPEMENT)"
) -> tuple[bytes, bytes]:
    """Retourne (PKCS#12 chiffré par `phrase`, certificat PEM) d'un certificat autosigné RSA."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    nom = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BF"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ONEA"),
            x509.NameAttribute(NameOID.COMMON_NAME, nom_commun),
        ]
    )
    debut = datetime.now(UTC) - timedelta(minutes=5)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nom)
        .issuer_name(nom)
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(debut)
        .not_valid_after(debut + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(cle, hashes.SHA256())
    )
    chiffrement = serialization.BestAvailableEncryption(phrase.encode("utf-8"))
    return (
        pkcs12.serialize_key_and_certificates(b"onea-signature", cle, cert, None, chiffrement),
        cert.public_bytes(serialization.Encoding.PEM),
    )
