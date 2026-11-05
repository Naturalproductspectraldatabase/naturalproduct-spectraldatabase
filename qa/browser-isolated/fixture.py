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
FIXTURE_VERSION = 'isolated-browser-field-policy-v3'
PRIVATE = 'SYNTHETIC-RESTRICTED-BROWSER-SENTINEL'
PUBLIC = 'SYNTHETIC-PUBLISHED-ORIGINAL-PRECISION'
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
        # Synthetic plausible shifts only, not experimental observations. Ethanol
        # has two carbon sites and three proton environments including OH.
        for shift,assignment,count in ((1.18,'H1',3),(3.65,'H2',2),(2.0,'OH',1)):
            conn.execute("INSERT INTO proton_nmr(compound_id,delta_ppm,assignment,proton_count,solvent,instrument_mhz) VALUES(1,?,?,?,'Synthetic fixture',500)", (shift,assignment,count))
        for shift,assignment in ((18.7,'C1'),(58.2,'C2')):
            conn.execute("INSERT INTO carbon_nmr(compound_id,delta_ppm,assignment,solvent,instrument_mhz) VALUES(1,?,?,'Synthetic fixture',125)", (shift,assignment))
        conn.execute("UPDATE compounds SET sample_code=?,collection_location=?,gps_coordinates=?,depth_m=42.125,note=?,doi='10.0000/synthetic-not-real',journal_name='Synthetic journal',article_title='Synthetic reference' WHERE id=1",(PRIVATE,PRIVATE,PUBLIC,PRIVATE))
        conn.execute("INSERT INTO specimens(id,specimen_name,scientific_name,collection_location,gps_coordinates,depth_m,collector,note) VALUES(1,?,'Synthetic taxon',?,?,42.125,?,?)",(PRIVATE,PRIVATE,PUBLIC,PRIVATE,PRIVATE))
        conn.execute("INSERT INTO specimen_compounds(specimen_id,compound_id,evidence_note,reference_note) VALUES(1,1,?,?)",(PRIVATE,PRIVATE))
        conn.execute("INSERT INTO bioactivity_records(compound_id,activity_label,potency_type,potency_value,potency_unit,note) VALUES(1,'Synthetic assay','IC50',2.1,'uM',?)",(PRIVATE,))
        conn.commit()
        assert conn.execute('SELECT count(*) FROM compounds').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM proton_nmr').fetchone()[0] == 3
        assert conn.execute('SELECT count(*) FROM carbon_nmr').fetchone()[0] == 2
        assert conn.execute('SELECT sample_code,gps_coordinates FROM compounds WHERE id=1').fetchone() == (PRIVATE,PUBLIC)
        conn.row_factory=sqlite3.Row
        row=dict(conn.execute('SELECT * FROM compounds WHERE id=1').fetchone())
        facts=[]
        def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
        for field in ('gps_coordinates','structure_image_path'):
            facts.append(dict(table='compounds',record_id='1',field=field,record_revision=row['updated_at'],value_sha256=digest(row[field]),classification='PUBLISHED_VERIFIED',verification_status='VERIFIED',source_reference='Synthetic QA source, not a publication',source_locator='Synthetic fixture figure/field',verified_by='Synthetic owner',verifier_role='owner',asset_sha256=hashlib.sha256((root/'data/structures/synthetic.png').read_bytes()).hexdigest() if field=='structure_image_path' else ''))
        (root/'provenance-fixture.json').write_text(json.dumps(dict(version=1,entries=facts)))
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
    (root/'synthetic-users.json').write_text(json.dumps(users))
    return json.dumps(users), credentials, hashlib.sha256(source.read_bytes()).hexdigest()
