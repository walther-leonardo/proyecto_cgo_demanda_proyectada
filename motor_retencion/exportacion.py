from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

from motor_retencion.definiciones import (
    obtener_definiciones_retencion,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

PREFIJO_REPORTE = "RETENCION_CGO"


# ============================================================
# NOMBRE DE ARCHIVO
# ============================================================

def generar_nombre_reporte_retencion(
    fecha_generacion: datetime | None = None,
) -> str:
    """
    Genera el nombre del reporte Excel del Motor 05.
    """

    if fecha_generacion is None:
        fecha_generacion = datetime.now()

    marca_tiempo = (
        fecha_generacion.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
    )

    return (
        f"{PREFIJO_REPORTE}_"
        f"{marca_tiempo}.xlsx"
    )


# ============================================================
# HELPERS EXCEL
# ============================================================

def _preparar_dataframe_excel(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepara un DataFrame para exportación sin modificar
    el objeto original.

    Los Period se convierten a texto para evitar problemas
    de compatibilidad con Excel.
    """

    resultado = df.copy()

    for columna in resultado.columns:

        if isinstance(
            resultado[columna].dtype,
            pd.PeriodDtype,
        ):

            resultado[
                columna
            ] = (
                resultado[
                    columna
                ]
                .astype("string")
            )

    return resultado


def _escribir_hoja(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    nombre_hoja: str,
) -> None:
    """
    Escribe una hoja y aplica ajustes visuales mínimos.

    No intenta convertir el Excel en un dashboard.
    """

    if df is None:
        return

    df_excel = (
        _preparar_dataframe_excel(
            df
        )
    )

    df_excel.to_excel(
        writer,
        sheet_name=nombre_hoja,
        index=False,
    )

    worksheet = (
        writer.sheets[
            nombre_hoja
        ]
    )

    worksheet.freeze_panes = "A2"

    worksheet.auto_filter.ref = (
        worksheet.dimensions
    )

    for columna in worksheet.columns:

        letra = (
            columna[0]
            .column_letter
        )

        longitud = max(
            len(
                str(
                    celda.value
                    if celda.value is not None
                    else ""
                )
            )
            for celda in columna
        )

        worksheet.column_dimensions[
            letra
        ].width = min(
            max(
                longitud + 2,
                10,
            ),
            35,
        )


# ============================================================
# RESUMEN EJECUTIVO
# ============================================================

def construir_resumen_exportacion(
    resultado: dict,
    fecha_generacion: datetime,
) -> pd.DataFrame:
    """
    Construye una hoja breve de control del reporte.
    """

    fecha_max_datos = (
        resultado[
            "fecha_max_datos"
        ]
    )

    secuencia = (
        resultado[
            "secuencia_preventiva"
        ]
    )

    ciclos = (
        resultado[
            "ciclos_retencion"
        ]
    )

    oportunidades = (
        resultado[
            "oportunidades"
        ]
    )

    resumen_cliente = (
        resultado[
            "resumen_cliente"
        ]
    )

    filas = [
        {
            "indicador":
                "Fecha generación",

            "valor":
                fecha_generacion,
        },
        {
            "indicador":
                "Fecha máxima de datos",

            "valor":
                fecha_max_datos,
        },
        {
            "indicador":
                "VIN con historial preventivo",

            "valor":
                secuencia[
                    "vin"
                ].nunique(),
        },
        {
            "indicador":
                "Visitas preventivas analíticas",

            "valor":
                len(
                    secuencia
                ),
        },
        {
            "indicador":
                "Oportunidades de ciclo",

            "valor":
                len(
                    ciclos
                ),
        },
        {
            "indicador":
                "Oportunidades de cohortes",

            "valor":
                len(
                    oportunidades
                ),
        },
        {
            "indicador":
                "Clientes analizados",

            "valor":
                resumen_cliente[
                    "nro_documento"
                ].nunique(),
        },
        {
            "indicador":
                "Nota clientes",

            "valor":
                (
                    "Información dummy utilizada para "
                    "validación metodológica."
                ),
        },
    ]

    return pd.DataFrame(
        filas
    )


# ============================================================
# EXPORTACIÓN PRINCIPAL
# ============================================================

def generar_excel_retencion(
    resultado: dict,
    fecha_generacion: datetime | None = None,
) -> BytesIO:
    """
    Genera el Excel del Motor 05 completamente en memoria.

    El Excel se mantiene deliberadamente ligero porque la
    principal capa de consumo será Streamlit y las gerencias
    probablemente generarán feedback sobre las salidas.

    El reporte conserva las bases analíticas más útiles para:
    - auditoría;
    - análisis ad hoc;
    - validación;
    - respaldo metodológico.
    """

    if fecha_generacion is None:
        fecha_generacion = datetime.now()

    archivo = BytesIO()

    resumen = (
        construir_resumen_exportacion(
            resultado=resultado,
            fecha_generacion=
                fecha_generacion,
        )
    )

    definiciones = (
        obtener_definiciones_retencion()
    )

    hojas = {
        # ----------------------------------------------------
        # Ejecutivo / metodología
        # ----------------------------------------------------

        "Resumen":
            resumen,

        "Definiciones":
            definiciones,

        # ----------------------------------------------------
        # Retención
        # ----------------------------------------------------

        "KPI_Retencion":
            resultado[
                "resumen_kpis"
            ],

        "Retencion_Hito":
            resultado[
                "retencion_por_hito"
            ],

        # ----------------------------------------------------
        # Cohortes
        # ----------------------------------------------------

        "Cohortes_Hito":
            resultado[
                "retencion_cohorte_hito"
            ],

        "Oportunidades":
            resultado[
                "oportunidades"
            ],

        # ----------------------------------------------------
        # Snowball
        # ----------------------------------------------------

        "Snowball":
            resultado[
                "snapshot_parque_general"
            ],

        "Snowball_Total":
            resultado[
                "snapshot_parque_total"
            ],

        # ----------------------------------------------------
        # Clientes
        # ----------------------------------------------------

        "Clientes":
            resultado[
                "resumen_cliente"
            ],

        "Cliente_VIN":
            resultado[
                "resumen_cliente_vin"
            ],

        "Perfiles":
            resultado[
                "perfiles_comerciales"
            ],

        # ----------------------------------------------------
        # Auditoría
        # ----------------------------------------------------

        "Aud_Retencion":
            resultado[
                "auditoria_retencion"
            ],

        "Aud_Cohortes":
            resultado[
                "auditoria_cohortes"
            ],

        "Aud_Snowball":
            resultado[
                "auditoria_snowball"
            ],

        "Aud_Clientes":
            resultado[
                "auditoria_clientes"
            ],
    }

    with pd.ExcelWriter(
        archivo,
        engine="openpyxl",
    ) as writer:

        for (
            nombre_hoja,
            dataframe,
        ) in hojas.items():

            _escribir_hoja(
                writer=writer,
                df=dataframe,
                nombre_hoja=
                    nombre_hoja,
            )

    archivo.seek(0)

    return archivo