"""Signaux de la communication.

`rapport_diffuse` (sender `Rapport`, arguments `rapport`, `diffusion`, `par`) est émis
`on_commit` à la diffusion (D14) ; le lot 8 s'y abonne.
"""

from django.dispatch import Signal

rapport_diffuse = Signal()
