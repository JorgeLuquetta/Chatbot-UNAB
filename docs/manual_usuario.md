# Manual de usuario — Asistente académico UNAB

Este manual explica cómo usar el asistente como **estudiante** (app móvil y chat web) y como **administrador**
(n8n, base de datos y servidor).

## 1. Para estudiantes

### 1.1 Instalar y abrir la app

1. En el celular Android, instala **Expo Go** desde Play Store.
2. En un computador, abre **https://qrapp.traumado.top** (o entra al portal **https://portal.traumado.top** y elige *App móvil*). Verás dos códigos QR.
3. En Expo Go toca **Scan QR code** y escanea el QR **App móvil**. La primera carga tarda 1 o 2 minutos.
4. Escribe tu **ID de estudiante** (por ejemplo `U00000010`) y toca el botón de enviar (➤). Para la demo no se pide contraseña.

> Sin celular: abre **https://chatbotia.traumado.top** (chat web) en cualquier navegador.
>
> **Portal:** https://portal.traumado.top reúne todas las herramientas (chat, app, plan académico, noticias, n8n y
> la bandeja de correo de prueba). En cada herramienta web, el botón con el **icono de la casa** (arriba a la
> izquierda) vuelve al portal.

### 1.2 Pestañas de la app

| Pestaña | Qué muestra |
|---|---|
| **Chat** | Conversación con el asistente. Toca una sugerencia o escribe tu pregunta (máx. 2000 caracteres). |
| **Mi ruta** | Tus materias por semestre: aprobadas (✔), en curso (◷) y pendientes (○), con nota y porcentaje de avance. |
| **Mi plan** | Estado académico, matrícula sugerida, proyección de grado y recomendaciones. |
| **Noticias** | Noticias de la UNAB (educación, tecnología e ingeniería de sistemas), con fuente y fecha. Toca una para abrirla. |
| **Calendario** | Fechas académicas (matrícula, parciales, finales). La app programa recordatorios locales. |

El botón de salida (arriba a la derecha) permite entrar con otro ID.

### 1.3 Envíos por correo

Cada estudiante de prueba tiene un correo temporal: `unab.<tu id en minúsculas>@yopmail.com` (por ejemplo
`unab.u00000010@yopmail.com`). La bandeja se abre sin registro en https://yopmail.com escribiendo `unab.u00000010`.

1. Pide el envío en el chat: *envíame mi informe de avance al correo*.
2. El asistente te muestra tu correo registrado. Responde:
   - **sí** → lo envía a ese correo;
   - **otro correo** (por ejemplo `micorreo@yopmail.com`) → lo actualiza y lo envía ahí;
   - **no** → cancela.
3. Recibes la confirmación con el enlace a la bandeja. Tienes 15 minutos para responder.

Solo se pueden enviar: **noticias** (con las imágenes adjuntas), tu **informe de avance** (estado académico,
matrícula sugerida, proyección y recomendaciones) y tu **informe de materias**. Máximo 5 envíos por hora.

