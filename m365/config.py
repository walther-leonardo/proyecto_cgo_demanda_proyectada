from pathlib import Path
from dotenv import load_dotenv
import os


# ==========================================================
# RUTA PRINCIPAL DEL PROYECTO
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================
# VARIABLES DE ENTORNO
# ==========================================================

load_dotenv(PROJECT_ROOT / ".env")

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")


# ==========================================================
# CACHE DE AUTENTICACIÓN
# ==========================================================

TOKEN_CACHE_FILE = PROJECT_ROOT / "token_cache.bin"


# ==========================================================
# SHAREPOINT — CGO DEMANDA PROYECTADA
# ==========================================================

SITE_NAME = "INTELIGENCIACOMERCIAL"

DRIVE_NAME = "Documentos"

PROJECT_FOLDER = "33.- proyecto CGO demanda proyectada"

INPUT_FOLDER = f"{PROJECT_FOLDER}/registros negocio"

OUTPUT_FOLDER = f"{PROJECT_FOLDER}/bases proyectadas"


# ==========================================================
# ARCHIVOS DE NEGOCIO
# ==========================================================

RETAIL_FILE = "retail.xlsx"
TALLER_FILE = "taller.xlsx"
CLIENTES_FILE = "clientes.xlsx"


# ==========================================================
# VALIDACIONES
# ==========================================================

if not TENANT_ID:
    raise ValueError(
        "TENANT_ID was not found in the .env file."
    )

if not CLIENT_ID:
    raise ValueError(
        "CLIENT_ID was not found in the .env file."
    )