# AGENTS.md — `shopping/`

Document d'entrée pour tout agent de codage qui intervient sur ce repo.
Lecture obligatoire avant toute modification.

Pour le contexte global du projet et les conventions transverses, voir `../AGENTS.md` à la racine du workspace.

---

## 1. Rôle

`shopping/` est le **backend du domaine liste de courses** de Rekipe. Il détient :

- les listes de courses (`ShoppingList`) ;
- les projections (`ShoppingProjection`) — agrégation prête à imprimer / cocher ;
- les fournisseurs (`Supplier`).

Le service **consomme** `meal-planner/` via HTTP (adapter `adapters/output/http`) pour générer une liste à partir d'un plan de repas. Il **expose** ses entités via REST + MCP au frontend `gwel` et à l'agent `shopping-agent`.

## 2. Stack et ports

| Élément | Valeur |
|---|---|
| Langage | Python 3.13 |
| Gestionnaire deps | `uv` |
| Framework de base | `arclith` |
| Web | FastAPI |
| MCP | FastMCP |
| Stockage prod | MongoDB (port `5971` en local) |
| Stockages alternatifs | `memory` (tests), `duckdb` (alt) |
| Auth | Keycloak (port `5990` en local) |
| REST | `8020` |
| MCP HTTP | `8021` |
| Probes (health/ready/metrics) | `9020` |
| Source de données externe | `meal-planner/` (REST `8010`) |

**Ne jamais changer ces ports** sans mettre à jour `start_services.sh`, `gwel/vite.config.ts`, et `shopping-agent/config.yaml`.

## 3. Architecture locale

Architecture hexagonale (mêmes principes que `recipe/` et `meal-planner/`) :

```
domain/
  models/                              # ShoppingList, ShoppingProjection, Supplier, enums
  exceptions.py
  ports/
    output/
      shopping_list_repository.py      # Persistence des listes
      supplier_repository.py           # Persistence des fournisseurs
      meal_plan_client.py              # Lecture plans depuis meal-planner/

application/                           # Services + use cases (génération de liste)

adapters/
  input/
    fastapi/                           # Routers REST
    fastmcp/                           # Tools MCP
    schemas/
  output/
    mongodb/repositories/              # Adapter prod
    memory/repositories/               # Adapter tests
    duckdb/repositories/               # Adapter alt
    http/                              # Client HTTP vers meal-planner/

infrastructure/
  containers/
  container.py
  logging_setup.py

config/
tests/units/
main.py                                # Entry point unique (MODE env var)
```

### Modes de lancement

Identiques à `recipe/` et `meal-planner/` (`api`, `mcp_http`, `mcp_sse`, `all`).

## 4. Règles de développement

### Règles transverses (rappel — voir `../AGENTS.md` §4)

- Architecture hexagonale stricte. `domain/` ne dépend que de `arclith` + `pydantic`.
- MongoDB est le seul adaptateur de production.
- Les plans de repas ne sont **jamais dupliqués en base**. La liste de courses lit `meal-planner/` via HTTP au moment de la génération, puis matérialise un agrégat figé.

### Règles spécifiques à ce repo

- **Génération idempotente** : régénérer une liste à partir du même plan doit produire le même résultat (modulo timestamp).
- **Pas de mutation rétroactive** : modifier un plan ne doit pas modifier les listes déjà générées. Les listes ont leur propre cycle de vie.
- **Tout nouveau tool MCP** doit être enregistré dans `adapters/input/fastmcp/register.py`.
- **Toute nouvelle route REST** doit être enregistrée dans `adapters/input/fastapi/register.py`.
- **Couverture de tests ≥ 80 %** : `make coverage`.
- **Pre-commit** : `make precommit` avant tout push.
- **Aucun secret** dans `config/*.yaml` versionné. Vault uniquement (`docs/vault.md`).

### Qualité

```bash
make lint typecheck security complexity
make test test-unit test-e2e
make coverage
make quality
make precommit
```

## 5. Commandes utiles

### Lancement local manuel

```bash
uv sync --group dev
MODE=all uv run python main.py
```

(Préférer `./start_services.sh up shopping` depuis la racine.)

### Vérifier la connexion à `meal-planner/`

```bash
curl -fsS "http://127.0.0.1:8010/meal-planner/v1/" | jq '.[0:1]'
```

## 6. Fichiers à lire en premier

1. `main.py` — entry point.
2. `domain/models/shopping_list.py` — modèle métier central.
3. `domain/models/shopping_projection.py` — agrégation prête à consommer.
4. `domain/models/supplier.py`.
5. `domain/ports/output/meal_plan_client.py` — contrat avec `meal-planner/`.
6. `adapters/output/http/` — implémentation du client HTTP.
7. `application/services/` — services métier.
8. `adapters/input/fastapi/register.py` + `adapters/input/fastmcp/register.py`.
9. `infrastructure/container.py`.
10. `config/`.

Pour ajouter une fonctionnalité, lire en plus :

- `docs/new-entity.md`
- `docs/http-conventions.md`
- `docs/implementation.md`
- `docs/vault.md`

## 7. Règle du journal — rappel

Toute modification non triviale doit être consignée dans `journal/YYYY-MM-DD-slug.md` à la **racine du workspace**. Voir `../AGENTS.md` §6 et `../journal/README.md`.

Cas spécifiques à ce repo qui exigent une entrée journal :

- changement de schéma `ShoppingList` / `ShoppingProjection` / `Supplier` ;
- changement du contrat avec `meal-planner/` ;
- changement de la logique d'agrégation (groupement par rayon, fusion d'ingrédients) ;
- ajout / retrait d'un adapter ;
- changement de port.

## 8. Hors scope

- Le **choix de fournisseur**, l'**optimisation de prix**, ou toute logique de suggestion vivent dans `shopping-agent/`. Ce repo n'embarque pas de logique LLM.
- Les **plans de repas** restent la propriété de `meal-planner/`. Ce repo en lit des projections.
- Les **recettes** restent la propriété de `recipe/`. Ce repo n'y accède **pas directement** : il passe toujours par `meal-planner/`.
