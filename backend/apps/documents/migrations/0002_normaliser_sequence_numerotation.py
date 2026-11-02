"""Corrige les formats de numérotation enregistrés avec `{sequence:02d}`.

Le validateur refuse toute mise en forme de `{sequence}` (la séquence est déjà sur 2 chiffres) ;
les lignes créées avant ce durcissement bloquaient donc la génération des documents.
"""

import re

from django.db import migrations

_SEQUENCE_FORMATEE = re.compile(r"\{sequence[:!][^}]*\}")


def normaliser_modele(modele: str) -> str:
    return _SEQUENCE_FORMATEE.sub("{sequence}", modele)


def normaliser(apps, schema_editor):  # type: ignore[no-untyped-def]
    FormatNumerotation = apps.get_model("documents", "FormatNumerotation")
    for fmt in FormatNumerotation.objects.filter(modele__contains="{sequence"):
        nouveau = normaliser_modele(fmt.modele)
        if nouveau != fmt.modele:
            fmt.modele = nouveau
            fmt.save(update_fields=["modele"])


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]
    operations = [migrations.RunPython(normaliser, migrations.RunPython.noop)]
