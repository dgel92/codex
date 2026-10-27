import concurrent.futures
import re
import tempfile
import unittest
import uuid
from pathlib import Path

from app import connect, create_app, normalized, quantity, record_movement, seed_demo


class QuantityTests(unittest.TestCase):
    def test_decimal_exactness_and_comma(self):
        self.assertEqual(quantity('0.125', 'litro'), 125)
        self.assertEqual(quantity('1,25', 'kg'), 1250)
        self.assertEqual(quantity('3', 'unidad'), 3000)

    def test_invalid_quantities(self):
        for value in ('0', '-1', 'NaN', 'Infinity', '', '1000001', '0.0001', 'abc'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                quantity(value, 'litro')

    def test_units_cannot_be_fractional(self):
        with self.assertRaises(ValueError):
            quantity('1.5', 'unidad')

    def test_uniqueness_normalization(self):
        self.assertEqual(normalized('  CINTA   Aisladora '), normalized('cinta aisladora'))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test-only-key'})
        seed_demo(self.app)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data=None, follow=True):
        self.client.get('/login')
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return self.client.post(path, data={**(data or {}), 'csrf': csrf}, follow_redirects=follow)

    def login(self, role='admin'):
        return self.post('/login', {'username': role, 'password': 'AdminDemo2026!' if role == 'admin' else 'OperarioDemo2026!'})

    def row(self, query, parameters=()):
        with connect(self.path) as c:
            return c.execute(query, parameters).fetchone()

    def product(self, **changes):
        data = dict(code='LIM-003', name='Desengrasante industrial', category='Limpieza', unit='litro', location='Puerta 3', minimum='3', maximum='25')
        data.update(changes)
        return self.post('/insumos/nuevo', data)

    def move(self, kind='entrada', **changes):
        data = dict(product_id='1', amount='2.5', reference='Remito prueba', sector='Molino', request_id=str(uuid.uuid4()))
        data.update(changes)
        return self.post(f'/movimientos/{kind}', data)

    def test_product_details_and_edit(self):
        self.login()
        page = self.client.get('/').text
        self.assertIn('id="product-1"', page)
        self.assertIn('Última modificación', page)
        before = self.row('SELECT updated_at FROM products WHERE id=1')[0]
        response = self.post('/insumos/1/editar', dict(category='Otros', location='Estante 2', minimum='25', maximum='50'))
        self.assertEqual(response.status_code, 200)
        product = self.row('SELECT * FROM products WHERE id=1')
        self.assertEqual((product['category'], product['location'], product['minimum'], product['maximum']), ('Otros', 'Estante 2', 25000, 50000))
        self.assertEqual(product['updated_by'], 1)
        self.assertGreaterEqual(product['updated_at'], before)
        self.assertIn('Aviso: stock bajo', response.text)
        self.assertEqual(self.row('SELECT COUNT(*) FROM threshold_changes WHERE product_id=1')[0], 1)

    def test_invalid_edits_are_atomic(self):
        self.login()
        original = tuple(self.row('SELECT * FROM products WHERE id=1'))
        for changes in (dict(category='inventada'), dict(location='inexistente'), dict(minimum='40'), dict(minimum='0')):
            data = dict(category='Otros', location='Estante 2', minimum='5', maximum='40')
            data.update(changes)
            self.assertEqual(self.post('/insumos/1/editar', data).status_code, 400)
            self.assertEqual(tuple(self.row('SELECT * FROM products WHERE id=1')), original)

    def test_delete_complete_and_confirmed(self):
        self.login()
        self.post('/insumos/1/editar', dict(category='Otros', location='Estante 2', minimum='5', maximum='40'))
        self.post('/insumos/1/eliminar', dict(confirmation='incorrecto'))
        self.assertIsNotNone(self.row('SELECT * FROM products WHERE id=1'))
        response = self.post('/insumos/1/eliminar', dict(confirmation='LIM-001'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.row('SELECT * FROM products WHERE id=1'))
        for table in ('movements', 'threshold_changes'):
            self.assertEqual(self.row(f'SELECT COUNT(*) FROM {table} WHERE product_id=1')[0], 0)
        self.assertEqual(self.row('SELECT COUNT(*) FROM products')[0], 3)
        self.assertEqual(self.post('/insumos/1/eliminar', dict(confirmation='LIM-001')).status_code, 404)

    def test_management_permissions_and_csrf(self):
        self.login('operario')
        self.assertEqual(self.client.get('/insumos/1/editar').status_code, 403)
        self.assertEqual(self.post('/insumos/1/editar', {}).status_code, 403)
        self.assertEqual(self.post('/insumos/1/eliminar', dict(confirmation='LIM-001')).status_code, 403)
        self.login()
        self.assertEqual(self.client.post('/insumos/1/eliminar', data=dict(confirmation='LIM-001')).status_code, 400)
        self.assertIsNotNone(self.row('SELECT * FROM products WHERE id=1'))
        self.assertEqual(self.client.get('/insumos/999/editar').status_code, 404)

    def test_low_stock_alert_strict_boundary_and_filters(self):
        self.login()
        self.assertNotIn('Aviso: stock bajo', self.client.get('/').text)
        self.move('salida', amount='19')
        self.assertNotIn('Aviso: stock bajo', self.client.get('/').text)
        response = self.move('salida', amount='1')
        self.assertIn('Aviso: stock bajo', response.text)
        self.assertIn('Aviso: stock bajo', self.client.get('/?q=inexistente').text)
        self.move('entrada', amount='1')
        self.assertNotIn('Aviso: stock bajo', self.client.get('/').text)

    def test_movement_updates_last_modification(self):
        self.login('operario')
        with connect(self.path) as c:
            c.execute("UPDATE products SET updated_at='2000-01-01T00:00:00+00:00' WHERE id=1")
        self.move('entrada', amount='1')
        row = self.row('SELECT updated_at, updated_by FROM products WHERE id=1')
        self.assertNotEqual(row['updated_at'], '2000-01-01T00:00:00+00:00')
        self.assertEqual(row['updated_by'], 2)

    def test_HU01_login_and_logout(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Administrador demo', response.text)
        self.post('/logout')
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_HU01_wrong_credentials_generic(self):
        for username in ('admin', 'desconocido'):
            response = self.post('/login', dict(username=username, password='wrong'))
            self.assertEqual(response.status_code, 401)
            self.assertIn('Credenciales incorrectas', response.text)

    def test_HU01_unauthenticated_requests_do_not_write(self):
        self.assertEqual(self.post('/insumos/nuevo', follow=False).status_code, 302)
        self.assertEqual(self.row('SELECT count(*) FROM products')[0], 4)

    def test_csrf_is_required(self):
        self.login()
        response = self.client.post('/movimientos/entrada', data=dict(product_id=1, amount=1))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 24000)

    def test_HU02_create_zero_stock(self):
        self.login()
        response = self.product()
        self.assertEqual(response.status_code, 200)
        p = self.row('SELECT * FROM products WHERE code=?', ('LIM-003',))
        self.assertEqual(p['stock'], 0)
        self.assertEqual(p['location'], 'Puerta 3')

    def test_HU02_duplicate_name_and_code(self):
        self.login()
        for changes in (dict(name='  LAVANDINA '), dict(code='lim-001')):
            response = self.product(**changes)
            self.assertEqual(response.status_code, 400)
            self.assertIn('Ya existe', response.text)
        self.assertEqual(self.row('SELECT count(*) FROM products')[0], 4)

    def test_HU02_required_and_structured_fields(self):
        self.login()
        for changes in (dict(name=''), dict(unit=''), dict(location='Ubicación inventada'), dict(category='Inválida')):
            with self.subTest(changes=changes):
                self.assertEqual(self.product(**changes).status_code, 400)

    def test_HU03_threshold_rules_and_audit(self):
        self.login()
        for minimum, maximum in [('3', '3'), ('4', '2'), ('0', '5'), ('-1', '5')]:
            self.assertEqual(self.post('/insumos/1/umbrales', dict(minimum=minimum, maximum=maximum)).status_code, 400)
        self.assertEqual(self.post('/insumos/1/umbrales', dict(minimum='6.5', maximum='45')).status_code, 200)
        p = self.row('SELECT * FROM products WHERE id=1')
        audit = self.row('SELECT * FROM threshold_changes WHERE product_id=1 ORDER BY id DESC LIMIT 1')
        self.assertEqual((p['minimum'], p['maximum'], p['updated_by']), (6500, 45000, 1))
        self.assertEqual(audit['user_id'], 1)
        self.assertTrue(audit['created_at'])

    def test_HU01_HU03_operario_restrictions_on_server(self):
        self.login('operario')
        page = self.client.get('/').text
        self.assertNotIn('Nuevo insumo', page)
        self.assertNotIn('Configurar</a>', page)
        for path in ['/insumos/nuevo', '/insumos/1/umbrales']:
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.post(path).status_code, 403)

    def test_HU04_combined_filters(self):
        self.login('operario')
        response = self.client.get('/?q=lav&category=Limpieza&location=Puerta+1')
        self.assertIn('Lavandina', response.text)
        self.assertNotIn('Perfumina</strong>', response.text)
        self.assertIn('24</strong>', response.text)
        self.assertIn('litro', response.text)
        self.assertIn('No hay insumos', self.client.get('/?q=inexistente').text)

    def test_HU05_exit_and_traceability(self):
        self.login('operario')
        self.assertEqual(self.move('salida', amount='2.125', observation='Limpieza POES').status_code, 200)
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 21875)
        m = self.row("SELECT * FROM movements WHERE kind='salida'")
        self.assertEqual((m['user_id'], m['quantity'], m['sector']), (2, 2125, 'Molino'))
        self.assertEqual(m['observation'], 'Limpieza POES')
        self.assertTrue(m['created_at'])

    def test_HU05_insufficient_stock_is_atomic(self):
        self.login('operario')
        response = self.move('salida', amount='25')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Stock insuficiente', response.text)
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 24000)
        self.assertEqual(self.row("SELECT count(*) FROM movements WHERE kind='salida'")[0], 0)

    def test_HU05_sector_required(self):
        self.login('operario')
        self.assertEqual(self.move('salida', sector='').status_code, 400)

    def test_HU06_entry_and_optional_reference(self):
        for user in ('admin', 'operario'):
            self.login(user)
            self.assertEqual(self.move('entrada', amount='0.1', reference='').status_code, 200)
            self.post('/logout')
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 24200)

    def test_HU06_rejects_invalid_and_fractional_units(self):
        self.login()
        for value in ('-1', '0', 'NaN', '0.0001'):
            self.assertEqual(self.move(amount=value).status_code, 400)
        self.assertEqual(self.move(product_id='3', amount='1.5').status_code, 400)

    def test_duplicate_submission_does_not_duplicate_stock(self):
        self.login()
        token = str(uuid.uuid4())
        self.move(amount='3', request_id=token)
        response = self.move(amount='3', request_id=token)
        self.assertIn('no se duplicó', response.text)
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 27000)
        self.assertEqual(self.row('SELECT count(*) FROM movements WHERE request_id=?', (token,))[0], 1)

    def test_concurrent_exits_cannot_overdraw(self):
        def withdraw(_):
            with connect(self.path) as c:
                try:
                    record_movement(c, 1, 'salida', '20', 2, sector='Molino', request_id=str(uuid.uuid4()))
                    return 'ok'
                except ValueError:
                    return 'rejected'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(withdraw, range(2)))
        self.assertCountEqual(outcomes, ['ok', 'rejected'])
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 4000)

    def test_persistence_and_repeatable_seed(self):
        self.login()
        self.move(amount='7')
        second = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test-only-key'})
        self.assertFalse(seed_demo(second))
        self.assertEqual(self.row('SELECT stock FROM products WHERE id=1')[0], 31000)
        self.assertEqual(self.row('SELECT count(*) FROM users')[0], 2)

    def test_html_escaping(self):
        self.login()
        self.product(name='<script>alert(1)</script>')
        page = self.client.get('/').text
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_health_and_cookie_flags(self):
        self.assertEqual(self.client.get('/health').json['status'], 'ok')
        response = self.client.get('/login')
        cookie = response.headers.get('Set-Cookie', '')
        # Force a fresh client so a new session cookie is actually issued.
        response = self.app.test_client().get('/login')
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', response.headers['Set-Cookie'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
