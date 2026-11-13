# Requirements Document

## Introduction

Chatbot de apoyo académico para la Universidad Autónoma de Bucaramanga (UNAB), desarrollado como trabajo final de Ciencia de Datos en Ingeniería de Sistemas. El sistema combina una aplicación Android nativa (Kotlin/Java) con un backend orquestado por n8n, un servidor MCP en Python (FastMCP), guardrails como microservicio FastAPI, y una base de datos vectorial (Supabase PostgreSQL + pgvector) para ofrecer a los estudiantes consultas sobre su ruta académica, calendario institucional, historial de cursos y noticias de la universidad mediante procesamiento de lenguaje natural.

## Glossary

- **Chatbot**: Sistema conversacional de apoyo académico desplegado en la UNAB.
- **App Android**: Aplicación móvil nativa desarrollada en Kotlin/Java que actúa como interfaz principal del Chatbot.
- **n8n**: Plataforma de orquestación de workflows containerizada en AWS EC2 Ubuntu, expuesta en el puerto 9000.
- **Servidor MCP**: Servidor Model Context Protocol implementado en Python con FastMCP que expone herramientas al LLM.
- **Guardrails**: Microservicio FastAPI independiente que valida entradas y salidas del Chatbot para garantizar respuestas apropiadas.
- **LLM**: Modelo de lenguaje grande (Claude o OpenAI GPT) utilizado para generación de respuestas.
- **RAG**: Retrieval-Augmented Generation; técnica de recuperación de contexto desde documentos para aumentar las respuestas del LLM.
- **Pipeline de Ingesta**: Proceso de chunking, generación de embeddings e inserción en pgvector a partir de documentos CCD.
- **pgvector**: Extensión de PostgreSQL para almacenamiento y búsqueda vectorial, alojada en Supabase.
- **BD Estudiantes**: Base de datos sintética que almacena el historial personalizado de cursos de cada estudiante.
- **Google Sheets**: Hoja de cálculo institucional que contiene el calendario académico de la UNAB.
- **Scraper**: Componente de web scraping one-shot que extrae noticias y novedades institucionales.
- **Workflow n8n**: Flujo de trabajo automatizado dentro de n8n que implementa una funcionalidad específica del Chatbot.
- **Ruteo por Intención**: Mecanismo que clasifica la consulta del usuario y la enruta al Workflow n8n correspondiente.
- **Memoria Persistente**: Almacenamiento del historial de conversación por sesión de usuario en la base de datos.
- **CCD**: Currículo por Competencias y Desempeños; documentos institucionales que describen la ruta académica.
- **Embedding**: Representación vectorial numérica de un fragmento de texto, generada por el LLM o modelo de embeddings.
- **Chunk**: Fragmento de texto resultante del proceso de división de documentos durante la ingesta.

---

## Requirements

### Requirement 1: Autenticación de usuarios en la App Android

**User Story:** As a student, I want to log in to the Android app with my institutional credentials, so that I can access my personalized academic information securely.

#### Acceptance Criteria

1. WHEN a student submits valid institutional credentials, THE App Android SHALL authenticate the student and open the main chat screen within 3 seconds.
2. WHEN a student submits invalid credentials, THE App Android SHALL display an error message indicating authentication failure without revealing credential details.
3. THE App Android SHALL maintain the authenticated session using a secure token stored in encrypted local storage.
4. WHEN an authenticated session token expires, THE App Android SHALL redirect the student to the login screen and invalidate the local token.
5. IF the authentication service is unreachable, THEN THE App Android SHALL display a connectivity error message and allow the student to retry.

---

### Requirement 2: Interfaz de chat

**User Story:** As a student, I want a chat interface in the Android app, so that I can send messages to the Chatbot and receive responses in a conversational format.

#### Acceptance Criteria

1. THE App Android SHALL present a scrollable message list that distinguishes student messages from Chatbot responses using different visual styles.
2. WHEN a student sends a message, THE App Android SHALL display the message in the chat list and transmit it to the backend within 1 second.
3. WHILE a Chatbot response is being generated, THE App Android SHALL display a loading indicator visible to the student.
4. WHEN the Chatbot returns a response, THE App Android SHALL render the response in the chat list within 500 milliseconds of receipt.
5. IF the backend returns an error response, THEN THE App Android SHALL display a friendly error message in the chat without exposing internal error details.
6. THE App Android SHALL support a minimum message input length of 1 character and a maximum of 2000 characters.

---

### Requirement 3: Ruteo por intención

**User Story:** As a student, I want my messages to be routed to the right information source, so that I always receive an accurate and contextually relevant response.

#### Acceptance Criteria

1. WHEN the backend receives a student message, THE Ruteo por Intención SHALL classify the message into one of four intents: consulta-general, calendario, cursos-realizados, or noticias.
2. WHEN the intent is classified as consulta-general, THE n8n SHALL execute the Workflow de Consulta General.
3. WHEN the intent is classified as calendario, THE n8n SHALL execute el Workflow de Calendario.
4. WHEN the intent is classified as cursos-realizados, THE n8n SHALL execute el Workflow de Cursos Realizados.
5. WHEN the intent is classified as noticias, THE n8n SHALL execute el Workflow de Noticias.
6. IF the message cannot be classified into any defined intent, THEN THE Ruteo por Intención SHALL route the message to the Workflow de Consulta General as a fallback.

