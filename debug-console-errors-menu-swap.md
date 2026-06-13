[OPEN] Debug Session: console-errors-menu-swap

## Sintomas
- Hay muchos errores en la consola del navegador.
- El "menu libro" deberia mostrar lo que hoy aparece abajo.
- La zona de abajo deberia mostrar lo que hoy aparece en el "menu libro".

## Hipotesis Iniciales
- H1. El responsive nuevo dejo selectores o nodos que ya no existen y el JS del dashboard intenta manipularlos igual.
- H2. El menu lateral/inferior esta usando el mismo contenedor visual pero con orden CSS incorrecto en mobile.
- H3. Al pasar estilos inline a CSS centralizado, alguna media query invirtio `flex-direction`, `order` o `position` en la navegacion.
- H4. El dashboard carga scripts duplicados o en orden incorrecto y eso dispara errores en consola al abrir detalle/lista.
- H5. El bloque que vos llamas "menu libro" y el bloque inferior comparten clases reutilizadas y una regla responsive los esta pisando.

## Evidencia Pendiente
- Errores concretos de consola.
- Vista exacta donde se reproduce el intercambio entre "menu libro" y "abajo".
- Confirmacion del archivo/vista afectada.

## Estado
- Sesion inicializada.
- Pendiente de inspeccion de runtime y de instrumentacion minima.
