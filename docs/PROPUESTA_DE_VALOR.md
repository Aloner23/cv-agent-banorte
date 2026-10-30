# Talento con evidencia: del agente de CV al descubrimiento de capacidades

**Propuesta para el Reto IA Banorte · Carlos Ignacio Alonso Reyes**

**Estado:** demostrador individual y propuesta de piloto. No constituye una solución contratada por Banorte ni reporta beneficios obtenidos por este agente.

## La idea en una frase

Convertir un perfil profesional en una conversación que permita encontrar experiencia relevante, conocer sus límites y revisar la evidencia que respalda cada respuesta.

El reto inmediato es representar la trayectoria de Carlos. La oportunidad de negocio que se propone explorar es un asistente interno para encontrar capacidades y experiencias en equipos de una organización: quién ha trabajado con determinada tecnología, qué proyectos documenta y a quién conviene consultar. Su función sería facilitar conversaciones y colaboración; las decisiones sobre contratación, desempeño, promoción o asignación seguirían en manos de personas.

## Problema y trabajo que ayuda a resolver

Un CV resume información en un formato fijo. Quien lo consulta necesita responder preguntas particulares: «¿Ha llevado una solución de IA a adopción?», «¿Qué parte construyó personalmente?» o «¿Esta cifra fue un ahorro realizado o una estimación?». Encontrar esas respuestas puede requerir leer varias secciones y pedir aclaraciones al candidato.

En una organización, la misma fricción puede aparecer entre perfiles, fichas de proyectos y presentaciones dispersas. La hipótesis es que existe experiencia útil que resulta difícil de localizar. Esta hipótesis todavía debe comprobarse con usuarios; el demostrador de un solo perfil no demuestra demanda empresarial ni ahorro a escala.

| Participante | Necesidad | Valor que se propone comprobar |
|---|---|---|
| Evaluador del reto o entrevistador | Preparar preguntas relevantes sobre Carlos | Llegar más rápido a hechos, ejemplos y vacíos de información |
| Carlos, como dueño del perfil | Explicar su experiencia de forma consistente | Mantener una versión revisable del contenido y evitar que el agente complete lo desconocido |
| Líder de proyecto o comunidad interna, en el piloto futuro | Encontrar colegas con experiencias documentadas | Reducir el tiempo hasta identificar personas a quienes consultar |
| Responsable de Talento, Transformación o una comunidad técnica | Mejorar el aprovechamiento de capacidades existentes | Medir utilidad y esfuerzo operativo antes de ampliar el servicio |
| Seguridad, privacidad y gobierno de IA | Controlar acceso, datos y cambios | Revisar un alcance acotado, sus evidencias y sus riesgos |

El patrocinador y posible comprador interno sería el responsable del proceso de descubrimiento de capacidades. La aprobación de tecnología, datos y presupuesto corresponde a las funciones internas competentes. No se supone que Banorte tenga este problema, presupuesto o intención de compra.

## Qué ofrece el demostrador

El agente permite consultar experiencia, proyectos, formación y habilidades de un perfil; sintetizar su trayectoria; mantener el contexto de una conversación; y reconocer información ausente. Expone una interfaz de chat y un endpoint textual para integrarse con la plataforma del reto.

Su diferenciador es la disciplina sobre el contenido: distinguir responsabilidad personal, resultado reportado, estimación y propuesta. Un vínculo o referencia a una sección permite revisar el origen; no demuestra por sí mismo que la afirmación sea verdadera.

Ejemplo de respuesta deseada:

> «El material de Carlos describe un generador de cartas que pasó de unas 50 horas a unos 5 minutos de generación, más revisión. La reducción es reportada en su perfil; no tengo una medición independiente ni el tiempo total de revisión.»

Esa precisión importa más que producir una cifra de ahorro llamativa.

## Alcance actual y evolución propuesta

