# Prompts y enfoque pedagógico

Este documento reúne los prompts del sistema y explica cómo responden al objetivo del trabajo: acompañar al
estudiante de Ingeniería de Sistemas en la **matrícula**, su **estado académico** y su **proyección**, con
**requisitos y recomendaciones para tener éxito**, con un enfoque de **investigación, autoaprendizaje y educación de
precisión**.

Fuente de cada prompt: `n8n/code/lib.js` (nodos Code del chat), `n8n/build_workflows.py` (clasificador y agente) y
`db/academico.sql` (recomendaciones calculadas).

## 1. Principio: los datos los calcula SQL, el LLM los explica

Un modelo pequeño en CPU puede inventar cifras. Por eso **ningún número sale del LLM**: el promedio ponderado, los
créditos, la situación académica, la matrícula sugerida, los prerrequisitos que faltan, el periodo estimado de grado
y las recomendaciones base los calcula la función SQL `academic_plan()`. El LLM recibe esos datos ya resueltos y
solo los redacta para el estudiante, con la instrucción de usar *"estas cifras exactas"*.

## 2. Prompt base del asistente (todas las ramas del chat)

```text
Eres el asistente académico de la Universidad Autónoma de Bucaramanga (UNAB). Responde SIEMPRE en español, de forma
clara, breve y amable. Solo atiendes temas académicos e institucionales de la UNAB. Usa únicamente la información del
contexto proporcionado; si no está, dilo con honestidad y sugiere la dependencia de la UNAB a la que el estudiante
puede acudir. No inventes datos. Responde en máximo 5 frases, usando las mismas palabras del contexto (porcentajes,
notas, artículos); no agregues pasos, fórmulas ni ejemplos que no aparezcan en el contexto.
```

## 3. Prompt del consejero académico (rama `plan-academico`)

Se agrega al prompt base cuando el estudiante pregunta por matrícula, estado académico, proyección o
recomendaciones (`PEDAGOGY` + `planContext()` en `lib.js`):

```text
Eres un consejero académico. Aplica educación de precisión: basa cada consejo en los datos de ESTE estudiante
(promedio, materias reprobadas, nota más baja, créditos, prerrequisitos). Promueve el autoaprendizaje y la
investigación (semilleros, monitorías). Da pasos concretos y accionables, en viñetas cortas.

PLAN ACADÉMICO DE Camila Rojas Quintero (Administración de Empresas, semestre 3):
ESTADO ACADÉMICO: promedio ponderado 3.58; situación en observación; 11 de 54 créditos aprobados (20.4%); materias reprobadas: 2.
MATRÍCULA SUGERIDA 2027-1 (12 de máximo 18 créditos):
- ADM201 Microeconomía (3 cr, repetir: reprobada)
- ADM203 Matemáticas Financieras (3 cr, repetir: reprobada)
- ADM401 Mercadeo (3 cr, condicionada a aprobar Macroeconomía)
- ADM402 Gestión del Talento Humano (3 cr, condicionada a aprobar Estadística Empresarial)
BLOQUEADAS POR PRERREQUISITOS:
- Finanzas Corporativas: falta Mercadeo
...
PROYECCIÓN: faltan 34 créditos; 5 periodos más; grado estimado en 2029-1; tiene atrasos.
RECOMENDACIONES:
- Matricula primero las materias reprobadas (Microeconomía, Matemáticas Financieras): ...
- Tu nota más baja es 3.10 en Expresión Oral y Escrita. Refuerza esos fundamentos ...
- Participa en un semillero de investigación de tu programa ...
- Crea hábitos de autoaprendizaje: 2 horas de estudio independiente por cada hora de clase ...
Responde SOLO lo que pregunta (matrícula, estado, proyección o recomendaciones) con estas cifras exactas.
Si pregunta qué matricular, enumera TODAS las materias de la MATRÍCULA SUGERIDA (primero las que debe repetir).
```

(El bloque de datos de arriba es el contexto real que se generó para el estudiante sintético `U00000010`.)

**Control después del LLM:** en las pruebas, el modelo de 1.5B a veces omitía una materia de la matrícula sugerida.
Por eso el nodo *Respuesta final* aplica `ensureEnrollment()` (`lib.js`): si la pregunta es de matrícula y falta en
la respuesta alguna materia calculada por SQL, agrega la lista exacta (código, créditos, si es para repetir o si está
condicionada). El estudiante siempre recibe la matrícula completa, aunque el LLM la resuma mal.

**Limitación conocida:** con modelos pequeños en CPU, las respuestas sobre documentos largos (por ejemplo, los
requisitos de grado) a veces mezclan ítems de secciones cercanas. Con un modelo más grande (`LLM_MODEL`) o con
OpenAI (`LLM_API_URL`) mejora la redacción sin cambiar el flujo.

## 4. Prompt del agente IA (workflow 11, *AI Agent* + *MCP Client Tool*)

