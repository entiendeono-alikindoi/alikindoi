import os
import requests
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="API de Contratación Pública (PLACSP)",
    description="Infraestructura de datos de licitaciones públicas para desarrolladores y empresas.",
    version="2.4.2",
    docs_url=None,
    redoc_url=None
)

# Claves de API válidas
VALID_API_KEYS = os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(",")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in VALID_API_KEYS:
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
            .table-custom {
                color: var(--text-main);
            }
            .table-custom th {
                background-color: #0f172a;
                border-color: var(--border-color);
                color: var(--text-muted);
            }
            .table-custom td {
                border-color: var(--border-color);
                vertical-align: middle;
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
                            <p class="text-muted m-0 small">Infraestructura de datos en tiempo real de la Contratación Pública Española</p>
                        </div>
                        <div>
                            <span class="badge-status me-2"><i class="fa-solid fa-circle me-1 small"></i> PRODUCCIÓN v2.4.2</span>
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
                                <h4 class="fw-bold mt-2 mb-0">X-API-KEY</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Control de Acceso</span>
                                <h4 class="fw-bold mt-2 mb-0 text-info">Protegido</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Conformidad Legal</span>
                                <h4 class="fw-bold mt-2 mb-0 text-warning">Ley 37/2007</h4>
                            </div>
                        </div>
                    </div>

                    <!-- Main Table Preview -->
                    <div class="card-custom mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold m-0"><i class="fa-solid fa-list me-2"></i>Vista Previa de Datos de Licitaciones (PLACSP)</h5>
                            <span class="text-muted small">Protegido por /tenders</span>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-custom align-middle">
                                <thead>
                                    <tr>
                                        <th>ID / Referencia</th>
                                        <th>Objeto del Contrato</th>
                                        <th>Órgano de Contratación</th>
                                        <th>Estado</th>
                                        <th>Acceso API</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td><code>PLACSP-2026-001</code></td>
                                        <td>Servicio de mantenimiento y desarrollo de software...</td>
                                        <td>Ministerio de Hacienda</td>
                                        <td><span class="badge bg-success">En Plazo</span></td>
                                        <td><span class="text-muted">Protegido (401)</span></td>
                                    </tr>
                                    <tr>
                                        <td><code>PLACSP-2026-002</code></td>
                                        <td>Suministro de licencias de infraestructura Cloud...</td>
                                        <td>Consejería de Infraestructuras</td>
                                        <td><span class="badge bg-primary">Adjudicado</span></td>
                                        <td><span class="text-muted">Protegido (401)</span></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal_notice():
    return """
    <html>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6;">
            <h2>Aviso Legal y Reutilización de Datos</h2>
            <p>Este servicio cumple con la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público.</p>
            <p><a href="/">Volver al Dashboard</a></p>
        </body>
    </html>
    """

@app.get("/tenders", dependencies=[Depends(verify_api_key)])
async def get_tenders(request: Request):
    return {
        "status": "success",
        "message": "Datos de licitaciones recuperados correctamente",
        "legal_notice": "Datos obtenidos bajo cumplimiento de la Ley 37/2007 de reutilización de datos públicos.",
        "data": [
            {"id": "PLACSP-2026-001", "objeto": "Servicio de desarrollo", "organo": "Ministerio de Hacienda"}
        ]
    }
