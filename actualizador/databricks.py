
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
from databricks import sql
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TABLA_ORDENES = "hive_metastore.db_gold.ordenes_unegocio_s4"
TABLA_FACTURACION = "hive_metastore.db_gold.facturacion_unegocio_s4"

COLUMNAS_ORDENES = [
    "ID_OPERACION",
    "FECHA_CONTABILIZACION",
    "CLASE_OPERACION",
    "DESCRIPCION_OPERACION",
    "SOLICITANTE",
    "NUMERO_DOC_SOLICITANTE",
    "NOMBRE_SOLICITANTE",
    "CELULAR_SOLICITANTE",
    "CORREO_SOLICITANTE",
    "UID_VEHICULO",
    "VIN",
    "PLACA",
    "MODELO",
    "MODELO_VERSION",
    "CATEGORIA_ORDEN",
    "SEDE_COSTO_FINAL",
    "STATUS_CANCELACION_ORDEN",
]

COLUMNAS_FACTURACION = [
    "FECHA_FACTURA_RP",
    "DOCUMENTO_SUNAT",
    "ORDEN_SERVICIO_ORIGINAL",
]


def primer_dia_mes_anterior(
    fecha: date | None = None,
) -> date:
    """Calcula el inicio de la ventana de actualización."""
    fecha = fecha or date.today()
    primer_dia_actual = fecha.replace(day=1)

    return (
        primer_dia_actual - timedelta(days=1)
    ).replace(day=1)


def _configuracion() -> tuple[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")

    hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")

    if not hostname or not http_path:
        raise ValueError(
            "Faltan las variables de conexión de Databricks."
        )

    return hostname, http_path


def _consultar(
    consulta: str,
    parametros: dict | None = None,
) -> pd.DataFrame:
    """Ejecuta una consulta de lectura y devuelve un DataFrame."""
    hostname, http_path = _configuracion()

    with sql.connect(
        server_hostname=hostname,
        http_path=http_path,
        auth_type="databricks-oauth",
    ) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                consulta,
                parameters=parametros or {},
            )

            columnas = [
                columna[0]
                for columna in cursor.description
            ]

            bloques = []

            while True:
                filas = cursor.fetchmany(10000)

                if not filas:
                    break

                bloques.extend(
                    tuple(fila) for fila in filas
                )

    return pd.DataFrame.from_records(
        bloques,
        columns=columnas,
    )


def obtener_ordenes(
    fecha_desde: date | None = None,
    sector: str = "13",
) -> pd.DataFrame:
    """
    Consulta órdenes de servicio y consumo de prepagos.

    Conserva todas las filas originales para permitir
    su posterior consolidación por ID_OPERACION.
    """
    fecha_desde = (
        fecha_desde or primer_dia_mes_anterior()
    )

    if sector not in ("13", "14"):
        raise ValueError("Sector no permitido: debe ser 13 o 14.")

    columnas = ", ".join(
        f"CAST({c} AS STRING) AS {c}"
        if c in (
            "ID_OPERACION",
            "NUMERO_DOC_SOLICITANTE",
            "SOLICITANTE",
        )
        else c
        for c in COLUMNAS_ORDENES
    )

    consulta = f"""
        SELECT {columnas}
        FROM {TABLA_ORDENES}
        WHERE ORG_VENTAS = 'PA22'
          AND SECTOR = :sector
          AND FECHA_CONTABILIZACION >= :fecha_desde
          AND (
                CAST(ID_OPERACION AS STRING) LIKE '6%'
             OR CAST(ID_OPERACION AS STRING) LIKE '7%'
          )
          AND COALESCE(
                UPPER(TRIM(STATUS_CANCELACION_ORDEN)),
                ''
          ) <> 'X'
    """

    return _consultar(
        consulta,
        {
            "sector": sector,
            "fecha_desde": fecha_desde.isoformat(),
        },
    )


def obtener_facturacion(
    ids_ordenes: Iterable[str],
    sector: str = "13",
) -> pd.DataFrame:
    """
    Consulta facturación únicamente de las órdenes indicadas.

    No elimina documentos repetidos: la selección del
    comprobante corresponde a la lógica de negocio.
    """
    if sector not in ("13", "14"):
        raise ValueError("Sector no permitido: debe ser 13 o 14.")

    ids = sorted({
        str(identificador).strip()
        for identificador in ids_ordenes
        if pd.notna(identificador)
        and str(identificador).strip()
    })

    if not ids:
        return pd.DataFrame(columns=COLUMNAS_FACTURACION)

    resultados = []

    # Lotes pequeños para evitar consultas SQL excesivamente
    # largas y mantener parámetros independientes.
    tamaño_lote = 200

    for inicio in range(0, len(ids), tamaño_lote):
        lote = ids[inicio:inicio + tamaño_lote]

        parametros = {
            f"orden_{i}": identificador
            for i, identificador in enumerate(lote)
        }
        parametros["sector"] = sector

        marcadores = ", ".join(
            f":orden_{i}" for i in range(len(lote))
        )

        consulta = f"""
            SELECT
                FECHA_FACTURA_RP,
                DOCUMENTO_SUNAT,
                CAST(ORDEN_SERVICIO_ORIGINAL AS STRING)
                    AS ORDEN_SERVICIO_ORIGINAL
            FROM {TABLA_FACTURACION}
            WHERE ORG_VENTAS_RP = 'PA22'
              AND SECTOR_MARA = :sector
              AND CAST(
                    ORDEN_SERVICIO_ORIGINAL AS STRING
                  ) IN ({marcadores})
        """

        resultados.append(
            _consultar(consulta, parametros)
        )

    return pd.concat(
        resultados,
        ignore_index=True,
    )
