# Quickstart — shopping

## Rôle

`shopping` est le service métier du volet courses de `rekipe`.

## Ports locaux

- API REST : `8020`
- MCP HTTP / SSE : `8021`
- Probes : `9020`

## Installation

```bash
cd /Users/killian/Karned/projets/Rekipe/shopping
uv sync --group dev
```

## Lancement

```bash
MODE=api uv run python main.py
MODE=mcp_http uv run python main.py
MODE=all uv run python main.py
```

## Configuration

- Keycloak : [config/adapters/input/keycloak.yaml](/Users/killian/Karned/projets/Rekipe/shopping/config/adapters/input/keycloak.yaml)
- MongoDB : [config/adapters/output/mongodb.yaml](/Users/killian/Karned/projets/Rekipe/shopping/config/adapters/output/mongodb.yaml)
- Tenant : [config/adapters/input/tenant.yaml](/Users/killian/Karned/projets/Rekipe/shopping/config/adapters/input/tenant.yaml)

Par défaut, le repository reste en `memory` dans `config/adapters/adapters.yaml`. La configuration MongoDB multi-tenant est préparée pour la suite.
