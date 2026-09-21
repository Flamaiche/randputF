"""Loot du site de crash (§7) : pile pondérée 0..3 par slot.

Le kit vanilla (pistolets, plaques, etc.) est vidé ; chaque slot reçoit un
nombre `n` d'un matériau aléatoire du pool, où `n ∈ {0,1,2,3}` suit une loi
pondérée STRICTEMENT décroissante : 0 = plus fréquent (slots vides), 3 = plus
rare. La formule paramétrique (exchangée avec le joueur) garantit la somme
des poids × valeur = 100 :

    c3 = t,  c2 = t + a,  c1 = 100 − 5t − 2a,  c0 = c1 + b

avec la contrainte 6t + 3a < 100 (⟺ c1 > c2, b ≥ 1), ce qui donne
c0 > c1 > c2 > c3. Les `c_i` sont les poids de tirage (P(0) = c0 / Σ),
exportés dans la seed sous `wreck.counts = [c0, c1, c2, c3]`.
"""

from __future__ import annotations

from tool.common.db import VanillaDB

# Butins de base : ressources NON-infinies uniquement (bois, pierre, poisson).
# Pas d'item crafté (plaques, fours...) dont la recette n'est pas garantie.
DEFAULT_LOOT = [
    "wood",
    "stone",
    "raw-fish",
]

# Paramètres par défaut de la formule : c0=24, c1=23, c2=16, c3=15 — P(0) ≈
# 31 %, vaisseau (5 slots) ≈ 6,4 items en moyenne.
DEFAULT_T = 15
DEFAULT_A = 1
DEFAULT_B = 1


def counts_from_formula(t: int, a: int, b: int) -> list[int]:
    """Calcule [c0, c1, c2, c3] depuis la formule générique et vérifie les
    invariants (décroissance stricte + somme des valeurs = 100)."""
    if not (isinstance(t, int) and isinstance(a, int) and isinstance(b, int)):
        raise ValueError("wreck: t, a, b doivent être des entiers")
    c3 = t
    c2 = t + a
    c1 = 100 - 5 * t - 2 * a
    c0 = c1 + b
    counts = [c0, c1, c2, c3]
    if any(c < 0 for c in counts):
        raise ValueError(f"wreck: compte négatif {counts}")
    if not (c0 > c1 > c2 > c3):
        raise ValueError(
            f"wreck: comptes non strictement décroissants {counts} "
            "(exiger 6t + 3a < 100 et b >= 1)"
        )
    value_sum = sum(i * c for i, c in enumerate(counts))
    if value_sum != 100:
        raise ValueError(f"wreck: somme des valeurs {value_sum} != 100 ({counts})")
    return counts


def build_wreck_config(config: dict | None, db: VanillaDB) -> dict:
    """Assemble la section `wreck` de la seed depuis la config."""
    cfg = (config or {}).get("wreck") or {}
    counts = counts_from_formula(
        int(cfg.get("t", DEFAULT_T)),
        int(cfg.get("a", DEFAULT_A)),
        int(cfg.get("b", DEFAULT_B)),
    )
    loot = [name for name in (cfg.get("loot") or DEFAULT_LOOT) if name in db.items]
    if not loot:
        raise ValueError("wreck: pool de loot vide après filtrage (items absents de la base)")
    return {"loot": loot, "counts": counts}