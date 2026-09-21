from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# COLUMNAS REQUERIDAS
# ============================================================

COLUMNAS_RETAIL_REQUERIDAS = [
    "vin",
    "modelo",
    "año",
    "f entrega",
    "sede",
    "asesor",
]

COLUMNAS_TALLER_REQUERIDAS = [
    "Id doc",
    "f factura servicio",
    "f orden",
    "servicio1",
    "servicio2",
    "vin",
    "modelo",
    "año",
    "sede",
    "asesor",
]

COLUMNAS_CLIENTES_REQUERIDAS = [
    "nro documento",
    "nombre",
    "telefono",
    "correo",
]


# ============================================================
# HELPERS
# ============================================================

def _validar_columnas(
    df: pd.DataFrame,
    columnas_requeridas: list[str],
    nombre_fuente: str,
) -> None:
    """
    Valida que una fuente contenga las columnas mínimas
    necesarias para el motor de retención.
    """

    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Columnas faltantes en {nombre_fuente}: "
            f"{faltantes}"
        )


def _normalizar_vin(
    serie: pd.Series,
) -> pd.Series:
    """
    Normaliza VIN para cruces consistentes entre fuentes.
    """

    vin = (
        serie
        .astype("string")
        .str.strip()
        .str.upper()
    )

    return vin.mask(
        vin.isin(
            [
                "",
                "NAN",
                "NONE",
                "<NA>",
            ]
        )
    )


def _normalizar_texto(
    serie: pd.Series,
) -> pd.Series:
    """
    Normalización mínima de dimensiones categóricas.

    No modifica semántica ni intenta corregir valores
    de negocio.
    """

    texto = (
        serie
        .astype("string")
        .str.strip()
    )

    return texto.mask(
        texto.isin(
            [
                "",
                "nan",
                "None",
                "<NA>",
            ]
        )
    )


def _normalizar_documento(
    serie: pd.Series,
) -> pd.Series:
    """
    Conserva el número de documento como texto.

    No convierte a número para evitar pérdida de formato.
    """

    documento = (
        serie
        .astype("string")
        .str.strip()
    )

    return documento.mask(
        documento.isin(
            [
                "",
                "nan",
                "None",
                "<NA>",
            ]
        )
    )


# ============================================================
# PREPARACIÓN DE RETAIL
# ============================================================