> Mientras no haya un servidor SMTP configurado, los correos llegan a la bandeja de prueba del portal
> (https://portal.traumado.top/correo/) en lugar de yopmail.

### 1.4 Mi plan: cómo leerlo

- **Promedio ponderado:** cada nota pesa según los créditos de la materia. Las reprobadas cuentan hasta que las
  apruebes.
- **Situación académica:**
  - *Excelencia*: promedio ≥ 4.3 sin reprobadas.
  - *Normal*: promedio ≥ 3.6 sin reprobadas.
  - *En observación*: 1 o 2 reprobadas o promedio entre 3.3 y 3.59.
  - *Prueba académica*: promedio < 3.3 o 3 o más reprobadas.
- **Matrícula sugerida:** las materias que puedes inscribir el próximo periodo, hasta tu carga máxima (12, 18 o 21
  créditos según tu situación). Primero aparecen las que debes **repetir** (↻). *"Si apruebas X"* significa que el
  prerrequisito está en curso y la matrícula depende de que lo apruebes.
- **Bloqueadas:** materias que aún no puedes ver porque les falta un prerrequisito.
- **Proyección:** créditos que faltan, periodos restantes y **periodo estimado de grado**. Tiene en cuenta los
  créditos y también la cadena de prerrequisitos.
- **Recomendaciones:** consejos calculados con tus datos (tu nota más baja, tus reprobadas, tu semestre). El botón
  **Pregúntale al asistente** abre el chat con esa pregunta.

### 1.5 Qué le puedo preguntar al chat

| Tema | Ejemplos |
|---|---|
| Matrícula | *¿Qué materias debo matricular el próximo semestre?* · *¿Cuántos créditos puedo inscribir?* |
| Estado académico | *¿Cuál es mi estado académico?* · *¿Cuál es mi promedio?* |
| Proyección | *¿Cuándo me voy a graduar?* · *¿En cuántos semestres termino?* |
| Recomendaciones | *Dame recomendaciones para tener éxito* · *¿Cómo mejoro mi promedio?* |
| Mis cursos | *¿Qué materias tengo pendientes?* · *¿Cuál es mi avance?* |
| Reglamento y requisitos | *¿Qué dice el reglamento sobre la habilitación?* · *¿Cuáles son los requisitos de grado?* · *¿Qué prerrequisitos tiene Inteligencia Artificial?* |
| Calendario | *¿Cuándo es la matrícula académica?* · *¿Cuándo son los exámenes finales?* |
| Noticias | *¿Qué noticias de tecnología hay hoy?* · *Noticias de ingeniería de sistemas* |
| Envíos por correo | *Envíame mi informe de avance al correo* · *Mándame las noticias de ingeniería por correo* · *Envíame mis materias al correo* |

- Las respuestas tardan **1 o 2 minutos**: el modelo de IA corre en el servidor de la universidad, sin servicios de
  pago. Mientras tanto la app muestra un contador.
- El asistente **solo responde consultas informativas de la universidad**. No hace operaciones (*¿cuánto es
  25+17?*), no resuelve ejercicios ni tareas, no redacta textos ni código y no traduce. Preguntas de otros temas o
  intentos de cambiar sus instrucciones se rechazan.
- Si falla la conexión, toca **Reintentar** en el mensaje de error. *Mi ruta* y *Calendario* muestran la última
  copia guardada cuando no hay internet.

## 2. Para administradores

### 2.1 Accesos

| Recurso | Dirección |
|---|---|
| Portal | https://portal.traumado.top |
| n8n (workflows y ejecuciones) | https://n8n.traumado.top — usuario y clave en `~/Chatbot-UNAB/CREDENCIALES.md` de la VM |
| Bandeja de correo de prueba | https://portal.traumado.top/correo/ |
| SSH a la VM | `ssh azureuser@135.232.242.188` (solo con contraseña, sin llaves; el puerto 22 solo acepta la IP del administrador) |
| PostgreSQL | dentro de la VM: `docker compose exec db psql -U postgres -d chatbot` |

Si cambia tu IP, actualiza la regla de SSH:

```bash
az network nsg rule update -g rg-chatbot-unab --nsg-name vm-chatbot-unabNSG -n ssh-mi-ip --source-address-prefixes <tu-ip>/32
```

### 2.2 Operación diaria

```bash
cd ~/Chatbot-UNAB
docker compose ps                                          # estado de los servicios
docker compose logs -f n8n mcp-server                      # registros
docker compose exec mcp-server python -m app.cli scrape    # actualizar noticias ya (además del cron de 6 h)
docker compose exec mcp-server python -m app.cli ingest    # volver a ingerir data/ccd/ después de agregar documentos
python3 scripts/setup_n8n.py --activate                    # reimportar workflows después de cambiar n8n/
./tests/e2e/evidencias.sh --mcp                            # regenerar las evidencias de prueba
```

- **Agregar documentos al RAG:** copia PDF, DOCX, TXT o MD en `data/ccd/` y ejecuta la ingesta.
- **Cambiar el calendario:** `INSERT INTO academic_calendar (event_name, event_date, description) VALUES (...)`.
- **Agregar fuentes de noticias:** edita `mcp-server/sources.json` (`type: html` con selectores CSS, o `type: rss`). Solo se guardan las de los dominios de `NEWS_ALLOWED_DOMAINS` (por defecto `unab.edu.co`).
- **Activar el envío real por correo (Brevo):** agrega al `.env` `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_USER=<login SMTP>`, `SMTP_PASSWORD=<clave SMTP>` y `SMTP_FROM=Asistente UNAB <tu-remitente-verificado>`, y ejecuta `docker compose up -d mcp-server`.
- **Respaldos:** `~/respaldos-chatbot/` (diario, 7 días). Restaurar: `gunzip -c ~/respaldos-chatbot/chatbot-AAAA-MM-DD.sql.gz | docker compose exec -T db psql -U postgres -d chatbot`.
- **Ver ejecuciones en n8n:** menú **Executions**. Cada ejecución muestra el recorrido por los nodos y los datos.

### 2.3 Encender, apagar y costos

```bash
az vm start      -g rg-chatbot-unab -n vm-chatbot-unab     # todo arranca solo
az vm deallocate -g rg-chatbot-unab -n vm-chatbot-unab     # apaga y deja de cobrar el cómputo
```

La IP es estática: no cambia al apagar y encender.

## Capturas de la app

Para agregar capturas del celular al README:

1. Abre la app en Expo Go con `U00000010` y visita *Chat* (con una respuesta de matrícula), *Mi plan* y *Noticias*.
2. Toma la captura (botón de encendido + volumen abajo).
3. Guárdalas como `docs/img/app_chat.png`, `docs/img/app_plan.png` y `docs/img/app_noticias.png` y súbelas al
   repositorio. El README ya tiene la sección **Capturas**; agrega
   `![Mi plan](docs/img/app_plan.png)`, etc.
