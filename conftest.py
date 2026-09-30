"""Met le dépôt sur sys.path pour que les tests puissent importer les
outils d'analyse (`tools/`) et les modules de tests (`tests/`), que le
paquet soit installé (editable/wheel) ou non.

Ces dossiers ne font pas partie du paquet publié (scripts d'audit hors
distribution) — cette conftest garantit des tests identiques en checkout
source ou en install classique.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))