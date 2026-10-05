# Programme de documentation — plan de travail

## Pourquoi ce fichier

Décisions prises avec le mainteneur sur la qualité de la documentation, et
méthode de réécriture. Ce document est un brouillon de travail : il vit dans
`atelier/`, versionné mais jamais livré.

## Le constat

Les notes de version étaient structurées par mécanisme interne (config,
témoin, outillage) et non par ce que le joueur vit. Conséquences :

- 90 commits, 57 fichiers, +4 229 lignes, invisibles dans la note ;
- le md5 du témoin et la note de semver occupaient l'espace le plus visible ;
- `docs/DEVIANCES.md`, la refonte du tool, la création du `CHANGELOG.md` et du
  `README_EN.md` n'étaient pas mentionnés ;
- aucune mention de ce que la version **ne** couvre pas.

## L'architecture retenue : trois étages

Le lecteur s'arrête où son besoin s'arrête. Chaque étage suppose qu'on a lu le
précédent, et n'est pas nécessaire au suivant.

| Étage | Pour qui | Contenu |
|---|---|---|
| **1. Jouer** | tout le monde | README, note de release, installation, dépannage |
| **2. Comprendre** | curieux, ~1 h | concept, modèle randput, ressources, recettes, arbre tech, solvabilité |
| **3. Développer** | développeurs | pipeline, modules, VanillaDB, runtime, config, témoin, dérives |

À ajouter dans `docs/README.md` : une table **« tu veux X → lis Y »** en tête.
C'est elle qui rend l'escalier explicite.

## Méthode de réécriture par IA

L'IA ne fournit **aucun** fait. Elle ne fait que reformuler ce que le
mainteneur a écrit. Le contenu est produit à partir d'une lecture du dépôt.

### Pipeline

1. Rédiger la version technique exhaustive du document, sans worrying de style.
2. Construire le prompt : contexte projet + document + **inventaire mécanique
   des invariants** + contre-exemples.
3. Un appel. `gemini-3.5-flash` ou `gemini-3.7-flash` (les `-preview` et
   `gemini-2.5-*` sont fermés ou saturés ; `gemini-flash-latest` est un alias
   roulant, utile comme secours).
4. Vérifier. Trois couches, dans cet ordre.
5. Corriger, puis commiter.

### Les trois couches de vérification

| Couche | Ce qu'elle attrape |
|---|---|
| Diff mécanique (`~/.config/randputf/verif-doc.sh`) | chiffre, chemin, version, empreinte qui bouge |
| Couverture | paragraphe d'origine sans descendant dans la réécriture |
| Relecture humaine contre le dépôt | erreur en prose, et non en token |

**La couche 1 ne suffit pas.** Constaté sur la note 1.0.1 : le diff a trouvé
`1.0.2` et `user.yaml`, et a laissé passer « les tests sont éliminatoires »
(faux terme) et « aucun fichier n'ayant été partagé » (fait faux — le zip
était téléchargeable). Les deux erreurs graves étaient en prose.

### Le prompt qui a fait la différence

Deux versions, même modèle.

- **Prompt simple** (« ne modifie aucun fait ») : 2 divergences de chiffres, 4
  erreurs de fond.
- **Prompt enrichi** : contexte projet, inventaire des chiffres/chemins/
  empreintes à recopier, liste de faits à ne pas déformer, et surtout **les
  erreurs de l'essai précédent en contre-exemples**. Résultat : 0 divergence,
  0 erreur.

Conclusion : la qualité du rendu suit la qualité de l'entrée. Un prompt
délibérément surchargé vaut mieux qu'un prompt court.

## Ce qui n'est pas fait

- **La release 1.0.1 publiée n'a pas été retirée** au moment de la première
  rédaction de ce plan. Si elle doit l'être, il faut supprimer **la release et
  le tag** : le workflow refuse de publier si le tag existe.
- L'escalier en trois étages n'est pas encore appliqué à `docs/README.md`.
- Les ~30 autres documents de prose n'ont pas été réécrits.
- `atelier/` n'est jamais réécrit sans accord explicite, fichier par fichier.

## Modèles

`gemini-3.8-flash` et `gemini-3.7-flash` sont stables mais **saturent souvent**
(erreur « high demand »). `gemini-3.5-flash` répondait le plus sûrement.
`gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite` : refusés,
« no longer available to new users ». Le quota gratuit est à 0 sur les modèles
Pro.
