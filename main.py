from fastapi import FastAPI, Query, Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional
import os
import time
import logging
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS Y TRAZABILIDAD (AUDIT TRAIL)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] AUDIT: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("TenderAPI")

app = FastAPI(
    title="API de Tenders Públicos - España (Production Grade)",
    description="API comercial segura de licitaciones públicas con rate limiting, trazabilidad y exención de responsabilidad.",
    version="2.3.0"
)

OFFICIAL_FEED_URL = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"

# Aviso legal inamovible (Ley 37/2007)
LEGAL_NOTICE = (
    "AVISO LEGAL Y LIMITACIÓN DE RESPONSABILIDAD: Datos obtenidos de fuentes abiertas "
    "institucionales (PLACSP) al amparo de la Ley 37/2007. El proveedor de esta API "
    "actúa como mero agregador tecnológico y de índice, no otorga derechos de propiedad intelectual, "
    "no garantiza la inalterabilidad o exactitud de los datos originales, y queda totalmente exento de "
    "responsabilidad por interrupciones del servicio derivadas de fallos en los servidores públicos oficiales."
)

# ---------------------------------------------------------------------------
# GESTIÓN DE CLIENTES POR VARIABLES DE ENTORNO
# ---------------------------------------------------------------------------
def cargar_clientes_autorizados():
    clientes_por_defecto = {
        "demo_key_123": "Cliente Demo",
        "cliente_premium_001": "Empresa Suscrita A"
    }
    env_keys = os.getenv("API_KEYS_CONFIG")
    if not env_keys:
        return clientes_por_defecto
    
    configurados = {}
    try:
        for item in env_keys.split(","):
            if ":" in item:
                key, name = item.split(":", 1)
                configurados[key.strip()] = name.strip()
    except Exception:
        return clientes_por_defecto
    return configurados if configurados else clientes_por_defecto

VALID_API_KEYS = cargar_clientes_autorizados()
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

# ---------------------------------------------------------------------------
# RATE LIMITING DEFENSIVO (Estricto: 20 peticiones por minuto)
# ---------------------------------------------------------------------------
REQUEST_WINDOW = 60  # segundos
MAX_REQUESTS_PER_WINDOW = 20
request_counts = defaultdict(list)

def verificar_rate_limit(api_key: str, cliente_nombre: str, endpoint: str):
    ahora = time.time()
    peticiones_cliente = request_counts[api_key]
    
    peticions_validas = [t for t in peticiones_cliente if ahora - t < REQUEST_WINDOW]
    
    if len(peticions_validas) >= MAX_REQUESTS_PER_WINDOW:
        logger.warning(f"BLOQUEO RATE LIMIT | Cliente: '{cliente_nombre}' | Endpoint: {endpoint}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Límite de peticiones excedido (Rate Limit). Máximo 20 peticiones por minuto."
        )
    
    peticions_validas.append(ahora)
    request_counts[api_key] = peticions_validas

def verify_api_key(request: Request, api_key: str = Depends(api_key_header)):
    client_ip = request.client.host if request.client else "Desconocida"
    path = request.url.path
    
    if not api_key or api_key not in VALID_API_KEYS:
        logger.warning(f"ACCESO RECHAZADO | IP: {client_ip} | Clave invalida/ausente | Ruta: {path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de API inválida o no proporcionada. Incluya el encabezado 'X-API-KEY'."
        )
    
    cliente_nombre = VALID_API_KEYS.get(api_key, "Desconocido")
    verificar_rate_limit(api_key, cliente_nombre, path)
    
    logger.info(f"ACCESO AUTORIZADO | Cliente: '{cliente_nombre}' | Ruta: {path} | IP: {client_ip}")
    return api_key

