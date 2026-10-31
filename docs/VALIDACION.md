# Evidencia de validación

Revisión: **30 de octubre de 2026**, entorno local de Carlos. Python 3.12.14. Dependencias fijadas en `constraints.txt`.

## Resultado comprobado

| Verificación | Resultado | Alcance |
|---|---|---|
| Suite `pytest` | **134 pruebas aprobadas** | Servidor, contrato textual, memoria, privacidad numérica, errores y adaptador Gemini con HTTP simulado |
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
- Presupuesto efectivo de salida, tiempo total, límites de historial y truncación automática sólo cuando el cliente la solicita.
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
3. Disponibilidad sostenida o garantía de servicio: HTTPS y una respuesta autenticada de Gemini sí se comprobaron en Render.
4. Compatibilidad con todas las variantes futuras del cliente: sí se revisaron conversaciones reales del agente registrado en la plataforma de Banorte.
5. Conformidad completa con toda la especificación Open Responses o con todos los SDKs.
6. Ahorro económico, mejora de reclutamiento, beneficio para Banorte o validación externa de los hechos del CV.
7. Protección universal contra inyección, fuga de cualquier formato de dato o aislamiento entre usuarios.

## Criterio para validar la calidad real

Ejecutar la suite con modelo, configuración y corpus identificados; revisar los fallos y una muestra de respuestas correctas. El modo calidad registra la revisión del corpus del endpoint; para el juez, exige que coincida con el corpus local. Su resultado no se puede trasladar automáticamente a otro modelo o a una revisión posterior del perfil.

Las reglas léxicas comprueban señales; no interpretan por completo negaciones, atribución o causalidad. Los casos de negocio y credenciales ausentes deben revisarse manualmente. El juez LLM también puede equivocarse, especialmente si comparte proveedor con el agente. Publicar resultados junto con las limitaciones que realmente aplican.

## Revisión posterior a las pruebas del usuario · 30/10/2026

Se revisó la conversación del agente registrado en Banorte: perfil, proyectos, falsas premisas, sueldo no documentado, cambio de identidad, estudios, intereses y contacto. Se verificó además HTTPS y una respuesta autenticada de Gemini en Render. Esta observación acredita la integración utilizada, no conformidad universal del protocolo.

La versión 1.1.1 mejora cierres conversacionales, enlaces de contacto y fechas individuales. Corrige el tratamiento de enlaces cuyo texto coincide con un identificador de fuente, incluso fragmentados en streaming. `/health` identifica versión, commit válido, prompt y corpus para distinguir lo evaluado de lo desplegado.

**134 pruebas técnicas pasan**. Se ejecutaron además tres consultas reales con el prompt revisado: contacto con enlaces, fechas separadas de ambas carreras y aficiones ausentes. La revisión manual confirmó esos tres comportamientos y ausencia de preguntas finales repetitivas. El reporte local es `evals/results/revision-conversacion.json` (excluido de Git). El lote completo de 34 casos corresponde a una revisión anterior: no se atribuye su puntuación a este nuevo prompt.

### Comprobación posterior al despliegue

Render desplegó correctamente el commit `a012b857dde0e2a0c661b9b28a49bab4b6d61d6f` (versión 1.1.1). CI de GitHub terminó con éxito. El endpoint público devolvió prompt `d3ff749428a6` y corpus `5e8bacea90d0`. Dos solicitudes autenticadas JSON comprobaron enlaces de contacto y fechas 2018–2023 / 2018–2024; una tercera solicitud SSE con `previous_response_id` identificó ITAM como institución de ambas carreras y terminó en `response.completed`. Reporte local: `evals/results/verificacion-publica-1.1.1.json`. Estas tres respuestas son pruebas dirigidas, no una nueva evaluación completa de 34 casos.

## Cloud Run · versión 1.2.0

140 pruebas técnicas locales aprobadas. Nuevos casos: continuidad entre dos clientes del almacén compartido simulado, rechazo inmediato de registros vencidos, IDs inválidos sin acceso a la base, errores sin detalles privados, persistencia fallida en JSON/SSE sin falso `completed` y `store=false` sin dependencia del almacén. La instalación de dependencias no presenta conflictos.

El despliegue real en Cloud Run y Firestore se comprobó el 30 de octubre de 2026 (México). El commit publicado `e140ce3021def011b8ffe12421c38608cec222d2` pasó CI y construcción de contenedor. Una respuesta JSON autenticada se guardó en la revisión `00002-v8x` y se recuperó por `previous_response_id` mediante SSE en `00003-jqd`, con `response.completed`. Sin clave: 401. Con `store=false`: 200 y continuación posterior: 404. TTL remoto: `ACTIVE`; índices del campo `payload`: excluidos.

Los logs correlacionaron `f3c67d28da894f83` con la revisión anterior (1342 ms), y `8be18b5f213b483c` con la nueva (1059 ms). Son observaciones puntuales, no un benchmark. Se instaló el panel, cinco métricas y la política de incidentes. El panel mostró datos reales de solicitudes, latencia, primer texto, tokens e instancias después del tiempo de agregación. Banorte guardó la nueva URL y una conversación real respondió correctamente sobre el vínculo entre datos e IA. Reportes locales excluidos del repositorio: `evals/results/cloudrun-primera-respuesta.json`, `cloudrun-sse-continuidad.json` y `cloudrun-store-false.json`. Estas pruebas de integración no sustituyen una nueva evaluación completa del contenido ni una prueba de carga.
