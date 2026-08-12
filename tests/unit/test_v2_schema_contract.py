"""Contract test: V2 API Pydantic response schemas must stay aligned with SDK dataclasses.

Compares field names between backend response models and SDK types.
Fails if a field exists in one but not the other (minus known exclusions).
Runs in CI without a backend — pure import-time introspection.
"""

import dataclasses
import importlib.util
from pathlib import Path
import sys

import pytest

from m8tes._types import (
    App,
    AppTool,
    AppTriggerType,
    AuditLog,
    Memory,
    PermissionPolicy,
    PermissionRequest,
    Run,
    RunFile,
    RunMessage,
    Task,
    Teammate,
    TeammateWebhook,
    Trigger,
    Webhook,
    WebhookDelivery,
)

# Load schemas.py directly from file path, bypassing app.routers.__init__
# which eagerly imports v1 routers that depend on the full fastapi package.
# In a standalone SDK checkout (the public repo) the backend source isn't
# present — skip the whole module instead of crashing test collection.
_schemas_path = (
    Path(__file__).resolve().parents[4] / "fastapi" / "app" / "routers" / "v2" / "schemas.py"
)
if not _schemas_path.exists():
    pytest.skip(
        "backend schemas.py not available (standalone SDK checkout)", allow_module_level=True
    )
# schemas.py imports one shared cross-layer contract (`app.contracts.tool_name`, the
# constrained tool-name type v1 and v2 must agree on), so the backend root has to be
# importable. `app/contracts/` is dependency-free by charter — stdlib + pydantic only —
# precisely so this standalone load keeps working without the backend's dependencies.
_backend_root = _schemas_path.parents[3]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

_spec = importlib.util.spec_from_file_location("v2_schemas", _schemas_path)
_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas)

TeammateResponse = _schemas.TeammateResponse
DevRunResponse = _schemas.DevRunResponse
DevTaskResponse = _schemas.DevTaskResponse
TriggerResponse = _schemas.TriggerResponse
AppResponse = _schemas.AppResponse
MemoryResponse = _schemas.MemoryResponse
WebhookResponse = _schemas.WebhookResponse
WebhookDeliveryResponse = _schemas.WebhookDeliveryResponse
PermissionRequestResponse = _schemas.PermissionRequestResponse
PermissionPolicyResponse = _schemas.PermissionPolicyResponse
RunFileResponse = _schemas.RunFileResponse
RunMessageResponse = _schemas.RunMessageResponse
TeammateWebhookResponse = _schemas.TeammateWebhookResponse
AppTriggerTypeSchemaResponse = _schemas.AppTriggerTypeResponse
AppToolSchemaResponse = _schemas.AppToolResponse
AuditLogResponse = _schemas.AuditLogResponse


def _pydantic_fields(model: type) -> set[str]:
    return set(model.model_fields.keys())


def _dataclass_fields(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


# (PydanticResponse, SDKDataclass, fields intentionally excluded from SDK)
SCHEMA_PAIRS = [
    (TeammateResponse, Teammate, set()),
    (DevRunResponse, Run, set()),
    (DevTaskResponse, Task, set()),
    (TriggerResponse, Trigger, set()),
    (AppResponse, App, set()),
    (MemoryResponse, Memory, set()),
    (WebhookResponse, Webhook, set()),
    (WebhookDeliveryResponse, WebhookDelivery, set()),
    (PermissionRequestResponse, PermissionRequest, set()),
    (PermissionPolicyResponse, PermissionPolicy, set()),
    (RunFileResponse, RunFile, set()),
    (RunMessageResponse, RunMessage, set()),
    (TeammateWebhookResponse, TeammateWebhook, set()),
    (AppTriggerTypeSchemaResponse, AppTriggerType, set()),
    (AppToolSchemaResponse, AppTool, set()),
    (AuditLogResponse, AuditLog, set()),
]


@pytest.mark.parametrize(
    "api_model,sdk_type,exclusions",
    SCHEMA_PAIRS,
    ids=[p[1].__name__ for p in SCHEMA_PAIRS],
)
def test_response_fields_match_sdk_type(api_model, sdk_type, exclusions):
    """Every field in the API response must exist in the SDK dataclass (and vice versa)."""
    api_fields = _pydantic_fields(api_model) - exclusions
    sdk_fields = _dataclass_fields(sdk_type)

    missing_from_sdk = api_fields - sdk_fields
    missing_from_api = sdk_fields - api_fields

    errors = []
    if missing_from_sdk:
        errors.append(
            f"Fields in {api_model.__name__} but missing from "
            f"{sdk_type.__name__}: {missing_from_sdk}\n"
            f"  → Add to sdk/py/m8tes/_types.py:{sdk_type.__name__}"
        )
    if missing_from_api:
        errors.append(
            f"Fields in {sdk_type.__name__} but missing from "
            f"{api_model.__name__}: {missing_from_api}\n"
            f"  → Add to fastapi/app/routers/v2/schemas.py:{api_model.__name__}"
        )

    assert not errors, "\n".join(errors)


def test_v2_schemas_load_without_the_backend_dependency_stack():
    """This module is loaded by `importlib` with only the SDK's own dependencies present —
    no `pydantic_settings`, no SQLAlchemy. A plain `from app.schemas...` import in
    schemas.py breaks that at COLLECTION time, taking the whole SDK suite red (it did:
    2026-07-28, adding a shared tool-name type). Anything schemas.py imports must live
    under `app/contracts/`, which is dependency-free by charter.
    """
    import importlib

    assert "pydantic_settings" not in sys.modules, (
        "loading the v2 schemas dragged in the backend settings stack — a heavy import "
        "crept into schemas.py or into app/contracts/"
    )
    # The shared contract itself must import cleanly on the SDK's dependency set.
    contract = importlib.import_module("app.contracts.tool_name")
    assert contract.TOOL_NAME_MAX_LENGTH == 255
