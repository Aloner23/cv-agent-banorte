# Evidencia de validación

Dependencias fijadas en `constraints.txt`. Las comprobaciones siguientes identifican su revisión: una prueba técnica simulada no acredita calidad del modelo, y una evaluación histórica no se traslada a un nuevo prompt o corpus.

## Checkpoint del release desplegado · 31 de octubre de 2026, 18:24 UTC

La versión **1.2.1** quedó desplegada con el commit [`aaa48635e964c494b2bfa99331ead92d93b29f3a`](https://github.com/Aloner23/cv-agent-banorte/commit/aaa48635e964c494b2bfa99331ead92d93b29f3a), corpus **`cac6e7ff0fa8`** y prompt **`d3ff749428a6`**. La revisión de Cloud Run **`carlos-cv-agent-00005-viy`** recibió el **100 % del tráfico** después de las comprobaciones siguientes. Este es el SHA del código ejecutado; la actualización posterior de este documento no requiere redesplegar y puede dejar `HEAD` del repositorio por delante del release activo.

| Verificación | Resultado y alcance |
|---|---|
| Pruebas técnicas locales | **186 aprobadas** en Python 3.12, con proveedor simulado; no miden calidad del LLM |
| CI del SHA desplegado | [Ejecución `41229006112`](https://github.com/Aloner23/cv-agent-banorte/actions/runs/41229006112): trabajos `test` y `container` exitosos |
| Construcción de producción | Cloud Build `ed380622-fbe8-47d3-a793-036e639afb17`: `SUCCESS` |
| Estado después de promover | `/health` y `/ready`: 200, versión, SHA y corpus esperados en las dos URLs oficiales del servicio; `/ready` declara `local_configuration_only` |
| JSON real antes de promover | 200 y `completed`; enlace de Cloud Run correcto; respuesta guardada y recuperada desde Firestore |
| SSE real antes de promover | 200 con `previous_response_id`, 12 eventos en secuencia y cierre `response.completed` seguido de `[DONE]`; enlace al repositorio correcto |
| Rechazos técnicos | Sin clave: 401; entero JSON de 5000 dígitos: 400 con mensaje sanitizado |

Se hicieron **dos generaciones reales** con Gemini y la configuración existente, sobre la revisión final aún sin tráfico de producción. JSON: request ID `7b45d043584340ab`, 1.148 s, 4008 tokens de entrada y 58 de salida. SSE: request ID `20e094bf58b943a2`, 0.666 s, 4082 tokens de entrada y 39 de salida. Son comprobaciones dirigidas de integración y continuidad, no percentiles de latencia, prueba de carga ni una nueva tasa de calidad. Después se promovió esa misma revisión y se verificaron salud, identidad del release y autenticación en el endpoint habitual.

El commit final añade a las correcciones de `1af0978c15da77bbe338dccfbe0d814eb5ee0dcc` una URL alternativa oficial de Cloud Run en el corpus: la URL que contiene el número de proyecto podía confundirse con un teléfono en el filtro de salida. Se agregó una regresión para preservar los enlaces públicos del corpus, incluso en streaming carácter por carácter; no se debilitó el filtro de privacidad. Esto explica el paso de 185 a **186 pruebas** y de `5f2d27259454` a **`cac6e7ff0fa8`**.

La **evaluación completa de los 38 casos actuales sigue pendiente**. El resultado histórico 33/34 pertenece a otro corpus y no se atribuye a este release. Tampoco se repitió el chat dentro de la plataforma Banorte durante este despliegue ni se modificó el registro del candidato.

Se conservaron la configuración de ejecución, los recursos y las referencias de secretos. Los tags temporales de prueba se retiraron. La revisión anterior `carlos-cv-agent-00003-jqd` quedó disponible como destino de rollback; no fue necesario ejecutarlo.

## Auditoría y correcciones previas al despliegue · 31 de octubre de 2026

Antes de las correcciones se reprodujeron **140 pruebas técnicas aprobadas** sobre el contenido de `4fcd41aeb2a1566ae62d8b61c4fd566ee7948869`. El servicio público informó versión 1.2.0, código `e140ce3021def011b8ffe12421c38608cec222d2`, prompt `d3ff749428a6` y corpus `5e8bacea90d0`; `/v1/models` sin clave devolvió 401. `/health` y `/ready` sólo comprobaron configuración, sin generar una respuesta nueva.

La revisión 1.2.1 corrige el error 500 ante un entero JSON excesivo, endurece los criterios de evaluación de cantidades, fechas y matices económicos, y reconcilia la documentación y la fuente del agente con Cloud Run. El lote histórico de 33/34 utilizó el corpus `00f9aee5320c`, distinto de las revisiones posteriores; no se presenta como exactitud de la versión actual. Las regresiones del evaluador usan respuestas sintéticas para probar sus criterios, no para medir Gemini. Una evaluación completa con el corpus actualizado sigue pendiente.

En el checkpoint previo, correspondiente a `1af0978c15da77bbe338dccfbe0d814eb5ee0dcc`, se aprobaron **185 pruebas técnicas** en Python 3.12, sin red ni credenciales reales. La suite dorada pasó a **38 casos y 21 rúbricas**, con 40 llamadas al agente y 38 adicionales si se activa el juez. Los casos de rúbrica sin juez permanecen pendientes. El corpus de esa etapa era `5f2d27259454`; el prompt no cambió. Se conservó la advertencia previa de deprecación de TestClient/httpx. En ese momento aún faltaba comprobar el SHA publicado en CI y en `/health`, además de JSON/SSE; la aceptación posterior se documenta en el checkpoint del release desplegado, arriba.

## Evidencia histórica · 30 de octubre de 2026

Entorno local de Carlos. Python 3.12.14.

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
