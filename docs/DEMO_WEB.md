# Demostración guiada y acceso sin clave

La página `/` (también `/demo`) explica el problema, permite conversar, muestra capturas reales y desarrolla arquitectura, decisiones, evaluación, operación y una hipótesis de producto. No requiere login ni pegar una clave. El botón «Guardar como PDF» usa la impresión del navegador como respaldo del recorrido.

## Acceso separado de la integración

`POST /demo/chat` acepta exclusivamente `message` (1–1500 caracteres) e `history` (hasta cuatro pares user/assistant y 8000 caracteres). No acepta `previous_response_id`, instrucciones, modelo, herramientas, streaming ni parámetros de generación. Fuerza `store=false`, JSON, temperatura 0.2 y máximo 450 tokens de salida. Usa el mismo núcleo del agente que `/v1/responses`, sin copiar la API key a un proxy HTTP ni al navegador.

`/v1/responses`, `/v1/models`, recuperación de respuestas y `/metrics` conservan su autenticación Bearer. `/chat` conserva la interfaz técnica para esa integración. La demo no puede leer conversaciones del endpoint protegido. El historial que devuelve el navegador es información no confiable, nunca una fuente de hechos del CV.

## Cuota compartida y límites del control

`DEMO_ENABLED=false` por defecto; el script de Cloud Run la habilita explícitamente. `DEMO_DAILY_LIMIT=80` y `DEMO_MINUTE_LIMIT=8` cuentan solicitudes admitidas antes de generar. Un único documento `cv_demo_control/quota` contiene contadores de día UTC y minuto; no guarda identidad, IP, pregunta ni respuesta. Las transacciones de Firestore evitan que dos instancias reserven la misma capacidad. Los errores posteriores consumen cuota, no se reembolsan. El adaptador puede reintentar fallos transitorios hasta tres veces: la cuota cuenta solicitudes del agente, no cada intento HTTP al proveedor.

Si el contador falla, la demo falla cerrada con 503; no usa un contador local como respaldo. 429 incluye `Retry-After`. El modo de desarrollo en memoria sólo limita su proceso; no es el control de producción. Los límites de entrada y salida se aplican en el servidor.

Es una demo pública, no un sistema de identidad ni protección contra denegación de servicio. Cualquiera puede consumir el cupo; las solicitudes rechazadas aún pueden generar costo de infraestructura y lecturas. Las cuotas de la API autenticada son distintas. El presupuesto mensual configurado envía alertas, no constituye un corte automático ni cubre necesariamente la factura de Gemini. Para un piloto: SSO, cuotas por usuario, autorización por documento y protección de borde según riesgo y volumen.

La retención `store=false` evita persistencia en el almacén de conversaciones de esta aplicación; no promete ausencia de procesamiento o retención por Gemini, el navegador o la infraestructura. Evitar datos sensibles.

## Reproducción y evidencias

```bash
DEMO_ENABLED=true LLM_PROVIDER=mock uvicorn app.main:app --port 8000
python -m pytest -q
```

La interfaz identifica el modo simulado. Para una conversación real, cargar la configuración de Gemini por entorno. Las capturas en `web/captures/` muestran conversaciones reales del 2 de noviembre de 2026: `chat.jpg` corresponde a la demo local conectada con Gemini; `platform.jpg`, al cliente del reto conectado con Cloud Run 1.2.1 antes de publicar la demo. No son conversaciones prefabricadas ni evidencia de que ambas superficies tengan la misma revisión.

La revisión móvil se realiza a 390 px y la de escritorio con el tamaño de navegador disponible. Pruebas de seguridad y cuota en `tests/test_demo.py`; evidencia adicional en [VALIDACION.md](VALIDACION.md).

Referencias de implementación: [transacciones de Firestore](https://firebase.google.com/docs/firestore/manage-data/transactions), [cliente Python 2.34.1](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.transaction.Transaction), [límites de instancias Cloud Run](https://docs.cloud.google.com/run/docs/configuring/max-instances-limits).
