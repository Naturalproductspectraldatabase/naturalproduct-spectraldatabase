"""Bounded browser QA. Emit only numeric/enum aggregate JSON; never DOM/screenshots/logs."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time
import traceback
import urllib.request

from playwright.sync_api import sync_playwright
from fixture import CANDIDATE, FIXTURE_VERSION, ROLES, PRIVATE, PUBLIC, prepare
import io
import zipfile

PORT = 8620
BASE = f'http://127.0.0.1:{PORT}'
RESULTS = {}
META = dict(candidate_sha=CANDIDATE, fixture=FIXTURE_VERSION, python=platform.python_version(),
            data_origin='new_synthetic_only', assets='generated_structure_only_no_repository_assets',
            theme_definition='shipped_config_vs_temporary_base_dark', browser_version='UNTESTED',
            rendered_browser_pages=0, authenticated_home_views=0)
for name in ('streamlit', 'rdkit', 'pandas', 'playwright', 'plotly', 'Pillow'):
    META[name] = importlib.metadata.version(name)


def emit(key, status, **metrics):
    assert status in ('PASS', 'FAIL', 'UNTESTED')
    row = dict(test=key, status=status, **metrics)
    RESULTS[key] = row
    print('NPDB_QA ' + json.dumps(dict(metadata=META, result=row), sort_keys=True), flush=True)
    # Disposable, incrementally durable within container; stdout is sole published evidence.
    with open('/tmp/aggregate-results.jsonl', 'a') as f:
        f.write(json.dumps(row, sort_keys=True)+'\n')


def attempt(key, fn):
    try:
        metrics = fn() or {}
        passed = metrics.pop('passed', True)
        status = metrics.pop('status_override',None) or ('PASS' if passed else 'FAIL')
        emit(key, status, **metrics)
    except Exception as exc:
        # Never publish raw exception text (can contain DOM, values or credentials).
        frames=[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name}
                for f in traceback.extract_tb(exc.__traceback__) if Path(f.filename).name=='browser_qa.py']
        emit(key, 'FAIL', error_type=type(exc).__name__,source_frames=frames,interaction=META.get('interaction','unknown'))


def settle(page):
    page.wait_for_timeout(350)
    page.get_by_test_id('stStatusWidget').wait_for(state='hidden', timeout=8000)
    page.wait_for_timeout(350)


def guarded_context(browser, width, transport="native_proxy"):
    options={}
    if transport=='native_proxy':
        options['proxy']={'server':'http://127.0.0.1:1','bypass':'127.0.0.1'}
    context = browser.new_context(**options, viewport={'width': width, 'height': 1000},
                                  device_scale_factor=1, service_workers='block',
                                  accept_downloads=True)
    context.set_default_timeout(8000)
    from urllib.parse import urlparse
    def allowed(url):
        u = urlparse(url)
        return u.scheme in ('http', 'ws') and u.hostname == '127.0.0.1' and u.port == PORT
    def route(req):
        if not allowed(req.request.url):
            return req.abort()
        response = req.fetch(max_redirects=0)
        if 300 <= response.status < 400:
            return req.abort()
        req.fulfill(response=response)
    if transport=='route_fetch':
        context.route('**/*', route)
    # Preserve Streamlit's native websocket subprotocol/cookie handshake. The
    # constructor guard limits browser destinations; kernel network=none is the
    # independent enforcement boundary for workers and backend processes too.
    context.add_init_script("""(() => {
      const Native = window.WebSocket;
      window.WebSocket = new Proxy(Native, {construct(target,args) {
        const u = new URL(args[0], location.href);
        if (u.protocol !== 'ws:' || u.hostname !== '127.0.0.1' || u.port !== '8620')
          throw new DOMException('Blocked non-loopback websocket', 'SecurityError');
        return Reflect.construct(target,args);
      }});
    })();""")
    META['transport']=transport
    return context



class BootstrapProbe:
    """Counts only: never retain response headers, URLs, frame bodies or console text."""
    def __init__(self, page):
        self.page=page
        self.http={}
        self.ws_handshakes=[]
        self.ws_sent=0
        self.ws_received=0
        self.ws_errors=[]
        self.js_errors=[]
        self.console_errors=[]
        self.cdp=page.context.new_cdp_session(page)
        self.cdp.send('Network.enable')
        self.cdp.on('Network.responseReceived', self.response)
        self.cdp.on('Network.webSocketHandshakeResponseReceived', self.handshake)
        self.cdp.on('Network.webSocketFrameSent', lambda _: self.count_ws('sent'))
        self.cdp.on('Network.webSocketFrameReceived', lambda _: self.count_ws('received'))
        self.cdp.on('Network.webSocketFrameError', lambda e:self.ws_errors.append(self.category(e.get('errorMessage',''))))
        page.on('pageerror',lambda e:self.js_errors.append(self.category(str(e))))
        page.on('console',lambda m:self.console_errors.append(self.category(m.text)) if m.type=='error' else None)

    @staticmethod
    def category(message):
        for marker,category in [('SyntaxError','SYNTAX'),('TypeError','TYPE'),('ReferenceError','REFERENCE'),
                                ('Content Security Policy','CSP'),('dynamically imported','DYNAMIC_IMPORT'),
                                ('ERR_PROXY_CONNECTION_FAILED','PROXY_DENIED'),('ERR_CONNECTION_REFUSED','CONNECTION_REFUSED'),
                                ('WebSocket','WEBSOCKET'),('ERR_FAILED','NETWORK_FAILED')]:
            if marker in message:
                return category
        return 'OTHER'

    def count_ws(self,direction):
        if direction=='sent': self.ws_sent+=1
        else: self.ws_received+=1

    def handshake(self,event):
        self.ws_handshakes.append(int(event.get('response',{}).get('status',0)))

    def response(self,event):
        response=event.get('response',{})
        kind=event.get('type','Other')
        if kind not in ('Document','Script','Stylesheet','Fetch','XHR'):return
        mime=response.get('mimeType','')
        category='javascript' if 'javascript' in mime else ('css' if 'css' in mime else ('html' if 'html' in mime else 'other'))
        key=f"{kind}:{int(response.get('status',0))}:{category}"
        self.http[key]=self.http.get(key,0)+1

    def metrics(self,root):
        values=dict(http_response_counts=self.http,ws_handshake_statuses=self.ws_handshakes,
                    ws_frames_sent=self.ws_sent,ws_frames_received=self.ws_received,
                    ws_error_categories=self.ws_errors,js_error_categories=self.js_errors,
                    console_error_categories=self.console_errors)
        try:
            values.update(self.page.evaluate("""() => ({document_ready:document.readyState,
              dom_elements:document.querySelectorAll('*').length,
              input_count:document.querySelectorAll('input').length,
              app_exception_count:document.querySelectorAll('[data-testid="stException"]').length,
              alert_count:document.querySelectorAll('[data-testid="stAlert"]').length,
              main_count:document.querySelectorAll('[data-testid="stMain"]').length})"""))
        except Exception:
            values['dom_probe_unavailable']=True
        marker=Path('/tmp')/(root.name+'-execution.txt')
        values['app_script_execution_starts']=len(marker.read_text().splitlines()) if marker.exists() else 0
        log=Path('/tmp/streamlit-private.log').read_text(errors='replace')
        values['server_error_types']=[n for n in ('NameError','TypeError','ModuleNotFoundError','PermissionError','StreamlitAPIException') if n in log]
        return values


def minimal_comparison(browser):
    root=Path('/tmp/minimal_control')
    (root/'scripts').mkdir(parents=True)
    (root/'.streamlit').mkdir()
    (root/'.streamlit/config.toml').write_bytes(Path('/baseline-config.toml').read_bytes())
    (root/'scripts/app.py').write_text('import streamlit as st\nst.title("Synthetic bootstrap control")\nst.text_input("Synthetic bootstrap input")\n')
    proc,log=start_app(root,'[]')
    ready=False
    try:
        for transport in ('route_fetch','native_proxy'):
            context=guarded_context(browser,768,transport)
            page=context.new_page()
            probe=BootstrapProbe(page)
            result=False
            error=None
            try:
                page.goto(BASE,timeout=15000)
                page.get_by_label('Synthetic bootstrap input',exact=True).wait_for(state='visible',timeout=15000)
                result=True
                META['rendered_browser_pages']+=1
            except Exception as exc:
                error=type(exc).__name__
            metrics=probe.metrics(root)
            emit(f'bootstrap/minimal/{transport}','PASS' if result else 'FAIL',
                 viewport=768,rendered_input=result,error_type=error,**metrics)
            if transport=='native_proxy':ready=result
            context.close()
    finally:
        proc.terminate()
        proc.wait(timeout=8)
        log.close()
    return ready


def login(page, credentials, role):
    page.goto(BASE, timeout=15000)
    page.get_by_placeholder('Enter your username').wait_for(state='visible', timeout=30000)
    META['rendered_browser_pages'] += 1
    META['interaction']='fill_synthetic_username'
    page.get_by_placeholder('Enter your username').fill(credentials[role][0])
    META['interaction']='fill_synthetic_password'
    page.get_by_placeholder('Enter your password').fill(credentials[role][1])
    META['interaction']='submit_synthetic_login'
    page.get_by_role('button', name=re.compile(r'^Open Database\s*→?$')).click()
    page.get_by_test_id('stSidebar').wait_for(state='attached')
    settle(page)
    page.get_by_role('button', name='Home', exact=True).wait_for(state='attached', timeout=15000)
    assert page.get_by_test_id('stException').count() == 0
    META['authenticated_home_views'] += 1
    META['interaction']='authenticated_home_ready'


LAYOUT_JS = '''() => {
 const box = e => { if (!e) return null; const r=e.getBoundingClientRect();
   return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1),right:+r.right.toFixed(1)}; };
 const main=document.querySelector('[data-testid="stMain"]');
 const content=document.querySelector('[data-testid="stMainBlockContainer"]') || main;
 const sidebar=document.querySelector('[data-testid="stSidebar"]');
 const sb=box(sidebar), b=box(content), m=box(main), w=window.innerWidth;
 const shown=sb && sb.right>1 && sb.x<w && getComputedStyle(sidebar).visibility!=='hidden';
 const fullyExpanded=shown && sb.x>=-1;
 const controls=[...main.querySelectorAll('button,input,textarea,select,[role="combobox"]')].filter(e=> {
  const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';});
 return {viewport:w,sidebar:sb,main:m,content:b,sidebar_intersects_viewport:!!shown,sidebar_fully_expanded:!!fullyExpanded,
  horizontal_overflow:Math.max(document.documentElement.scrollWidth-w,main.scrollWidth-main.clientWidth),
  clipped_controls:controls.filter(e=>{const r=e.getBoundingClientRect();return r.x < -2 || r.right>w+2;}).length,
  control_count:controls.length, blank_left_px:shown?0:Math.max(0,b.x+(parseFloat(getComputedStyle(content).paddingLeft)||0)),
  exception_count:document.querySelectorAll('[data-testid="stException"]').length};
}'''


def sidebar_state(page, expanded):
    current = page.evaluate(LAYOUT_JS)['sidebar_fully_expanded']
    if current != expanded:
        if expanded:
            toggle = page.locator('[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"]').filter(visible=True).first
        else:
            page.get_by_test_id('stSidebar').hover(position={'x':10,'y':20})
            page.wait_for_timeout(150)
            toggle = page.get_by_test_id('stSidebar').locator('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"]').first
            if not toggle.count():
                toggle = page.get_by_test_id('stSidebar').locator('button').first
        toggle.click(timeout=5000)
        page.wait_for_timeout(400)
    result = page.evaluate(LAYOUT_JS)
    result['requested_expanded'] = expanded
    result['passed'] = ((result['sidebar_fully_expanded'] if expanded else not result['sidebar_intersects_viewport']) and
                        result['horizontal_overflow'] <= 1 and result['clipped_controls'] == 0 and
                        result['exception_count'] == 0 and
                        (expanded or result['blank_left_px'] <= max(96, result['viewport']*.12)))
    return result


def nav(page, name):
    sidebar_state(page, True)
    page.get_by_test_id('stSidebar').get_by_role('button', name=name, exact=True).click()
    settle(page)
    # On small screens collapse before interacting with underlying controls.
    if page.viewport_size['width'] <= 768:
        sidebar_state(page, False)


def keyboard_nav(page):
    sidebar_state(page, True)
    target = page.get_by_test_id('stSidebar').get_by_role('button', name='Search Spectra', exact=True)
    META['interaction']='keyboard_tab_navigation'
    page.keyboard.press('Escape')
    reached = False
    for count in range(60):
        page.keyboard.press('Tab')
        if target.evaluate('(e)=>e===document.activeElement'):
            reached = True
            break
    ring = False
    if reached:
        ring = target.evaluate(r'''e=>{const s=getComputedStyle(e);return
          (s.outlineStyle!=='none' && parseFloat(s.outlineWidth)>=2) ||
          /rgba?\([^)]*\) 0px 0px 0px ([2-9]|[1-9][0-9])/.test(s.boxShadow);}'''.replace('return\n', 'return '))
        page.keyboard.press('Enter')
        settle(page)
    return dict(passed=reached and page.get_by_role('radio', name='13C Match', exact=True).count()>0,
                reached_by_tab=reached, tab_limit=60, visible_focus_estimate=bool(ring))


def recovery(page):
    page.goto(BASE)
    button = page.get_by_role('button', name='Forgot password?', exact=True)
    button.wait_for(state='visible')
    META['rendered_browser_pages'] += 1
    button.focus()
    button.press('Enter')
    dialog = page.get_by_role('dialog')
    dialog.wait_for()
    focus_in = dialog.evaluate('(e)=>e.contains(document.activeElement)')
    no_link = page.get_by_role('link', name='Contact account recovery', exact=True).count() == 0
    page.keyboard.press('Escape')
    dialog.wait_for(state='hidden')
    return_focus = button.evaluate('(e)=>e===document.activeElement')
    return dict(passed=focus_in and return_focus and no_link, opened=True,
                focus_inside=focus_in, focus_returned=return_focus, no_contact_link=no_link)


def role_ui(page, role):
    sidebar_state(page, True)
    for summary in page.get_by_test_id('stSidebar').locator('details > summary').all():
        if not summary.evaluate('(e)=>e.parentElement.open'):
            summary.click()
    sidebar = page.get_by_test_id('stSidebar')
    edit = sidebar.get_by_role('button', name='Update Metadata', exact=True).count()>0
    delete = sidebar.get_by_role('button', name='Delete Record', exact=True).count()>0
    return dict(passed=edit==(role!='viewer') and delete==(role=='owner'),
                edit_navigation_present=edit, delete_navigation_present=delete,
                boundary='UI_only_backend_tests_separate')


def nmr(page, mode, evidence_key):
    META['interaction']='navigate_search'
    nav(page, 'Search Spectra')
    META['interaction']='select_nmr_mode'
    page.get_by_test_id('stMain').get_by_role('radiogroup').first.get_by_text(mode,exact=True).click()
    settle(page)
    if mode in ('1H Match', 'Combined Match'):
        META['interaction']='fill_proton_query'
        page.get_by_label('Enter 1H peaks (comma, space, or newline separated)', exact=True).fill('1, 2, 3')
    if mode in ('13C Match', 'Combined Match'):
        META['interaction']='fill_carbon_query'
        page.get_by_label('Enter 13C peaks (comma, space, or newline separated)', exact=True).fill('10, 20, 30')
    label = {'1H Match':'Run 1H Match','13C Match':'Run 13C Match','Combined Match':'Run Combined Match'}[mode]
    META['interaction']='submit_nmr_query'
    page.get_by_role('button', name=label, exact=True).click()
    settle(page)
    units = page.get_by_test_id('stMain').get_by_text('ppm', exact=False).count()>0
    metrics=readability(page)
    state='FAIL' if metrics['below_4_5'] else ('UNTESTED' if metrics['unknown_background'] or not metrics['measured'] else 'PASS')
    emit(evidence_key,state,estimate_only=True,**metrics)
    META['interaction']='open_nmr_record'
    page.get_by_role('button', name='Open Record #1', exact=True).click()
    settle(page)
    record = page.get_by_role('button', name='Download Full Record', exact=False).count()>0
    correct = page.get_by_test_id('stMain').get_by_text('Synthetic ethanol', exact=False).count()>0
    return dict(passed=record and correct and page.get_by_test_id('stException').count()==0,
                record_open=record, correct_synthetic_record=correct, ppm_text_present=units)


def downloaded_zip(page):
    META['interaction']='download_full_record'
    with page.expect_download(timeout=10000) as pending:
        page.get_by_role('button',name='Download Full Record',exact=True).click()
    download=pending.value
    data=Path(download.path()).read_bytes()
    assert download.url.startswith(BASE+'/media/')
    return data,download.url


def inspect_record_export(page,role):
    data,url=downloaded_zip(page)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text='\n'.join(archive.read(n).decode() for n in archive.namelist() if n.endswith(('.csv','.txt','.json')))
        manifest=json.loads(archive.read('manifest.json'))
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(archive.read('NPDB_full_record.xlsx')),data_only=True)
        spreadsheet='\n'.join(str(c.value) for sheet in book for row in sheet for c in row if c.value is not None)
    return dict(passed=PUBLIC in text and PUBLIC in spreadsheet and (PRIVATE in text)==(role=='owner') and
                (PRIVATE in spreadsheet)==(role=='owner') and manifest['compound_id']==1 and
                '1H_NMR' in book.sheetnames and '13C_NMR' in book.sheetnames and manifest['included'].get('linked_specimen_rows')==1,
                production_format_zip_opened=True,xlsx_opened=True,published_preserved=PUBLIC in text,
                restricted_present=PRIVATE in text,expected_restricted=role=='owner',same_compound_id=manifest['compound_id']==1)


def issued_capability(browser,root,credentials,alteration):
    # Private synthetic control file changes server allowlist on the NEXT real
    # app-script execution; no application source or production config touched.
    original=(root/'synthetic-users.json').read_text()
    context=guarded_context(browser,1280);page=context.new_page()
    try:
        login(page,credentials,'owner')
        nmr(page,'13C Match','capability_diagnostic/'+alteration)
        data,url=downloaded_zip(page)
        initial=context.request.get(url,max_redirects=0)
        initial_available=initial.status==200 and hashlib.sha256(initial.body()).digest()==hashlib.sha256(data).digest()
        if alteration=='logout':
            sidebar_state(page,True)
            page.get_by_role('button',name='Log out',exact=True).click()
        else:
            users=json.loads(original)
            if alteration=='remove':users=[u for u in users if u['role']!='owner']
            elif alteration=='rotate':
                next(u for u in users if u['role']=='owner')['password_hash']='pbkdf2_sha256$10000$rotated$synthetic'
            else:next(u for u in users if u['role']=='owner')['role']='viewer'
            (root/'synthetic-users.json').write_text(json.dumps(users))
            sidebar_state(page,True)
            page.get_by_role('button',name='Home',exact=True).click()
        page.get_by_placeholder('Enter your username').wait_for(state='visible',timeout=10000)
        # A different browser context has no authenticated application session.
        anonymous=guarded_context(browser,1280)
        try:
            response=anonymous.request.get(url,max_redirects=0)
            remains=response.status==200 and hashlib.sha256(response.body()).digest()==hashlib.sha256(data).digest()
        finally:anonymous.close()
        return dict(passed=not remains,status_override='UNTESTED' if not initial_available else None,initial_authorized_retrieval_status=initial.status,backend_login_revoked=True,anonymous_replay_status=response.status,
                    identical_capability_bytes_retrievable=remains,
                    limitation='NATIVE_STREAMLIT_MEDIA_CAPABILITY_NOT_RECIPIENT_BOUND',synthetic_only=True)
    finally:
        (root/'synthetic-users.json').write_text(original)
        context.close()


def readability(page):
    # Conservative DOM estimate: gradients/complex backgrounds remain UNTESTED.
    return page.evaluate('''() => {
      const rgba=s=>(s.match(/[\\d.]+/g)||[]).map(Number);
      const lum=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
      let measured=0,low=0,unknown=0;
      for(const e of document.querySelectorAll('[data-testid="stCaptionContainer"] p,[data-testid="stWidgetLabel"] p,input,textarea')){
        const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;
        let bg=null;
        for(let n=e;n;n=n.parentElement){const s=getComputedStyle(n);if(s.backgroundImage!=='none'){break;}
          const c=rgba(s.backgroundColor);if(c.length===3||(c.length===4&&c[3]===1)){bg=c;break;}}
        const cs=getComputedStyle(e),fg=rgba(cs.webkitTextFillColor||cs.color);
        if(!bg||fg.length<3||(fg.length===4&&fg[3]<1)||Number(cs.opacity)<1){unknown++;continue;}
        const a=lum(fg),b=lum(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        measured++;if(ratio<4.5)low++;
      }
      return {measured,below_4_5:low,unknown_background:unknown};
    }''')


def start_app(root, users):
    hooks=Path('/tmp/qa-bootstrap-hooks')
    hooks.mkdir(exist_ok=True)
    (hooks/'sitecustomize.py').write_text("""import os, sys
