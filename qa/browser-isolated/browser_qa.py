"""Bounded browser QA. Emit only numeric/enum aggregate JSON; never DOM/screenshots/logs."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import traceback
import urllib.request

from playwright.sync_api import sync_playwright
from fixture import CANDIDATE, FIXTURE_VERSION, ROLES, prepare

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
        emit(key, 'PASS' if passed else 'FAIL', **metrics)
    except Exception as exc:
        # Never publish raw exception text (can contain DOM, values or credentials).
        emit(key, 'FAIL', error_type=type(exc).__name__)


def settle(page):
    page.wait_for_timeout(350)
    page.get_by_test_id('stStatusWidget').wait_for(state='hidden', timeout=8000)
    page.wait_for_timeout(350)


def guarded_context(browser, width):
    context = browser.new_context(viewport={'width': width, 'height': 1000},
                                  device_scale_factor=1, service_workers='block',
                                  accept_downloads=False)
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
    context.route('**/*', route)
    def websocket(ws):
        if allowed(ws.url):
            ws.connect_to_server()
        else:
            ws.close()
    context.route_web_socket('**/*', websocket)
    return context


def login(page, credentials, role):
    page.goto(BASE, timeout=15000)
    page.get_by_placeholder('Enter your username').wait_for(state='visible')
    META['rendered_browser_pages'] += 1
    page.get_by_placeholder('Enter your username').fill(credentials[role][0])
    page.get_by_placeholder('Enter your password').fill(credentials[role][1])
    page.get_by_role('button', name='Open Database', exact=True).click()
    page.get_by_test_id('stSidebar').wait_for(state='attached')
    settle(page)
    page.get_by_role('button', name='Home', exact=True).wait_for(state='attached', timeout=15000)
    assert page.get_by_test_id('stException').count() == 0
    META['authenticated_home_views'] += 1


LAYOUT_JS = '''() => {
 const box = e => { if (!e) return null; const r=e.getBoundingClientRect();
   return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1),right:+r.right.toFixed(1)}; };
 const main=document.querySelector('[data-testid="stMain"]');
 const content=document.querySelector('[data-testid="stMainBlockContainer"]') || main;
 const sidebar=document.querySelector('[data-testid="stSidebar"]');
 const sb=box(sidebar), b=box(content), m=box(main), w=window.innerWidth;
 const shown=sb && sb.right>1 && sb.x<w && getComputedStyle(sidebar).visibility!=='hidden';
 const controls=[...main.querySelectorAll('button,input,textarea,select,[role="combobox"]')].filter(e=> {
  const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';});
 return {viewport:w,sidebar:sb,main:m,content:b,sidebar_intersects_viewport:!!shown,
  horizontal_overflow:Math.max(document.documentElement.scrollWidth-w,main.scrollWidth-main.clientWidth),
  clipped_controls:controls.filter(e=>{const r=e.getBoundingClientRect();return r.x < -2 || r.right>w+2;}).length,
  control_count:controls.length, blank_left_px:shown?0:Math.max(0,b.x+(parseFloat(getComputedStyle(content).paddingLeft)||0)),
  exception_count:document.querySelectorAll('[data-testid="stException"]').length};
}'''


def sidebar_state(page, expanded):
    current = page.evaluate(LAYOUT_JS)['sidebar_intersects_viewport']
    if current != expanded:
        if expanded:
            toggle = page.locator('[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"]').filter(visible=True).first
        else:
            toggle = page.get_by_test_id('stSidebar').locator('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"]').first
            if not toggle.count():
                toggle = page.get_by_test_id('stSidebar').locator('button').first
        toggle.click(timeout=5000)
        page.wait_for_timeout(400)
    result = page.evaluate(LAYOUT_JS)
    result['requested_expanded'] = expanded
    result['passed'] = (result['sidebar_intersects_viewport'] == expanded and
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
    page.locator('body').click(position={'x': 5, 'y': 5})
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
    nav(page, 'Search Spectra')
    page.get_by_role('radio', name=mode, exact=True).check()
    settle(page)
    if mode in ('1H Match', 'Combined Match'):
        page.get_by_label('Enter 1H peaks (comma, space, or newline separated)', exact=True).fill('1, 2, 3')
    if mode in ('13C Match', 'Combined Match'):
        page.get_by_label('Enter 13C peaks (comma, space, or newline separated)', exact=True).fill('10, 20, 30')
    label = {'1H Match':'Run 1H Match','13C Match':'Run 13C Match','Combined Match':'Run Combined Match'}[mode]
    page.get_by_role('button', name=label, exact=True).click()
    settle(page)
    units = page.get_by_test_id('stMain').get_by_text('ppm', exact=False).count()>0
    metrics=readability(page)
    state='FAIL' if metrics['below_4_5'] else ('UNTESTED' if metrics['unknown_background'] or not metrics['measured'] else 'PASS')
    emit(evidence_key,state,estimate_only=True,**metrics)
    page.get_by_role('button', name='Open Record #1', exact=True).click()
    settle(page)
    record = page.get_by_role('button', name='Download Full Record', exact=False).count()>0
    correct = page.get_by_test_id('stMain').get_by_text('Synthetic ethanol', exact=False).count()>0
    return dict(passed=record and correct and page.get_by_test_id('stException').count()==0,
                record_open=record, correct_synthetic_record=correct, ppm_text_present=units)


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
    env = dict(PATH='/venv/bin:/usr/bin:/bin', HOME='/tmp/qa-home', TMPDIR='/tmp',
               LANG='C.UTF-8', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
               NPDB_READ_BACKEND='local', NPDB_APPROVED_USERS=users)
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
        for theme in themes:
            root = Path('/tmp')/theme
            META['stage']='fixture_preflight'
            users, credentials, source_hash = prepare(root, dark=theme=='temporary_dark')
            META['app_py_sha256'] = source_hash
            META['fixture_generator_sha256'] = hashlib.sha256(Path('/qa/fixture.py').read_bytes()).hexdigest()
            emit(f'{theme}/fixture_preflight','PASS',compounds=2,proton_peaks=3,carbon_peaks=3,sensitive_fields_blank=True)
            META['stage']='streamlit_start'
            proc, log = start_app(root, users)
            try:
                for width in widths:
                    context = guarded_context(browser, width)
                    page = context.new_page()
                    try:
                        META['stage']='synthetic_login'
                        login(page, credentials, 'viewer')
                        if theme=='shipped' and width==768:
                            # Readiness is not layout acceptance. App defects stay FAIL below.
                            smoke = True
                            META['stage']='browser_matrix'
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
                            emit('runner_smoke_768','FAIL',error_type=type(exc).__name__,authenticated_home_rendered=False)
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
                    except Exception as exc:
                        emit(f'{theme}/role/{role}','FAIL',error_type=type(exc).__name__)
                    finally:
                        context.close()
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
