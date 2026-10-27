"""Smoke de gestión y avisos: Chromium del sistema, base temporal, sin tocar datos reales."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as instance:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    process = subprocess.Popen([sys.executable, 'app.py', '--seed-demo', '--port', str(port)],
                               cwd=ROOT, env={**os.environ, 'MVP_INSTANCE': instance},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + '/health', timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError('El servidor no inició')
                time.sleep(0.1)
        else:
            raise RuntimeError('El servidor no respondió')
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)
            page.locator('#username').fill('admin')
            page.locator('#password').fill('AdminDemo2026!')
            page.locator('button[type=submit]').click()
            page.get_by_role('button', name='Lavandina', exact=True).click()
            dialog = page.locator('dialog[open]')
            expect(dialog).to_contain_text('Última modificación')
            expect(dialog).to_contain_text('litro')
            page.keyboard.press('Escape')
            expect(page.locator('dialog[open]')).to_have_count(0)
            page.get_by_role('button', name='Lavandina', exact=True).click()
            page.get_by_role('link', name='Editar insumo', exact=True).click()
            page.locator('#category').select_option('Otros')
            page.locator('#location').select_option('Estante 2')
            page.locator('#minimum').fill('25')
            page.locator('#maximum').fill('50')
            page.get_by_role('button', name='Guardar cambios').click()
            expect(page.get_by_role('alert')).to_contain_text('Lavandina')
            page.get_by_role('button', name='Cerrar aviso de stock').click()
            expect(page.get_by_role('alert')).to_have_count(0)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_role('button', name='Lavandina', exact=True).click()
            expect(page.locator('dialog[open]')).to_be_visible()
            page.get_by_role('button', name='Cerrar ×').click()
            page.goto(base + '/insumos/1/editar')
            expect(page.locator('#category')).to_have_value('Otros')
            expect(page.locator('#location')).to_have_value('Estante 2')
            page.locator('#confirmation').fill('LIM-001')
            page.get_by_role('button', name='Eliminar insumo y movimientos').click()
            expect(page.get_by_role('button', name='Lavandina', exact=True)).to_have_count(0)
            expect(page.get_by_role('alert')).to_have_count(0)
            assert not errors, errors
            browser.close()
            print('OK: ficha, teclado, edición, aviso, cierre, móvil y eliminación en Chromium.')
    finally:
        process.terminate()
        process.wait(timeout=10)
