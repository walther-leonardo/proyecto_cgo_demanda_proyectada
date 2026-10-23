
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from databricks import sql
from dotenv import load_dotenv

# Permite ejecutar este archivo directamente desde tests/.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from m365.config import (
    DRIVE_NAME,
    INPUT_FOLDER,
    SITE_NAME,
    TALLER_FILE,
)
from m365.sharepoint import SharePoint
from m365.excel import read_excel


ARCHIVO_SERVICIOS = "nivel de servicio.xlsx"
ARCHIVO_MODELOS = "modelos vehiculos.xlsx"

TABLA_ORDENES = "hive_metastore.db_gold.ordenes_unegocio_s4"

COLUMNAS_SQL = [
    "ID_OPERACION",
    "FECHA_CONTABILIZACION",
    "CLASE_OPERACION",
    "DESCRIPCION_OPERACION",
    "NUMERO_DOC_SOLICITANTE",
    "UID_VEHICULO",
    "VIN",
    "PLACA",
    "MODELO",
    "MODELO_VERSION",
    "CATEGORIA_ORDEN",
    "SEDE_COSTO_FINAL",
    "STATUS_CANCELACION_ORDEN",
]


def normalizar(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip().replace("", pd.NA)


def fecha_inicio_consulta() -> str:
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    if hoy.month == 1:
        return f"{hoy.year - 1}-12-01"
    return f"{hoy.year}-{hoy.month - 1:02d}-01"


def conectar_sharepoint() -> tuple[SharePoint, str]:
    cliente = SharePoint()

    site = cliente.get_site(SITE_NAME)
    if site is None:
        raise RuntimeError("No se encontró el sitio de SharePoint.")

    drive = cliente.get_drive(site["id"], DRIVE_NAME)
    if drive is None:
        raise RuntimeError("No se encontró la biblioteca de SharePoint.")

    return cliente, drive["id"]


def cargar_excel(
    cliente: SharePoint,
    drive_id: str,
    nombre: str,
    dtype: dict | None = None,
) -> pd.DataFrame:
    archivo = cliente.download_file_by_path(
        drive_id=drive_id,
        file_path=f"{INPUT_FOLDER}/{nombre}",
    )
    return read_excel(archivo, dtype=dtype)


def consultar_ordenes(desde: str) -> pd.DataFrame:
    load_dotenv(ROOT / ".env")

    hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")

    if not hostname or not http_path:
        raise ValueError("Falta la configuración de Databricks.")

    columnas = ", ".join(COLUMNAS_SQL)

    consulta = f"""
        SELECT {columnas}
        FROM {TABLA_ORDENES}
        WHERE ORG_VENTAS = 'PA22'
          AND SECTOR = '13'
          AND FECHA_CONTABILIZACION >= '{desde}'
          AND (
              CAST(ID_OPERACION AS STRING) LIKE '6%'
              OR CAST(ID_OPERACION AS STRING) LIKE '7%'
          )
          AND (
              STATUS_CANCELACION_ORDEN IS NULL
              OR TRIM(STATUS_CANCELACION_ORDEN) <> 'X'
          )
    """

    with sql.connect(
        server_hostname=hostname,
        http_path=http_path,
        auth_type="databricks-oauth",
    ) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(consulta)
            filas = cursor.fetchall()
            nombres = [col[0] for col in cursor.description]

    return pd.DataFrame.from_records(filas, columns=nombres)


def diagnosticar(
    ordenes: pd.DataFrame,
    taller: pd.DataFrame,
    servicios: pd.DataFrame,
    modelos: pd.DataFrame,
) -> None:
    # Normalización de identificadores y claves.
    for columna in COLUMNAS_SQL:
        if columna in ordenes and columna != "FECHA_CONTABILIZACION":
            ordenes[columna] = normalizar(ordenes[columna])

    taller["Id doc"] = normalizar(taller["Id doc"])
    servicios["Nivel_4"] = normalizar(servicios["Nivel_4"])
    servicios["servicio1"] = normalizar(servicios["servicio1"])
    modelos["Material"] = normalizar(modelos["Material"])

    total_filas = len(ordenes)

    # No debemos inventar un identificador para órdenes nulas.
    sin_id = ordenes["ID_OPERACION"].isna().sum()
    ordenes = ordenes.dropna(subset=["ID_OPERACION"]).copy()

    grupos = ordenes.groupby("ID_OPERACION", sort=False)
    cantidad_ordenes = grupos.ngroups

    ordenes_duplicadas = int(
        (grupos.size() > 1).sum()
    )

    # Comparación incremental contra el archivo actual.
    ids_existentes = set(taller["Id doc"].dropna())
    ids_databricks = set(ordenes["ID_OPERACION"])

    ids_nuevos = ids_databricks - ids_existentes

    nuevas = ordenes[
        ordenes["ID_OPERACION"].isin(ids_nuevos)
    ].copy()

    # Categorías presentes en los diccionarios.
    catalogo_servicios = servicios.dropna(
        subset=["Nivel_4"]
    ).copy()

    mapa_servicios = catalogo_servicios.drop_duplicates(
        subset=["Nivel_4"]
    ).set_index("Nivel_4")["servicio1"]

    nuevas["servicio_identificado"] = (
        nuevas["CATEGORIA_ORDEN"].map(mapa_servicios)
    )

    nuevas["es_preventivo"] = (
        nuevas["servicio_identificado"]
        .str.lower()
        .eq("preventivo")
        .fillna(False)
    )

    # Comprobamos cobertura por orden, no solamente por fila.
    grupos_nuevos = nuevas.groupby("ID_OPERACION")

    ordenes_preventivas = int(
        grupos_nuevos["es_preventivo"].any().sum()
    )

    sin_categoria = nuevas[
        nuevas["CATEGORIA_ORDEN"].isna()
    ]["ID_OPERACION"].nunique()

    categorias_desconocidas = nuevas[
        nuevas["CATEGORIA_ORDEN"].notna()
        & nuevas["servicio_identificado"].isna()
    ]["ID_OPERACION"].nunique()

    categorias_distintas = grupos_nuevos[
        "CATEGORIA_ORDEN"
    ].nunique(dropna=True)

    ordenes_multicategoria = int(
        (categorias_distintas > 1).sum()
    )

    # Un modelo se busca primero por MODELO y luego
    # por MODELO_VERSION, respetando la regla manual.
    materiales = set(modelos["Material"].dropna())

    encontrado_modelo = nuevas["MODELO"].isin(materiales)
    encontrado_version = nuevas["MODELO_VERSION"].isin(
        materiales
    )

    sin_modelo = nuevas[
        ~(encontrado_modelo | encontrado_version)
    ]["ID_OPERACION"].nunique()

    # Auditoría de información indispensable.
    faltantes = {}
    for columna in (
        "VIN",
        "PLACA",
        "NUMERO_DOC_SOLICITANTE",
    ):
        faltantes[columna] = nuevas.loc[
            nuevas[columna].isna(),
            "ID_OPERACION",
        ].nunique()

    print("\n" + "=" * 58)
    print("🐔 DIAGNÓSTICO CGO — DATABRICKS / SHAREPOINT")
    print("=" * 58)

    indicadores = {
        "Filas consultadas": total_filas,
        "Filas sin ID_OPERACION": sin_id,
        "Órdenes distintas en Databricks": cantidad_ordenes,
        "Órdenes con varias filas": ordenes_duplicadas,
        "Órdenes ya existentes en taller": len(
            ids_databricks & ids_existentes
        ),
        "Órdenes nuevas": len(ids_nuevos),
        "Órdenes nuevas preventivas identificadas": (
            ordenes_preventivas
        ),
        "Órdenes nuevas con categoría vacía": sin_categoria,
        "Órdenes nuevas con categoría no reconocida": (
            categorias_desconocidas
        ),
        "Órdenes nuevas con múltiples categorías": (
            ordenes_multicategoria
        ),
        "Órdenes nuevas sin modelo reconocido": sin_modelo,
        "Órdenes nuevas sin VIN": faltantes["VIN"],
        "Órdenes nuevas sin placa": faltantes["PLACA"],
        "Órdenes nuevas sin documento": (
            faltantes["NUMERO_DOC_SOLICITANTE"]
        ),
    }

    for nombre, valor in indicadores.items():
        print(f"{nombre}: {valor:,}")

    print("\n✅ Diagnóstico finalizado. No se modificaron archivos.")


def main() -> None:
    desde = fecha_inicio_consulta()
    print(f"🐔 Consultando órdenes desde {desde}")

    print("Conectando a SharePoint...")
    cliente, drive_id = conectar_sharepoint()

    print("Leyendo taller.xlsx...")
    taller = cargar_excel(
        cliente, drive_id, TALLER_FILE,
        dtype={"Id doc": "string"},
    )

    print("Leyendo diccionario de servicios...")
    servicios = cargar_excel(
        cliente, drive_id, ARCHIVO_SERVICIOS,
        dtype={"Nivel_4": "string"},
    )

    print("Leyendo diccionario de modelos...")
    modelos = cargar_excel(
        cliente, drive_id, ARCHIVO_MODELOS,
        dtype={"Material": "string"},
    )

    print("Consultando Databricks...")
    ordenes = consultar_ordenes(desde)

    diagnosticar(ordenes, taller, servicios, modelos)


if __name__ == "__main__":
    main()
