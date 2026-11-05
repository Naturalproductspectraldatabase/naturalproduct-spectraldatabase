"""Shared synthetic server configuration; executes real authorization functions."""
import ast
import hashlib
import hmac
import json
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
    ns.update(hashlib=hashlib, hmac=hmac, json=json, wraps=wraps)
    tree = ast.parse(APP.read_text())
    for name in ('configured_session_identity', 'current_backend_role', 'is_backend_owner',
                 'require_backend_permission', 'authorized_read', 'is_owner_editor'):
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)
    identity = ns['configured_session_identity']()
    if identity:
        ns['st'].session_state['npdb_credential_revision'] = identity[1]
    return ns
