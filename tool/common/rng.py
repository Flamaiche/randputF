"""Flux RNG de la génération — construction centralisée.

Chaque phase consomme un flux RNG **dédié** (`random.Random`), indépendant des
autres et déterministe par seed : aucune phase n'altère les tirages d'une
autre, et rejouer une seed reproduit le même `seed.json` octet pour octet.
`make_seeded_rng` est l'unique fabrique : le **préfixe** (espace de noms de la
phase) est une constante stable — le changer modifierait toutes les seeds
historiques, le déterminisme byte-à-byte et les balayages de rejouabilité en
dépendent (cf. `docs/nondeterminism.md`).
"""

import random


def make_seeded_rng(seed_value: int, prefix: str) -> random.Random:
    """Retourne le flux RNG de la phase ``prefix``, déterministe par seed.

    Le flux est `random.Random(f"{prefix}{seed_value}")` : ``prefix`` est
    comparé à l'identité de la phase (« randputF:lakes: », « randputF:wells: »,
    « randputf:extractor-timing: », …) et doit rester **stable** — c'est lui
    qui isole les tirages de la phase et garantit la reproductibilité.
    """
    return random.Random(f"{prefix}{seed_value}")