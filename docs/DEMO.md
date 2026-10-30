# Demostración de seis minutos y defensa del proyecto

Este guion representa la solución final. Las frases sobre despliegue o calidad sólo se pueden usar después de completar [la aceptación](OPERACION.md). Si Gemini no está conectado, presentar la interfaz como demostración técnica extractiva y reconocer que falta la validación del modelo.

## Preparación

Tener abiertos el chat, el repositorio, este documento y el reporte de evaluación de la versión desplegada. Confirmar proveedor, modelo y huella del corpus en `/health`; comprobar una respuesta real. En el alojamiento gratuito, abrir el servicio con antelación y esperar su arranque. No mostrar claves ni el panel de variables durante la grabación.

## 0:00–0:45 · El problema y la idea

«Un CV presenta información en un orden fijo, pero un entrevistador tiene preguntas concretas. Construí un agente que permite explorar mi experiencia, pedir ejemplos y reconocer qué información no está documentada. Mi propuesta es hacer más fácil encontrar evidencia para una conversación profesional. El reto utiliza mi perfil; una evolución posible sería descubrir capacidades internas para proyectos, después de validar esa necesidad con usuarios.»

## 0:45–2:45 · Mostrar comportamiento, no sólo la pantalla

| Orden | Pregunta | Qué observar y explicar |
|---|---|---|
| 1 | «Resume el perfil de Carlos y qué conecta su experiencia.» | Síntesis clara basada en experiencia, datos y adopción; referencias al CV |
| 2 | «Explícame el caso de Cartas PGMM y qué falta para validar el ahorro neto.» | Diferencia ~5 minutos de generación, revisión humana y ahorro neto no acreditado |
| 3 | «¿Los $4.5 millones de RCP son ahorro realizado?» | Identifica costo de una edición anterior; no infiere ahorro neto |
| 4 | «¿Tiene certificación PMP o un doctorado?» | Reconoce ausencia de información; tampoco inventa que estén planeados |
| 5 | «¿Qué hizo en Ingenico?» y después «¿Qué tecnologías aplicó ahí?» | Conserva el referente entre turnos y responde con lo documentado |

No leer todas las respuestas. Elegir dos para comentar y mostrar las restantes si hay tiempo. Una respuesta incorrecta debe reconocerse y registrarse; no presentarla como exitosa.

## 2:45–4:00 · Explicar tres decisiones

«Primero, usé todo el CV curado como contexto porque es pequeño y las preguntas cruzan varias secciones. Eso evita perder información por recuperar el fragmento equivocado. Su costo se mide por tokens y lo compararía con BM25 si el corpus creciera. No necesito una base vectorial para demostrar este caso.»

«Segundo, separé el contrato que exige el reto del proveedor. La plataforma habla con `/v1/responses`; el adaptador consulta Gemini. Conservé Gemini y dejé el modelo configurable. Esa separación reduce el impacto de un cambio, pero cambiar proveedor requiere volver a evaluar.»

«Tercero, puse controles verificables en el servidor: tamaño de entrada, historial, salida, tiempo, autenticación y estados de error. El modelo recibe reglas de fidelidad; las pruebas verifican lo que el servidor puede garantizar. Una referencia ayuda a revisar una respuesta, pero no demuestra por sí sola que sea verdadera.»

## 4:00–5:00 · Mostrar evidencia de calidad

Abrir [VALIDACION.md](VALIDACION.md) y el reporte correspondiente. Indicar cuántas pruebas técnicas pasaron, sin confundirlas con calidad de Gemini.

«Separé pruebas técnicas reproducibles de una evaluación de contenido con 34 casos. Un endpoint en modo simulado no puede pasar como evaluación del modelo. Los casos cubren información ausente, falsas premisas, varios turnos y matices económicos. El juez LLM es una señal adicional, con revisión humana de casos críticos.»

Si todavía no hay evaluación real: «La infraestructura pasó las pruebas locales. La calidad con Gemini y la integración en Banorte siguen pendientes; no presento resultados que aún no he medido.»

Si ya se realizó: sustituir esa frase por fecha, modelo, revisión del corpus, numerador/denominador, fallos encontrados y correcciones. No reutilizar resultados después de cambiar prompt, conocimiento o modelo sin evaluar el impacto.

## 5:00–6:00 · Negocio y siguiente decisión

