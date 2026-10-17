"""End-to-end validation and actual browser recording on an isolated database.

Run with a Python environment containing requirements-dev.txt and Chromium/ffmpeg.
No mutations to the development database; the child server is stopped on exit.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'entregables'
CAPTURES = OUT / 'capturas'
RAW = OUT / 'raw'


def main():
    for path in (OUT, CAPTURES, RAW):
        path.mkdir(parents=True, exist_ok=True)
    cache = ROOT / 'instance/.playwright'
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(cache)
    ffmpeg = shutil.which('ffmpeg')
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    if not ffmpeg or not chromium:
        raise RuntimeError('Instalá Chromium y ffmpeg antes de grabar la demo.')
    # Playwright's recording protocol is compatible with the verified system ffmpeg.
    # Locate its expected binary path using the bundled browser registry manifest.
    import playwright
    manifest = Path(playwright.__file__).parent / 'driver/package/browsers.json'
    revision = next(x['revision'] for x in json.loads(manifest.read_text())['browsers'] if x['name'] == 'ffmpeg')
    ffmpeg_path = cache / f'ffmpeg-{revision}' / 'ffmpeg-linux'
    ffmpeg_path.parent.mkdir(parents=True, exist_ok=True)
    if not ffmpeg_path.exists():
        ffmpeg_path.symlink_to(ffmpeg)
    checks, chapters = [], []
    with tempfile.TemporaryDirectory(prefix='mvp-demo-') as instance, socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        env = {**os.environ, 'MVP_INSTANCE': instance, 'PYTHONUNBUFFERED': '1'}
        with (OUT / 'servidor-demo.log').open('w') as log:
            server = subprocess.Popen([sys.executable, str(ROOT / 'app.py'), '--seed-demo', '--port', str(port)], env=env, stdout=log, stderr=log, cwd=ROOT)
            try:
                base = f'http://127.0.0.1:{port}'
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Falló el servidor de demo; consultar servidor-demo.log')
                    try:
                        with urllib.request.urlopen(base + '/health', timeout=1) as response:
                            assert json.load(response)['status'] == 'ok'
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('El servidor no respondió al control de salud.')
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=chromium, headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width':1440,'height':1000}, record_video_dir=str(RAW), record_video_size={'width':1440,'height':1000}, locale='es-AR')
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    start = time.monotonic()

                    def chapter(text, screenshot=None):
                        chapters.append((time.monotonic() - start, text))
                        if screenshot:
                            page.screenshot(path=str(CAPTURES / f'{screenshot}.png'))
                        page.wait_for_timeout(4000)

                    def check(name):
                        checks.append({'caso':name, 'resultado':'APROBADO'})

                    page.goto(base + '/inicio')
                    chapter('EasyStock | Diseño del equipo FullStackers aplicado al MVP de Intendencia.', '00-inicio')
                    page.get_by_role('link', name='Ingresar al MVP').click()
                    check('Portada: estética y recursos gráficos de EasyStock')
                    chapter('HU-01 | Acceso por usuario y rol. Datos ficticios de demostración.', '01-login')
                    page.locator('#username').fill('admin')
                    page.locator('#password').fill('AdminDemo2026!')
                    page.get_by_role('button', name='Ingresar').click()
                    expect(page.get_by_role('heading', name='Inventario de insumos.')).to_be_visible()
                    check('HU-01: inicio de sesión Administrador')
                    chapter('Inventario centralizado: cantidad disponible, categoría y ubicación física.', '02-inventario')
                    page.get_by_role('link', name='＋ Nuevo insumo').last.click()
                    page.locator('#code').fill('LIM-003')
                    page.locator('#name').fill('Desengrasante industrial')
                    page.locator('#category').select_option('Limpieza')
                    page.locator('#unit').select_option('litro')
                    page.locator('#location').select_option('Puerta 3')
                    page.locator('#minimum').fill('3')
                    page.locator('#maximum').fill('25')
                    chapter('HU-02 | Alta de insumo con código único y ubicación estructurada.', '03-alta')
                    page.get_by_role('button', name='Guardar insumo').click()
                    row = page.get_by_role('row').filter(has_text='Desengrasante industrial')
                    expect(row.locator('.stock strong')).to_have_text('0')
                    check('HU-02: alta con stock cero y ubicación Puerta 3')
                    row.get_by_role('link', name='Configurar umbrales').click()
                    page.locator('#minimum').fill('4')
                    page.locator('#maximum').fill('30')
                    chapter('HU-03 | Configuración de mínimos y máximos, reservada al Administrador.', '04-umbrales')
                    page.get_by_role('button', name='Guardar umbrales').click()
                    expect(page.get_by_role('row').filter(has_text='Desengrasante industrial')).to_contain_text('4 / 30')
                    check('HU-03: edición de umbrales')
                    page.get_by_role('button', name='Cerrar sesión').click()
                    page.locator('#username').fill('operario')
                    page.locator('#password').fill('OperarioDemo2026!')
                    page.get_by_role('button', name='Ingresar').click()
                    expect(page.get_by_role('link', name='Nuevo insumo')).to_have_count(0)
                    check('HU-01: Operario sin acciones de administración')
                    page.get_by_role('link', name='Registrar entrada', exact=True).first.click()
                    page.locator('#product_id').select_option(label='Desengrasante industrial · LIM-003')
                    page.locator('#amount').fill('10')
                    page.locator('#reference').fill('Remito DEMO-001')
                    page.locator('#observation').fill('Recepción ficticia para la presentación académica')
                    chapter('HU-06 | Recepción de 10 litros con referencia de remito y usuario responsable.', '05-entrada')
                    page.get_by_role('button', name='Confirmar entrada').click()
                    expect(page.get_by_role('row').filter(has_text='Desengrasante industrial').locator('.stock strong')).to_have_text('10')
                    check('HU-06: entrada incrementa el stock a 10 litros')
                    page.locator('#q').fill('desengrasante')
                    page.locator('#category').select_option('Limpieza')
                    page.locator('#location').select_option('Puerta 3')
                    page.get_by_role('button', name='Buscar', exact=True).click()
                    expect(page.locator('tbody tr')).to_have_count(1)
                    chapter('HU-04 | Búsqueda por nombre y filtros combinados de categoría y ubicación.', '06-busqueda')
                    check('HU-04: búsqueda y filtros combinados')
                    page.get_by_role('link', name='Registrar salida de Desengrasante').click()
                    page.locator('#amount').fill('12')
                    page.locator('#sector').select_option('Molino')
                    page.get_by_role('button', name='Confirmar salida').click()
                    expect(page.get_by_role('status')).to_contain_text('Stock insuficiente')
                    chapter('HU-05 | Salida de 12 litros rechazada: solo hay 10 disponibles.', '07-stock-insuficiente')
                    check('HU-05: bloqueo de salida superior al stock')
                    page.locator('#amount').fill('2.5')
                    page.locator('#observation').fill('Limpieza POES - demostración')
                    chapter('HU-05 | Consumo válido: 2,5 litros para el sector Molino.', '08-salida')
                    page.get_by_role('button', name='Confirmar salida').click()
                    row = page.get_by_role('row').filter(has_text='Desengrasante industrial')
                    expect(row.locator('.stock strong')).to_have_text('7.5')
                    chapter('Resultado verificado: 10 litros recibidos - 2,5 retirados = 7,5 litros.', '09-resultado')
                    check('HU-05: consumo actualiza stock a 7,5 litros')
                    page.goto(base + '/insumos/nuevo')
                    expect(page.get_by_role('heading', name='Acceso restringido')).to_be_visible()
                    check('Permisos: acceso directo de Operario a alta bloqueado (403)')
                    page.goto(base)
                    # Validate responsive layout without creating a second recording.
                    page.set_viewport_size({'width':390, 'height':844})
                    expect(page.get_by_role('heading', name='Inventario de insumos.')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    page.screenshot(path=str(CAPTURES / '10-movil.png'), full_page=True)
                    check('Interfaz móvil: 390 px sin desborde global')
                    page.set_viewport_size({'width':1440, 'height':1000})
                    page.wait_for_timeout(1500)
                    assert not errors, errors
                    check('Navegador sin errores JavaScript')
                    video = page.video
                    context.close()
                    raw_video = video.path()
                    browser.close()
                # Confirm DB contents independently of the UI assertions.
                import sqlite3
                connection = sqlite3.connect(str(Path(instance) / 'inventario.sqlite3'))
                stock, = connection.execute("SELECT stock FROM products WHERE code='LIM-003'").fetchone()
                assert stock == 7500
                movements = connection.execute("SELECT m.kind,m.quantity,m.sector,u.username,m.created_at FROM movements m JOIN products p ON p.id=m.product_id JOIN users u ON u.id=m.user_id WHERE p.code='LIM-003' ORDER BY m.id").fetchall()
                assert [(r[0],r[1],r[3]) for r in movements] == [('entrada',10000,'operario'), ('salida',2500,'operario')]
                connection.close()
                check('Persistencia SQL: dos movimientos con cantidad, usuario y fecha; saldo 7500 milésimas')
                report = dict(ejecutado_en_utc=datetime.now(timezone.utc).isoformat(), tipo='Recorrido funcional real en Chromium; base aislada y datos ficticios', aprobados=len(checks), fallidos=0, casos=checks, movimientos=movements)
                (OUT / 'pruebas-navegador.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                (OUT / 'demo-capitulos.json').write_text(json.dumps(chapters, ensure_ascii=False, indent=2))
                # Real screen recording, with Spanish captions in a separate band.
                duration = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(raw_video)], text=True))
                def stamp(seconds):
                    millis = round(seconds * 1000)
                    return f'{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02},{millis%1000:03}'
                subtitles = []
                for i, (seconds, text) in enumerate(chapters):
                    end = chapters[i+1][0] if i+1 < len(chapters) else duration
                    subtitles.append(f'{i+1}\n{stamp(seconds)} --> {stamp(end)}\n{text}\n')
                subtitle_file = OUT / 'Demo-MVP.srt'
                subtitle_file.write_text('\n'.join(subtitles))
                vf = "pad=1440:1080:0:0:color=0x212121,subtitles=Demo-MVP.srt:force_style='FontName=DejaVu Sans,FontSize=8,Alignment=2,MarginV=2,Outline=1,Shadow=0'"
                subprocess.run([ffmpeg,'-y','-i',str(raw_video),'-vf',vf,'-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT / 'Demo-MVP.mp4')], cwd=OUT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                print(json.dumps({'aprobados':len(checks),'fallidos':0,'video':str(OUT / 'Demo-MVP.mp4')},ensure_ascii=False))
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == '__main__':
    main()
