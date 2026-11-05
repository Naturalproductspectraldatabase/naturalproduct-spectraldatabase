"""Shared synthetic server configuration; executes real authorization functions."""
import ast
import hashlib
import hmac
import json
import re
import sys
import sqlite3
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / 'scripts/app.py'


def bind_authorization(ns=None, role='owner', username=None, authenticated=True):
    ns = {} if ns is None else ns
    username = username or 'synthetic_' + role
    users = [dict(username=username, role=role, password_hash='synthetic-nonproduction-hash')]
    ns.setdefault('st', SimpleNamespace(session_state=dict(npdb_authenticated=authenticated,
                  npdb_username=username, npdb_role=role, npdb_auth_mode='approved_users')))
    ns.setdefault('load_approved_users', lambda: users)
    ns.setdefault('load_approved_names', lambda: [])
    ns.setdefault('get_secret_setting', lambda *keys: '')
    ns.setdefault('allow_plaintext_password_secrets', lambda: False)
    ns.setdefault('OWNER_EDITOR_USERNAME', 'npdb_tyas')
    ns.setdefault('normalize_login_slug', lambda x: ''.join(c for c in str(x or '').lower() if c.isalnum()))
    sys.path.insert(0,str(APP.parent))
    from npdb_field_access import Disclosure, READ_DEPTH, ASSET_IO, SealedPayload, verify_payload, evidence_from_config, is_protected, canonical, context
    from npdb_location_policy import FieldPolicy, Identity, value_digest
    ns.update(hashlib=hashlib,hmac=hmac,json=json,wraps=wraps,re=re,sqlite3=sqlite3,
              Disclosure=Disclosure,READ_DEPTH=READ_DEPTH,ASSET_IO=ASSET_IO,SealedPayload=SealedPayload,verify_payload=verify_payload,
              evidence_from_config=evidence_from_config,is_protected=is_protected,canonical=canonical,
              field_context=context,FieldPolicy=FieldPolicy,Identity=Identity,value_digest=value_digest)
    ns.setdefault('get_secret_object',lambda *keys:None)
    ns.setdefault('record_related_specimen_tables',lambda *args:{})
    ns.setdefault('_FIELD_READ_CAPABILITY',object())
    ns.setdefault('get_npdb_read_backend',lambda:'supabase' if ns.get('use_supabase_backend',lambda:False)() else 'local')
    tree = ast.parse(APP.read_text())
    for name in ('configured_session_identity', 'current_backend_role', 'is_backend_owner',
                 'require_backend_permission', 'field_policy_revision', 'current_disclosure', 'policy_frame', 'policy_record',
                 'project_authorized_result', 'field_policy_raw_record', 'asset_policy_approval', 'finish_asset_policy', 'preserve_unseen_fields',
                 'guarded_download_button', 'authorized_read', 'is_owner_editor'):
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)
    identity = ns['configured_session_identity']()
    if identity:
        ns['st'].session_state['npdb_credential_revision'] = identity[1]
    return ns
