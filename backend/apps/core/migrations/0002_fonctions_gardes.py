"""Fonctions PL/pgSQL du gel en base (lot 9, T10, D6).

Les déclencheurs eux-mêmes et les droits du rôle applicatif sont posés après la migration par le
récepteur `post_migrate` de `apps.core` (toutes les tables existent alors).
"""

from django.db import migrations


def installer_fonctions(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor != "postgresql":
        return
    from apps.core.gardes_sql import installer_fonctions as installer

    installer(schema_editor.connection)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(installer_fonctions, migrations.RunPython.noop)]
