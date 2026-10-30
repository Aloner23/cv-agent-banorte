# Evidencia de validación

Revisión: **30 de octubre de 2026**, entorno local de Carlos. Python 3.12.14. Dependencias fijadas en `constraints.txt`.

## Resultado comprobado

| Verificación | Resultado | Alcance |
|---|---|---|
| Suite `pytest` | **85 pruebas aprobadas** | Servidor, contrato textual, memoria, privacidad numérica, errores y adaptador Gemini con HTTP simulado |
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

La prueba técnica de esta sesión usó el puerto local 8800 y `--interval 0.1` para un lote de sólo cuatro solicitudes. La evaluación completa usa por defecto 2.1 segundos entre inicios de solicitudes para respetar el límite público. El reporte local más reciente está en `evals/results/latest.md` y se identifica como **prueba técnica mock; no evalúa calidad del modelo**.

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

1. Calidad, fidelidad o latencia de **Gemini real**. No se ejecutaron llamadas al proveedor porque falta una clave configurada.
2. Resultado de la suite semántica de **34 casos**: quedó preparada, no se afirma que esté aprobada.
3. Disponibilidad HTTPS, credencial y cuota en una cuenta de alojamiento.
4. Compatibilidad con el cliente exacto de Banorte: requiere registro y conversación dentro de su plataforma.
5. Conformidad completa con toda la especificación Open Responses o con todos los SDKs.
6. Ahorro económico, mejora de reclutamiento, beneficio para Banorte o validación externa de los hechos del CV.
7. Protección universal contra inyección, fuga de cualquier formato de dato o aislamiento entre usuarios.

## Criterio para validar la calidad real

Ejecutar la suite con modelo, configuración y corpus identificados; revisar los fallos y una muestra de respuestas correctas. El modo calidad registra la revisión del corpus del endpoint; para el juez, exige que coincida con el corpus local. Su resultado no se puede trasladar automáticamente a otro modelo o a una revisión posterior del perfil.

Las reglas léxicas comprueban señales; no interpretan por completo negaciones, atribución o causalidad. Los casos de negocio y credenciales ausentes deben revisarse manualmente. El juez LLM también puede equivocarse, especialmente si comparte proveedor con el agente. Publicar resultados junto con las limitaciones que realmente aplican.
