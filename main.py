from fastapi import FastAPI, HTTPException
from typing import Optional

app = FastAPI(
    title="API de Tenders Públicos - España",
    description="API profesional para consulta y filtrado de licitaciones públicas con total cumplimiento normativo.",
    version="1.0.0"
)

# Base de datos simulada y estructurada de ejemplo (en siguientes pasos la conectaremos a los canales oficiales en vivo)
LICITACIONES_EJEMPLO = [
    {
        "id": 1,
        "titulo": "Servicios de desarrollo de software y ciberseguridad",
        "organo": "Ministerio de Asuntos Económicos",
        "presupuesto": "150.000 €",
        "fecha_limite": "2026-06-30",
        "enlace_oficial": "https://contrataciondelestado.es"
    },
    {
        "id": 2,
        "titulo": "Suministro de equipos informáticos para oficinas públicas",
        "organo": "Comunidad Autónoma",
        "presupuesto": "45.000 €",
        "fecha_limite": "2026-05-15",
        "enlace_oficial": "https://contrataciondelestado.es"
    },
    {
        "id": 3,
        "titulo": "Mantenimiento de infraestructuras de red y telecomunicaciones",
        "organo": "Ayuntamiento Local",
        "presupuesto": "80.000 €",
        "fecha_limite": "2026-07-01",
        "enlace_oficial": "https://contrataciondelestado.es"
    }
]

@app.get("/")
def inicio():
    return {
        "estado": "Activo",
        "mensaje": "API de Tenders de España operando bajo normativas de transparencia y reutilización de datos públicos.",
        "endpoints_disponibles": ["/tenders", "/tenders/buscar?palabra=..."]
    }

@app.get("/tenders")
def listar_tenders():
    """Devuelve el listado completo de licitaciones públicas disponibles con su respectiva fuente oficial."""
    return {
        "total": len(LICITACIONES_EJEMPLO),
        "aviso_legal": "Datos obtenidos de fuentes abiertas institucionales conforme al derecho de información.",
        "resultados": LICITACIONES_EJEMPLO
    }

@app.get("/tenders/buscar")
def buscar_tenders(palabra: str):
    """Permite filtrar licitaciones de forma inteligente según palabras clave introducidas por el usuario."""
    encontrados = [
        t for t in LICITACIONES_EJEMPLO 
        if palabra.lower() in t["titulo"].lower() or palabra.lower() in t["organo"].lower()
    ]
    
    if not encontrados:
        raise HTTPException(status_code=404, detail=f"No se han encontrado licitaciones para la búsqueda: '{palabra}'")
        
    return {
        "busqueda": palabra,
        "encontrados": len(encontrados),
        "resultados": encontrados
    }
