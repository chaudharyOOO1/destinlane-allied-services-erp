"""Optional, actor-scoped idempotent response replay for transactional ERP writes.

No key means legacy behavior. A supplied key and normalized payload are bound
to the authenticated actor and operation. A PostgreSQL transaction-level lock
serializes identical requests; the response is persisted in the same transaction
as the business rows, never in a separate commit.
"""
import hmac
import json
import re
from hashlib import sha256

from fastapi import HTTPException
from fastapi.params import Param
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from app.core.config import settings

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")


def auth_recovery_marker(token):
    """A trusted, unguessable identity for retrying one remote Auth provisioning.

    Used only when a browser-supplied idempotency key is present. It protects
    unrelated pre-existing Auth accounts from password resets by create flows.
    """
    if token is None:
        return None
    actor_id, operation, key, _digest = token
    scope = f"destinlane-auth-recovery-v1:{actor_id}:{operation}:{key}"
    return hmac.new(settings.SECRET_KEY.encode(), scope.encode(), sha256).hexdigest()


def begin(db, actor_id, operation, key, request_payload):
    # Direct service-level unit tests may invoke endpoint functions without
    # FastAPI dependency injection, leaving the Header declaration as default.
    if key is None or isinstance(key, Param):
        return None, None
    if not _KEY.fullmatch(key):
        raise HTTPException(422, "Idempotency-Key must be 8-128 ASCII characters.")
    canonical = json.dumps(jsonable_encoder(request_payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hmac.new(settings.SECRET_KEY.encode(), canonical.encode(), sha256).hexdigest()
    db.execute(text("select pg_advisory_xact_lock(hashtextextended(:scope,0))"),
               {"scope": f"{actor_id}:{operation}:{key}"})
    existing = db.execute(text("""select request_digest,response from api_idempotency_requests
        where actor_id=:actor and operation=:operation and request_key=:key"""),
        {"actor": actor_id, "operation": operation, "key": key}).mappings().first()
    if existing:
        if not hmac.compare_digest(existing["request_digest"], digest):
            raise HTTPException(409, "Idempotency-Key was already used for a different request.")
        return existing["response"], None
    return None, (actor_id, operation, key, digest)


def save(db, token, response):
    if token is None:
        return
    actor_id, operation, key, digest = token
    db.execute(text("""insert into api_idempotency_requests
      (actor_id,operation,request_key,request_digest,response)
      values (:actor,:operation,:key,:digest,cast(:response as jsonb))"""),
      {"actor":actor_id,"operation":operation,"key":key,"digest":digest,
       "response":json.dumps(jsonable_encoder(response), ensure_ascii=False, separators=(",", ":"))})
