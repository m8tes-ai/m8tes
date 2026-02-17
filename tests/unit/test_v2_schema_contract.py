"""Contract test: V2 API Pydantic response schemas must stay aligned with SDK dataclasses.

Compares field names between backend response models and SDK types.
Fails if a field exists in one but not the other (minus known exclusions).
Runs in CI without a backend — pure import-time introspection.
"""

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from m8tes._types import (
    App,
    Memory,
    PermissionPolicy,
    PermissionRequest,
    Run,
    Task,
    Teammate,
    Trigger,
    Webhook,
    WebhookDelivery,
)

# Load schemas.py directly from file path, bypassing app.routers.__init__
# which eagerly imports v1 routers that depend on the full fastapi package.
_schemas_path = (
    Path(__file__).resolve().parents[4] / "fastapi" / "app" / "routers" / "v2" / "schemas.py"
)
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
