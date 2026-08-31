"""Contract test: V2 API Pydantic response schemas must stay aligned with SDK dataclasses.

Compares field names between backend response models and SDK types.
Fails if a field exists in one but not the other (minus known exclusions).
Runs in CI without a backend — pure import-time introspection.
"""

import dataclasses
import importlib.util
from pathlib import Path
import re
import sys

import pytest

from m8tes._types import (
    App,
    AppTool,
    AppTriggerType,
    AuditLog,
    Channel,
    ChannelInstallLinks,
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
ChannelResponse = _schemas.ChannelResponse
ChannelInstallLinksResponse = _schemas.ChannelInstallLinksResponse


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
    (ChannelResponse, Channel, set()),
    (ChannelInstallLinksResponse, ChannelInstallLinks, set()),
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


# --- Round-trip parsing -------------------------------------------------------
#
# The name comparison above answers "does the field EXIST on both sides?". It does
# not answer "does from_dict actually READ it off the wire?" — and those came apart:
# `Run.billing_surface` was declared on the dataclass (so the pair above matched)
# and never assigned in `Run.from_dict`, so every parsed run reported the default
# "platform" no matter what the server sent. A caller filtering their own API
# traffic on it saw one value forever, with nothing red anywhere.
#
# So: build a payload whose value for each field differs from that field's default,
# parse it, and require the value to survive. A field added to a dataclass and
# forgotten in from_dict fails here.

_UNSUPPORTED = object()


def _probe_value(field: dataclasses.Field):
    """A wire value for `field` that differs from its default, or _UNSUPPORTED.

    Keyed off the annotation TEXT because `from __future__ import annotations` keeps
    these as strings. _UNSUPPORTED is returned only for a field whose type is a NESTED
    dataclass (`usage: RunUsage | None`) — those are covered by the hand-written cases
    elsewhere in the suite. Everything else is synthesized, including `Literal[...]`
    and a bare `list`.

    The value must differ from the field's own default, or a parser that drops the
    field would still look correct — which is exactly how `billing_surface` shipped.
    """
    text = str(field.type).replace(" ", "")
    default = field.default if field.default is not dataclasses.MISSING else None
    if text.startswith("Literal["):
        # The first option that is not already the default.
        return next((o for o in re.findall(r"'([^']*)'", text) if o != default), _UNSUPPORTED)
    base = text.split("|")[0]
    if base == "list[int]":
        return [1, 2]
    if base == "list" or base.startswith("list["):
        return ["probe"]
    if base.startswith("dict"):
        return {"probe": "value"}
    if base == "bool":
        return not bool(default)
    if base in ("int", "float"):
        return 4242
    if base == "str":
        return f"probe-{field.name}"
    return _UNSUPPORTED


def _probe_payload(sdk_type: type) -> dict:
    payload = {}
    for field in dataclasses.fields(sdk_type):
        value = _probe_value(field)
        if value is not _UNSUPPORTED:
            payload[field.name] = value
    return payload


ROUND_TRIP_TYPES = [pair[1] for pair in SCHEMA_PAIRS]


@pytest.mark.parametrize("sdk_type", ROUND_TRIP_TYPES, ids=[t.__name__ for t in ROUND_TRIP_TYPES])
def test_from_dict_parses_every_declared_field(sdk_type):
    """Every scalar field a response carries must survive `from_dict`, not just exist."""
    payload = _probe_payload(sdk_type)
    if not payload:
        pytest.skip(f"{sdk_type.__name__} declares only nested-object fields")

    parsed = sdk_type.from_dict(dict(payload))

    dropped = [
        f"  {name}: sent {sent!r}, got {getattr(parsed, name, '<attribute missing>')!r}"
        for name, sent in payload.items()
        if getattr(parsed, name, _UNSUPPORTED) != sent
    ]
    assert not dropped, (
        f"{sdk_type.__name__}.from_dict did not read these fields off the wire:\n"
        + "\n".join(dropped)
        + f"\n  → Assign them in sdk/py/m8tes/_types.py:{sdk_type.__name__}.from_dict"
    )


# The only fields the probe cannot build, with the reason. A whole annotation
# category that stops working lands its fields HERE, which is why coverage is
# guarded by this exact set and not by a count: at 244 fields, a floor low enough
# to tolerate normal churn is also high enough to survive losing every `int` and
# every `bool`.
_NESTED_OBJECT_FIELDS = {
    ("Run", "usage"),  # RunUsage — covered by test_v2_billing.py
    ("ChannelInstallLinks", "slack"),  # SlackInstallLink — covered by test_v2_resources.py
    ("ChannelInstallLinks", "github"),  # GitHubInstallLink — same
}


def test_the_probe_builds_a_discriminating_value_for_every_flat_field():
    """The round-trip test above is only as good as the payload it parses.

    Two ways it can silently stop testing anything, both guarded here:

    1. `_probe_value` returns _UNSUPPORTED for a field it used to build, so the
       field quietly drops out of the payload. Anything not in the set above is a
       regression, not a new nested type.
    2. It builds a value EQUAL to the field's default. Then a parser that dropped
       the field would still produce that value and the round-trip test would pass.
       One inverted token (`not bool(default)` losing its `not`) does exactly this
       to every bool field while the field count stays put.
    """
    unbuilt, indistinguishable = [], []
    for sdk_type in ROUND_TRIP_TYPES:
        payload = _probe_payload(sdk_type)
        for field in dataclasses.fields(sdk_type):
            key = (sdk_type.__name__, field.name)
            if field.name not in payload:
                if key not in _NESTED_OBJECT_FIELDS:
                    unbuilt.append(f"  {key[0]}.{key[1]}: {field.type}")
                continue
            default = field.default if field.default is not dataclasses.MISSING else None
            if payload[field.name] == default:
                indistinguishable.append(f"  {key[0]}.{key[1]}: probe == default {default!r}")

    assert not unbuilt, (
        "_probe_value stopped building these fields, so nothing tests them:\n"
        + "\n".join(unbuilt)
        + "\n  \u2192 Fix _probe_value, or add the field to _NESTED_OBJECT_FIELDS with its reason"
    )
    assert not indistinguishable, (
        "these probe values equal the field default, so a parser that dropped the "
        "field would still pass:\n" + "\n".join(indistinguishable)
    )
