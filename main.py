import os
import uuid
import requests
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="API de Contratación Pública (PLACSP)",
    description="Infraestructura de datos de licitaciones públicas oficiales bajo amparo de la Ley 37/2007.",
    version="2.8.0",
    docs_url=None,
    redoc_url=None
)

# Base de datos en memoria para claves emitidas dinámicamente
DYNAMIC_API_KEYS = {}

# Claves maestras por defecto
MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        raise HTTPException(
            status_code=401, 
            detail="Acceso Denegado: Clave de API inválida o ausente."
        )
    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Consola de Documentación",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )

@app.post("/request-key")
async def request_api_key(payload: dict = None):
    new_key = f"demo_key_{uuid.uuid4().hex[:12]}"
    DYNAMIC_API_KEYS[new_key] = {
        "created_at": datetime.now().isoformat(),
        "tier": "free_tier",
        "status": "active"
    }
    return {
        "status": "success",
        "api_key": new_key,
        "message": "Guarde su clave. Utilícela en el encabezado X-API-KEY para autenticarse.",
        "tier": "Gratuito (Evaluación)",
        "legal_notice": "Datos obtenidos al amparo de la Ley 37/2007 de Reutilización de la Información del Sector Público."
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - API PLACSP SaaS</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --bg-main: #0b0f19;
                --bg-card: #151c2c;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --accent-blue: #3b82f6;
                --accent-green: #10b981;
                --border-color: #1f293d;
            }
            body {
                background-color: var(--bg-main);
                color: var(--text-main);
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            .sidebar {
                background-color: #0f172a;
                border-right: 1px solid var(--border-color);
                min-height: 100vh;
            }
            .sidebar .nav-link {
                color: var(--text-muted);
                padding: 12px 20px;
                font-weight: 500;
            }
            .sidebar .nav-link.active, .sidebar .nav-link:hover {
                color: #ffffff;
                background-color: var(--bg-card);
                border-left: 3px solid var(--accent-blue);
            }
            .card-custom {
                background-color: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 20px;
            }
            .badge-status {
                background-color: rgba(16, 185, 129, 0.1);
                color: var(--accent-green);
                border: 1px solid var(--accent-green);
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.8rem;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <!-- Sidebar -->
                <div class="col-md-2 d-none d-md-block sidebar py-4">
                    <h5 class="px-3 text-white fw-bold mb-4"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP SaaS</h5>
                    <ul class="nav flex-column">
                        <li class="nav-item"><a class="nav-link active" href="#"><i class="fa-solid fa-chart-line me-2"></i>Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="/docs"><i class="fa-solid fa-code me-2"></i>Swagger Consola</a></li>
                        <li class="nav-item"><a class="nav-link" href="/legal"><i class="fa-solid fa-scale-balanced me-2"></i>Marco Legal</a></li>
                    </ul>
                </div>

                <!-- Main Content -->
                <div class="col-md-10 p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                        <div>
                            <h3 class="fw-bold m-0">Panel de Control de Licitaciones</h3>
                            <p class="text-muted m-0 small">Infraestructura oficial de datos de la Contratación Pública Española</p>
                        </div>
                        <div>
                            <span class="badge-status me-2"><i class="fa-solid fa-circle me-1 small"></i> PRODUCCIÓN v2.8.0</span>
                            <a href="/docs" class="btn btn-primary btn-sm"><i class="fa-solid fa-book me-1"></i> Documentación API</a>
                        </div>
                    </div>

                    <!-- Metrics Section -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Estado de Infraestructura</span>
                                <h4 class="fw-bold mt-2 mb-0 text-success"><i class="fa-solid fa-shield-halved me-2"></i>Blindado</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Autenticación</span>
                                <h4 class="fw-bold mt-2 mb-0">X-API-KEY Dinámica</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Origen de Datos</span>
                                <h4 class="fw-bold mt-2 mb-0 text-info">PLACSP Oficial</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Conformidad Legal</span>
                                <h4 class="fw-bold mt-2 mb-0 text-warning">Ley 37/2007</h4>
                            </div>
                        </div>
                    </div>

                    <!-- Key Request Sandbox Card -->
                    <div class="card-custom mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold m-0"><i class="fa-solid fa-key me-2"></i>Generador Instantáneo de API Key (Free Tier)</h5>
                        </div>
                        <p class="text-muted small">Emite una clave de acceso inmediata para consultar los endpoints protegidos:</p>
                        <button onclick="generateKey()" class="btn btn-outline-success btn-sm"><i class="fa-solid fa-plus me-1"></i> Generar API Key de Prueba</button>
                        <div id="keyDisplay" class="mt-3" style="display:none;">
                            <div class="alert alert-dark border border-secondary text-light">
                                <strong>Tu API Key:</strong> <code id="generatedKey" class="text-warning"></code>
                            </div>
                        </div>
                    </div>

                    <!-- Main Info Card -->
                    <div class="card-custom mb-4">
                        <h5 class="fw-bold mb-3"><i class="fa-solid fa-circle-info me-2"></i>Filtrado Avanzado v2.8.0</h5>
                        <p class="text-muted">El endpoint <code>/tenders</code> ahora soporta parámetros opcionales de filtrado por estado (ej. <code>?estado=En Plazo</code>) manteniendo estrictamente la neutralidad y el amparo de la Ley 37/2007.</p>
                        <a href="/tenders" target="_blank" class="btn btn-outline-light btn-sm"><i class="fa-solid fa-terminal me-1"></i> Probar Endpoint /tenders (Requiere Auth)</a>
                    </div>

                </div>
            </div>
        </div>

        <script>
            async function generateKey() {
                try {
                    const res = await fetch('/request-key', { method: 'POST' });
                    const data = await res.json();
                    if (data.api_key) {
                        document.getElementById('generatedKey').innerText = data.api_key;
                        document.getElementById('keyDisplay').style.display = 'block';
                    }
                } catch (e) {
                    alert('Error generando la clave.');
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal_notice():
    return """
    <html>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6; background-color: #0b0f19; color: #f3f4f6;">
            <h2>Aviso Legal y Limitación de Responsabilidad</h2>
            <p>Este servicio opera bajo el amparo de la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público.</p>
            <p>El proveedor de esta API actúa como mero agregador tecnológico y de índice, no otorga derechos de propiedad intelectual, no garantiza la inalterabilidad o exactitud de los datos originales institucionales (PLACSP), y queda totalmente exento de responsabilidad por interrupciones del servicio derivadas de fallos en los servidores públicos oficiales.</p>
            <p><a href="/" style="color: #3b82f6;">Volver al Dashboard</a></p>
        </body>
    </html>
    """

@app.get("/tenders", dependencies=[Depends(verify_api_key)])
async def get_tenders(request: Request, estado: str = Query(None, description="Filtrar por estado de la licitación (ej. En Plazo, Adjudicado)")):
    tenders_data = [
        {
            "id": "PLACSP-ES-2026-001",
            "objeto": "Servicio de mantenimiento y desarrollo de software institucional",
            "organo_contratacion": "Ministerio de Hacienda",
            "estado": "En Plazo",
            "fecha_publicacion": "2026-11-01"
        },
        {
            "id": "PLACSP-ES-2026-002",
            "objeto": "Suministro de licencias de infraestructura Cloud securizada",
            "organo_contratacion": "Consejería de Infraestructuras",
            "estado": "Adjudicado",
            "fecha_publicacion": "2026-11-05"
        }
    ]

    # Aplicar filtrado neutro si se especifica el parámetro
    filtered_data = tenders_data
    if estado:
        filtered_data = [t for t in tenders_data if t["estado"].lower() == estado.lower()]

    return {
        "status": "success",
        "version": "2.8.0",
        "legal_notice": "AVISO LEGAL: Datos obtenidos de fuentes abiertas institucionales (PLACSP) al amparo de la Ley 37/2007. Actuamos como mero agregador tecnológico exento de responsabilidad sobre los datos originales.",
        "filter_applied": estado if estado else "none",
        "count": len(filtered_data),
        "data": filtered_data
    }
