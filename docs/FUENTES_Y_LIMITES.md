# Fuentes, trazabilidad y límites

Revisión documental: 30 de octubre de 2026. Responsable del contenido: Carlos Ignacio Alonso Reyes.

## Fuente utilizada

Se cotejaron el texto y las dos páginas renderizadas del archivo local `Carlos_Alonso_CV Actualizado.pdf` con las seis secciones de `knowledge/`. El PDF original permanece fuera de este repositorio: contiene un teléfono que deliberadamente no forma parte del contexto público del agente.

Huella SHA-256 del PDF revisado:

```text
95ea798e19e70465d33c9522170c900b6c08fc5ea6ea967a986e7d8a44da6cde
```

El cotejo acredita correspondencia con el documento aportado, no veracidad externa de cargos, títulos, premios o cifras. No se consultaron expedientes de empleadores ni bases privadas. La cuenta GitHub `Aloner23` se corroboró mediante la conexión autorizada del usuario; sus repositorios no se incorporan automáticamente como evidencia de proyectos del CV.

| Referencia del agente | Archivo | Ubicación en el PDF |
|---|---|---|
| `[perfil]` | `knowledge/01_perfil.md` | Página 1, encabezado, perfil ejecutivo y áreas de especialidad |
| `[bbva-actual]` | `knowledge/02_bbva_actual.md` | Página 1, experiencia profesional |
| `[proyectos-ia]` | `knowledge/03_proyectos_ia.md` | Página 1, soluciones; página 2, portafolio adicional |
| `[trayectoria-previa]` | `knowledge/04_trayectoria_previa.md` | Página 2, trayectoria |
| `[formacion-habilidades]` | `knowledge/05_formacion_habilidades.md` | Página 2, formación, herramientas e idiomas |
| `[liderazgo-reconocimientos]` | `knowledge/06_liderazgo_reconocimientos.md` | Página 2, liderazgo y distinciones |

La sección «Este agente de CV» y las aclaraciones de interpretación son documentación editorial de este proyecto, no pasajes del PDF. Su estado de publicación debe actualizarse sólo después de verificar los enlaces públicos. El endpoint `/health` expone `knowledge_revision`, una huella del corpus cargado, para asociar evaluaciones con una versión concreta.

## Correcciones realizadas respecto al avance

- Eliminada la instrucción que presentaba PMP y Scrum como certificaciones planeadas: no aparecen en la fuente. La respuesta correcta es que no están documentadas, sin inventar siquiera una intención de obtenerlas.
- Al iniciar la revisión no se encontró un repositorio del agente. Posteriormente se publicó [Aloner23/cv-agent-banorte](https://github.com/Aloner23/cv-agent-banorte); la ausencia inicial es un hallazgo histórico, no el estado actual.
- Precisado el significado de los indicadores: costo histórico, estimación, tiempo de generación y caso de negocio son conceptos distintos.
- Las referencias `[id]` se solicitan al modelo y ayudan a revisar una afirmación. No existe un verificador semántico que pruebe automáticamente que cada cita respalda cada frase. Las reglas, los tests y las evaluaciones reducen fallos, no garantizan ausencia de alucinaciones.

## Interpretación defendible de las cifras

| Dato del CV | Qué se puede decir | Qué no se puede concluir |
|---|---|---|
| Edición RCP tercerizada >$4.5 M MXN | Costo de referencia de la edición anterior | Que se ahorró exactamente esa cantidad o que existe un ROI auditado |
| RCP resultados, ~$80 mil MXN | Desarrollo externo que se busca evitar; solución en desarrollo | Beneficio realizado, neto y auditado |
| PGMM, ~50 horas → ~5 minutos más revisión | Reducción reportada en generación de lotes, con revisión posterior | Tiempo total de extremo a extremo o ahorro neto sin medir revisión y operación |
| Monitoreo, 4 horas diarias | Ahorro de tiempo estimado | Ahorro de efectivo o evidencia de captura del beneficio |
| Publicación, 2 horas por vacante | Ahorro aproximado reportado | Magnitud anual sin volumen y tasa de uso |
| Liderazgo, ~$2 M MXN anuales | Valor planteado en un caso de negocio | Beneficio ya realizado |
| Human IA Feedback y NPS | Objetivo de mejorar experiencia | Aumento medido del NPS: la fuente no lo reporta |

## Información que el agente debe reconocer como ausente

Salario, disponibilidad contractual, doctorado, certificaciones no documentadas, porcentajes de exactitud de los proyectos, arquitectura detallada no descrita, gasto operativo, volumen real de transacciones, pruebas de seguridad bancaria y causalidad independiente de los resultados. No inferir dominio experto de todas las herramientas listadas ni participación individual exclusiva en iniciativas colectivas.

## Actualizar el contenido

1. Carlos revisa y corrige el CV o aporta evidencia publicable.
2. Editar sólo los Markdown pertinentes, preservando los ids; marcar lo estimado, planeado y logrado.
3. Confirmar que no se incorporaron teléfonos, secretos o información de empleadores que no deba publicarse.
4. Ejecutar pruebas locales y la evaluación con Gemini; registrar la revisión del corpus, modelo, fecha y resultados.
5. Desplegar la revisión, verificar la configuración y hacer una conversación real de extremo a extremo.

Cloud Run conserva temporalmente las conversaciones en Firestore; el backend en memoria del proceso se utiliza en local y en Render. El límite de 200 respuestas sólo aplica a memoria. Cada respuesta vence lógicamente una hora después de guardarse; el borrado físico de Firestore es asíncrono. Al continuar una conversación se guarda una nueva copia de sus turnos con otra caducidad, por lo que no es un plazo máximo desde la primera captura de cada dato.

El navegador no persiste la clave de acceso ni el historial. Iniciar una conversación nueva no borra registros del servidor, y `store=false` evita nuevas escrituras sin eliminar las anteriores ni impedir el envío de contexto al modelo. Antes de un piloto empresarial se deben acordar la retención, la eliminación y el tratamiento de datos con el proveedor aprobado. Ver [operación de Cloud Run](CLOUD_RUN.md).