---

### Requirement 4: Workflow de Consulta General (RAG institucional)

**User Story:** As a student, I want to ask general academic questions and receive answers based on official UNAB documents, so that I get reliable institutional information.

#### Acceptance Criteria

1. WHEN el Workflow de Consulta General receives a student question, THE Servidor MCP SHALL retrieve the top-5 most semantically similar document chunks from pgvector using the question embedding.
2. WHEN document chunks are retrieved, THE LLM SHALL generate a response using the retrieved chunks as context and the student question as input.
3. THE LLM SHALL produce responses in the same language used by the student (Spanish).
4. WHEN a response is generated, THE Guardrails SHALL validate the response before it is returned to the student.
5. IF Guardrails determine the response is out of scope or inappropriate, THEN THE Guardrails SHALL replace the response with a predefined safe fallback message.
6. THE Workflow de Consulta General SHALL complete and return a response within 10 seconds of receiving the student question.

---

### Requirement 5: Workflow de Calendario Académico

**User Story:** As a student, I want to ask about academic calendar dates, so that I can plan my activities around institutional deadlines and events.

#### Acceptance Criteria

1. WHEN el Workflow de Calendario receives a question about academic dates, THE n8n SHALL query the Google Sheets calendar document to retrieve relevant date entries.
2. WHEN calendar data is retrieved from Google Sheets, THE LLM SHALL generate a natural-language response summarizing the relevant dates for the student's question.
3. THE Workflow de Calendario SHALL return a response to the student within 8 seconds of receiving the question.
4. IF the Google Sheets service is unavailable, THEN THE Workflow de Calendario SHALL return an informative error message indicating the calendar is temporarily unavailable.
5. THE n8n SHALL authenticate with Google Sheets using service account credentials stored securely in n8n environment variables.

---

### Requirement 6: Workflow de Cursos Realizados

**User Story:** As a student, I want to ask about my completed and pending courses, so that I can understand my academic progress on the curricular map.

#### Acceptance Criteria

1. WHEN el Workflow de Cursos Realizados receives a query, THE Servidor MCP SHALL retrieve the authenticated student's course history records from the BD Estudiantes using the student's session identifier.
2. WHEN course history is retrieved, THE LLM SHALL generate a personalized response describing the student's completed courses, pending courses, and overall progress percentage.
3. THE Workflow de Cursos Realizados SHALL return a response within 8 seconds of receiving the student query.
4. IF the BD Estudiantes is unreachable, THEN THE Workflow de Cursos Realizados SHALL return an error message and log the failure in n8n.
5. THE Servidor MCP SHALL ensure a student can only access course history records associated with the student's own session identifier.

---

### Requirement 7: Workflow de Noticias

**User Story:** As a student, I want to ask about recent UNAB news and announcements, so that I stay informed about institutional events.

#### Acceptance Criteria

1. WHEN el Workflow de Noticias receives a news-related question, THE n8n SHALL query the news records stored in the database after the last Scraper ingestion.
2. WHEN news records are found, THE LLM SHALL generate a response summarizing the most relevant news items in relation to the student's question.
3. THE Workflow de Noticias SHALL return a response within 8 seconds of receiving the question.
4. IF no news records are found in the database, THEN THE Workflow de Noticias SHALL return a message indicating no recent news is available.

---

### Requirement 8: Pipeline de Ingesta y Embeddings

**User Story:** As a data engineer, I want a pipeline to ingest CCD documents into the vector database, so that the RAG system has up-to-date institutional knowledge available for queries.

#### Acceptance Criteria

1. WHEN the Pipeline de Ingesta is triggered manually, THE Pipeline de Ingesta SHALL split each CCD document into Chunks of a maximum of 512 tokens with an overlap of 50 tokens.
2. WHEN Chunks are generated, THE Pipeline de Ingesta SHALL generate one Embedding vector per Chunk using the configured embedding model.
3. WHEN Embeddings are generated, THE Pipeline de Ingesta SHALL store each Chunk text and its Embedding in the pgvector table in Supabase.
4. WHEN ingestion is complete, THE Pipeline de Ingesta SHALL log the total number of documents processed, chunks created, and embeddings stored.
5. IF an error occurs during Embedding generation or storage, THEN THE Pipeline de Ingesta SHALL log the error with the affected document name and continue processing the remaining documents.

---

### Requirement 9: Scraper de Noticias (One-Shot)

**User Story:** As a data engineer, I want a manual web scraping process to collect UNAB news, so that the news database is populated with current institutional information.

#### Acceptance Criteria

