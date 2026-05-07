# SKILLS.md — `shopping/`

Recettes paramétriques pour les tâches récurrentes sur le backend `shopping`.
Pour les tâches cross-repo, voir `../SKILLS.md` à la racine du workspace.

Format : chaque skill est identifiée `SK-SH##` (SH = Shopping).

---

## SK-SH01 — Ajouter une nouvelle entité métier

**Contexte :** ajouter une entité de domaine avec persistence et exposition REST + MCP.

### Référence canonique

`docs/new-entity.md` est le guide pas-à-pas complet. Mêmes étapes que `recipe/` (voir `../recipe/SKILLS.md` SK-R01).

### Checklist synthétique

1. **Domain** : `domain/models/<entity>.py` + `domain/ports/output/<entity>_repository.py`.
2. **Application** : `application/services/<entity>_service.py` + use cases si nécessaire.
3. **Adapters output (les trois)** : `memory`, `mongodb`, `duckdb`.
4. **Adapters input** : schéma + router REST + tools MCP.
5. **Infrastructure** : container DI + ré-export.
6. **Tests** : domain + memory repo, coverage ≥ 80 %.
7. **Documentation** : entrée `journal/` à la racine du workspace.

### Validation

```bash
make precommit
make coverage
MODE=all uv run python main.py
```

---

## SK-SH02 — Ajouter un tool MCP

**Contexte :** exposer une nouvelle opération via MCP (consommée par `shopping-agent` ou autre).

### Étapes

1. `adapters/input/fastmcp/tools/<entity>_tools.py` — méthode `@mcp.tool()`, docstring soignée.
2. Vérifier l'enregistrement dans `adapters/input/fastmcp/register.py` → `register_tools()`.
3. Schémas pydantic pour les structures complexes.
4. Test : `tests/units/adapters/input/fastmcp/test_<entity>_tools.py`.

### Validation

```bash
make test-unit
MODE=mcp_http uv run python main.py
```

---

## SK-SH03 — Étendre le contrat avec `meal-planner/`

**Contexte :** lire un nouveau champ d'un plan ou un nouveau filtre depuis `meal-planner/`.

### Étapes

1. Vérifier que le champ existe côté `meal-planner/`. Si non : intervenir d'abord dans `meal-planner/`.

2. Étendre le port `domain/ports/output/meal_plan_client.py`.

3. Mettre à jour `adapters/output/http/`.

4. Mettre à jour les stubs mémoire utilisés en tests.

### Validation

```bash
make test-unit
./start_services.sh up meal-planner
./start_services.sh up shopping
```

---

## SK-SH04 — Ajuster la logique d'agrégation d'une projection

**Contexte :** changer la façon dont les ingrédients sont groupés (par rayon, par fournisseur, par recette source...) ou fusionnés (mêmes UUID, mêmes unités).

### Étapes

1. Identifier le use case responsable dans `application/services/` (recherche : `Projection`, `aggregate`, `merge`).

2. Si la modification change le **format de sortie**, créer une nouvelle version du schéma (pas une mutation rétroactive). Coexister un temps, déprécier l'ancien.

3. Tests : ajouter un cas qui couvre l'agrégation à partir d'un plan multi-recettes avec doublons d'ingrédients.

4. Si la modification touche la sémantique métier (ex. inclure/exclure les ingrédients du frigo) : entrée journal explicite avec le **pourquoi**.

### Validation

```bash
make test-unit
MODE=api uv run python main.py
# Générer une projection sur un plan connu, vérifier le format.
```

---

## SK-SH05 — Diagnostiquer une liste vide ou incomplète

**Contexte :** une liste générée à partir d'un plan ne contient pas tous les ingrédients attendus.

### Étapes

1. Vérifier que `meal-planner/` répond et que le plan référencé existe :

   ```bash
   curl -fsS "http://127.0.0.1:8010/meal-planner/v1/<plan_uuid>" | jq
   ```

2. Vérifier les snapshots du plan : si un slot a un `MealItem` sans `RecipeSnapshot`, l'agrégation ne le prend pas en compte.

3. Logs `shopping` : repérer les warnings `meal_plan_client` (timeout, 4xx, parsing).

4. Vérifier les exclusions explicites côté `Supplier` ou `ShoppingList` (champs `excluded_*`).

### Validation

```bash
./start_services.sh logs shopping | tail -50
```

---

## SK-SH06 — Migrer un schéma `ShoppingList` ou `Supplier`

**Contexte :** changer la forme d'un document persisté.

### Étapes

Mêmes principes que `../meal-planner/SKILLS.md` SK-MP05 :

1. Migration progressive (optionnel → backfill → obligatoire).
2. Script idempotent dans `scripts/`.
3. Snapshot Mongo avant migration (`../SKILLS.md` SK-W03).
4. Tests sur l'ancien format.

### Validation

```bash
make test-unit
make coverage
```

---

## SK-SH07 — Restaurer ou exporter la base MongoDB locale

**Contexte :** repartir d'un état connu.

Voir `../SKILLS.md` SK-W03. Base par défaut : `shopping` (cf. `config/adapters/output/mongodb.yaml`).
