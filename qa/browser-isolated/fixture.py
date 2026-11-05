"""Generate only new synthetic records; extract schema functions without running app."""
import ast
import os
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing

CANDIDATE = os.environ['NPDB_QA_CANDIDATE']
FIXTURE_VERSION = 'isolated-browser-v1'
ROLES = ('owner', 'editor', 'viewer')


def prepare(root, dark=False):
    root.mkdir()
    scripts = root / 'scripts'
    shutil.copytree('/baseline', scripts)
    for name in ('database', 'data/structures', '.streamlit'):
        (root/name).mkdir(parents=True, exist_ok=True)
    config = Path('/baseline-config.toml').read_text()
    if dark:
        config += '\n[theme]\nbase="dark"\n'
    (root/'.streamlit/config.toml').write_text(config)
    source = scripts/'app.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == os.environ['NPDB_QA_APP_SHA256']
    tree = ast.parse(source.read_text())
    def connect():
        return sqlite3.connect(root/'database/nmr.db')
    # No Streamlit caches exist during disposable fixture creation. App source stays untouched.
    env = {'get_connection': connect, 'invalidate_cached_views': lambda: None}
    for name in ('ensure_columns_with_cursor', 'ensure_database_schema'):
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), env)
    env['ensure_database_schema']()
    from rdkit import Chem
    from rdkit.Chem import Draw
    Draw.MolToFile(Chem.MolFromSmiles('CCO'), str(root/'data/structures/synthetic.png'), size=(400, 300))
    with closing(connect()) as conn:
        conn.execute("INSERT INTO compounds(id,trivial_name,molecular_formula,smiles,compound_class,source_category,structure_image_path,curation_status,data_source) VALUES(1,'Synthetic ethanol','C2H6O','CCO','Synthetic','Synthetic','data/structures/synthetic.png','imported','Synthetic fixture')")
        conn.execute("INSERT INTO compounds(id,trivial_name,molecular_formula,smiles,compound_class,source_category,curation_status,data_source) VALUES(2,'Synthetic distractor','CH4','C','Synthetic','Synthetic','imported','Synthetic fixture')")
        for x in (1, 2, 3):
            conn.execute("INSERT INTO proton_nmr(compound_id,delta_ppm,assignment,solvent,instrument_mhz) VALUES(1,?,?,'Synthetic',500)", (x, f'H{x}'))
        for x in (10, 20, 30):
            conn.execute("INSERT INTO carbon_nmr(compound_id,delta_ppm,assignment,solvent,instrument_mhz) VALUES(1,?,?,'Synthetic',125)", (x, f'C{x}'))
        conn.commit()
        assert conn.execute('SELECT count(*) FROM compounds').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM proton_nmr').fetchone()[0] == 3
        assert conn.execute('SELECT count(*) FROM carbon_nmr').fetchone()[0] == 3
        assert conn.execute('SELECT count(*) FROM compounds WHERE sample_code IS NOT NULL OR collection_location IS NOT NULL OR gps_coordinates IS NOT NULL OR depth_m IS NOT NULL').fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM compounds WHERE curation_status != 'imported'").fetchone()[0] == 0
    assert not list(root.rglob('secrets.toml'))
    users = []
    credentials = {}
    # Dummy fixture accounts only, generated in a disposable container. Never emitted.
    for role in ROLES:
        username, password = f'synthetic_{role}', f'synthetic_fixture_password_{role}'
        salt = f'qa-{role}'
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 10000)
        encoded = base64.urlsafe_b64encode(digest).decode().rstrip('=')
        users.append({'username': username, 'role': role, 'password_hash': f'pbkdf2_sha256$10000${salt}${encoded}'})
        credentials[role] = (username, password)
    return json.dumps(users), credentials, hashlib.sha256(source.read_bytes()).hexdigest()
