# Revisión de entrega · 30 de octubre de 2026

## Qué está listo

- Código público: https://github.com/Aloner23/cv-agent-banorte
- Servicio en Render: https://carlos-cv-agent.onrender.com
- Recurso conversacional: `POST /v1/responses`, con clave del agente (no la clave de Gemini).
- Agente registrado y conversaciones revisadas en la plataforma del reto.
- Propuesta de negocio, decisiones técnicas, evidencia de evaluación y guion de seis minutos en este repositorio.
- Revisión 1.1.1: respuestas directas sin invitación repetitiva, contacto clicable, fechas por carrera y conservación de enlaces al procesar citas. Estado público con huellas de código, prompt y corpus.

## Cómo defender la solución

**Problema:** un CV obliga a recorrer información estática; el interlocutor necesita evidencia concreta para su pregunta. El agente facilita esa consulta y reconoce lo que no está documentado.

**Contexto completo:** seis documentos pequeños permiten incluir el perfil completo. Evita perder relaciones entre experiencia y proyectos por una recuperación incompleta. Si crecen corpus y costo, comparar recuperación con las mismas preguntas antes de añadir infraestructura.

**Gemini y contrato separado:** conservar el proveedor permite mejorar el producto existente. El adaptador a Open Responses desacopla el cliente del modelo. Una sustitución exige nuevas evaluaciones, no sólo cambiar una variable.

**Citas como metadatos:** la conversación puede mantenerse natural mientras conserva referencias para revisión. Que una cita exista no prueba que la afirmación sea correcta: se necesita evaluación de contenido.

**Controles y evaluación:** el servidor limita entrada, salida, tiempo y acceso. Las pruebas técnicas no miden veracidad; los casos reales y la revisión humana complementan un juez automático que también cometió omisiones.

**Negocio:** evolucionar hacia descubrimiento de capacidades internas sólo tras validar necesidad, permisos y evidencia. Piloto propuesto: cuatro semanas, 20–30 participantes voluntarios, comparación con búsqueda manual, tiempo por tarea, calidad y costo. El ejemplo de 400 consultas y cinco minutos menos implica 33.3 horas brutas al mes; no es ahorro realizado ni beneficio probado para Banorte. Ver [propuesta](PROPUESTA_DE_VALOR.md).

## Qué queda para presentar

1. Confirmar que los datos del perfil siguen vigentes y que la posición seleccionada en la cuenta es Senior; esta revisión no verificó ese ajuste de cuenta.
2. Ensayar el [guion](DEMO.md) con el servicio abierto antes de comenzar: Render Free advierte arranques de 50 segundos o más tras inactividad.
3. Realizar la demostración y compartir el enlace del repositorio por el canal solicitado por reclutamiento. No se ha enviado ningún mensaje al reclutador.

Cloud Run es una alternativa preparada, no el despliegue utilizado. La tarjeta de agente es descriptiva y experimental, no una implementación completa de A2A. El caso es un demostrador con información pública, no una solución bancaria de producción.
