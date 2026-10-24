---
name: add-api-endpoint
description: Add or change an endpoint of the stepboard API, contract first. Use for any new route, new response field, new status code or changed request body in the Django backend.
when_to_use: Requests like "add an endpoint for…", "the API should also return…", "add a GET/POST …", or any change to openapi.yaml, backend/leaderboard/serializers.py, views.py or urls.py.
argument-hint: "[METHOD /path and what it does, e.g. GET /families/{family_id}/streaks]"
---

# Add an API endpoint, contract first

Endpoint: $ARGUMENTS

Work in this order. The contract tests fail until steps 1 to 3 agree, and the contract-check hook reports drift after each edit; that's expected mid-change.

## 1. The contract: `openapi.yaml`

- Add the path and operation: a unique `operationId`, a `summary`, path parameters via `#/components/parameters` (e.g. `FamilyId`), query parameters, and the request body.
- List every response it can return: success (`200`, or `201` when it creates something), `404` (`#/components/responses/NotFound`) for an unknown family or member, `422` (`#/components/responses/ValidationError`) for a bad body or date.
- Put new object shapes in `components/schemas`, with `required` and types (`[integer, "null"]` for nullable).

## 2. The data, if it changes

- Change `backend/leaderboard/models.py`, then `python manage.py makemigrations` in `backend/`. Never edit a committed migration (the guard hook blocks it); add a new one.

## 3. The code

- `serializers.py`: one serializer per schema, field names exactly as in `openapi.yaml`. Input serializers validate; days use `today_eastern()`, never the server's date.
- `views.py`: `@api_view([...])`. Look up the path resource first with `get_family()` / `get_member()` (404), then validate with `serializer.is_valid(raise_exception=True)` (422 via `exceptions.py`). Database reads for boards go in `queries.py`; ranking rules stay in pure `ranking.py`.
- `urls.py`: the path exactly as in `openapi.yaml`, no trailing slash.
- Frontend: only if the app uses it, add one method to `frontend/src/api.js` (components never call `fetch`).

## 4. Tests

- `backend/tests/integration/test_<area>.py`: success, each `404` and `422`, and a wrong method (`405`).
- `backend/tests/integration/test_contract_responses.py`: add a call to `calls()` for **every response the contract documents**; that test fails if one is never produced.
- A user-facing flow also gets a journey in `tests/integration/test_workflows.py`. Logic on its own (a rule, a calculation) gets unit tests in `tests/unit/`.
- For a new rule, break the code on purpose once and confirm a test fails for the right reason.

## 5. Check

From `backend/`:

```sh
python -m pytest tests/integration/test_contract.py tests/integration/test_contract_responses.py
python manage.py makemigrations --check --dry-run
pytest
```

Then `pytest` again with `DATABASE_URL` set to the local Postgres (see `backend/tests/README.md`), and `npm test` in `frontend/` if `api.js` changed.

## 6. Finish

- If AI assistants should use it, add it to the MCP server (`mcp-server/stepboard_mcp/api.py` and a tool in `server.py`, with tests).
- Update `product-spec.md` if behavior changed.
- Add an entry to `docs/ai-workflow.md`: the request, what was checked, and anything verification caught.
- Commit on a branch and open a pull request; merging to `main` deploys.
