import os
import uuid
import time
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="PLACSP API — Contratación Pública",
    description="API limpia y optimizada de licitaciones públicas bajo la Ley 37/2007.",
    version="5.1.0",
    docs_url=None,
    redoc_url=None
)

DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
AUDIT_LOGS = []
API_KEY_METRICS = {}
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def get_tenders_dataset():
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        dataset = []
        ministerios = ["Ministerio de Asuntos Económicos", "Ministerio de Hacienda", "Ministerio de Transportes", "Ministerio de Sanidad"]
        for i in range(1, 41):
            dataset.append({
                "id": f"EXP-2026-{str(i).zfill(3)}",
                "titulo": f"Suministro y servicios tecnológicos avanzados - Lote {i}",
                "organo": ministerios[i % len(ministerios)],
                "estado": "En Plazo" if i % 2 == 0 else "Adjudicado",
                "presupuesto": round(35000 + (i * 12500), 2),
                "fecha": f"2026-11-{str((i % 28) + 1).zfill(2)}"
            })
        CACHE_STORAGE["data"] = dataset
        CACHE_STORAGE["timestamp"] = now
    return CACHE_STORAGE["data"]

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        raise HTTPException(status_code=401, detail="API Key inválida o ausente.")
    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="API Docs", swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "5.1.0", "uptime": int(time.time() - START_TIME)}

@app.post("/request-key")
async def request_key(payload: dict = None):
    tier = payload.get("tier", "free") if payload else "free"
    new_key = f"placsp_{tier}_{uuid.uuid4().hex[:10]}"
    DYNAMIC_API_KEYS[new_key] = {"tier": tier}
    return {"status": "success", "api_key": new_key, "tier": tier.upper()}