«El valor se debe medir por tiempo hasta encontrar evidencia útil, fidelidad, tareas resueltas y costo por tarea. Propongo un piloto de cuatro semanas con una comunidad pequeña y contenido autorizado, comparando búsqueda manual con el asistente. La meta inicial sería reducir 30% el tiempo de tarea sin deteriorar calidad; es una hipótesis, no un resultado obtenido.»

«Por ejemplo, 400 consultas mensuales con cinco minutos menos por tarea liberarían unas 33 horas. Sólo una parte podría convertirse en capacidad útil, y eso no equivale automáticamente a ahorro de dinero. La decisión de ampliar dependería de datos del piloto, incluyendo revisión y mantenimiento.»

«Este proyecto muestra cómo traduzco una necesidad en una solución acotada, verificable y con un criterio de negocio para decidir qué construir después.»

## Preguntas probables

**¿Es un agente si no usa herramientas?**

Es un asistente conversacional especializado con contexto, políticas y memoria. El reto lo denomina agente de CV. No necesita autonomía para actuar sobre sistemas externos: incorporaría una herramienta sólo si resolver una pregunta requiriera una acción o una fuente que hoy falta.

**¿Por qué Gemini?**

Mantiene la solución inicial y permite enfocarse en calidad e integración. El modelo predeterminado vigente se eligió como punto de partida para texto de baja latencia; no declaro superioridad sin comparación. Si falla en fidelidad, acceso, costo o latencia, compararía alternativas con las mismas preguntas.

**¿Por qué no LangChain, una base vectorial o varios agentes?**

El flujo actual consulta un único corpus pequeño. Esas piezas pueden ser útiles cuando hay varias fuentes, permisos o herramientas, pero hoy agregarían mantenimiento. La decisión es proporcional al problema y revisable si cambian los requisitos.

**¿Qué garantiza que no alucina?**

Nada garantiza ausencia total de alucinaciones. El corpus acotado, las instrucciones, las referencias y las evaluaciones reducen el riesgo. Las pruebas con trampas y la revisión de atribución buscan detectar fallos; los límites deterministas controlan aspectos distintos.

**¿Cómo sabes que una cita es correcta?**

El evaluador coteja la afirmación con la sección del CV. El servidor no valida semánticamente cada cita. Una evolución útil sería un registro de afirmaciones y evidencias revisadas, antes de automatizar ese control.

**¿Qué pasa si se corta la conexión o Gemini falla?**

El servidor limita el tiempo y distingue respuesta incompleta de fallo. La interfaz avisa y permite reintentar. Sólo hay reintentos acotados ante ciertos errores HTTP previos a la salida; no se reinicia una generación a mitad de texto ni se cambia silenciosamente de proveedor.

**¿Cómo controlas costos?**

Con salida e historial acotados, autenticación y límite de solicitudes. Mediría tokens facturables, reintentos, evaluaciones y costo por tarea resuelta. El límite por IP no es un presupuesto financiero: hacen falta alertas y límites en la cuenta del proveedor.

**¿Qué se pierde al reiniciar?**

Las respuestas almacenadas temporalmente en memoria. El cliente recibe un error claro si intenta continuar con un id expirado; puede iniciar otra conversación. Varias instancias requerirían memoria compartida con reglas de acceso y retención.

**¿Está listo para un banco?**

Es un demostrador. Un piloto con información interna requiere proveedor y tratamiento de datos aprobados, identidad, permisos por documento, aislamiento, retención, evaluación y operación asignada. Un único secreto compartido y una instancia gratuita no sustituyen esas capacidades.

**¿Qué validarías primero en negocio?**

Que localizar experiencia sea un problema frecuente y costoso, que exista evidencia autorizada y que los usuarios acepten la respuesta como ayuda. Después mediría tiempo completo de tarea, calidad y costo; si no mejora el proceso, no ampliaría el piloto.

## Preguntas para el agente Guía de Banorte

1. ¿El registro espera la base `/v1` o el endpoint completo `/v1/responses`?
2. ¿Qué campos envía el cliente, incluyendo `tools`, `stream`, `store`, `truncation` y `model`?
3. ¿Utiliza `previous_response_id` o reenvía el historial completo? ¿Qué tiempo de respuesta admite?
4. ¿Hay una prueba de aceptación o ejemplos de requests para la integración?
5. ¿Qué evidencia esperan para disponibilidad, evaluación y demo, y cuál es la fecha límite?

El contenido del agente Guía requiere acceso a la plataforma. No se presume haberlo consultado sólo por haber abierto la página de inicio de sesión.