# ---------------------------------------------------------------------------
# CONSUMO RESILIENTE DE DATOS (PLACSP)
# ---------------------------------------------------------------------------
def fetch_real_tenders():
    tenders = []
    try:
        req = urllib.request.Request(
            OFFICIAL_FEED_URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', ns)
        for idx, entry in enumerate(entries[:50], start=1):
            title = entry.findtext('atom:title', default='Sin título', namespaces=ns)
            link_elem = entry.find('atom:link', ns)
            link = link_elem.attrib.get('href', 'https://contrataciondelestado.es') if link_elem is not None else 'https://contrataciondelestado.es'
            summary = entry.findtext('atom:summary', default='', namespaces=ns)
            updated = entry.findtext('atom:updated', default='', namespaces=ns)
            
            tenders.append({
                "id": idx,
                "titulo": title.strip(),
                "organo": "Organismo Público (PLACSP)",
                "resumen": summary.strip() if summary else "Ver enlace oficial para detalles.",
                "fecha_actualizacion": updated,
                "enlace_oficial": link
            })
    except Exception as e:
        logger.error(f"FALLO FUENTE PLACSP | Error técnico: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La fuente oficial de la PLACSP no se encuentra disponible temporalmente. Exención de responsabilidad aplicada."
        )
    return tenders

# ---------------------------------------------------------------------------
# PORTAL WEB INTERACTIVO (PÁGINA PRINCIPAL)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, tags=["General"])
def portal_bienvenida():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portal de Desarrollo | API PLACSP Tenders</title>
        <style>
            :root {
                --bg: #0f172a;
                --card: #1e293b;
                --accent: #3b82f6;
                --text: #f8fafc;
                --muted: #94a3b8;
                --border: #334155;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 40px 20px;
                display: flex;
                justify-content: center;
            }
            .container {
                max-width: 900px;
                width: 100%;
            }
            .header {
                border-bottom: 1px solid var(--border);
                padding-bottom: 24px;
                margin-bottom: 32px;
            }
            .badge {
                background-color: #10b981;
                color: #042f2e;
                font-weight: bold;
                font-size: 12px;
                padding: 4px 8px;
                border-radius: 4px;
                text-transform: uppercase;
            }
            h1 { font-size: 32px; margin: 12px 0 8px 0; }
            p.subtitle { color: var(--muted); font-size: 16px; margin: 0; }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-bottom: 32px;
            }
            .card {
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 24px;
            }
            .card h3 { margin-top: 0; font-size: 18px; color: var(--accent); }
            pre {
                background: #090d16;
                padding: 16px;
                border-radius: 6px;
                overflow-x: auto;
                font-size: 13px;
                color: #38bdf8;
                border: 1px solid var(--border);
            }
            .btn {
                display: inline-block;
                background: var(--accent);
                color: white;
                text-decoration: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                margin-right: 12px;
            }
            .btn-secondary {
                background: transparent;
                border: 1px solid var(--border);
                color: var(--text);
            }
            .footer-legal {
                font-size: 12px;
                color: var(--muted);
                background: #1e293b50;
                padding: 16px;
                border-radius: 6px;
                border: 1px solid var(--border);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="badge">Producción v2.3.0</span>
                <h1>API de Contratación Pública (PLACSP)</h1>
                <p class="subtitle">Infraestructura de datos de licitaciones para desarrolladores y empresas.</p>
            </div>

            <div style="margin-bottom: 32px;">
                <a href="/docs" class="btn">Explorar Consola Swagger (/docs)</a>
                <a href="/legal" class="btn btn-secondary">Términos Legales (/legal)</a>
            </div>

            <div class="grid">
                <div class="card">
                    <h3>⚡ Rendimiento y Seguridad</h3>
                    <p style="font-size: 14px; color: var(--muted);">
                        Autenticación mediante cabecera <code>X-API-KEY</code>. Control de peticiones activo de 
                        <strong>20 req/min</strong> para garantizar la estabilidad del servicio.
                    </p>
                </div>
                <div class="card">
                    <h3>⚖️ Marco Legal Cumplido</h3>
                    <p style="font-size: 14px; color: var(--muted);">
                        Servicio adaptado a la <strong>Ley 37/2007</strong> de reutilización de información del sector público. 
                        Trazabilidad completa y auditoría de uso.
                    </p>
                </div>
            </div>

            <div class="card" style="margin-bottom: 32px;">
                <h3>🚀 Ejemplo de Integración Rápida (Python)</h3>
                <pre>import requests

headers = {"X-API-KEY": "tu_clave_de_acceso"}
response = requests.get("https://mi-api-tender.onrender.com/tenders", headers=headers)

if response.status_code == 200:
    licitaciones = response.json()
    print(f"Total obtenidas: {licitaciones['total']}")
else:
    print(f"Error: {response.status_code}")</pre>
            </div>

            <div class="footer-legal">
                <strong>Aviso de exención de responsabilidad:</strong> Los datos se obtienen en tiempo real de fuentes públicas institucionales. El servicio actúa únicamente como agregador tecnológico y de índice estructurado.
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/legal", tags=["Legal y Términos"])
def obtener_aviso_legal():
    return {
        "condiciones_servicio": "El uso de esta API implica la aceptación de los términos de reutilización de datos abiertos.",
        "fuente_oficial": "https://contrataciondelestado.es",
        "aviso_legal_completo": LEGAL_NOTICE,
        "exencion_responsabilidad": "El prestador del servicio no asume daños por la indisponibilidad temporal o fallos en el feed de la PLACSP."
    }

@app.get("/tenders", tags=["Licitaciones"])
def listar_tenders(key: str = Depends(verify_api_key)):
    data = fetch_real_tenders()
    return {
        "cliente_autorizado": VALID_API_KEYS.get(key),
        "total": len(data),
        "aviso_legal": LEGAL_NOTICE,
        "resultados": data
    }

@app.get("/tenders/buscar", tags=["Licitaciones"])
def buscar_tenders(
    q: str = Query(..., description="Texto a buscar en el título o descripción"),
    limite: Optional[int] = Query(10, description="Número máximo de resultados"),
    key: str = Depends(verify_api_key)
):
    todos = fetch_real_tenders()
    filtrados = [
        t for t in todos 
        if q.lower() in t["titulo"].lower() or q.lower() in t["resumen"].lower()
    ]
    return {
        "cliente_autorizado": VALID_API_KEYS.get(key),
        "termino_busqueda": q,
        "total_encontrados": len(filtrados),
        "aviso_legal": LEGAL_NOTICE,
        "resultados": filtrados[:limite]
    }
