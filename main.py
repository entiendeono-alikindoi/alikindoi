import os
import uuid
import time
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="PLACSP Intelligence — API & B2G Data Platform",
    description="Infraestructura comercial de datos de contratación pública española bajo la Ley 37/2007.",
    version="6.1.0",
    docs_url=None,
    redoc_url=None
)

DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
API_KEY_METRICS = {}
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

TODAS_LAS_CCAA = [
    "Andalucía", "Aragón", "Asturias", "Baleares", "Canarias",
    "Cantabria", "Castilla-La Mancha", "Castilla y León", "Cataluña",
    "Ceuta", "Comunidad Valenciana", "Extremadura", "Galicia",
    "La Rioja", "Madrid", "Melilla", "Murcia", "Navarra", "País Vasco"
]

def get_commercial_dataset():
    """Genera licitaciones distribuidas por las 17 CC.AA. y 2 ciudades autónomas."""
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        plantillas = [
            ("Servicios de desarrollo de software y ciberseguridad", "Consejería de Transformación Digital"),
            ("Obras de rehabilitación energética en edificios públicos", "Consejería de Fomento e Infraestructuras"),
            ("Suministro de equipamiento médico y hospitalario", "Servicio Regional de Salud"),
            ("Consultoría jurídica y auditoría de fondos europeos", "Consejería de Hacienda y Administración Pública"),
            ("Mantenimiento integral de flotas y movilidad sostenible", "Ayuntamiento / Diputación Provincial")
        ]
        dataset = []
        # Generamos 57 expedientes (3 por cada una de las 19 regiones)
        for idx in range(57):
            ccaa = TODAS_LAS_CCAA[idx % len(TODAS_LAS_CCAA)]
            titulo_base, organo_base = plantillas[idx % len(plantillas)]
            estado = "En Plazo" if idx % 3 != 0 else "Adjudicado"
            dataset.append({
                "id": f"EXP-2026-{str(idx + 1).zfill(4)}",
                "titulo": f"{titulo_base} ({ccaa}) - Lote {(idx // 19) + 1}",
                "organo": f"{organo_base} — {ccaa}",
                "ccaa": ccaa,
                "estado": estado,
                "presupuesto": round(48000 + ((idx + 1) * 14250), 2),
                "adjudicatario": "Indra / Telefónica UTE" if estado == "Adjudicado" else None,
                "fecha": f"2026-11-{str((idx % 28) + 1).zfill(2)}"
            })
        CACHE_STORAGE["data"] = dataset
        CACHE_STORAGE["timestamp"] = now
    return CACHE_STORAGE["data"]

def verify_commercial_api_key(x_api_key: str = Header(...)):
    now = time.time()
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        raise HTTPException(status_code=401, detail="Acceso Denegado: API Key inválida o expirada. Genera una nueva en los planes.")
    
    tier = "enterprise" if x_api_key in MASTER_KEYS else DYNAMIC_API_KEYS.get(x_api_key, {}).get("tier", "free")
    limits = {"free": 20, "pro": 120, "enterprise": 500}
    limit_rate = limits.get(tier, 20)

    if x_api_key not in MASTER_KEYS:
        client_history = REQUEST_COUNTS.get(x_api_key, [])
        client_history = [t for t in client_history if now - t < 60]
        if len(client_history) >= limit_rate:
            raise HTTPException(status_code=429, detail=f"Límite de peticiones excedido ({limit_rate}/min) para el plan {tier.upper()}.")
        client_history.append(now)
        REQUEST_COUNTS[x_api_key] = client_history

    API_KEY_METRICS[x_api_key[:10] + "..."] = API_KEY_METRICS.get(x_api_key[:10] + "...", 0) + 1
    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="PLACSP API Docs", swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png")

@app.get("/health", tags=["Sistema"])
async def health():
    return {
        "status": "operational",
        "version": "6.1.0",
        "regions_covered": len(TODAS_LAS_CCAA),
        "uptime_seconds": int(time.time() - START_TIME),
        "compliance": "Ley 37/2007 RISP"
    }

@app.post("/commercial/subscribe", tags=["Comercial"])
async def commercial_subscribe(payload: dict):
    tier = payload.get("tier", "free").lower()
    if tier not in ["free", "pro", "enterprise"]:
        tier = "free"
    
    new_key = f"placsp_{tier}_{uuid.uuid4().hex[:12]}"
    DYNAMIC_API_KEYS[new_key] = {"tier": tier, "created_at": datetime.now().isoformat()}
    
    return {
        "status": "success",
        "message": f"Suscripción al plan {tier.upper()} activada.",
        "api_key": new_key,
        "tier": tier.upper(),
        "rate_limit_rpm": 20 if tier == "free" else (120 if tier == "pro" else 500)
    }