| Dimensión | Demostrador del reto | Piloto empresarial propuesto |
|---|---|---|
| Personas | Un perfil | 20–30 voluntarios de una comunidad acotada |
| Fuentes | Secciones curadas en Markdown, cotejadas con el CV proporcionado | Fichas aprobadas por sus titulares y dueños de proyecto |
| Acceso | Endpoint del reto con clave configurada | Identidad corporativa y permisos por documento |
| Consultas | Trayectoria de Carlos | Experiencias y capacidades documentadas dentro del grupo autorizado |
| Respuestas | Síntesis del perfil y límites | Personas a consultar y evidencia autorizada, sin puntuación de empleabilidad |
| Operación | Servicio demostrativo de una instancia | Retención definida, almacenamiento controlado, cuotas y responsable operativo |
| Evaluación | Contrato técnico y casos de respuesta | Calidad de búsqueda, fidelidad, tiempo de tarea, utilidad y carga de mantenimiento |

La versión actual no incluye búsqueda entre empleados, integración con un sistema de recursos humanos, verificación de credenciales, permisos por documento ni decisiones automatizadas de talento. Tampoco prueba aptitudes mediante el lenguaje del CV ni infiere personalidad, edad, salud u otros atributos sensibles.

## Piloto de cuatro semanas

**Semana 1 — Descubrir y establecer la línea base.** Entrevistar a cinco o seis usuarios del proceso; seleccionar 20–30 participantes voluntarios y unas 30 tareas representativas; medir cuánto tardan hoy los usuarios en localizar una evidencia útil. Acordar qué datos pueden utilizarse, cómo corregirlos y cuándo retirarlos. Si no existe una necesidad repetida o las fuentes no tienen autorización, no iniciar la ingestión.

**Semana 2 — Preparar y evaluar.** Curar fichas con dueño, fecha de revisión, evidencia, rol y estado de cada proyecto. Implementar aislamiento y permisos antes de incorporar múltiples personas. Construir un conjunto de preguntas con respuestas esperadas, preguntas sin respuesta y pruebas de acceso indebido. Reservar preguntas que no se usen para ajustar el sistema.

**Semana 3 — Comparar en tareas reales.** Hacer una prueba cruzada: una mitad de usuarios comienza con búsqueda manual y otra con el asistente, usando tareas equivalentes para reducir el efecto de aprendizaje. Registrar tiempo completo de tarea, incluida la revisión y corrección; éxito de la tarea; afirmaciones sin respaldo; y comentarios. No utilizar el experimento para seleccionar o excluir personas.

**Semana 4 — Decidir con evidencia.** Revisar muestras de respuestas entre dos evaluadores, resolver desacuerdos, calcular costos y documentar incidentes. Decidir continuar, ajustar o cerrar. Una mejora de tiempo con peor fidelidad no alcanza para ampliar el piloto.

Los tamaños anteriores son supuestos de diseño, no un cálculo de potencia estadística. Un piloto pequeño orienta decisiones y descubre fallos; no acredita eficacia universal.

## Métricas y criterios propuestos

Los umbrales siguientes son metas iniciales para acordar con el patrocinador. No son resultados del proyecto ni garantías del modelo.

| Métrica | Cómo calcularla | Criterio propuesto para continuar |
|---|---|---|
| Tiempo de tarea | Mediana de minutos desde la pregunta hasta una evidencia aceptada, incluida revisión | Reducción de al menos 30% frente a tareas manuales equivalentes |
| Tareas resueltas | Tareas que cumplen la rúbrica / tareas intentadas | Al menos 80%, sin empeorar frente a la línea base |
| Fidelidad | Afirmaciones sobre personas respaldadas por una fuente autorizada / afirmaciones comprobables revisadas | Al menos 95%; toda afirmación inventada relevante exige corrección |
| Abstención correcta | Preguntas sin respaldo respondidas reconociendo ausencia / preguntas sin respaldo | Al menos 95% en la muestra reservada |
| Acceso indebido | Pruebas que revelan contenido fuera del permiso del usuario | Cero en el conjunto de pruebas; una fuga detiene el piloto hasta resolverla |
| Utilidad percibida | Usuarios que califican 4 o 5 en escala de 1–5 / usuarios que respondieron | Al menos 70%; reportar también cuántos no respondieron |
| Costo por tarea resuelta | Costo operativo atribuible / tareas resueltas | Inferior al valor de la capacidad liberada, con el criterio del patrocinador |
| Mantenimiento | Horas mensuales de actualización, revisión y soporte | Incluidas en el costo y compatibles con un responsable asignado |

Reportar numeradores y denominadores, distribución y casos fallidos. Un «95%» sobre pocas observaciones aporta menos evidencia que el mismo porcentaje sobre una muestra amplia y representativa. Las evaluaciones automáticas del repositorio sirven como alarmas de regresión; la rúbrica humana decide si la tarea quedó resuelta.

