# Decisiones técnicas y sus límites

Este documento explica la lógica del diseño del agente de CV. Distingue lo implementado, lo que debe verificarse en el despliegue y la evolución que tendría sentido si cambia el problema. La existencia de código o de pruebas no acredita por sí sola un despliegue exitoso ni la calidad de un modelo real.

## 1. Un flujo acotado para un problema acotado

El servicio recibe una pregunta, selecciona el contexto profesional, consulta un modelo y entrega una respuesta. No necesita actuar en sistemas externos para explicar un CV. Por eso se evita un ciclo abierto de herramientas y se mantiene visible dónde entran los datos, dónde se aplican límites y dónde puede fallar el proveedor.

```mermaid
flowchart LR
    U[Chat o plataforma del reto] --> A[FastAPI /v1/responses]
    A --> V[Autenticación y validación]
    V --> C[Contexto y reglas del agente]
    K[Markdown curado] --> C
    C --> G[Adaptador Gemini]
    G --> O[Control de salida]
    O --> R[JSON o eventos SSE]
    R --> U
    A <--> M[Historial: memoria o Firestore]
```

La propuesta comercial derivada se desarrolla en [PROPUESTA_DE_VALOR.md](PROPUESTA_DE_VALOR.md). El demostrador no incorpora aún la arquitectura de identidad y autorización necesaria para consultar perfiles de varios empleados.

## 2. Gemini configurable: continuidad y posibilidad de comparación

**Decisión.** Conservar Gemini, elegido por Carlos y ya integrado en el avance. Separar el nombre público del agente del proveedor y modelo reales mediante configuración. El adaptador está en [providers.py](../app/providers.py).

**Por qué.** Mejorar y verificar un flujo existente tiene más valor inmediato que migrarlo sin una hipótesis de calidad, costo o latencia. La interfaz común permite comparar proveedores con las mismas preguntas y cambiar la implementación sin modificar el cliente del reto.

**Costo y límite.** Esta elección no demuestra que Gemini sea el mejor o más barato. Cada proveedor difiere en roles, uso de tokens, errores, límites y finalización. Un cambio por configuración debe acompañarse de pruebas y una nueva evaluación; no equivale a un reemplazo semánticamente idéntico. Los adaptadores alternativos no constituyen un respaldo automático en caso de caída.