@app.get("/tenders", dependencies=[Depends(verify_commercial_api_key)], tags=["Licitaciones"])
async def get_tenders(
    q: str = Query(None, description="Búsqueda textual en título u órgano"),
    ccaa: str = Query(None, description="Filtrar por Comunidad Autónoma"),
    estado: str = Query(None, description="Filtrar por estado: En Plazo o Adjudicado"),
    formato: str = Query("json", description="Formato: json o csv"),
    limit: int = Query(20, ge=1, le=60)
):
    data = get_commercial_dataset()
    if q:
        q_low = q.lower()
        data = [t for t in data if q_low in t["titulo"].lower() or q_low in t["organo"].lower()]
    if ccaa:
        data = [t for t in data if ccaa.lower() == t["ccaa"].lower()]
    if estado:
        data = [t for t in data if estado.lower() == t["estado"].lower()]

    if formato.lower() == "csv":
        lines = ["expediente;titulo;organo;ccaa;estado;presupuesto_eur"]
        for t in data[:limit]:
            lines.append(f"{t['id']};\"{t['titulo']}\";\"{t['organo']}\";{t['ccaa']};{t['estado']};{t['presupuesto']}")
        return PlainTextResponse(content="\n".join(lines), media_type="text/csv")
    
    return {
        "total_matches": len(data),
        "data": data[:limit],
        "legal_notice": "Datos públicos reutilizados conforme a la Ley 37/2007."
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def commercial_dashboard():
    ccaa_options = "".join([f'<option value="{c}">{c}</option>' for c in TODAS_LAS_CCAA])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PLACSP Intelligence — Contratación Pública en España</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                --bg: #080c14;
                --surface: #111827;
                --border: #243044;
                --text: #f8fafc;
                --text-soft: #cbd5e1;
                --primary: #3b82f6;
                --accent-pro: #f59e0b;
            }}
            body {{ background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }}
            .navbar-saas {{ background: rgba(17, 24, 39, 0.92); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); }}
            .card-saas {{ background-color: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }}
            .pricing-card {{ background: #141d2f; border: 1px solid var(--border); border-radius: 12px; padding: 24px; transition: transform 0.2s; }}
            .pricing-card:hover {{ transform: translateY(-2px); }}
            .pricing-card.featured {{ border: 2px solid var(--accent-pro); box-shadow: 0 10px 30px rgba(245, 158, 11, 0.15); }}
            .text-soft {{ color: var(--text-soft) !important; }}
            .form-control, .form-select {{ background-color: #080c14; border-color: #334155; color: #f8fafc; font-size: 0.92rem; }}
            .form-control::placeholder {{ color: #94a3b8; }}
            .form-control:focus, .form-select:focus {{ background-color: #080c14; border-color: var(--primary); color: #ffffff; box-shadow: none; }}
            #cookie-banner {{ position: fixed; bottom: 0; left: 0; right: 0; background: #111827; border-top: 1px solid var(--border); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 9999; }}
            .table {{ color: var(--text); }}
            .table th {{ color: #94a3b8; border-bottom-color: var(--border); font-size: 0.78rem; text-transform: uppercase; }}
            .table td {{ border-bottom-color: var(--border); font-size: 0.88rem; vertical-align: middle; }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-saas sticky-top px-4 py-3">
            <div class="container-fluid">
                <span class="fw-bold fs-5 text-white"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP <span class="text-primary">Intelligence</span></span>
                <div class="d-flex align-items-center gap-2">
                    <span class="badge bg-success bg-opacity-25 text-success border border-success d-none d-sm-inline-block">19 Regiones Activas</span>
                    <a href="/docs" class="btn btn-outline-light btn-sm"><i class="fa-solid fa-terminal me-1"></i> API Docs</a>
                    <a href="/legal" class="btn btn-outline-secondary btn-sm text-soft"><i class="fa-solid fa-scale-balanced me-1"></i> Aviso Legal</a>
                </div>
            </div>
        </nav>

        <div class="container py-5" style="max-width: 1200px;">
            
            <div class="text-center mb-5">
                <span class="badge bg-primary bg-opacity-20 text-info border border-primary px-3 py-1 rounded-pill mb-3">COBERTURA NACIONAL · LEY 37/2007</span>
                <h1 class="fw-bold display-6 mb-3 text-white">Inteligencia de Contratación Pública en Tiempo Real</h1>
                <p class="text-soft mx-auto" style="max-width: 680px;">Consulta, filtra y exporta licitaciones públicas de las 17 Comunidades Autónomas, Ceuta y Melilla con latencia ultrabaja.</p>
            </div>

            <!-- Planes Comerciales -->
            <div class="row g-4 mb-5">
                <div class="col-md-4">
                    <div class="pricing-card h-100 d-flex flex-column justify-content-between">
                        <div>
                            <span class="badge bg-secondary mb-2">STARTER</span>
                            <h3 class="fw-bold mb-1 text-white">0 € <span class="fs-6 fw-normal text-soft">/ gratis</span></h3>
                            <p class="text-soft small mb-4">Para validación y pruebas iniciales de desarrollo.</p>
                            <ul class="list-unstyled small text-soft mb-4">
                                <li class="mb-2">✓ 20 peticiones / minuto</li>
                                <li class="mb-2">✓ Cobertura 19 regiones</li>
                                <li class="mb-2">✓ Exportación JSON y CSV</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('free')" class="btn btn-outline-light w-100 fw-semibold btn-sm py-2">Activar Plan Free</button>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="pricing-card featured h-100 d-flex flex-column justify-content-between">
                        <div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-warning text-dark fw-bold">PRO BUSINESS</span>
                                <span class="small text-warning fw-semibold">★ Recomendado</span>
                            </div>
                            <h3 class="fw-bold mb-1 text-white">49 € <span class="fs-6 fw-normal text-soft">/ mes</span></h3>
                            <p class="text-soft small mb-4">Para empresas, PYMEs y despachos de licitaciones.</p>
                            <ul class="list-unstyled small text-white mb-4">
                                <li class="mb-2">✓ <strong>120 peticiones / minuto</strong></li>
                                <li class="mb-2">✓ Filtros completos por CC.AA.</li>
                                <li class="mb-2">✓ Alertas automáticas Webhooks</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('pro')" class="btn btn-warning w-100 fw-bold text-dark btn-sm py-2">Suscribirme a Pro</button>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="pricing-card h-100 d-flex flex-column justify-content-between">
                        <div>
                            <span class="badge bg-info text-dark mb-2">ENTERPRISE</span>
                            <h3 class="fw-bold mb-1 text-white">199 € <span class="fs-6 fw-normal text-soft">/ mes</span></h3>
                            <p class="text-soft small mb-4">Para grandes consultorías e integraciones CRM.</p>
                            <ul class="list-unstyled small text-soft mb-4">
                                <li class="mb-2">✓ <strong>500 peticiones / minuto</strong></li>
                                <li class="mb-2">✓ SLA garantizado 99.9%</li>
                                <li class="mb-2">✓ Soporte técnico prioritario</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('enterprise')" class="btn btn-outline-info w-100 fw-semibold btn-sm py-2">Contratar Enterprise</button>
                    </div>
                </div>
            </div>

            <!-- Credencial Activa -->
            <div id="credentialBox" class="card-saas mb-4" style="border-color: #334155;">
                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                    <div>
                        <span class="small text-soft d-block">Credencial activa en el buscador (<strong id="activePlanBadge" class="text-info">DEMO</strong>):</span>
                        <code id="activeApiKey" class="text-warning fs-6 user-select-all">clave_demo_123</code>
                    </div>
                    <button onclick="copyActiveKey()" class="btn btn-outline-warning btn-sm"><i class="fa-regular fa-copy me-1"></i> Copiar API Key</button>
                </div>
            </div>

            <!-- Buscador Comercial en Vivo -->
            <div class="card-saas mb-5">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="fw-semibold m-0 text-white"><i class="fa-solid fa-magnifying-glass me-2 text-primary"></i>Buscador en Directo (Toda España)</h5>
                    <span id="matchCounter" class="badge bg-primary bg-opacity-25 text-info">Cargando...</span>
                </div>

                <div class="row g-2 mb-4">
                    <div class="col-md-4">
                        <input type="text" id="searchInput" class="form-control" placeholder="Buscar (ej: software, obras, salud)..." onkeyup="if(event.key==='Enter') runSearch()">
                    </div>
                    <div class="col-md-3">
                        <select id="searchCcaa" class="form-select" onchange="runSearch()">
                            <option value="">Todas las CC.AA. (19)</option>
                            {ccaa_options}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <select id="searchEstado" class="form-select" onchange="runSearch()">
                            <option value="">Cualquier estado</option>
                            <option value="En Plazo">En Plazo</option>
                            <option value="Adjudicado">Adjudicado</option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <button onclick="runSearch()" class="btn btn-primary w-100 fw-semibold">Buscar</button>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="table table-hover align-middle">
                        <thead>
                            <tr>
                                <th>Expediente</th>
                                <th>Objeto / Título</th>
                                <th>Órgano</th>
                                <th>CC.AA.</th>
                                <th>Presupuesto</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody id="resultsTable">
                            <tr><td colspan="6" class="text-center text-soft py-4">Cargando licitaciones nacionales...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Banner Cookies RGPD -->
        <div id="cookie-banner">
            <span class="small text-soft"><i class="fa-solid fa-cookie-bite text-warning me-2"></i>Utilizamos cookies técnicas esenciales amparadas por la <a href="/legal" class="text-info">Ley 37/2007</a>. Al continuar navegando, aceptas su uso.</span>
            <button onclick="acceptCookies()" class="btn btn-sm btn-light fw-bold px-3">Aceptar</button>
        </div>

        <script>
            let currentApiKey = "clave_demo_123";

            if (localStorage.getItem('cookies_accepted') === 'true') {{
                document.getElementById('cookie-banner').style.display = 'none';
            }}
            function acceptCookies() {{
                localStorage.setItem('cookies_accepted', 'true');
                document.getElementById('cookie-banner').style.display = 'none';
            }}

            function copyActiveKey() {{
                navigator.clipboard.writeText(currentApiKey);
            }}

            async function subscribePlan(tier) {{
                try {{
                    const res = await fetch('/commercial/subscribe', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{tier: tier}})
                    }});
                    const data = await res.json();
                    if (data.api_key) {{
                        currentApiKey = data.api_key;
                        document.getElementById('activeApiKey').innerText = data.api_key;
                        document.getElementById('activePlanBadge').innerText = data.tier;
                        document.getElementById('credentialBox').style.borderColor = '#f59e0b';
                        runSearch();
                    }}
                }} catch (e) {{
                    alert('No se pudo conectar con el servidor para emitir la clave.');
                }}
            }}

            async function runSearch() {{
                const q = document.getElementById('searchInput').value;
                const ccaa = document.getElementById('searchCcaa').value;
                const estado = document.getElementById('searchEstado').value;
                const tbody = document.getElementById('resultsTable');
                const counter = document.getElementById('matchCounter');

                const params = new URLSearchParams({{ limit: 20 }});
                if (q) params.append('q', q);
                if (ccaa) params.append('ccaa', ccaa);
                if (estado) params.append('estado', estado);

                try {{
                    const res = await fetch('/tenders?' + params.toString(), {{
                        headers: {{'X-API-KEY': currentApiKey}}
                    }});
                    const data = await res.json();

                    if (!res.ok) {{
                        counter.innerText = 'Error';
                        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-warning py-4">${{data.detail || 'Error de autenticación'}}</td></tr>`;
                        return;
                    }}

                    counter.innerText = `${{data.total_matches}} expedientes encontrados`;

                    if (data.data && data.data.length > 0) {{
                        tbody.innerHTML = data.data.map(t => `
                            <tr>
                                <td><code class="text-info">${{t.id}}</code></td>
                                <td class="fw-medium text-white">${{t.titulo}}</td>
                                <td class="text-soft small">${{t.organo}}</td>
                                <td><span class="badge bg-dark border border-secondary text-white">${{t.ccaa}}</span></td>
                                <td class="text-success fw-semibold">${{t.presupuesto.toLocaleString('es-ES', {{minimumFractionDigits: 2}})}} €</td>
                                <td><span class="badge ${{t.estado === 'En Plazo' ? 'bg-success bg-opacity-25 text-success' : 'bg-secondary bg-opacity-50 text-white'}}">${{t.estado}}</span></td>
                            </tr>
                        `).join('');
                    }} else {{
                        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-soft py-4">No se encontraron licitaciones con esos filtros.</td></tr>';
                    }}
                }} catch (e) {{
                    counter.innerText = 'Sin conexión';
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-4">Error de red al consultar la API.</td></tr>';
                }}
            }}

            // Cargar resultados automáticamente al entrar a la página
            window.addEventListener('DOMContentLoaded', runSearch);
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head><title>Aviso Legal — PLACSP Intelligence</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body style="background:#080c14; color:#f8fafc; padding:50px; font-family:'Inter',sans-serif;">
        <div class="container" style="max-width:750px;">
            <h2 class="text-warning fw-bold mb-4">Aviso Legal, Privacidad y Ley 37/2007</h2>
            <p class="text-light">Este servicio opera como plataforma tecnológica de agregación y consulta optimizada de datos públicos abiertos de contratación estatal, amparada bajo la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público (RISP).</p>
            <p class="text-light">El proveedor actúa como mero agregador tecnológico exento de responsabilidad sobre la inalterabilidad o exactitud de los datos originales institucionales de la PLACSP.</p>
            <a href="/" class="btn btn-primary btn-sm mt-4">Volver a la Plataforma</a>
        </div>
    </body>
    </html>
    """