def preparar_retail(
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Valida y normaliza Retail.

    La nueva columna 'nro documento' se conserva cuando
    está disponible, pero no es requisito para el cálculo
    vehicular de retención.
    """

    _validar_columnas(
        df=retail,
        columnas_requeridas=COLUMNAS_RETAIL_REQUERIDAS,
        nombre_fuente="Retail",
    )

    resultado = retail.copy()

    resultado["vin"] = _normalizar_vin(
        resultado["vin"]
    )

    resultado["f entrega"] = pd.to_datetime(
        resultado["f entrega"],
        errors="coerce",
    )

    for columna in [
        "modelo",
        "sede",
        "asesor",
    ]:
        resultado[columna] = _normalizar_texto(
            resultado[columna]
        )

    if "nro documento" in resultado.columns:
        resultado["nro documento"] = (
            _normalizar_documento(
                resultado["nro documento"]
            )
        )

    return resultado


# ============================================================
# PREPARACIÓN DE TALLER
# ============================================================

def preparar_taller(
    taller: pd.DataFrame,
) -> pd.DataFrame:
    """
    Valida y normaliza Taller.

    No aplica todavía reglas de trayectoria, mantenimiento,
    retención ni correcciones de KM.
    """

    _validar_columnas(
        df=taller,
        columnas_requeridas=COLUMNAS_TALLER_REQUERIDAS,
        nombre_fuente="Taller",
    )

    resultado = taller.copy()

    resultado["vin"] = _normalizar_vin(
        resultado["vin"]
    )

    resultado["f factura servicio"] = pd.to_datetime(
        resultado["f factura servicio"],
        errors="coerce",
    )

    resultado["f orden"] = pd.to_datetime(
        resultado["f orden"],
        errors="coerce",
    )

    for columna in [
        "servicio1",
        "servicio2",
        "modelo",
        "sede",
        "asesor",
    ]:
        resultado[columna] = _normalizar_texto(
            resultado[columna]
        )

    if "nro documento" in resultado.columns:
        resultado["nro documento"] = (
            _normalizar_documento(
                resultado["nro documento"]
            )
        )

    return resultado


# ============================================================
# PREPARACIÓN DE CLIENTES
# ============================================================

def preparar_clientes(
    clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normaliza la tabla de clientes.

    Esta fuente se prepara desde ahora para permitir
    posteriormente análisis y rankings a nivel cliente.

    No participa en la clasificación PANA/NOPANA.
    """

    _validar_columnas(
        df=clientes,
        columnas_requeridas=COLUMNAS_CLIENTES_REQUERIDAS,
        nombre_fuente="Clientes",
    )

    resultado = clientes.copy()

    resultado["nro documento"] = (
        _normalizar_documento(
            resultado["nro documento"]
        )
    )

    for columna in [
        "nombre",
        "telefono",
        "correo",
    ]:
        resultado[columna] = _normalizar_texto(
            resultado[columna]
        )

    return resultado


# ============================================================
# PARQUE PANA
# ============================================================

def construir_parque_pana(
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una fila por VIN vendido por PanaAutos.

    Si existen múltiples registros Retail para el mismo VIN,
    conserva el registro con la fecha de entrega más reciente.
    """

    columnas = [
        "vin",
        "modelo",
        "año",
        "f entrega",
        "sede",
        "asesor",
    ]

    if "nro documento" in retail.columns:
        columnas.append(
            "nro documento"
        )

    parque_pana = (
        retail[columnas]
        .dropna(
            subset=["vin"]
        )
        .sort_values(
            [
                "vin",
                "f entrega",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=["vin"],
            keep="last",
        )
        .rename(
            columns={
                "f entrega":
                    "fecha_entrega",

                "año":
                    "anio_vehiculo",
            }
        )
        .reset_index(
            drop=True
        )
    )

    parque_pana["parque"] = "PANA"

    if parque_pana["vin"].duplicated().any():
        raise ValueError(
            "El parque PANA contiene VIN duplicados."
        )

    if parque_pana["vin"].isna().any():
        raise ValueError(
            "El parque PANA contiene VIN vacíos."
        )

    return parque_pana


# ============================================================
# PARQUE OBSERVADO EN TALLER
# ============================================================

def construir_parque_taller(
    taller: pd.DataFrame,
    parque_pana: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una fila por VIN observado históricamente
    en Taller y clasifica el vehículo como PANA o NOPANA.
    """

    taller_con_vin = taller[
        taller["vin"].notna()
    ].copy()

    vins_pana = set(
        parque_pana[
            "vin"
        ]
        .dropna()
        .tolist()
    )

    parque_taller = (
        taller_con_vin
        .groupby(
            "vin",
            as_index=False,
        )
        .agg(
            fecha_primera_visita=(
                "f factura servicio",
                "min",
            ),

            fecha_ultima_visita=(
                "f factura servicio",
                "max",
            ),

            registros_taller=(
                "vin",
                "size",
            ),
        )
    )

    parque_taller["parque"] = np.where(
        parque_taller["vin"].isin(
            vins_pana
        ),
        "PANA",
        "NOPANA",
    )

    if parque_taller["vin"].duplicated().any():
        raise ValueError(
            "El parque Taller contiene VIN duplicados."
        )

    return parque_taller


# ============================================================
# ENRIQUECER PARQUE PANA CON HISTORIA DE TALLER
# ============================================================

def agregar_presencia_taller_a_pana(
    parque_pana: pd.DataFrame,
    parque_taller: pd.DataFrame,
) -> pd.DataFrame:
    """
    Indica si cada VIN vendido por PanaAutos ha tenido
    presencia histórica en Taller.
    """

    resultado = parque_pana.merge(
        parque_taller[
            [
                "vin",
                "fecha_primera_visita",
                "fecha_ultima_visita",
                "registros_taller",
            ]
        ],
        on="vin",
        how="left",
        validate="one_to_one",
    )

    resultado[
        "presencia_historica_taller"
    ] = (
        resultado[
            "fecha_primera_visita"
        ]
        .notna()
    )

    resultado[
        "registros_taller"
    ] = (
        resultado[
            "registros_taller"
        ]
        .fillna(0)
        .astype(int)
    )

    return resultado


# ============================================================
# UNIVERSO DE EVENTOS
# ============================================================

def construir_eventos(
    taller: pd.DataFrame,
    parque_pana: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye el universo estándar de eventos Taller.

    Mantiene todos los tipos de servicio.
    El filtrado preventivo se realizará posteriormente
    en el motor de retención.
    """

    resultado = taller.copy()

    resultado = resultado.rename(
        columns={
            "Id doc":
                "id_evento",

            "f factura servicio":
                "fecha_evento",
        }
    )

    vins_pana = set(
        parque_pana[
            "vin"
        ]
        .dropna()
        .tolist()
    )

    resultado["parque"] = np.where(
        resultado["vin"].isin(
            vins_pana
        ),
        "PANA",
        "NOPANA",
    )

    resultado[
        "servicio1_normalizado"
    ] = (
        resultado[
            "servicio1"
        ]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    return resultado


# ============================================================
# PREVENTIVOS BASE
# ============================================================

def construir_preventivos_base(
    eventos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Obtiene únicamente eventos preventivos.

    Todavía NO reconstruye secuencias ni aplica reglas de KM.
    """

    preventivos = eventos[
        eventos[
            "servicio1_normalizado"
        ].eq(
            "PREVENTIVO"
        )
    ].copy()

    preventivos = preventivos[
        preventivos["vin"].notna()
        & preventivos[
            "fecha_evento"
        ].notna()
    ].copy()

    preventivos = (
        preventivos
        .sort_values(
            [
                "vin",
                "fecha_evento",
                "id_evento",
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    return preventivos


# ============================================================
# AUDITORÍA BÁSICA
# ============================================================

def construir_auditoria_datos(
    retail: pd.DataFrame,
    taller: pd.DataFrame,
    clientes: pd.DataFrame,
    parque_pana: pd.DataFrame,
    parque_taller: pd.DataFrame,
    eventos: pd.DataFrame,
    preventivos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Genera métricas básicas de calidad y cobertura para
    diagnosticar las fuentes antes del cálculo de retención.
    """

    registros = [
        {
            "metrica": "filas_retail",
            "valor": len(retail),
        },
        {
            "metrica": "vin_unicos_retail",
            "valor": retail["vin"].nunique(),
        },
        {
            "metrica": "filas_taller",
            "valor": len(taller),
        },
        {
            "metrica": "vin_unicos_taller",
            "valor": taller["vin"].nunique(),
        },
        {
            "metrica": "filas_clientes",
            "valor": len(clientes),
        },
        {
            "metrica": "documentos_unicos_clientes",
            "valor": clientes[
                "nro documento"
            ].nunique(),
        },
        {
            "metrica": "vin_parque_pana",
            "valor": len(parque_pana),
        },
        {
            "metrica": "vin_parque_taller",
            "valor": len(parque_taller),
        },
        {
            "metrica": "vin_taller_pana",
            "valor": int(
                parque_taller[
                    "parque"
                ]
                .eq("PANA")
                .sum()
            ),
        },
        {
            "metrica": "vin_taller_nopana",
            "valor": int(
                parque_taller[
                    "parque"
                ]
                .eq("NOPANA")
                .sum()
            ),
        },
        {
            "metrica": "eventos_taller",
            "valor": len(eventos),
        },
        {
            "metrica": "eventos_preventivos_base",
            "valor": len(preventivos),
        },
        {
            "metrica": "eventos_sin_vin",
            "valor": int(
                eventos[
                    "vin"
                ]
                .isna()
                .sum()
            ),
        },
        {
            "metrica": "eventos_sin_fecha",
            "valor": int(
                eventos[
                    "fecha_evento"
                ]
                .isna()
                .sum()
            ),
        },
    ]

    return pd.DataFrame(
        registros
    )


# ============================================================
# PIPELINE DE PREPARACIÓN
# ============================================================

def preparar_datos_retencion(
    retail: pd.DataFrame,
    taller: pd.DataFrame,
    clientes: pd.DataFrame,
) -> dict:
    """
    Punto de entrada oficial para la preparación de fuentes
    del Motor de Retención.

    No calcula todavía:
    - trayectorias;
    - retención;
    - cohortes;
    - snowball;
    - rankings de clientes.
    """

    # --------------------------------------------------------
    # 1. Normalizar fuentes
    # --------------------------------------------------------

    retail_preparado = preparar_retail(
        retail
    )

    taller_preparado = preparar_taller(
        taller
    )

    clientes_preparado = preparar_clientes(
        clientes
    )

    # --------------------------------------------------------
    # 2. Parque PANA
    # --------------------------------------------------------

    parque_pana = construir_parque_pana(
        retail_preparado
    )

    # --------------------------------------------------------
    # 3. Parque Taller PANA / NOPANA
    # --------------------------------------------------------

    parque_taller = construir_parque_taller(
        taller=taller_preparado,
        parque_pana=parque_pana,
    )

    # --------------------------------------------------------
    # 4. Presencia histórica Taller
    # --------------------------------------------------------

    parque_pana = (
        agregar_presencia_taller_a_pana(
            parque_pana=parque_pana,
            parque_taller=parque_taller,
        )
    )

    # --------------------------------------------------------
    # 5. Universo de eventos
    # --------------------------------------------------------

    eventos = construir_eventos(
        taller=taller_preparado,
        parque_pana=parque_pana,
    )

    # --------------------------------------------------------
    # 6. Preventivos base
    # --------------------------------------------------------

    preventivos = construir_preventivos_base(
        eventos
    )

    # --------------------------------------------------------
    # 7. Fecha máxima efectiva disponible
    # --------------------------------------------------------

    fecha_max_datos = (
        eventos[
            "fecha_evento"
        ]
        .max()
    )

    if pd.isna(fecha_max_datos):
        raise ValueError(
            "No fue posible determinar la fecha máxima "
            "de información de Taller."
        )

    # --------------------------------------------------------
    # 8. Auditoría
    # --------------------------------------------------------

    auditoria = construir_auditoria_datos(
        retail=retail_preparado,
        taller=taller_preparado,
        clientes=clientes_preparado,
        parque_pana=parque_pana,
        parque_taller=parque_taller,
        eventos=eventos,
        preventivos=preventivos,
    )

    # --------------------------------------------------------
    # 9. Resultado
    # --------------------------------------------------------

    return {
        "retail":
            retail_preparado,

        "taller":
            taller_preparado,

        "clientes":
            clientes_preparado,

        "parque_pana":
            parque_pana,

        "parque_taller":
            parque_taller,

        "eventos":
            eventos,

        "preventivos":
            preventivos,

        "fecha_max_datos":
            fecha_max_datos,

        "auditoria_datos":
            auditoria,
    }   