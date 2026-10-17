# Manual de usuario · MVP v1

Todos los ejemplos emplean datos ficticios.

## 1. Iniciar sesión (HU-01)

Ingresar con el usuario y contraseña asignados. El Administrador ve el catálogo, el alta y la configuración de umbrales. El Operario ve el inventario y el registro de entradas/salidas. La sesión identifica automáticamente al responsable de las operaciones. Cerrar sesión al finalizar, especialmente en dispositivos compartidos.

## 2. Crear un insumo (HU-02)

Como Administrador, seleccionar **Nuevo insumo**. Completar código interno, nombre, categoría, unidad y ubicación. Seleccionar una de las ubicaciones disponibles (puerta, estante o cajón). Definir mínimo y máximo positivos; el mínimo debe ser menor al máximo. Seleccionar **Guardar insumo**.

El código y el nombre deben ser únicos, sin distinguir mayúsculas/minúsculas ni espacios repetidos. El stock inicial es cero. No usar el alta para asignar existencias: registrarlas como entrada.

## 3. Configurar niveles (HU-03)

En el inventario, seleccionar **Configurar** junto al mínimo/máximo del insumo. Completar los nuevos valores y guardar. El sistema registra fecha y administrador responsable. Los umbrales no bloquean entradas superiores al máximo; la futura pantalla de alertas está fuera de esta versión.

## 4. Consultar stock y ubicación (HU-04)

Escribir parte del nombre, código, categoría o ubicación en la búsqueda. Opcionalmente combinar categoría y ubicación en los selectores. Presionar **Buscar**. Se muestran nombre, código, categoría, ubicación exacta, cantidad y unidad. **Limpiar** quita los filtros.

La tabla obtiene los datos vigentes en cada consulta. Para ver operaciones realizadas desde otra sesión, usar **Actualizar**.

## 5. Registrar entrada (HU-06)

Seleccionar **Registrar entrada**, elegir un insumo y revisar su ubicación/disponibilidad. Indicar la cantidad recibida y, opcionalmente, remito u otra referencia y observación. Seleccionar **Confirmar entrada**. Comprobar el mensaje de éxito y el nuevo saldo.

## 6. Registrar salida (HU-05)

Seleccionar **Registrar salida**, elegir insumo e indicar cantidad y sector de destino. Añadir una observación si corresponde. Seleccionar **Confirmar salida**. Si no alcanza el stock, se informa **Stock insuficiente** sin descontar existencias ni crear el movimiento. Corregir la cantidad e intentar nuevamente.

Las cantidades siempre deben ser positivas: enteros para unidades; hasta tres decimales para litros o kg. Cada movimiento registra usuario, fecha y hora UTC. Si se reenvía el mismo formulario, la operación no se duplica.

## 7. Qué hacer ante un error

- **Credenciales incorrectas:** verificar usuario/contraseña sin compartirlos.
- **Código o nombre existente:** buscar el insumo antes de intentar otra alta.
- **Acceso restringido:** solicitar la operación a un Administrador.
- **Sesión del formulario vencida:** recargar la página e ingresar los datos nuevamente.
- **Stock insuficiente:** comprobar existencias físicas y registradas; nunca inventar una entrada para forzar un consumo.

Esta versión no incluye edición/borrado de movimientos, recuperación de contraseñas ni altas de usuarios desde la interfaz.
