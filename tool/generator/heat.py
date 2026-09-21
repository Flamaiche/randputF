"""Modèle « chaleur » (docs/energie.md §10bis).

La chaleur est un milieu transportable entre bâtiments via des conduites
capables de l'échanger :
- SOURCE        (``is_heat_source``, ex. nuclear-reactor)  : la produit ;
- TRANSPORT     (``is_heat_transport``, ex. heat-pipe)     : la fait circuler ;
- CONSOMMATEUR  (``is_heat_sink``, ex. heat-exchanger)     : la demande pour
  convertir son fluide d'entrée en fluide de sortie.

Un consommateur ne fonctionne QUE raccordé à une source via des conduites
(energy_source 'heat' vanilla). Un consommateur ne doit jamais être débloqué
avant sa source + transport (mirroir « extracteur avant besoin » du starter §7).
La garantie est posée à la volée par ``recursive_phase._ensure_heat_prereq`` :
au premier instant où un sink reçoit sa recette fluide→fluide, des steps
injectés AVANT la tech du consommateur débloquent la SOURCE et le TRANSPORT.

Le pool sans consommateur rend le modèle inerte : aucune contrainte ni unlock
ajoutée (une seed sans heat-exchanger ne voit rien).
"""

from __future__ import annotations

from tool.common.db import VanillaDB


def find_heat_roles(db: VanillaDB) -> dict[str, list[str]]:
    """Partition des bâtiments selon leur rôle dans le modèle chaleur.

    Retourne ``{"sources": [...], "transports": [...], "sinks": [...]}``.
    Si le pool n'a aucun consommateur, le modèle est inerte (aucune garantie
    ajoutée) ; si une source ou un transport manque, la chaîne est
    insatisfiable (jamais en vanilla — le validateur s'en chargerait).
    """
    sinks = sorted(b.name for b in db.buildings.values() if b.is_heat_sink)
    return {
        "sources": sorted(b.name for b in db.buildings.values() if b.is_heat_source),
        "transports": sorted(b.name for b in db.buildings.values() if b.is_heat_transport),
        "sinks": sinks,
    }