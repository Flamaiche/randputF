"""Modèle « chaleur » (README §10bis / docs/tags.md §5bis).

La chaleur est un milieu transportable entre bâtiments — à la manière d'un
fluide qui ne circulerait que dans les éléments capables de l'échanger :
- SOURCE        (``is_heat_source``, ex. nuclear-reactor)  : la PRODUIT ;
- TRANSPORT     (``is_heat_transport``, ex. heat-pipe)     : la fait circuler ;
- CONSOMMATEUR  (``is_heat_sink``, ex. heat-exchanger)     : la DEMANDE pour
  convertir son fluide d'entrée en fluide de sortie.

En jeu, un consommateur ne fonctionne QUE raccordé à une source via des
conduites (energy_source 'heat' vanilla = réseau de chaleur réel). Pour que la
suite reste faisable, un consommateur ne doit JAMAIS être débloqué avant sa
source + son transport — miroir de la garantie « extracteur avant besoin » du
starter (§7). La garantie est posée à la volée : au premier instant où un sink
reçoit sa recette de craft (recette fluide→fluide, créée par la phase
récursive), ``recursive_phase._ensure_heat_prereq`` injecte — AVANT la tech du
consommateur — des steps qui débloquent la SOURCE et le TRANSPORT.

Le pool sans consommateur rend le modèle parfaitement inerte : il n'ajoute
aucune contrainte ni aucun unlock (une seed sans heat-exchanger ne voit rien).
"""

from __future__ import annotations

from tool.common.db import VanillaDB


def find_heat_roles(db: VanillaDB) -> dict[str, list[str]]:
    """Partition des bâtiments selon leur rôle dans le modèle chaleur.

    Retourne ``{"sources": [...], "transports": [...], "sinks": [...]}``.
    Une seule des trois listes est vide lorsque le pool n'a AUCUN consommateur
    (le modèle est alors inerte : aucune garantie n'est ajoutée) ou lorsqu'une
    source/un transport manque pour assouvir les sinks (chaîne insatisfiable,
    jamais en vanilla — le validateur s'en chargerait).
    """
    sinks = sorted(b.name for b in db.buildings.values() if b.is_heat_sink)
    return {
        "sources": sorted(b.name for b in db.buildings.values() if b.is_heat_source),
        "transports": sorted(b.name for b in db.buildings.values() if b.is_heat_transport),
        "sinks": sinks,
    }