El modelo inicial de esta revisión es `gemini-3.5-flash-lite`. Se actualizó desde 2.5 Flash porque el catálogo de Google restringe la familia 2.5 a usuarios anteriores y recomienda modelos recientes para nuevos proyectos. La ficha consultada el 30 de octubre de 2026 lo identifica como estable; debe validarse acceso y calidad en la cuenta del titular. [Catálogo oficial](https://ai.google.dev/gemini-api/docs/models), [ficha de 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

**Cuándo reconsiderarla.** Si el modelo incumple la calidad acordada, cambia su disponibilidad o no satisface los requisitos del entorno objetivo. Comparar calidad, latencia, costo medido y tratamiento de datos con contenido autorizado. No migrar por popularidad.

## 3. Contexto completo para seis documentos

**Decisión.** Usar `KNOWLEDGE_MODE=full` para cargar el corpus pequeño del CV. La implementación está en [knowledge.py](../app/knowledge.py).

**Por qué.** Preguntas como «Resume la trayectoria» cruzan experiencia, proyectos y formación. Enviar todas las secciones evita que una recuperación defectuosa excluya un dato necesario. También simplifica depuración: es posible reconstruir qué información estaba disponible para la respuesta.

**Costo y límite.** El contexto se envía con cada solicitud y consume tokens; un contexto completo no obliga al modelo a usarlo correctamente. La presencia de una fuente tampoco valida su veracidad. Medir el tamaño con el modelo elegido y considerar instrucciones, historial y salida; no defender la decisión con una estimación fija de tokens sin medición.

El prefijo estable puede beneficiarse de caché del proveedor. Los ahorros dependen de un acierto real y de las condiciones del modelo; no se presuponen al calcular costos. [Documentación de caché de Gemini](https://ai.google.dev/gemini-api/docs/caching).

**Cuándo reconsiderarla.** Si crece el corpus, se degrada la calidad, el costo/latencia incumple objetivos o se necesitan permisos distintos por documento. En un servicio con varios usuarios, filtrar por autorización ocurre antes de construir el contexto.

## 4. BM25 opcional como alternativa medible

**Decisión.** Mantener recuperación léxica con BM25 como modo `retrieval`, sin base vectorial ni servicio de embeddings.

**Por qué.** El CV tiene términos concretos —empresas, herramientas y proyectos— para los que una búsqueda léxica es una base simple y explicable. Permite explorar el costo de reducir contexto y comparar respuestas con la misma evaluación.

**Costo y límite.** Una coincidencia léxica puede perder sinónimos, referencias de varios turnos y preguntas de síntesis; devolver los primeros resultados no garantiza que contengan la respuesta. No se presenta BM25 como «RAG empresarial» ni se afirma que supere a embeddings sin un experimento.

**Evolución.** Construir preguntas con pasajes esperados y medir recuperación, además de calidad final. `Recall@k = pasajes relevantes recuperados / pasajes relevantes esperados`. Probar búsqueda híbrida y reranking sólo si resuelven fallos observados; decidir por resultado y costo, no por un umbral arbitrario de tamaño.

## 5. Markdown curado y evidencia con alcance explícito

**Decisión.** El modelo consulta [knowledge/](../knowledge/), organizado por perfil, experiencia, proyectos, formación y liderazgo. El cotejo con el CV de origen se registra en [FUENTES_Y_LIMITES.md](FUENTES_Y_LIMITES.md).

**Por qué.** Facilita corregir fechas, atribuciones y estados; revisar cambios en Git; y separar contenido publicable de material interno. La maquetación del PDF no pasa directamente al contexto.

**Costo y límite.** Curar es una actividad editorial. Puede introducir omisiones o errores. «Fuente del agente» significa contenido disponible para responder, no una verificación independiente de la experiencia. Las cifras deben conservar los calificadores «reportado», «estimado» o «en desarrollo» que correspondan. La ausencia de un dato no demuestra que el hecho sea falso; sólo impide afirmarlo con estas fuentes.

El servidor normaliza referencias agrupadas y elimina ids que no están en el contexto, incluso en streaming. Preserva enlaces Markdown. Este control no comprueba que la afirmación esté sustentada. Las referencias a secciones permiten localizar el respaldo. Una referencia debe llevar a contenido que sustente la afirmación; mencionar un identificador válido no basta. Revisión humana y preguntas adversarias son necesarias para comprobar esa correspondencia.

**Evolución.** Registrar dueño, fecha de revisión, estado y evidencia por afirmación. Antes de ampliar el corpus, definir quién puede autorizar su publicación, corregirlo y retirarlo.

## 6. REST con httpx, con responsabilidad explícita sobre el protocolo

**Decisión.** Usar adaptadores REST pequeños con `httpx`, en lugar de sumar varios SDKs o un framework de orquestación.

**Por qué.** Un flujo de consulta y respuesta requiere pocas operaciones. Un contrato interno común hace visibles el payload, el streaming, los tokens y los errores de cada proveedor. Se reduce el número de abstracciones que el evaluador necesita recorrer.

**Costo y límite.** Menos dependencias no significa menos responsabilidad: el proyecto mantiene el parseo de eventos, timeouts, errores y cambios del proveedor. Los reintentos deben limitarse a fallos transitorios antes de emitir contenido; reiniciar una generación a mitad de stream puede duplicar texto y costo. Un reintento tampoco garantiza que el proveedor no haya facturado un intento previo.

**Cuándo reconsiderarla.** Si las funciones necesarias crecen o un SDK oficial reduce mantenimiento y errores, adoptarlo detrás del mismo contrato. Un framework sólo se justifica cuando sus capacidades resuelven complejidad real.

## 7. FastAPI y una superficie textual de Open Responses

**Decisión.** Servir una API HTTP asíncrona con respuestas JSON y SSE; traducir la conversación y eventos a una superficie de Open Responses mediante [openresponses.py](../app/openresponses.py) y [main.py](../app/main.py).

**Por qué.** El reto exige ese contrato de integración. La separación permite que la plataforma use el mismo agente independientemente de Gemini. FastAPI permite mantener la validación, las rutas, la autenticación y la transmisión de eventos en un servicio compacto.

**Alcance.** El servicio se concentra en mensajes de texto y continuidad de conversación. No implementar imágenes, herramientas o modalidades adicionales evita prometer funciones ajenas al CV. Los campos no soportados deben rechazarse explícitamente, no aceptarse simulando su ejecución.

**Verificación necesaria.** Comprobar esquema, orden de eventos, números de secuencia, respuesta terminal, errores y continuidad; después probar el cliente real del reto. La especificación exige que el tipo del evento coincida con su campo `event` y que el stream termine con un evento terminal; `[DONE]` puede seguirlo. Implementar parte de la especificación no equivale a certificar conformidad completa. [Especificación oficial de Open Responses](https://www.openresponses.org/specification).

## 8. Límites y controles en capas

**Decisión.** Combinar reglas del agente, validación, historial acotado, límites de salida, autenticación configurada y controles de exposición de datos.

**Por qué.** El prompt orienta al modelo; el servidor debe imponer lo que puede verificar de forma determinista. Un usuario no puede obtener más presupuesto o autoridad por solicitarlo en el chat. El agente habla de Carlos en tercera persona para identificar claramente que lo representa y no puede asumir compromisos en su nombre.

**Hallazgo real.** El juez aprobó respuestas que imitaban un personaje mientras lo negaban. Un recordatorio adicional tampoco lo resolvió. Por ello, las órdenes directas de cambiar identidad al principio del mensaje reciben una respuesta de alcance sin invocar al modelo; el resto conserva el flujo conversacional. Esta regla puede rechazar una reformulación legítima que comience igual y no cubre variantes no detectadas.

**Límites de la defensa.** Detectar palabras de inyección aporta una señal, no una garantía. Una expresión regular de teléfono no es un sistema general de prevención de fugas. Una API key compartida tampoco ofrece aislamiento por usuario. El historial aportado por el cliente puede contener afirmaciones inventadas: no debe convertirse en fuente de hechos.

**Controles para un piloto interno.** Identidad corporativa, permisos por documento, cuotas por usuario, rotación de secretos, reglas de retención, revisión del tratamiento de datos y pruebas de fuga entre usuarios. No se declara cumplimiento bancario por usar un proveedor conocido o por añadir un prompt de seguridad.

## 9. Estado compartido y ejecución serverless

**Decisión.** Cloud Run ejecuta el contenedor y Firestore conserva temporalmente las conversaciones consultadas mediante `previous_response_id`. La identidad del servicio accede sólo a la base `cv-agent` y a sus dos secretos. Render y el backend en memoria quedan como alternativa de desarrollo y respaldo.

**Por qué.** Una instancia serverless puede desaparecer o ser reemplazada al publicar otra revisión. Separar el estado permite continuar la conversación sin depender de un proceso específico. Se comprobó con una respuesta creada en la revisión `00002-v8x` y recuperada mediante SSE en `00003-jqd`.

**Costo y límite.** Firestore agrega lecturas, escrituras y retención, pero evita mantener una instancia Redis siempre encendida para este volumen. El historial caduca lógicamente al cabo de una hora y la política TTL activa solicita su limpieza física asíncrona. `store=false` evita almacenarlo. Un fallo de persistencia se comunica como error, no como éxito con continuidad inexistente.

El secreto compartido autentica la integración, no a cada visitante. Antes de incorporar datos internos o múltiples perfiles se requieren identidad individual, aislamiento y permisos. El backend en memoria de Render pierde historial al reiniciar y no comparte estado entre procesos. Ver [Cloud Run](CLOUD_RUN.md).

## 10. Evaluar contrato, contenido y utilidad por separado

| Capa | Qué demuestra | Qué no demuestra |
|---|---|---|
| Pruebas con proveedor simulado | Comportamiento reproducible del servicio, errores y contrato | Fidelidad o utilidad de Gemini |
| Casos de respuesta con Gemini | Comportamiento observado del modelo, prompt y corpus de esa versión | Ausencia de errores en preguntas no cubiertas |
| Reglas deterministas | Presencia o ausencia de señales esperadas | Comprensión del sentido, atribución o matiz correcto |
| Juez LLM opcional | Segunda señal para priorizar revisión | Veredicto independiente e infalible |
| Revisión humana y tareas | Respaldo de afirmaciones, claridad y utilidad para el usuario | Validación universal o auditoría de hechos laborales |

La suite está en [evals/](../evals/) y las pruebas del servicio en [tests/](../tests/). Para afirmar un resultado deben mostrarse ejecución, fecha, configuración, casos, fallos y reporte correspondiente. No decir «todas las evaluaciones pasan» a partir de pruebas simuladas. Cuando el juez use el mismo proveedor, reconocer la posible correlación de errores y calibrarlo con personas.

Preguntas especialmente relevantes: credenciales no documentadas, falsas premisas sobre empleadores, cifras estimadas, diferencias entre contribución y liderazgo, historial manipulado, instrucciones que intentan cambiar el rol, y errores de proveedor. La meta es encontrar fallos y convertirlos en regresiones reproducibles.

## 11. Operación y criterio de entrega

Registrar identificador de respuesta, tiempos, consumo disponible y errores sin guardar por defecto el contenido completo de las conversaciones. No registrar secretos ni cuerpos de error del proveedor que puedan contener datos sensibles. Revisar también qué conserva la plataforma de alojamiento.

Un `/health` exitoso acredita que el proceso responde, no que Gemini pueda completar una llamada. La comprobación real debe hacer una consulta controlada con presupuesto y revisar la respuesta. Observar p50/p95, fallos, tokens y costo; el tiempo total de respuesta y el tiempo al primer texto visible son métricas diferentes.

Ante una regresión: pausar el acceso si hay exposición de datos, conservar evidencia técnica mínima, volver a la versión anterior de código/prompt/conocimiento, repetir los casos fallidos y documentar la recuperación. El cambio de proveedor es una decisión verificada, no una recuperación automática silenciosa.

La entrega se considera lista cuando el perfil esté cotejado y autorizado, las pruebas del código pasen, la evaluación con Gemini tenga resultados revisados, exista un endpoint HTTPS comprobado desde fuera, el agente funcione dentro de la plataforma del reto y el repositorio público no contenga secretos o información privada. Estos son criterios de entrega; no se presume que ya se hayan cumplido.

## 12. Interoperabilidad, contenedor y observabilidad (iteración del 30 de octubre)

**Tolerante en lo inocuo, estricto en lo que cambia el comportamiento.** La plataforma del reto conecta cualquier endpoint Open Responses y sugiere parámetros como `reasoning` o `temperature: 0.7`. Rechazarlos con 400 rompía la integración sin proteger nada. Ahora se aceptan e ignoran los parámetros que no alteran lo que el agente hace (se registran y se cuentan), mientras que herramientas, salida estructurada o ejecución en segundo plano se siguen rechazando para no simular capacidades. `temperature` acepta el rango del estándar (0–2) y se aplica como máximo 1. `truncation=auto` permite descartar turnos antiguos sólo cuando el cliente lo pide.

**Tarjeta de agente A2A.** `/.well-known/agent-card.json` describe al agente, su habilidad, el esquema Bearer y la URL Open Responses. Permite que una plataforma lo registre a partir de la URL. No existe una convención publicada para enlazar Open Responses desde A2A; se usan los campos estándar (`url`, `additionalInterfaces`) y una extensión que apunta a la especificación.

**Un contenedor, dos destinos.** El `Dockerfile` (usuario sin privilegios, dependencias fijadas, sólo código y conocimiento) corre en Cloud Run y en cualquier runtime OCI. Render se conserva como respaldo; el despliegue actual en Cloud Run incorpora Secret Manager, cuenta de servicio de mínimo privilegio, escalado a cero con techo de instancias y observabilidad nativa. Detalle en [CLOUD_RUN.md](CLOUD_RUN.md).

**Observabilidad sin contenido.** Cada solicitud tiene `X-Request-ID` y, en Cloud Run, se correlaciona con Cloud Trace. Los logs JSON registran estado, latencia total, tiempo al primer token, tokens, guardrails activados y códigos de error; nunca textos de usuario, respuestas ni credenciales. `/metrics` (protegido) resume la instancia: p50/p95, tokens, errores y parámetros ignorados. Es deliberadamente en memoria: la vista agregada corresponde a Cloud Logging/Monitoring, no a una base de datos propia.

**Citas fuera del texto, no fuera del sistema.** Los corchetes `[perfil]` hacían verificable cada afirmación, pero en una plataforma que muestra texto plano interrumpían la lectura. El modelo sigue citando —es lo que permite evaluar fidelidad—, y el servidor decide la presentación: por defecto quita los ids del texto y los entrega como anotaciones `file_citation` del estándar, con su posición; registra en logs qué fuentes respaldaron cada respuesta. Los clientes que saben mostrarlos (el chat web, la evaluación) los piden visibles con `metadata.citations`.
