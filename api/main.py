import os
import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="FastAPI + N8N Automation")

# --- MODELOS DE DATOS ---
class TareaEntrada(BaseModel):
    titulo: str
    prioridad: str  # "alta", "media", "baja"
    descripcion: Optional[str] = None

class TareaDB(TareaEntrada):
    id: int
    completada: bool = False

# Simulación de Base de Datos en memoria
DB_TAREAS = []
id_counter = 1

# Mock de usuarios para el Workflow 2
DB_USUARIOS = {
    42: {"nombre": "Ana Gómez", "email": "ana@empresa.com", "plan": "Premium"},
    100: {"nombre": "Juan Pérez", "email": "juan@empresa.com", "plan": "Free"}
}

# --- DISPATCHER (BACKGROUND TASK) ---
async def notificar_n8n(webhook_url: str, payload: dict):
    """Envía el evento a N8N. Si N8N está caído, el timeout evita que FastAPI se cuelgue."""
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:
        # Fallo silencioso: N8N caído no debe romper la respuesta al usuario
        pass

# --- ENDPOINTS ---

@app.post("/tareas", status_code=201)
async def crear_tarea(tarea: TareaEntrada, background_tasks: BackgroundTasks):
    global id_counter
    # 1. Guardar en "Base de datos"
    nueva_tarea = TareaDB(
        id=id_counter,
        titulo=tarea.titulo,
        prioridad=tarea.prioridad,
        descripcion=tarea.descripcion
    )
    DB_TAREAS.append(nueva_tarea)
    id_counter += 1

    # 2. Notificar a N8N en segundo plano
    webhook_url = os.getenv("N8N_WEBHOOK_TAREAS", "")
    background_tasks.add_task(
        notificar_n8n,
        webhook_url,
        {"evento": "tarea_creada", "tarea": nueva_tarea.model_dump()}
    )
    
    return {"ok": True, "data": nueva_tarea}

@app.get("/tareas")
async def listar_tareas(completada: Optional[bool] = None):
    if completada is not None:
        return [t for t in DB_TAREAS if t.completada == completada]
    return DB_TAREAS

@app.get("/usuarios/{usuario_id}")
async def obtener_usuario(usuario_id: int):
    if usuario_id in DB_USUARIOS:
        return DB_USUARIOS[usuario_id]
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@app.post("/api/chat")
async def mock_ia_chat(prompt: dict):
    """Simulador de agente IA / LangGraph para pruebas locales"""
    texto_prompt = prompt.get("message", "").lower()
    
    # Simulación para Workflow 1 (Consejo)
    if "consejo" in texto_prompt:
        return {"text": "Prioriza delegar subtareas y bloquea las primeras 2 horas del día para este entregable."}
    
    # Simulación para Workflow 2 (Análisis de Feedback)
    if "feedback" in texto_prompt or "calificación" in texto_prompt:
        return {
            "sentimiento": "negativo" if "malo" in texto_prompt or "tarda" in texto_prompt else "positivo",
            "problema_principal": "Rendimiento/Lentitud de la aplicación",
            "accion": "Generar ticket de soporte prioritario"
        }
        
    # Simulación para Workflow 3 (Informe Ejecutivo)
    return {"informe": "Informe Ejecutivo: Se observa una acumulación de tareas de prioridad alta. Se recomienda asignar más recursos al sprint actual."}

# --- BONUS: Health Check ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "api_alive": True}