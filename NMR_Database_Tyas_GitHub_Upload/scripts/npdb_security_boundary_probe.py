"""Offline audit probe: execute selected real backend functions with fake I/O.

Exit 1 means boundary findings, not a failed production request. No app import,
Streamlit run, credential loading, database connection or network operation.
"""
import argparse
import ast
import json
import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace


def functions(source, names, namespace):
    tree = ast.parse(source)
    for name in names:
        node = next(n for n in reversed(tree.body)
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<audited-app>', 'exec'), namespace)


def probe(app):
    source = app.read_text(encoding='utf-8')
    findings = []
    for role in ('viewer', 'editor', 'unauthenticated'):
        touched = []
        def request(*args, **kwargs):
            touched.append('REST mutation')
            return []
        ns = dict(st=SimpleNamespace(session_state={
            'npdb_authenticated': role != 'unauthenticated',
            'npdb_username': 'synthetic_user', 'npdb_role': role,
            'npdb_auth_mode': 'approved_users',
        }), cloud_backend_is_configured=lambda: False,
            use_supabase_backend=lambda: True,
            use_supabase_write_backend=lambda: True,
            use_local_read_backend=lambda: False,
            _supabase_request=request, record_audit_event=lambda *a: None,
            invalidate_cached_views=lambda: None)
        available = {n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
        if 'require_backend_permission' in available:
            ns.update(hashlib=hashlib, hmac=hmac, json=json,
                      load_approved_users=lambda: [dict(username='synthetic_user', role=role,
                                                       password_hash='synthetic-only-hash')],
                      load_approved_names=lambda: [], get_secret_setting=lambda *a: '',
                      allow_plaintext_password_secrets=lambda: False,
                      OWNER_EDITOR_USERNAME='synthetic_owner',
                      normalize_login_slug=lambda v: str(v).lower())
            functions(source, ['configured_session_identity', 'current_backend_role',
                               'require_backend_permission'], ns)
            identity = ns['configured_session_identity']()
            if identity:
                ns['st'].session_state['npdb_credential_revision'] = identity[1]
        functions(source, ['ensure_write_target_ready' , 'supabase_delete_row',
                           'delete_compound_record'], ns)
        try:
            ns['delete_compound_record'](123456)
        except PermissionError:
            pass
        if touched:
            findings.append({'boundary': 'delete_compound_record', 'role': role,
                             'result': 'reached fake REST DELETE without denial'})
    return findings


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=Path(__file__).with_name('app.py'))
    args = parser.parse_args()
    result = probe(args.app)
    print(json.dumps({'synthetic_only': True, 'findings': result}, indent=2))
    raise SystemExit(bool(result))