## Caso económico: fórmula y ejemplo ilustrativo

Separar tiempo liberado, valor de capacidad y ahorro de caja evita atribuir al agente beneficios que todavía no existen.

```text
Horas liberadas = consultas mensuales × (minutos manuales − minutos con asistente) / 60
Valor de capacidad = horas liberadas × costo laboral cargado por hora
Beneficio neto estimado = valor de capacidad realizable − costo operativo incremental
Retorno estimado = beneficio neto estimado / costo operativo incremental
```

**Escenario exclusivamente ilustrativo:** 400 consultas al mes, 12 minutos por tarea manual y 7 minutos con asistente, incluida la revisión. La diferencia sería de 33.3 horas mensuales. Si la organización lograra reasignar la mitad de ese tiempo a trabajo útil, la capacidad realizable sería de 16.7 horas. No se asigna un precio a esas horas ni se presentan como reducción de nómina.

El cálculo debe incluir tareas fallidas, correcciones y mantenimiento. Para que hubiera ahorro de caja habría que demostrar una reducción efectiva de gasto; liberar tiempo no lo prueba.

### Costos que deben medirse

```text
Costo LLM = Σ[(tokens de entrada no cacheados × tarifa de entrada)
            + (tokens cacheados × tarifa de caché)
            + (tokens de salida facturables × tarifa de salida)] / unidad de facturación

Costo total = LLM de conversaciones + evaluaciones y reintentos + alojamiento
            + almacenamiento/observabilidad + revisión de contenido + soporte
```

Completar las tarifas con el contrato y la facturación vigentes del proveedor elegido; no asumir descuentos, créditos o aciertos de caché. Contrastar los tokens reportados por la aplicación con el consumo facturado, incluidos conceptos específicos del modelo. El costo por conversación debe incluir todos sus turnos. Si no hay tareas resueltas, el costo por tarea resuelta no es calculable y el piloto no demuestra valor.

## Riesgos y decisiones de producto

| Riesgo concreto | Respuesta propuesta |
|---|---|
| Un resultado estimado se narra como ahorro realizado | Etiquetar estado y tipo de evidencia; evaluar explícitamente esos matices |
| Perfil desactualizado o atribución incorrecta | Dueño del contenido, fecha de revisión y mecanismo de corrección o retiro |
| Una respuesta favorece perfiles mejor redactados | Evaluar cobertura; mostrar evidencia y límites; no ordenar por una puntuación de mérito |
| Acceso a información de otra persona o proyecto | Autorizar fuentes antes de recuperarlas; pruebas de aislamiento por usuario y documento |
| Datos enviados a un proveedor no aprobado | Usar únicamente contenido autorizado en el reto; revisar proveedor, región y tratamiento antes del piloto interno |
| Abuso del endpoint o gasto inesperado | Autenticación, límites de consumo, alertas de gasto y procedimiento para deshabilitar acceso |
| Sobreconfianza en una respuesta fluida | Identificar al agente como IA y permitir consultar el contenido que sustenta la respuesta |

## Qué demuestra sobre el candidato

La solución busca demostrar capacidad para traducir una necesidad en un producto acotado: elegir una arquitectura proporcional al problema, diseñar una integración verificable, controlar afirmaciones, definir medidas de calidad y construir un caso económico comprobable. Esas son evidencias del trabajo realizado en este repositorio. Las experiencias laborales narradas proceden del material del perfil y no cuentan con validación externa por este proyecto.

Las cifras presentes en [proyectos de IA](../knowledge/03_proyectos_ia.md) deben conservar su naturaleza: el costo histórico de una edición tercerizada no equivale al ahorro de su sustitución; un business case no equivale a ingreso o beneficio capturado; y un proyecto en desarrollo no equivale a una implantación terminada. El cotejo con el PDF proporcionado se documenta en [FUENTES_Y_LIMITES.md](FUENTES_Y_LIMITES.md); no reemplaza la confirmación del titular sobre vigencia y autorización para publicar los detalles profesionales.

Documentos complementarios: [decisiones técnicas](DECISIONES_TECNICAS.md) y [demostración de 6 minutos](DEMO.md).