from pathlib import Path
def count_execution(event,args):
    if event=='exec' and args and getattr(args[0],'co_name','')=='<module>' and getattr(args[0],'co_filename','').endswith('/scripts/app.py'):
        with open(os.environ['QA_EXECUTION_MARKER'],'a') as marker:marker.write('exec\\n')
        if Path(os.environ['QA_SYNTHETIC_USERS']).exists():
            os.environ['NPDB_APPROVED_USERS']=Path(os.environ['QA_SYNTHETIC_USERS']).read_text()
sys.addaudithook(count_execution)
""")
    env = dict(PATH='/venv/bin:/usr/bin:/bin', HOME='/tmp/qa-home', TMPDIR='/tmp',
               LANG='C.UTF-8', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
               NPDB_READ_BACKEND='local', NPDB_APPROVED_USERS=users,
               NPDB_FIELD_PROVENANCE=(root/'provenance-fixture.json').read_text() if (root/'provenance-fixture.json').exists() else '',
               QA_SYNTHETIC_USERS=str(root/'synthetic-users.json'),
               PYTHONPATH=str(hooks),QA_EXECUTION_MARKER=str(Path('/tmp')/(root.name+'-execution.txt')))
    log = open('/tmp/streamlit-private.log', 'wb')
    proc = subprocess.Popen(['/venv/bin/python','-m','streamlit','run','scripts/app.py',
                             '--server.address=127.0.0.1',f'--server.port={PORT}',
                             '--server.headless=true','--browser.gatherUsageStats=false'],
                            cwd=root, env=env, stdout=log, stderr=log)
    for _ in range(60):
        if proc.poll() is not None:
            raise RuntimeError('isolated_app_start_failed')
        try:
            with urllib.request.urlopen(BASE+'/_stcore/health', timeout=.3) as response:
                if response.status == 200:
                    return proc, log
        except Exception:
            time.sleep(.25)
    proc.terminate()
    raise RuntimeError('isolated_app_health_timeout')


def isolation():
    assert os.getuid() == 10001
    assert os.statvfs('/').f_flag & os.ST_RDONLY
    status = Path('/proc/self/status').read_text()
    assert int(next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:')), 16) == 0
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('NoNewPrivs:')) == '1'
    assert {name for _,name in socket.if_nameindex()} == {'lo'}
    assert not any('SUPABASE' in k or 'GITHUB_TOKEN' in k for k in os.environ)
    assert not Path('/var/run/docker.sock').exists()
    assert not Path('/github/workspace').exists()
    assert not Path('/baseline/secrets.toml').exists()
    routes = Path('/proc/net/route').read_text().splitlines()[1:]
    assert not any(line.split()[1]=='00000000' for line in routes)
    try:
        connection = socket.create_connection(('192.0.2.1',443), timeout=1)
    except OSError:
        emit('isolation', 'PASS', default_route=False, nonloopback_connection_blocked=True,
             root_readonly=True, host_workspace_mounted=False, inherited_credentials=False)
    else:
        connection.close()
        raise RuntimeError('network_isolation_failed')


def main():
    assert sys.version_info[:2] == (3,12)
    for package,version in {'streamlit':'1.66.1','pandas':'2.2.3','rdkit':'2026.9.1','playwright':'1.64.1','plotly':'7.1.0','Pillow':'12.3.0','openpyxl':'3.1.5'}.items():
        assert importlib.metadata.version(package) == version
    META['stage']='isolation_preflight'
    # Suppress raw third-party diagnostics; only aggregate JSON is public.
    fd=os.open('/tmp/browser-library-private.log',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.dup2(fd,2)
    os.close(fd)
    isolation()
    Path('/tmp/qa-home').mkdir()
    themes = ('shipped','temporary_dark')
    widths = (768,320,390,1280,1920)
    for theme in themes:
        for width in widths:
            for state in ('collapsed','expanded'):
                emit(f'{theme}/layout/{width}/{state}', 'UNTESTED')
        for role in ROLES:
            emit(f'{theme}/role/{role}', 'UNTESTED')
            for mode in ('1H Match','13C Match','Combined Match'):
                emit(f'{theme}/nmr/{role}/{mode}', 'UNTESTED')
                emit(f'{theme}/nmr_readability/{role}/{mode}', 'UNTESTED')
        for item in ('keyboard_navigation','focus_indicator','recovery_focus','readability'):
            emit(f'{theme}/{item}', 'UNTESTED')
    emit('runner_smoke_768', 'UNTESTED')
    with sync_playwright() as pw:
        META['stage']='chromium_launch'
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        META['browser_version'] = browser.version
        smoke = False
        META['stage']='minimal_bootstrap_comparison'
        if not minimal_comparison(browser):
            emit('runner_smoke_768','UNTESTED',reason='minimal_control_not_ready')
            browser.close()
            return 2
        for theme in themes:
            root = Path('/tmp')/theme
            META['stage']='fixture_preflight'
            users, credentials, source_hash = prepare(root, dark=theme=='temporary_dark')
            META['app_py_sha256'] = source_hash
            META['fixture_generator_sha256'] = hashlib.sha256(Path('/qa/fixture.py').read_bytes()).hexdigest()
            emit(f'{theme}/fixture_preflight','PASS',compounds=2,proton_peaks=3,carbon_peaks=3,sensitive_fields_synthetic_only=True, linked_specimens=1,linked_bioactivity=1,published_field_approvals=2)
            META['stage']='streamlit_start'
            proc, log = start_app(root, users)
            try:
                for width in widths:
                    context = guarded_context(browser, width)
                    page = context.new_page()
                    probe=BootstrapProbe(page) if theme=='shipped' and width==768 else None
                    try:
                        META['stage']='synthetic_login'
                        login(page, credentials, 'viewer')
                        if theme=='shipped' and width==768:
                            # Readiness is not layout acceptance. App defects stay FAIL below.
                            smoke = True
                            META['stage']='browser_matrix'
                            emit('bootstrap/npdb/native_proxy','PASS',**probe.metrics(root))
                            emit('runner_smoke_768','PASS', viewport=768, rendered_pages=1,
                                 browser_started=True, authenticated_synthetic_home=True)
                        for state in ('collapsed','expanded'):
                            attempt(f'{theme}/layout/{width}/{state}',lambda s=state:sidebar_state(page,s=='expanded'))
                        if width==768:
                            attempt(f'{theme}/keyboard_navigation', lambda: keyboard_nav(page))
                            row=RESULTS[f'{theme}/keyboard_navigation']
                            focus_status=('PASS' if row.get('visible_focus_estimate') else 'FAIL') if row.get('reached_by_tab') else 'UNTESTED'
                            emit(f'{theme}/focus_indicator', focus_status,
                                 estimate_only=True)
                        if width==1280:
                            nav(page,'Search Spectra')
                            metrics=readability(page)
                            status='FAIL' if metrics['below_4_5'] else ('UNTESTED' if metrics['unknown_background'] or not metrics['measured'] else 'PASS')
                            emit(f'{theme}/readability',status,estimate_only=True,**metrics)
                    except Exception as exc:
                        if not smoke:
                            diagnostics=probe.metrics(root) if probe else {}
                            emit('bootstrap/npdb/native_proxy','FAIL',error_type=type(exc).__name__,**diagnostics)
                            emit('runner_smoke_768','FAIL',error_type=type(exc).__name__,authenticated_home_rendered=False,**diagnostics)
                            return 2
                        emit(f'{theme}/page/{width}','FAIL',error_type=type(exc).__name__)
                    finally:
                        context.close()
                for role in ROLES:
                    context=guarded_context(browser,1280)
                    page=context.new_page()
                    try:
                        login(page,credentials,role)
                        attempt(f'{theme}/role/{role}',lambda r=role:role_ui(page,r))
                        for mode in ('1H Match','13C Match','Combined Match'):
                            attempt(f'{theme}/nmr/{role}/{mode}',lambda m=mode:nmr(page,m,f'{theme}/nmr_readability/{role}/{m}'))
                        attempt(f'{theme}/field_export/{role}',lambda r=role:inspect_record_export(page,r))
                    except Exception as exc:
                        emit(f'{theme}/role/{role}','FAIL',error_type=type(exc).__name__)
                    finally:
                        context.close()
                if theme=='shipped':
                    for alteration in ('logout','remove','rotate','role'):
                        attempt('issued_capability/'+alteration,lambda a=alteration:issued_capability(browser,root,credentials,a))
                context=guarded_context(browser,1280)
                try:
                    attempt(f'{theme}/recovery_focus',lambda:recovery(context.new_page()))
                finally:
                    context.close()
            finally:
                proc.terminate()
                proc.wait(timeout=8)
                log.close()
        browser.close()
    counts={status:sum(r['status']==status for r in RESULTS.values()) for status in ('PASS','FAIL','UNTESTED')}
    print('NPDB_QA_SUMMARY '+json.dumps(dict(candidate_sha=CANDIDATE,runner_feasible=smoke,counts=counts,
        rendered_browser_pages=META['rendered_browser_pages'], authenticated_home_views=META['authenticated_home_views'],
        release='BLOCKED',production_restore='BLOCKED',browser_acceptance='NOT_APPROVED',
        no_screenshots_or_traces=True)),flush=True)
    # UI failures are recorded, never interpreted as acceptance. Runner feasibility is this job's gate.
    return 0 if smoke else 2


if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        frames=[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name}
                for f in traceback.extract_tb(exc.__traceback__)
                if Path(f.filename).name in ('browser_qa.py','fixture.py','app.py')]
        emit('runner_fatal','FAIL',error_type=type(exc).__name__,source_frames=frames)
        sys.exit(2)
