# Quickstart — shopping

## Rôle

`shopping` est le service métier du volet courses de `rekipe`.

## Ports locaux

- API REST : `8020`
- MCP HTTP / SSE : `8021`
- Probes : `9020`

## Installation

```bash
cd shopping
uv sync --group dev
```

## Lancement

```bash
MEAL_PLANNER_BASE_URL=http://127.0.0.1:8010 MODE=api uv run python main.py
MEAL_PLANNER_BASE_URL=http://127.0.0.1:8010 MODE=mcp_http uv run python main.py
MEAL_PLANNER_BASE_URL=http://127.0.0.1:8010 MODE=all uv run python main.py
```

## Configuration

- Keycloak : `config/adapters/input/keycloak.yaml`
- MongoDB : `config/adapters/output/mongodb.yaml`
- Tenant : `config/adapters/input/tenant.yaml`

Par défaut, le repository est `mongodb` dans `config/adapters/adapters.yaml`.
La configuration locale attendue dans `secrets.yaml` est :

```yaml
adapters:
  mongodb:
    uri: mongodb://localhost:5971
```

La génération depuis une période consomme la projection du calendrier meal-planner, pas uniquement les plans `confirmed`.