1. WHEN the Scraper is triggered manually, THE Scraper SHALL extract news articles from the configured UNAB institutional web sources.
2. WHEN news articles are extracted, THE Scraper SHALL store each article with its title, publication date, summary, and source URL in the news database table.
3. WHEN the scraping run is complete, THE Scraper SHALL log the number of articles extracted and stored.
4. IF a news source URL is unreachable during scraping, THEN THE Scraper SHALL log the unreachable URL and continue processing the remaining sources.
5. THE Scraper SHALL deduplicate articles based on the source URL before storing, so that duplicate entries are not created on repeated manual runs.

---

### Requirement 10: Memoria Persistente entre sesiones

**User Story:** As a student, I want the Chatbot to remember my previous questions within a session and across sessions, so that I do not have to repeat context in follow-up questions.

#### Acceptance Criteria

1. WHEN a student sends a message, THE Chatbot SHALL retrieve the last 10 conversation exchanges for the student's session from Memoria Persistente storage before calling the LLM.
2. WHEN the LLM generates a response, THE Chatbot SHALL append both the student's message and the LLM response to the Memoria Persistente storage for the student's session.
3. THE Chatbot SHALL scope Memoria Persistente records to individual student session identifiers so that one student cannot access another student's conversation history.
4. WHEN a student's stored conversation history exceeds 50 exchanges, THE Chatbot SHALL retain only the most recent 50 exchanges and delete the older records.

---

### Requirement 11: Guardrails de seguridad y contexto

**User Story:** As a system administrator, I want all LLM responses to pass through content and scope validation, so that the Chatbot only returns appropriate academic content to students.

#### Acceptance Criteria

1. WHEN the Guardrails microservice receives an LLM response, THE Guardrails SHALL evaluate the response against a predefined list of prohibited topics and out-of-scope subject categories.
2. WHEN a student message is received by the backend, THE Guardrails SHALL validate the input for prompt injection patterns before the message is forwarded to the LLM.
3. IF an LLM response is classified as out-of-scope, THEN THE Guardrails SHALL return a standard fallback response: "Solo puedo ayudarte con temas académicos de la UNAB."
4. IF an input message is classified as a prompt injection attempt, THEN THE Guardrails SHALL reject the message and return an error response without forwarding it to the LLM.
5. THE Guardrails SHALL log every rejection event with the timestamp, student session identifier, and rejection reason for audit purposes.

---

### Requirement 12: Visualización de Ruta Académica

**User Story:** As a student, I want to see my academic roadmap in the app, so that I can visually understand my curricular progress.

#### Acceptance Criteria

1. THE App Android SHALL provide a dedicated Ruta Académica screen that displays the full list of courses organized by semester.
2. WHEN the Ruta Académica screen is opened, THE App Android SHALL retrieve the student's course completion status from the backend and render each course as completed or pending.
3. THE App Android SHALL visually differentiate completed courses from pending courses using distinct colors or icons.
4. WHEN course data is unavailable due to a connectivity error, THE App Android SHALL display a cached version of the last successfully loaded Ruta Académica with a staleness indicator.

---

### Requirement 13: Calendario en la App Android

**User Story:** As a student, I want a calendar view in the app, so that I can browse academic dates without sending a chat message.

#### Acceptance Criteria

1. THE App Android SHALL provide a dedicated Calendario screen that displays academic events and deadlines retrieved from the backend.
2. WHEN the Calendario screen is opened, THE App Android SHALL fetch current calendar data from the backend and render events grouped by month.
3. WHEN a student taps an event, THE App Android SHALL display the event name, date, and description in a detail view.
4. IF calendar data cannot be fetched, THEN THE App Android SHALL display the last cached calendar data with a message indicating the data may not be current.

---

### Requirement 14: Notificaciones Push

**User Story:** As a student, I want to receive push notifications about important academic dates, so that I am reminded of deadlines without opening the app.

#### Acceptance Criteria

1. WHEN an academic event is within 48 hours of its date, THE Chatbot backend SHALL send a push notification to the student's registered Android device via a push notification service.
2. WHEN a student receives a push notification, THE App Android SHALL display the notification with the event name and date in the device notification tray.
3. WHEN a student taps a push notification, THE App Android SHALL open the Calendario screen and scroll to the relevant event.
4. WHERE a student has disabled push notifications at the OS level, THE App Android SHALL respect the OS setting and not attempt to deliver notifications to that student.

---

### Requirement 15: Infraestructura y Despliegue

**User Story:** As a DevOps engineer, I want the backend components containerized and deployed on AWS EC2, so that the system is reproducible and operable in a cloud environment.

#### Acceptance Criteria

1. THE n8n SHALL run as a Docker container on an AWS EC2 Ubuntu instance and be accessible on port 9000.
2. THE Servidor MCP SHALL run as a separate Docker container on the same EC2 instance and expose its MCP endpoint only to the n8n container network.
3. THE Guardrails SHALL run as a separate Docker container on the same EC2 instance and expose its FastAPI HTTP endpoint only to the n8n container network.
4. THE n8n SHALL store all credentials (Google Sheets service account, Supabase connection string, LLM API keys) as encrypted n8n environment variables and not in plaintext workflow configurations.
5. WHEN any backend container stops unexpectedly, THE Docker runtime SHALL automatically restart the container using a restart policy of `unless-stopped`.
