# Puesta en marcha, publicación y operación

## 1. Configuración local

Usar Python 3.12 y las versiones de `constraints.txt`. El modo predeterminado es Gemini; sin su clave el proceso responde en `/health`, pero `/ready` y las solicitudes reales indican configuración incompleta. El modo sin proveedor se activa explícitamente con `LLM_PROVIDER=mock`.

Copiar `.env.example` a `.env` sólo si aún no existe. Completar `GEMINI_API_KEY` en el archivo local o en el gestor de secretos del alojamiento. Crear un secreto independiente para `AGENT_API_KEY`; esa es la clave que se comparte con la plataforma del reto. Nunca compartir la clave de Gemini con visitantes ni ponerla en JavaScript.

Arranque local:

```bash
source .venv/bin/activate
uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Para ver únicamente la demostración sin costo de modelo:

```bash
LLM_PROVIDER=mock uvicorn app.main:app --host 127.0.0.1 --port 8000
```

El navegador requiere el servidor; abrir `web/index.html` como archivo no conecta el agente.

## 2. Crear el repositorio público

Repositorio: [Aloner23/cv-agent-banorte](https://github.com/Aloner23/cv-agent-banorte). Publicar el contenido de esta carpeta, no su carpeta superior: el PDF original contiene un teléfono y no forma parte del repositorio. `.env*`, entornos virtuales, logs, reportes locales y temporales están excluidos mediante `.gitignore`.

Confirmar los archivos que se incluirán antes del primer push. No incluir claves, conversaciones privadas ni el PDF original. Las capturas de `docs/images/` muestran la interfaz con contenido profesional curado y estado de demostración.

El repositorio se creó en la cuenta del titular. La publicación del código y la disponibilidad del endpoint HTTPS son verificaciones independientes.

## 3. Desplegar en Render

En la cuenta del titular, seleccionar **New → Blueprint** y conectar el repositorio. `render.yaml` fija:

- Python 3.12.14 y dependencias verificadas mediante constraints.
- Gemini explícito con `gemini-3.5-flash-lite`, contexto completo y una instancia.
- `GEMINI_API_KEY` como secreto que debe proporcionar el titular.
- `AGENT_API_KEY` generado por Render.
- Inicio con Uvicorn y comprobación de vida en `/health`.

El Blueprint no prueba por sí mismo que la credencial, el modelo o la cuota funcionen. Después del despliegue comprobar `/ready` y realizar una consulta autenticada real.

El plan gratuito es de demostración: puede suspenderse tras inactividad y tardar en arrancar. Abrirlo antes de la demo y verificarlo. Si se requiere disponibilidad constante, elegir un plan adecuado después de revisar su costo; no contratarlo automáticamente. [Limitaciones de Render](https://render.com/docs/free).

### Proxy y límite de solicitudes

El código usa `request.client.host`; no confía directamente en cualquier `X-Forwarded-For`. Uvicorn sólo debe aceptar encabezados de proxies conocidos. Configurar `FORWARDED_ALLOW_IPS` según la red real del despliegue y comprobarlo allí. Si varios clientes se observan como la misma IP del proxy, compartirán las 30 solicitudes/minuto. No resolverlo confiando indiscriminadamente en cualquier cliente.

Para el reto, autenticación y cuotas de proveedor son controles adicionales. Para un piloto con usuarios, imponer cuotas por identidad autenticada y un límite global de presupuesto.

## 4. Evaluación con Gemini

Desde una configuración autorizada que contenga la clave del agente del destino:

```bash
python -m dotenv -f .env run -- python -m evals.run_evals --url https://TU-SERVICIO.onrender.com
```

`--judge` además requiere una clave local de proveedor y el mismo corpus que el endpoint. Ejecutarlo implica llamadas adicionales facturables. Los reportes se guardan en `evals/results/`, fuera de Git por defecto. Revisar contenido antes de compartir un reporte.

Los 34 casos más varios turnos pueden superar 30 solicitudes en un minuto. El evaluador deja por defecto 6.1 segundos entre inicios de llamadas al agente y al juez, compartiendo la misma pausa para respetar la cuota del proveedor; si se ajusta el límite, debe documentarse en el reporte. Las latencias miden solicitudes, no incluyen la pausa deliberada. No inflar el límite público para ocultar una prueba fallida.

Revisar manualmente los casos de títulos no documentados, NPS, costo histórico y ahorro neto, y los de inyección. No aceptar sólo un porcentaje agregado. Comparar con `retrieval` únicamente como experimento explícito, registrando ambos modos.

## 5. Registrar y probar en Banorte

1. Iniciar sesión o completar la creación de cuenta personalmente y seleccionar la posición Senior.
2. Conversar con el agente Guía y resolver las preguntas de [DEMO.md](DEMO.md).
3. En **Agentes → Añadir un agente**, ingresar la URL HTTPS real en el formato que solicite el formulario. El recurso implementado es `POST /v1/responses`; no adivinar si el formulario agrega esa ruta a una base.
4. Proporcionar `AGENT_API_KEY`, nunca `GEMINI_API_KEY`.
5. Seleccionar el agente en el chat y probar una pregunta directa, una continuación, un dato ausente y una pregunta de impacto económico.
6. Guardar evidencia de la integración y anexar el repositorio público y la demostración.

La revisión inicial sólo alcanzó la pantalla de inicio de sesión; no se conoce aún el payload exacto del cliente Banorte. Si envía un campo no soportado, usar su request real para ajustar el adaptador y añadir una prueba de regresión; no relajar validación indiscriminadamente.

## 6. Operación mínima

| Señal | Interpretación | Acción |
|---|---|---|
| `/health` no responde | Proceso o alojamiento caído, o arranque en curso | Revisar plataforma, estado y logs |
| `/ready` devuelve 503 | Falta credencial/corpus o modo mock | Corregir configuración; no declarar servicio listo |
| 401 del agente | Clave de acceso incorrecta o ausente | Revisar `AGENT_API_KEY`, sin mostrarla |
| 429 del agente | Límite local de solicitudes | Esperar `Retry-After`; revisar proxy y uso |
| 503 con `provider_rate_limit` | Gemini limitó solicitudes o agotó cuota | Respetar `Retry-After`; si persiste, revisar cuota de la cuenta |
| 502 con código de proveedor | Error, filtrado, respuesta vacía o stream inválido | Revisar estado, acceso al modelo y cuota; no cambiar silenciosamente de proveedor |
| 504 o error de tiempo en SSE | Se agotó el tiempo total | Revisar latencia y capacidad antes de ampliar timeout |
| `response.incomplete` | Se alcanzó presupuesto de salida | Pedir una pregunta más acotada o continuar |
| `previous_response_not_found` | Caducidad, expulsión por capacidad, reinicio o `store=false` | Iniciar conversación nueva o reenviar historial autorizado |
| Error de límite de historial | Conversación excede límites | Iniciar conversación nueva; no se descarta contexto silenciosamente |

Los logs de aplicación registran id, estado, latencia, tokens, flags y revisión del corpus. Los logs HTTP del alojamiento pueden conservar otros metadatos: definir retención antes de uso empresarial. Un log exitoso no certifica veracidad de respuesta.

## 7. Recuperación y aceptación

Ante un error de contenido: conservar pregunta, versión y respuesta con datos mínimos; corregir fuente/prompt; agregar el caso a evaluación; probar y redeplegar. Ante fuga o abuso: deshabilitar acceso o rotar el secreto, revisar alcance y recuperar la última versión verificada. Un cambio de secreto requiere actualizar el registro de Banorte.

Antes de declarar entrega completa:

- [ ] CV vigente y contenido autorizado para publicación.
- [ ] Pruebas técnicas pasan con las dependencias fijadas.
- [ ] Repositorio público accesible desde fuera de la sesión del titular.
- [ ] Gemini configurado y probado realmente; modelo/cuota disponibles.
- [ ] Endpoint HTTPS responde con y sin streaming y mantiene varios turnos.
- [ ] Evaluación de 34 casos revisada, con fallos y límites explícitos.
- [ ] Agente registrado y funcionando dentro de Banorte.
- [ ] Demo preparada con resultados actuales, sin secretos en pantalla.
