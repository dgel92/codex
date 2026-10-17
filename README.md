# Intendencia · Versión 1 del MVP

Aplicación web académica para el control interno del pañol de Molinos Florencia S.A.U. Desarrollada a partir de las etapas 7 a 10 de **ABP- PP (1).pdf**. Incluye HU-01 a HU-06; los datos y usuarios de ejemplo son ficticios.

## Iniciar

Requisitos: Python 3.12 o posterior. No necesita Node, servicios externos, claves de API ni conexión con el ERP.

```bash
cd /workspace/codex
python3 -m venv /workspace/.venv-mvp
/workspace/.venv-mvp/bin/python -m pip install -r requirements.txt
/workspace/.venv-mvp/bin/python app.py --seed-demo
```

El servidor de desarrollo escucha en el puerto 8000, solo en la máquina local. Abrirlo con un navegador local al servidor. Para otro equipo, usar un túnel o un despliegue autenticado con HTTPS. No exponer el servidor de desarrollo a Internet.

En otro directorio, reemplazar las rutas anteriores por las de la copia del proyecto y su entorno virtual. `--port` permite elegir otro puerto. `--init-only` inicializa la base sin iniciar el servidor.

### Cuentas ficticias de demostración

| Usuario | Contraseña de demostración | Rol |
|---|---|---|
| `admin` | `AdminDemo2026!` | Administrador |
| `operario` | `OperarioDemo2026!` | Operario |

Estas credenciales son públicas y exclusivas del ejemplo académico. La carga `--seed-demo` actúa solo sobre una base sin usuarios y nunca reemplaza datos existentes. Crea cuatro insumos y movimientos de apertura ficticios.

## Funciones

| Historia | Implementación |
|---|---|
| HU-01 | Acceso con contraseña cifrada mediante hash scrypt; sesión, salida y autorización en servidor por rol. |
| HU-02 | Alta con código/nombre únicos, categoría, unidad y ubicación estructurada; stock inicial cero. |
| HU-03 | Mínimos y máximos positivos, mínimo menor al máximo, edición solo por administrador y registro interno de usuario/fecha. |
| HU-04 | Búsqueda parcial por nombre, código, categoría o ubicación; filtros combinados y tabla de existencias. |
| HU-05 | Salida por cantidad y sector; observación opcional, bloqueo por stock insuficiente y transacción atómica. |
| HU-06 | Entrada con cantidad positiva, referencia opcional y registro de usuario/fecha. |

Administrador y Operario pueden registrar entradas y salidas; el Administrador hereda la operación del pañol. Los roles y ubicaciones propuestos requieren validación de la organización. La base admite litros/kg con hasta tres decimales y unidades enteras. La pantalla consulta el stock actual en cada petición; después de un movimiento propio muestra el nuevo saldo. Para cambios de otro dispositivo, usar **Actualizar** o repetir la búsqueda. No hay actualización push.

No se implementaron las pantallas de alertas HU-07 ni el historial avanzado HU-08, reservados para la Versión 2 en la etapa 10. Los movimientos sí quedan persistidos como base de trazabilidad. No hay integración con Oracle JD Edwards, compras, pagos ni contabilidad.

## Persistencia

SQLite se crea en `instance/inventario.sqlite3`; la clave aleatoria de sesión queda en `instance/.session-key` con permisos 0600. Ambas rutas están ignoradas por Git y excluidas del paquete de entrega. Detener y reiniciar conserva los datos. No borrar la carpeta para actualizar la aplicación.

Para una base aislada, definir `MVP_INSTANCE=/ruta/a/otra/carpeta` antes de iniciar. Para un despliegue posterior detrás de HTTPS, definir `MVP_SECURE_COOKIE=1`. La versión entregada está preparada para demostración local; antes de uso corporativo faltan, entre otros aspectos, aprovisionamiento real de usuarios, protección contra intentos de acceso reiterados, copias de respaldo operativas, revisión de seguridad y despliegue WSGI con TLS.

## Pruebas y evidencias

```bash
cd /workspace/codex
/workspace/.venv-mvp/bin/python -m unittest discover -s tests -v
```

Las pruebas unitarias e integrales usan bases temporales. Verifican reglas de cantidades, autenticación, permisos, filtros, altas, unicidad, umbrales, entradas/salidas, idempotencia, concurrencia y persistencia. No modifican la base de desarrollo.

Para reproducir la demo automatizada y las capturas:

```bash
/workspace/.venv-mvp/bin/python -m pip install -r requirements-dev.txt
# Se necesitan Chromium y ffmpeg instalados en el sistema.
/workspace/.venv-mvp/bin/python scripts/demo.py
/workspace/.venv-mvp/bin/python scripts/presentacion.py
```

El grabador inicia y detiene su propio servidor en un puerto disponible, usa una base temporal independiente y comprueba el saldo final en pantalla y en SQL. La demostración no es una animación: es una grabación del navegador operando el producto. Incluye subtítulos en español y no tiene narración de audio.

Los entregables están en `entregables/`: presentación editable PowerPoint, presentación PDF, video MP4, informe de validación, manual y registros de pruebas. El guion permite repetir la exposición de forma presencial.

## Estructura

`app.py`: servidor, persistencia y reglas de negocio. `templates/` y `static/`: interfaz. `tests/`: pruebas unitarias e integrales. `scripts/`: demo y generación de presentación. `docs/`: alcance, manual y guion.

Esta nueva implementación y sus pruebas fueron realizadas durante esta sesión de desarrollo. No acreditan que las pruebas o la demo existieran en la instancia académica anterior ni constituyen aceptación por parte de la empresa.
