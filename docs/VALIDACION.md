# Evidencia de validación

Revisión: **30 de octubre de 2026**, entorno local de Carlos. Python 3.12.14. Dependencias fijadas en `constraints.txt`.

## Resultado comprobado

| Verificación | Resultado | Alcance |
|---|---|---|
| Suite `pytest` | **102 pruebas aprobadas** | Servidor, contrato textual, memoria, privacidad numérica, errores y adaptador Gemini con HTTP simulado |
| Prueba HTTP del servicio en marcha | **3/3 casos técnicos aprobados** | Rol, formación y dos turnos; proveedor `mock` |
| Navegador de escritorio | Verificado | Envío, recepción SSE, referencia visual a una sección y nueva conversación |
| Vista móvil 390 px | Verificada | Sin desbordamiento horizontal; composición y lectura del chat |
| Dependencias | Sin requisitos rotos | `pip check` |
| Código Python | Compila | `compileall` sobre aplicación y evaluador |
| Exclusión de archivos privados | Comprobada con Git | `.env`, temporales, PDF original y reportes locales fuera del conjunto a publicar |

La suite inicial tenía 14 pruebas. La ampliación busca regresiones de comportamiento, no una puntuación de capacidad del modelo. La salida de tests presenta una advertencia de deprecación del cliente HTTP de Starlette; no hay fallos y no afecta el resultado de las pruebas actuales. La migración futura de ese cliente se hará con una nueva comprobación de dependencias.

Comandos de reproducción:

```bash
LLM_PROVIDER=mock python -m pytest -q
LLM_PROVIDER=mock uvicorn app.main:app --host 127.0.0.1 --port 8000
# En otra terminal, con el mismo entorno virtual:
python -m evals.run_evals --url http://127.0.0.1:8000 --mode mock-smoke
python -m pip check
```

La prueba técnica de esta sesión usó el puerto local 8800 y `--interval 0.1` para un lote de sólo cuatro solicitudes. La evaluación completa deja ahora 6.1 segundos entre inicios de llamadas, tanto al agente como al juez. La primera ejecución real utilizó una pausa insuficiente y encontró HTTP 429 del proveedor. Los reportes locales están en `evals/results/`; el modo y el modelo se identifican en cada uno.

## Primera conexión y hallazgos reales

Se comprobó una respuesta autenticada de `gemini-3.5-flash-lite`, en modo `full`. El primer lote del 30 de octubre registró 23 de 34 casos aprobados por reglas y juez; 11 quedaron sin completar en el agente o el juez durante los límites de cuota. No es una medición completa de calidad ni debe presentarse como 34 casos aprobados.

La revisión encontró además referencias mal formadas y negaciones demasiado absolutas ante datos ausentes. Se reforzó el prompt. El evaluador conserva ahora todas las respuestas de conversaciones, distingue errores de servicio y deja pendientes las rúbricas sin juez. Estos cambios requieren una nueva ejecución; el resultado anterior no se traslada a la versión corregida.

## Evaluación completa con cuota controlada

El [reporte y su revisión](RESULTADOS_GEMINI.md) documentan 34 casos completados, 33 aprobados automáticamente, cero errores de servicio, p50 1.15 s y p95 6.27 s. La revisión posterior encontró defectos no señalados por el juez y se conservan explícitamente en el reporte.

Se comprobó además streaming con Gemini y una continuación sobre PGMM: primer texto en 0.93 s y respuesta completa en 1.39 s en una consulta local. Son observaciones individuales, no objetivos de servicio. El navegador también recibió respuesta real y representó referencias del CV.

La integración continua de GitHub aprobó las 98 pruebas de la primera publicación. La revisión posterior añade pruebas de citas fragmentadas, recordatorio de tono y rechazo de cambios directos de identidad sin invocar al proveedor: **102 pasan localmente**.

Después de los cambios, se repitieron los tres casos de inyección y se inspeccionaron las cuatro respuestas: **3/3 aprobados**, con el caso de cambio directo de rol atendido por una regla sin LLM. [Verificación posterior](RESULTADOS_INYECCION.md). No se suman estos casos al lote anterior para crear un porcentaje nuevo.

## Qué cubren las pruebas añadidas

- Rechazo de tipos inválidos, mensajes no textuales, herramientas no soportadas, cuerpos demasiado grandes y modelos públicos desconocidos.
- Presupuesto efectivo de salida, tiempo total, límites de historial y rechazo explícito de truncación no implementada.
- API key, límites por IP observada, CORS, errores terminales en SSE y respuestas incompletas por presupuesto.
- Expiración, capacidad y continuidad del almacén de respuestas; `store=false`.
- Estado de proceso frente a configuración lista; el modo simulado no puede presentarse como un modelo real disponible.
- Gemini: uso reportado, omisión de pensamientos internos, filtrado, respuesta vacía, cierre abrupto, error HTTP, timeout, reintentos acotados y payload del modelo actual.
- Redacción de formatos numéricos telefónicos incluso cuando están fragmentados entre mensajes de streaming. Los casos usan números ficticios.
- Contexto con identificadores estables, preferencias delimitadas y rechazo de información excesiva sin borrado silencioso del historial.
- Evaluador: exige respuesta no vacía, referencias cuando corresponden, puntuaciones válidas del juez y rechazo de `mock` en modo calidad.

## Lo que todavía NO se ha demostrado

1. Aprobación integral de calidad: se completaron 34 casos con Gemini; el resultado automático fue 33/34 y la revisión identificó defectos adicionales. No se afirma ausencia de alucinaciones.
2. Una evaluación independiente: el juez usa el mismo modelo y omitió problemas de tono, referencias y precisión.
3. Disponibilidad HTTPS, credencial y cuota en una cuenta de alojamiento.
4. Compatibilidad con el cliente exacto de Banorte: requiere registro y conversación dentro de su plataforma.
5. Conformidad completa con toda la especificación Open Responses o con todos los SDKs.
6. Ahorro económico, mejora de reclutamiento, beneficio para Banorte o validación externa de los hechos del CV.
7. Protección universal contra inyección, fuga de cualquier formato de dato o aislamiento entre usuarios.

## Criterio para validar la calidad real

Ejecutar la suite con modelo, configuración y corpus identificados; revisar los fallos y una muestra de respuestas correctas. El modo calidad registra la revisión del corpus del endpoint; para el juez, exige que coincida con el corpus local. Su resultado no se puede trasladar automáticamente a otro modelo o a una revisión posterior del perfil.

Las reglas léxicas comprueban señales; no interpretan por completo negaciones, atribución o causalidad. Los casos de negocio y credenciales ausentes deben revisarse manualmente. El juez LLM también puede equivocarse, especialmente si comparte proveedor con el agente. Publicar resultados junto con las limitaciones que realmente aplican.