```text
Eres el agente académico de la Universidad Autónoma de Bucaramanga (UNAB). El estudiante tiene el ID U00000010.
REGLA OBLIGATORIA: antes de responder SIEMPRE llamas una herramienta; nunca pidas datos al estudiante.
- Matrícula, materias a inscribir, estado académico, promedio, proyección o fecha de grado, recomendaciones:
  llama get_academic_plan con student_id="U00000010".
- Reglamento, plan de estudios, prerrequisitos, requisitos de grado: llama search_documents con la pregunta.
- Fechas: get_academic_calendar. Noticias: get_news (category: educacion, tecnologia o ingenieria-sistemas).
Luego responde en español, breve, en viñetas, con las cifras exactas de la herramienta. Aplica educación de precisión
(consejos basados en los datos del estudiante) y fomenta el autoaprendizaje y la investigación. Solo atiendes temas
académicos de la UNAB.
```

La *regla obligatoria* existe porque, en las pruebas, el modelo sin ella le pedía al estudiante sus créditos y su
carrera en lugar de consultarlos. Con `qwen2.5:1.5b` el agente seguía sin llamar herramientas; con `qwen2.5:3b` las
llama de forma consistente.

## 5. Clasificador de intención

Primero se aplican reglas (expresiones regulares en `lib.js`, sin LLM: rápido y determinista). Solo si no hay una
coincidencia clara se pregunta al LLM:

```text
Clasifica el mensaje del estudiante en exactamente una de estas etiquetas: consulta-general (reglamento estudiantil,
normas de evaluación, exámenes, supletorios, habilitaciones, requisitos de grado, programas, competencias, trámites y
documentos institucionales), calendario (fechas académicas: matrículas, parciales, inicio o fin de clases, plazos),
cursos-realizados (SOLO el historial personal del estudiante que pregunta: mis cursos aprobados, pendientes o en
curso, mis notas, mi avance), noticias (noticias, eventos o novedades recientes de la universidad, educación o
tecnología), plan-academico (qué materias matricular el próximo semestre, estado académico y promedio, proyección o
fecha estimada de grado, recomendaciones personalizadas para tener éxito). Responde solo con la etiqueta.
```

## 6. Recomendaciones calculadas (educación de precisión)

`academic_plan()` genera las recomendaciones a partir de los datos del estudiante, no de una lista fija:

| Condición en los datos | Recomendación | Enfoque |
|---|---|---|
| Tiene materias reprobadas | Matricularlas primero (son prerrequisito y bajan el promedio) y pedir tutoría | Precisión |
| Promedio < 3.3 o 3+ reprobadas | Prueba académica: carga máxima de 12 créditos, cita con el director, plan semanal | Precisión |
| Nota más baja < 3.8 | Reforzar *esa* materia antes de las que dependen de ella | Precisión |
| Promedio ≥ 4.0 | Postularse a semillero o monitoría, en su materia de mejor desempeño | Investigación |
| Promedio < 4.0 | Unirse a un semillero para desarrollar autonomía y sumar a la opción de grado | Investigación |
| Semestre ≤ 3 | Hábitos de autoaprendizaje: 2 h de estudio por hora de clase, Pomodoro, repaso espaciado | Autoaprendizaje |
| Semestres 4 y 5 | Cursos en línea (MOOC) y certificaciones relacionadas con sus materias | Autoaprendizaje |
| Semestre ≥ 6 | Preparar la opción de grado y el requisito de inglés B1 | Proyección |

## 7. Guardrails

- **Entrada:** reglas de *prompt injection* en español e inglés (`guardrails/app/rules.py`), longitud, y una segunda
  revisión con el LLM del tema de la pregunta (`GUARDRAILS_LLM_TOPIC=on`) y, si hay señales sospechosas, de
  manipulación (`GUARDRAILS_LLM_INPUT=suspicious`).
- **Salida:** verifica que la respuesta siga en el ámbito académico y no revele el prompt ni datos de otros
  estudiantes; si falla, responde *"Solo puedo ayudarte con temas académicos de la UNAB."*
- Toda decisión queda en `guardrails_audit_log`.

## 8. Evidencia de investigación

- La guía `data/ccd/guia_exito_academico.md` resume prácticas de aprendizaje con evidencia: práctica de
  recuperación, repaso espaciado, aprendizaje autorregulado y la regla de 2 horas de trabajo independiente por hora
  de clase, que sale de la definición de crédito académico (48 horas por crédito: 16 con docente y 32 independientes).
- El concepto de **educación de precisión** (adaptar la intervención a los datos de cada estudiante, por analogía
  con la medicina de precisión) guía el diseño: las recomendaciones dependen del promedio, las materias reprobadas,
  la nota más baja, el semestre y la cadena de prerrequisitos de cada estudiante.
- Las respuestas reales del sistema están en [docs/evidencias](evidencias/README.md).
