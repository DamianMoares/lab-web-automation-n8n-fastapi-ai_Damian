![logo_ironhack_blue 7](https://user-images.githubusercontent.com/23629340/40541063-a07a0a8a-601a-11e8-91b5-2f13e4e6b441.png)

# Lab | Sistema de automatización con N8N + FastAPI + IA

## Objetivo

Construir tres workflows N8N que, juntos, forman el sistema de automatización completo del proyecto: reacción a eventos, análisis de feedback con IA e informe diario programado.

## Setup

1. Haz un fork de este repositorio.
2. Clona tu fork en tu entorno local.
3. Completa la integración de FastAPI dentro de la carpeta `api/`.
4. Construye los tres workflows de N8N descritos más abajo.
5. Exporta cada workflow desde N8N en formato JSON.
6. N8N corriendo en `http://localhost:5678`
7. Tu API FastAPI (del lab D1) corriendo en `http://localhost:8000`
8. Anota las URLs de los webhooks que N8N te vaya generando

## Entrega

1. Guarda los archivos exportados dentro de `n8n-workflows/`.
2. Sube tus cambios a tu fork.
3. Abre un Pull Request con tu solución.

Tu PR debe incluir:
- el código actualizado de FastAPI
- los tres archivos JSON exportados desde N8N
- cualquier nota necesaria para ejecutar tu solución localmente

## Arquitectura del sistema

```text
FastAPI (eventos)
  ↓ background task
N8N Webhook
  ├── Workflow 1: Tarea urgente → análisis IA → respuesta
  ├── Workflow 2: Feedback → análisis IA → ticket si negativo
  └── Workflow 3: Schedule diario → estadísticas → informe IA

N8N también llama a FastAPI:
  POST /api/chat   — el agente LangGraph
  POST /tareas     — crear tareas
  GET  /tareas     — consultar estadísticas
```

## Paso 1 — Integrar el dispatcher en FastAPI

Añade esta función a tu `main.py` para que la API notifique a N8N en segundo plano:

```python
import httpx
import os
from fastapi import BackgroundTasks

async def notificar_n8n(webhook_url: str, payload: dict):
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:
        pass  # N8N no debe bloquear la respuesta principal

@app.post("/tareas", status_code=201)
async def crear_tarea(tarea: TareaEntrada, background_tasks: BackgroundTasks):
    nueva = guardar_en_db(tarea)
    background_tasks.add_task(
        notificar_n8n,
        os.getenv("N8N_WEBHOOK_TAREAS", ""),
        {"evento": "tarea_creada", "tarea": nueva.dict()}
    )
    return {"ok": True, "data": nueva}
```

## Workflow 1 — Tarea urgente con consejo de IA

**Trigger**: `POST /webhook/evento-tarea`

**Datos de entrada**:
```json
{
  "evento": "tarea_creada",
  "tarea": { "id": 1, "titulo": "Presentación cliente", "prioridad": "alta" }
}
```

**Lógica**:
```text
[Webhook]
   ↓
[IF: tarea.prioridad === "alta"]
   ↓ TRUE                         ↓ FALSE
[HTTP POST /api/chat:           [Set: urgente = false]
 "Da un consejo breve para
  gestionar esta tarea urgente:
  '{{tarea.titulo}}'"]
   ↓
[Set: urgente = true, consejo = {{respuesta_ia}}]
   ↓
[Merge]
   ↓
[Set: timestamp = {{new Date().toISOString()}}]
   ↓
[Respond: { ok: true, urgente, consejo }]
```

## Workflow 2 — Feedback → análisis → ticket

**Trigger**: `POST /webhook/feedback`

**Datos de entrada**:
```json
{ "usuario_id": 42, "mensaje": "La app tarda mucho", "calificacion": 2 }
```

**Lógica**:
```text
[Webhook]
   ↓
[HTTP GET /usuarios/{{usuario_id}}]
   ↓ { nombre, email, plan }

[HTTP POST /api/chat:
 "Analiza este feedback de {{nombre}} (plan: {{plan}}):
  '{{mensaje}}' — Calificación: {{calificacion}}/5.
  Devuelve JSON: { sentimiento, problema_principal, accion }"]
   ↓ { sentimiento, problema_principal, accion }

[IF: calificacion < 3]
   ↓ TRUE
[HTTP POST /tareas:
 { titulo: "Ticket feedback: {{problema_principal}}",
   prioridad: "alta",
   descripcion: "Usuario: {{nombre}} | Cal: {{calificacion}}/5" }]
   ↓
[Merge]
   ↓
[Respond: { ok: true, sentimiento, ticket_creado: [bool] }]
```

Prueba con:
- `calificacion: 5, mensaje: "Perfecto, me encanta"` → no crea ticket
- `calificacion: 1, mensaje: "No funciona nada"` → crea ticket urgente

## Workflow 3 — Informe diario programado

**Trigger**: Schedule — cada día a las 9:00

**Lógica**:
```text
[Schedule: 9:00 diario]
   ↓
[HTTP GET /tareas?completada=false]
   ↓ lista de tareas pendientes

[Code: agrupar por prioridad]
   const tareas = $input.all().map(i => i.json);
   const porPrioridad = tareas.reduce((acc, t) => {
     acc[t.prioridad] = (acc[t.prioridad] || 0) + 1;
     return acc;
   }, {});
   return [{ json: { total: tareas.length, porPrioridad } }];

[HTTP POST /api/chat:
 "Genera un informe diario ejecutivo en 3 párrafos.
  Tareas pendientes: {{total}}. 
  Por prioridad: {{porPrioridad}}.
  Incluye una recomendación de acción."]
   ↓ { informe }

[Code: guardar en archivo]
   const fs = require('fs');
   const entrada = {
     fecha: new Date().toISOString(),
     informe: $json.informe,
     stats: $json.stats
   };
   fs.appendFileSync('informes.jsonl', JSON.stringify(entrada) + '\n');
   return [{ json: { guardado: true } }];
```

*(El email queda como bonus — ver sección Bonus)*

## Entrega

Estructura esperada en el repositorio:

```text
mi-proyecto/
├── api/
│   ├── main.py           (con notificar_n8n integrado)
│   └── ...
└── n8n-workflows/
    ├── workflow-tarea-urgente.json
    ├── workflow-feedback.json
    └── workflow-informe-diario.json
```

Exporta cada workflow desde N8N: menú `⋮` → **Download**.

## Checklist de entrega

- [ ] La API llama al webhook de N8N cuando se crea una tarea (BackgroundTasks)
- [ ] Workflow 1: detecta prioridad alta y obtiene consejo de IA
- [ ] Workflow 2: crea ticket cuando la calificación es < 3 y no lo crea cuando es ≥ 3
- [ ] Workflow 3: el schedule está configurado y el nodo Code agrupa correctamente
- [ ] Los 3 workflows están exportados como JSON en `n8n-workflows/`
- [ ] N8N falla → FastAPI sigue respondiendo (verificar con N8N apagado)

## Bonus

- Configura el Workflow 3 para enviar el informe por email (Mailtrap para pruebas)
- Añade validación de API key en el Workflow 2 (`headers["x-api-key"] === $env.WEBHOOK_SECRET`)
- Implementa `GET /health` en FastAPI que verifique si el webhook de N8N responde