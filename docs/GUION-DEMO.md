# Guion de presentación funcional · 5 minutos

## Introducción (45 segundos)

El relevamiento identifica retiros de insumos menores sin registrar y materiales difíciles de encontrar. Este MVP propone una herramienta independiente para el pañol de Intendencia. No modifica el ERP corporativo. La demostración utiliza únicamente datos ficticios.

## Acceso y catálogo (60 segundos)

Ingresar como Administrador. Mostrar la tabla de existencias y las ubicaciones. Crear **Desengrasante industrial**, código **LIM-003**, categoría Limpieza, unidad litro y ubicación Puerta 3. Configurar mínimo 3 y máximo 25. Guardar y señalar que el stock inicial es cero. Editar luego los umbrales a 4 y 30 para demostrar HU-03.

## Operación diaria (90 segundos)

Cerrar sesión e ingresar como Operario. Mostrar que las acciones administrativas no aparecen. Registrar una entrada de 10 litros del nuevo insumo, con referencia Remito DEMO-001. Buscar por nombre, categoría Limpieza y Puerta 3. Mostrar la disponibilidad de 10 litros.

## Validación y resultado (60 segundos)

Intentar retirar 12 litros para el sector Molino: el sistema debe rechazar la salida por stock insuficiente. Corregir a 2,5 litros y confirmar. Mostrar el resultado: **10 - 2,5 = 7,5 litros**. Explicar que el usuario y la fecha se registran automáticamente. Mostrar el bloqueo al intentar acceder directamente al alta desde el rol Operario.

## Evidencias y límites (45 segundos)

Presentar los resultados reales del informe y el registro de pruebas. La prueba de dos retiros concurrentes verifica que solo se permite el que tiene stock suficiente. Aclarar que la validación es técnica y automatizada, sin aprobación organizacional ni despliegue productivo. Las pantallas de alertas e historial avanzado corresponden a la Versión 2.

## Si se usa el video

Reproducir `Demo-MVP.mp4`, con subtítulos en español. La grabación ejecuta el flujo anterior en una base temporal nueva, sin alterar la base de desarrollo. El video no tiene audio; este guion sirve como narración presencial.