@app.get("/tenders", dependencies=[Depends(verify_api_key)])
async def get_tenders(q: str = Query(None), limit: int = Query(10, ge=1, le=50)):
    data = get_tenders_dataset()
    if q:
        data = [t for t in data if q.lower() in t["titulo"].lower() or q.lower() in t["organo"].lower()]
    return {"total": len(data), "data": data[:limit]}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PLACSP API — Contratación Pública</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --bg: #090d16;
                --surface: #111827;
                --border: #1f293d;
                --text: #f9fafb;
                --muted: #9ca3af;
                --primary: #3b82f6;
            }
            body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
            .card-clean { background-color: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 28px; }
            .form-control, .form-select { background-color: #070a10; border-color: var(--border); color: white; }
            .form-control:focus, .form-select:focus { background-color: #070a10; border-color: var(--primary); color: white; box-shadow: none; }
            #cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #111827; border-top: 1px solid var(--border); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 9999; }
            .table { color: var(--text); }
            .table th { color: var(--muted); border-bottom-color: var(--border); font-size: 0.8rem; text-transform: uppercase; }
            .table td { border-bottom-color: var(--border); font-size: 0.9rem; }
        </style>
    </head>
    <body>
        <div class="container py-5" style="max-width: 900px;">
            <!-- Header -->
            <div class="d-flex justify-content-between align-items-center mb-5 pb-3 border-bottom border-secondary">
                <div>
                    <h4 class="fw-bold m-0"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP <span class="text-primary">API</span></h4>
                    <p class="text-muted small m-0">Datos oficiales de contratación pública bajo la Ley 37/2007</p>
                </div>
                <div>
                    <a href="/docs" class="btn btn-outline-light btn-sm px-3"><i class="fa-solid fa-book me-1"></i> Documentación API</a>
                </div>
            </div>

            <!-- Card 1: Obtener API Key de forma sencilla -->
            <div class="card-clean mb-4">
                <h5 class="fw-semibold mb-2">1. Obtén tu Clave de Acceso</h5>
                <p class="text-muted small mb-3">Selecciona tu nivel de acceso y genera tu credencial al instante.</p>
                <div class="row g-2 align-items-center">
                    <div class="col-md-5">
                        <select id="tierSelect" class="form-select">
                            <option value="free">Plan Free (20 peticiones/min)</option>
                            <option value="pro">Plan Pro (120 peticiones/min)</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <button onclick="generateKey()" class="btn btn-primary w-100 fw-semibold">Generar API Key</button>
                    </div>
                </div>
                <div id="keyBox" class="mt-3 p-3 rounded bg-dark border border-secondary" style="display:none;">
                    <span class="text-muted small d-block mb-1">Tu Clave API (Guárdala bien):</span>
                    <code id="keyValue" class="text-info fs-6 user-select-all"></code>
                </div>
            </div>

            <!-- Card 2: Buscador Visual Sencillo (Adiós al JSON crudo) -->
            <div class="card-clean">
                <h5 class="fw-semibold mb-2">2. Buscador en Directo</h5>
                <p class="text-muted small mb-3">Prueba el buscador de licitaciones de forma visual y directa.</p>
                
                <div class="input-group mb-3">
                    <input type="text" id="searchInput" class="form-control" placeholder="Escribe para buscar (ej: Ministerio, suministro)...">
                    <button onclick="searchTenders()" class="btn btn-outline-primary px-4">Buscar</button>
                </div>

                <div class="table-responsive">
                    <table class="table table-hover align-middle">
                        <thead>
                            <tr>
                                <th>Expediente</th>
                                <th>Título / Objeto</th>
                                <th>Órgano</th>
                                <th>Presupuesto</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody id="resultsTable">
                            <tr><td colspan="5" class="text-center text-muted py-4">Introduce un término o pulsa buscar para ver resultados.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="text-center text-muted small mt-5">
                Plataforma amparada por la <a href="/legal" class="text-muted text-decoration-underline">Ley 37/2007</a> de Reutilización de la Información del Sector Público.
            </div>
        </div>

        <!-- Banner Cookies RGPD -->
        <div id="cookie-banner">
            <span class="small text-muted"><i class="fa-solid fa-cookie-bite text-warning me-2"></i>Usamos únicamente cookies técnicas esenciales. Al navegar, aceptas su uso.</span>
            <button onclick="acceptCookies()" class="btn btn-sm btn-light fw-bold px-3">Aceptar</button>
        </div>

        <script>
            let currentApiKey = "clave_demo_123";

            if (localStorage.getItem('cookies_accepted') === 'true') {
                document.getElementById('cookie-banner').style.display = 'none';
            }
            function acceptCookies() {
                localStorage.setItem('cookies_accepted', 'true');
                document.getElementById('cookie-banner').style.display = 'none';
            }

            async function generateKey() {
                const tier = document.getElementById('tierSelect').value;
                const res = await fetch('/request-key', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tier: tier})
                });
                const data = await res.json();
                if (data.api_key) {
                    currentApiKey = data.api_key;
                    document.getElementById('keyValue').innerText = data.api_key;
                    document.getElementById('keyBox').style.display = 'block';
                }
            }

            async function searchTenders() {
                const q = document.getElementById('searchInput').value;
                const tbody = document.getElementById('resultsTable');
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Buscando...</td></tr>';

                try {
                    const res = await fetch('/tenders?q=' + encodeURIComponent(q), {
                        headers: {'X-API-KEY': currentApiKey}
                    });
                    const data = await res.json();
                    
                    if (data.data && data.data.length > 0) {
                        tbody.innerHTML = data.data.map(t => `
                            <tr>
                                <td><code>${t.id}</code></td>
                                <td class="fw-medium">${t.titulo}</td>
                                <td class="text-muted small">${t.organo}</td>
                                <td class="text-success fw-semibold">${t.presupuesto.toLocaleString()} €</td>
                                <td><span class="badge bg-secondary bg-opacity-25 text-info">${t.estado}</span></td>
                            </tr>
                        `).join('');
                    } else {
                        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No se encontraron licitaciones.</td></tr>';
                    }
                } catch (e) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Error al consultar la API. Verifica tu clave.</td></tr>';
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head><title>Aviso Legal</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body style="background:#090d16; color:#f9fafb; padding:40px; font-family:'Inter',sans-serif;">
        <div class="container" style="max-width:700px;">
            <h3 class="text-primary mb-3">Aviso Legal y Marco Regulatorio</h3>
            <p class="text-muted">Servicio operado bajo la <strong>Ley 37/2007</strong> de Reutilización de la Información del Sector Público. Actuamos como agregador tecnológico exento de responsabilidad sobre los contenidos originales de la PLACSP.</p>
            <a href="/" class="btn btn-light btn-sm mt-3">Volver al Inicio</a>
        </div>
    </body>
    </html>
    """
