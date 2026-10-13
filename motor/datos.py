from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONTRATOS DE FUENTE
# ============================================================

COLUMNAS_RETAIL = [
    "f factura venta",
    "modelo",
    "año",
    "vin",
    "f entrega",
    "sede",
    "asesor",
    "nro documento",
]


COLUMNAS_TALLER = [
    "Id doc",
    "f factura servicio",
    "f orden",
    "doc ref",
    "servicio1",
    "servicio2",
    "placa",
    "vin",
    "modelo",
    "año",
    "sede",
    "asesor",
    "nro documento",
]


COLUMNAS_CLIENTES = [
    "nro documento",
    "nombre",
    "telefono",
    "correo",
]


# ============================================================
# PARÁMETROS DE AUDITORÍA
# ============================================================

LONGITUD_VIN_ESPERADA = 17

UMBRAL_KM_POCO_FRECUENTE = 5


# ============================================================
# HELPERS GENERALES
# ============================================================

def _normalizar_texto(
    serie: pd.Series,
    upper: bool = False,
) -> pd.Series:
    """
    Normaliza columnas de texto sin convertir valores nulos
    en cadenas como 'nan', 'None' o '<NA>'.
    """

    resultado = (
        serie
        .astype("string")
        .str.strip()
    )

    resultado = resultado.replace(
        {
            "": pd.NA,
            "nan": pd.NA,
            "None": pd.NA,
            "<NA>": pd.NA,
        }
    )

    if upper:
        resultado = resultado.str.upper()

    return resultado


def _validar_columnas(
    df: pd.DataFrame,
    columnas_requeridas: list[str],
    nombre_fuente: str,
) -> None:
    """
    Detiene el proceso si la estructura de una fuente
    no contiene todas las columnas requeridas.
    """

    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"{nombre_fuente} no cumple el contrato de datos.\n"
            f"Columnas faltantes: {faltantes}"
        )


def _convertir_fecha_excel(
    serie: pd.Series,
) -> pd.Series:
    """
    Convierte fechas provenientes de Excel de forma robusta.

    Soporta:
    - fechas ya interpretadas por pandas;
    - números seriales de Excel;
    - textos de fecha reconocibles.

    Evita interpretar timestamps internos como días de Excel.
    """

    resultado = pd.Series(
        pd.NaT,
        index=serie.index,
        dtype="datetime64[ns]",
    )

    # --------------------------------------------------------
    # 1. Serie ya interpretada completamente como fecha
    # --------------------------------------------------------

    if pd.api.types.is_datetime64_any_dtype(serie):
        return (
            pd.to_datetime(
                serie,
                errors="coerce",
            )
            .dt.normalize()
        )

    # --------------------------------------------------------
    # 2. Seriales numéricos razonables de Excel
    # --------------------------------------------------------

    numerica = pd.to_numeric(
        serie,
        errors="coerce",
    )

    mask_serial_excel = (
        numerica.notna()
        &
        numerica.between(
            1,
            100000,
        )
    )

    if mask_serial_excel.any():
        resultado.loc[
            mask_serial_excel
        ] = (
            pd.Timestamp("1899-12-30")
            +
            pd.to_timedelta(
                numerica.loc[
                    mask_serial_excel
                ],
                unit="D",
            )
        )

    # --------------------------------------------------------
    # 3. Fechas restantes
    # --------------------------------------------------------

    mask_restante = (
        resultado.isna()
        &
        serie.notna()
    )

    if mask_restante.any():
        resultado.loc[
            mask_restante
        ] = pd.to_datetime(
            serie.loc[
                mask_restante
            ],
            errors="coerce",
        )

    return resultado.dt.normalize()


def extraer_mantenimiento_km(
    serie: pd.Series,
) -> pd.Series:
    """
    Extrae el nivel nominal de mantenimiento desde servicio2.

    Ejemplos:
        1K   -> 1
        5K   -> 5
        10K  -> 10
        150K -> 150

    Los valores no interpretables retornan NA.

    IMPORTANTE:
    El motor considera el ciclo desde 1K.
    """

    texto = (
        serie
        .astype("string")
        .str.upper()
        .str.strip()
    )

    extraido = texto.str.extract(
        r"(\d+(?:[.,]\d+)?)",
        expand=False,
    )

    extraido = extraido.str.replace(
        ",",
        ".",
        regex=False,
    )

    return pd.to_numeric(
        extraido,
        errors="coerce",
    ).astype("Float64")


def _contar_claves_con_multiples_valores(
    df: pd.DataFrame,
    columna_clave: str,
    columna_valor: str,
) -> int:
    """
    Cuenta cuántas claves están relacionadas con más de
    un valor distinto no nulo.
    """

    base = df.loc[
        df[columna_clave].notna()
        &
        df[columna_valor].notna(),
        [
            columna_clave,
            columna_valor,
        ],
    ].drop_duplicates()

    if base.empty:
        return 0

    cantidad_valores = (
        base
        .groupby(
            columna_clave
        )[columna_valor]
        .nunique()
    )

    return int(
        (cantidad_valores > 1).sum()
    )


def _contar_vin_longitud_invalida(
    serie: pd.Series,
) -> int:
    """
    Cuenta VIN no vacíos cuya longitud no es 17 caracteres.
    Es un indicador descriptivo de calidad, no una exclusión.
    """

    vin = serie.dropna()

    return int(
        (
            vin.str.len()
            != LONGITUD_VIN_ESPERADA
        ).sum()
    )


def _crear_indicador_calidad(
    fuente: str,
    indicador: str,
    casos: int,
    total_base: int,
) -> dict:
    """
    Construye una fila estándar para CALIDAD_DATOS.
    """

    porcentaje = (
        casos / total_base
        if total_base > 0
        else np.nan
    )

    return {
        "fuente": fuente,
        "indicador": indicador,
        "casos": int(casos),
        "total_base": int(total_base),
        "porcentaje": porcentaje,
    }


# ============================================================
# PREPARAR RETAIL
# ============================================================

def preparar_retail(
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Valida y normaliza retail.xlsx.
    """

    _validar_columnas(
        retail,
        COLUMNAS_RETAIL,
        "retail.xlsx",
    )

    df = retail[
        COLUMNAS_RETAIL
    ].copy()

    df["vin"] = _normalizar_texto(
        df["vin"],
        upper=True,
    )

    df["modelo"] = _normalizar_texto(
        df["modelo"],
        upper=True,
    )

    df["sede"] = _normalizar_texto(
        df["sede"],
        upper=True,
    )

    df["asesor"] = _normalizar_texto(
        df["asesor"],
        upper=True,
    )

    df["nro documento"] = _normalizar_texto(
        df["nro documento"],
    )

    # Se conserva el formato comercial:
    # 20/20, 21/21, 25/26, etc.
    df["año"] = _normalizar_texto(
        df["año"],
    )

    df["fecha_entrega"] = (
        _convertir_fecha_excel(
            df["f entrega"]
        )
    )

    return df


# ============================================================
# PREPARAR TALLER
# ============================================================

def preparar_taller(
    taller: pd.DataFrame,
) -> pd.DataFrame:
    """
    Valida y normaliza taller.xlsx.
    """

    _validar_columnas(
        taller,
        COLUMNAS_TALLER,
        "taller.xlsx",
    )

    df = taller[
        COLUMNAS_TALLER
    ].copy()

    df["vin"] = _normalizar_texto(
        df["vin"],
        upper=True,
    )

    df["placa"] = _normalizar_texto(
        df["placa"],
        upper=True,
    )

    df["modelo"] = _normalizar_texto(
        df["modelo"],
        upper=True,
    )

    df["sede"] = _normalizar_texto(
        df["sede"],
        upper=True,
    )

    df["asesor"] = _normalizar_texto(
        df["asesor"],
        upper=True,
    )

    df["nro documento"] = _normalizar_texto(
        df["nro documento"],
    )

    df["servicio1"] = _normalizar_texto(
        df["servicio1"],
        upper=True,
    )

    df["servicio2"] = _normalizar_texto(
        df["servicio2"],
        upper=True,
    )

    # Id doc será posteriormente nro_orden_servicio.
    df["Id doc"] = _normalizar_texto(
        df["Id doc"],
    )

    df["doc ref"] = _normalizar_texto(
        df["doc ref"],
    )

    df["año"] = _normalizar_texto(
        df["año"],
    )

    df["fecha_orden"] = (
        _convertir_fecha_excel(
            df["f orden"]
        )
    )

    df["fecha_factura_servicio"] = (
        _convertir_fecha_excel(
            df["f factura servicio"]
        )
    )

    df["es_preventivo"] = (
        df["servicio1"]
        .eq("PREVENTIVO")
    )

    df["mantenimiento_km"] = (
        extraer_mantenimiento_km(
            df["servicio2"]
        )
    )

    return df


# ============================================================
# PREPARAR CLIENTES
# ============================================================

def preparar_clientes(
    clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Valida y normaliza clientes.xlsx.
    """

    _validar_columnas(
        clientes,
        COLUMNAS_CLIENTES,
        "clientes.xlsx",
    )

    df = clientes[
        COLUMNAS_CLIENTES
    ].copy()

    df["nro documento"] = (
        _normalizar_texto(
            df["nro documento"],
        )
    )

    df["nombre"] = (
        _normalizar_texto(
            df["nombre"],
        )
    )

    df["telefono"] = (
        _normalizar_texto(
            df["telefono"],
        )
    )

    df["correo"] = (
        _normalizar_texto(
            df["correo"],
        )
    )

    return df


# ============================================================
# CLASIFICACIÓN DE PARQUE
# ============================================================

def clasificar_parque(
    taller: pd.DataFrame,
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clasifica cada registro de Taller:

    PANA:
        VIN presente en Retail.

    NOPANA:
        VIN observado en Taller pero no presente en Retail.
    """

    resultado = taller.copy()

    vin_pana = set(
        retail.loc[
            retail["vin"].notna(),
            "vin",
        ].unique()
    )

    resultado["parque"] = np.where(
        resultado["vin"].isin(
            vin_pana
        ),
        "PANA",
        "NOPANA",
    )

    return resultado


# ============================================================
# HISTORIAL PREVENTIVO BASE
# ============================================================

def construir_historial_preventivo_base(
    taller: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la base preventiva inicial.

    Incluye mantenimientos desde 1K.

    Todavía NO consolida órdenes cercanas dentro de
    una visita analítica de 7 días.

    Solo exige:
    - servicio preventivo;
    - VIN disponible;
    - fecha de orden válida.

    Los registros cuyo servicio2 no permite interpretar
    kilometraje se conservan por ahora para auditoría.
    """

    historia = taller.loc[
        taller["es_preventivo"]
        &
        taller["vin"].notna()
        &
        taller["fecha_orden"].notna()
    ].copy()

    historia = (
        historia
        .sort_values(
            [
                "vin",
                "fecha_orden",
                "Id doc",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return historia


# ============================================================
# AUDITORÍA DE MANTENIMIENTOS
# ============================================================

def auditar_mantenimientos_especiales(
    historia_preventiva: pd.DataFrame,
) -> dict:
    """
    Identifica:

    - servicio2 preventivos sin KM interpretable;
    - distribución de niveles de mantenimiento;
    - niveles de KM con muy pocos registros.

    Esta función no modifica ni elimina registros.
    """

    sin_km_detalle = (
        historia_preventiva.loc[
            historia_preventiva[
                "mantenimiento_km"
            ].isna(),
            [
                "servicio2",
                "vin",
                "fecha_orden",
                "Id doc",
                "placa",
                "modelo",
                "parque",
                "nro documento",
            ],
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )

    valores_sin_km = (
        sin_km_detalle[
            "servicio2"
        ]
        .value_counts(
            dropna=False
        )
        .rename_axis(
            "servicio2"
        )
        .reset_index(
            name="cantidad"
        )
    )

    distribucion_km = (
        historia_preventiva.loc[
            historia_preventiva[
                "mantenimiento_km"
            ].notna()
        ]
        .groupby(
            "mantenimiento_km",
            as_index=False,
        )
        .agg(
            cantidad=(
                "vin",
                "size",
            ),
            vin_unicos=(
                "vin",
                "nunique",
            ),
        )
        .sort_values(
            "mantenimiento_km"
        )
        .reset_index(
            drop=True
        )
    )

    kilometrajes_raros = (
        distribucion_km.loc[
            distribucion_km[
                "cantidad"
            ]
            <= UMBRAL_KM_POCO_FRECUENTE
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )

    return {
        "sin_km_detalle":
            sin_km_detalle,

        "valores_sin_km":
            valores_sin_km,

        "distribucion_km":
            distribucion_km,

        "kilometrajes_raros":
            kilometrajes_raros,
    }


# ============================================================
# AUDITORÍA GENERAL DE FUENTES
# ============================================================

def construir_auditoria_fuentes(
    retail: pd.DataFrame,
    taller: pd.DataFrame,
    clientes: pd.DataFrame,
    historia_preventiva: pd.DataFrame,
) -> dict:
    """
    Auditoría descriptiva resumida de las fuentes.

    No modifica datos.
    """

    documentos_clientes = set(
        clientes.loc[
            clientes[
                "nro documento"
            ].notna(),
            "nro documento",
        ].unique()
    )

    documentos_preventivos = (
        historia_preventiva[
            "nro documento"
        ]
    )

    preventivos_documento_sin_maestro = (
        documentos_preventivos.notna()
        &
        ~documentos_preventivos.isin(
            documentos_clientes
        )
    )

    documentos_retail = (
        retail[
            "nro documento"
        ]
    )

    retail_documento_sin_maestro = (
        documentos_retail.notna()
        &
        ~documentos_retail.isin(
            documentos_clientes
        )
    )

    documentos_taller = (
        taller[
            "nro documento"
        ]
    )

    taller_documento_sin_maestro = (
        documentos_taller.notna()
        &
        ~documentos_taller.isin(
            documentos_clientes
        )
    )

    auditoria = {
        # ----------------------------------------------------
        # Retail
        # ----------------------------------------------------

        "retail_filas":
            len(retail),

        "retail_vin_vacio":
            int(
                retail[
                    "vin"
                ].isna().sum()
            ),

        "retail_vin_longitud_invalida":
            _contar_vin_longitud_invalida(
                retail["vin"]
            ),

        "retail_vin_duplicado":
            int(
                retail[
                    "vin"
                ].duplicated().sum()
            ),

        "retail_modelo_vacio":
            int(
                retail[
                    "modelo"
                ].isna().sum()
            ),

        "retail_documento_vacio":
            int(
                retail[
                    "nro documento"
                ].isna().sum()
            ),

        "retail_documento_sin_cliente":
            int(
                retail_documento_sin_maestro.sum()
            ),

        "retail_fecha_entrega_invalida":
            int(
                retail[
                    "fecha_entrega"
                ].isna().sum()
            ),

        "retail_sede_vacia":
            int(
                retail[
                    "sede"
                ].isna().sum()
            ),

        "retail_vin_con_varios_modelos":
            _contar_claves_con_multiples_valores(
                retail,
                "vin",
                "modelo",
            ),

        "retail_vin_con_varios_documentos":
            _contar_claves_con_multiples_valores(
                retail,
                "vin",
                "nro documento",
            ),

        # ----------------------------------------------------
        # Taller
        # ----------------------------------------------------

        "taller_filas":
            len(taller),

        "taller_vin_vacio":
            int(
                taller[
                    "vin"
                ].isna().sum()
            ),

        "taller_vin_longitud_invalida":
            _contar_vin_longitud_invalida(
                taller["vin"]
            ),

        "taller_modelo_vacio":
            int(
                taller[
                    "modelo"
                ].isna().sum()
            ),

        "taller_placa_vacia":
            int(
                taller[
                    "placa"
                ].isna().sum()
            ),

        "taller_documento_vacio":
            int(
                taller[
                    "nro documento"
                ].isna().sum()
            ),

        "taller_documento_sin_cliente":
            int(
                taller_documento_sin_maestro.sum()
            ),

        "taller_fecha_orden_invalida":
            int(
                taller[
                    "fecha_orden"
                ].isna().sum()
            ),

        "taller_preventivos":
            int(
                taller[
                    "es_preventivo"
                ].sum()
            ),

        "preventivos_utilizables":
            len(
                historia_preventiva
            ),

        "preventivos_sin_km_interpretable":
            int(
                historia_preventiva[
                    "mantenimiento_km"
                ].isna().sum()
            ),

        "preventivos_sin_documento":
            int(
                historia_preventiva[
                    "nro documento"
                ].isna().sum()
            ),

        "preventivos_documento_sin_cliente":
            int(
                preventivos_documento_sin_maestro.sum()
            ),

        "taller_vin_con_varios_modelos":
            _contar_claves_con_multiples_valores(
                taller,
                "vin",
                "modelo",
            ),

        "taller_vin_con_varias_placas":
            _contar_claves_con_multiples_valores(
                taller,
                "vin",
                "placa",
            ),

        "taller_placa_con_varios_vin":
            _contar_claves_con_multiples_valores(
                taller,
                "placa",
                "vin",
            ),

        # ----------------------------------------------------
        # Clientes
        # ----------------------------------------------------

        "clientes_filas":
            len(clientes),

        "clientes_documento_vacio":
            int(
                clientes[
                    "nro documento"
                ].isna().sum()
            ),

        "clientes_documento_duplicado":
            int(
                clientes[
                    "nro documento"
                ]
                .duplicated()
                .sum()
            ),

        "clientes_nombre_vacio":
            int(
                clientes[
                    "nombre"
                ].isna().sum()
            ),

        "clientes_telefono_vacio":
            int(
                clientes[
                    "telefono"
                ].isna().sum()
            ),

        "clientes_correo_vacio":
            int(
                clientes[
                    "correo"
                ].isna().sum()
            ),

        "clientes_documento_con_varios_nombres":
            _contar_claves_con_multiples_valores(
                clientes,
                "nro documento",
                "nombre",
            ),

        "clientes_documento_con_varios_telefonos":
            _contar_claves_con_multiples_valores(
                clientes,
                "nro documento",
                "telefono",
            ),

        "clientes_documento_con_varios_correos":
            _contar_claves_con_multiples_valores(
                clientes,
                "nro documento",
                "correo",
            ),
    }

    return auditoria


# ============================================================
# CALIDAD DE DATOS PARA REPORTE
# ============================================================

def construir_calidad_datos(
    retail: pd.DataFrame,
    taller: pd.DataFrame,
    clientes: pd.DataFrame,
    historia_preventiva: pd.DataFrame,
    auditoria: dict,
) -> pd.DataFrame:
    """
    Genera una tabla descriptiva destinada a convertirse
    posteriormente en la hoja CALIDAD_DATOS del Excel final.

    No pretende realizar un estudio profundo de calidad.
    Su objetivo es documentar la calidad de las fuentes
    utilizadas para generar cada proyección.
    """

    total_retail = len(retail)
    total_taller = len(taller)
    total_clientes = len(clientes)
    total_preventivos = len(
        historia_preventiva
    )

    filas = [
        # ----------------------------------------------------
        # Retail
        # ----------------------------------------------------

        _crear_indicador_calidad(
            "RETAIL",
            "VIN vacío",
            auditoria[
                "retail_vin_vacio"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "VIN con longitud distinta de 17",
            auditoria[
                "retail_vin_longitud_invalida"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "VIN duplicado",
            auditoria[
                "retail_vin_duplicado"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "Modelo vacío",
            auditoria[
                "retail_modelo_vacio"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "Documento vacío",
            auditoria[
                "retail_documento_vacio"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "Documento sin maestro de clientes",
            auditoria[
                "retail_documento_sin_cliente"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "Fecha de entrega inválida",
            auditoria[
                "retail_fecha_entrega_invalida"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "Sede vacía",
            auditoria[
                "retail_sede_vacia"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "VIN relacionado con varios modelos",
            auditoria[
                "retail_vin_con_varios_modelos"
            ],
            total_retail,
        ),

        _crear_indicador_calidad(
            "RETAIL",
            "VIN relacionado con varios documentos",
            auditoria[
                "retail_vin_con_varios_documentos"
            ],
            total_retail,
        ),

        # ----------------------------------------------------
        # Taller
        # ----------------------------------------------------

        _crear_indicador_calidad(
            "TALLER",
            "VIN vacío",
            auditoria[
                "taller_vin_vacio"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "VIN con longitud distinta de 17",
            auditoria[
                "taller_vin_longitud_invalida"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Modelo vacío",
            auditoria[
                "taller_modelo_vacio"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Placa vacía",
            auditoria[
                "taller_placa_vacia"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Documento vacío",
            auditoria[
                "taller_documento_vacio"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Documento sin maestro de clientes",
            auditoria[
                "taller_documento_sin_cliente"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Fecha de orden inválida",
            auditoria[
                "taller_fecha_orden_invalida"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "VIN relacionado con varios modelos",
            auditoria[
                "taller_vin_con_varios_modelos"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "VIN relacionado con varias placas",
            auditoria[
                "taller_vin_con_varias_placas"
            ],
            total_taller,
        ),

        _crear_indicador_calidad(
            "TALLER",
            "Placa relacionada con varios VIN",
            auditoria[
                "taller_placa_con_varios_vin"
            ],
            total_taller,
        ),

        # ----------------------------------------------------
        # Preventivos
        # ----------------------------------------------------

        _crear_indicador_calidad(
            "PREVENTIVOS",
            "Preventivo sin KM interpretable",
            auditoria[
                "preventivos_sin_km_interpretable"
            ],
            total_preventivos,
        ),

        _crear_indicador_calidad(
            "PREVENTIVOS",
            "Preventivo sin documento",
            auditoria[
                "preventivos_sin_documento"
            ],
            total_preventivos,
        ),

        _crear_indicador_calidad(
            "PREVENTIVOS",
            "Documento sin maestro de clientes",
            auditoria[
                "preventivos_documento_sin_cliente"
            ],
            total_preventivos,
        ),

        # ----------------------------------------------------
        # Clientes
        # ----------------------------------------------------

        _crear_indicador_calidad(
            "CLIENTES",
            "Documento vacío",
            auditoria[
                "clientes_documento_vacio"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Documento duplicado",
            auditoria[
                "clientes_documento_duplicado"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Nombre vacío",
            auditoria[
                "clientes_nombre_vacio"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Teléfono vacío",
            auditoria[
                "clientes_telefono_vacio"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Correo vacío",
            auditoria[
                "clientes_correo_vacio"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Documento relacionado con varios nombres",
            auditoria[
                "clientes_documento_con_varios_nombres"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Documento relacionado con varios teléfonos",
            auditoria[
                "clientes_documento_con_varios_telefonos"
            ],
            total_clientes,
        ),

        _crear_indicador_calidad(
            "CLIENTES",
            "Documento relacionado con varios correos",
            auditoria[
                "clientes_documento_con_varios_correos"
            ],
            total_clientes,
        ),
    ]

    calidad = pd.DataFrame(
        filas
    )

    calidad["porcentaje"] = (
        calidad[
            "porcentaje"
        ]
        .astype(float)
    )

    return calidad

# ============================================================
# función adicional ante datos derales de clientes
# ============================================================

def consolidar_clientes_ultimo_registro(
    clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye un maestro temporal de clientes con una sola fila
    por nro documento.

    Regla de negocio temporal
    -------------------------
    1. Se respeta el orden original del archivo clientes.xlsx.
       Las filas ubicadas más abajo se consideran más recientes.

    2. Para cada nro documento:
       - se utiliza el último registro que tenga teléfono válido;
       - si ningún registro del documento tiene teléfono válido,
         se utiliza el último registro disponible.

    3. Se conserva la fila completa seleccionada, por lo que
       nombre, teléfono y correo pertenecen al mismo registro.

    Esta estrategia evita merges many-to-many y refleja el
    mecanismo actual de actualización incremental de clientes.
    """

    if clientes.empty:
        return clientes.copy()

    columnas_requeridas = [
        "nro documento",
        "telefono",
    ]

    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in clientes.columns
    ]

    if faltantes:
        raise ValueError(
            "CLIENTES no contiene las columnas requeridas: "
            f"{faltantes}"
        )

    df = clientes.copy()

    # --------------------------------------------------------
    # Conservar orden físico del archivo.
    # Una fila mayor = registro más reciente.
    # --------------------------------------------------------

    df["_orden_fuente"] = range(
        len(df)
    )

    # --------------------------------------------------------
    # Normalizar documento
    # --------------------------------------------------------

    df["nro documento"] = (
        df["nro documento"]
        .astype("string")
        .str.strip()
    )

    df["nro documento"] = (
        df["nro documento"]
        .replace(
            {
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "<NA>": pd.NA,
            }
        )
    )

    # No podemos construir identidad sin documento.
    df = df.loc[
        df["nro documento"].notna()
    ].copy()

    # --------------------------------------------------------
    # Identificar teléfono válido.
    #
    # Por ahora la regla es deliberadamente conservadora:
    # válido = no nulo / no vacío.
    #
    # No hacemos todavía limpieza avanzada de teléfonos porque
    # eso corresponde al futuro proyecto de Calidad de Clientes.
    # --------------------------------------------------------

    telefono = (
        df["telefono"]
        .astype("string")
        .str.strip()
    )

    df["_telefono_valido"] = (
        telefono.notna()
        &
        ~telefono.isin(
            [
                "",
                "nan",
                "None",
                "<NA>",
            ]
        )
    )

    # --------------------------------------------------------
    # A. Último registro CON teléfono por documento
    # --------------------------------------------------------

    ultimo_con_telefono = (
        df.loc[
            df["_telefono_valido"]
        ]
        .sort_values(
            "_orden_fuente",
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "nro documento",
            ],
            keep="last",
        )
    )

    # --------------------------------------------------------
    # B. Último registro disponible por documento
    #
    # Sirve como fallback cuando nunca encontramos teléfono.
    # --------------------------------------------------------

    ultimo_registro = (
        df
        .sort_values(
            "_orden_fuente",
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "nro documento",
            ],
            keep="last",
        )
    )

    # --------------------------------------------------------
    # Documentos que ya tienen una fila con teléfono
    # --------------------------------------------------------

    documentos_con_telefono = set(
        ultimo_con_telefono[
            "nro documento"
        ]
    )

    # --------------------------------------------------------
    # Solo fallback para documentos sin teléfono histórico
    # --------------------------------------------------------

    fallback_sin_telefono = (
        ultimo_registro.loc[
            ~ultimo_registro[
                "nro documento"
            ].isin(
                documentos_con_telefono
            )
        ]
    )

    # --------------------------------------------------------
    # Maestro final
    # --------------------------------------------------------

    maestro = pd.concat(
        [
            ultimo_con_telefono,
            fallback_sin_telefono,
        ],
        ignore_index=True,
    )

    # Recuperamos orden documental estable.
    maestro = (
        maestro
        .sort_values(
            "_orden_fuente",
            kind="stable",
        )
        .drop(
            columns=[
                "_orden_fuente",
                "_telefono_valido",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # Control contractual crítico
    # --------------------------------------------------------

    duplicados = int(
        maestro[
            "nro documento"
        ]
        .duplicated()
        .sum()
    )

    if duplicados != 0:
        raise ValueError(
            "El maestro consolidado de clientes todavía "
            f"contiene {duplicados} documentos duplicados."
        )

    return maestro



# ============================================================
# PIPELINE DE PREPARACIÓN
# ============================================================

def preparar_datos(
    retail_raw: pd.DataFrame,
    taller_raw: pd.DataFrame,
    clientes_raw: pd.DataFrame,
) -> dict:
    """
    Punto de entrada oficial de la preparación de datos.

    Retorna:
    - Retail normalizado
    - Taller normalizado
    - Clientes normalizado
    - Historial preventivo base
    - Auditoría resumida
    - Auditoría de mantenimientos especiales
    - Tabla de calidad preparada para reporte

    Todavía no realiza:
    - consolidación de visitas a 7 días;
    - trayectoria por VIN;
    - clasificación de comportamiento;
    - referencias históricas;
    - proyección de demanda.
    """

    retail = preparar_retail(
        retail_raw
    )

    taller = preparar_taller(
        taller_raw
    )

    clientes = preparar_clientes(
        clientes_raw
    )

    clientes = consolidar_clientes_ultimo_registro(
        clientes
    )

    taller = clasificar_parque(
        taller=taller,
        retail=retail,
    )

    historia_preventiva = (
        construir_historial_preventivo_base(
            taller
        )
    )

    auditoria = (
        construir_auditoria_fuentes(
            retail=retail,
            taller=taller,
            clientes=clientes,
            historia_preventiva=historia_preventiva,
        )
    )

    auditoria_mantenimientos = (
        auditar_mantenimientos_especiales(
            historia_preventiva
        )
    )

    calidad_datos = (
        construir_calidad_datos(
            retail=retail,
            taller=taller,
            clientes=clientes,
            historia_preventiva=historia_preventiva,
            auditoria=auditoria,
        )
    )

    auditoria_clientes = pd.DataFrame(
        [
            {
                "metrica":
                    "filas_clientes_originales",
                "valor":
                    len(clientes_raw),
            },
            {
                "metrica":
                    "clientes_maestro",
                "valor":
                    len(clientes),
            },
            {
                "metrica":
                    "documentos_unicos_maestro",
                "valor":
                    clientes[
                        "nro documento"
                    ].nunique(),
            },
            {
                "metrica":
                    "documentos_duplicados_maestro",
                "valor":
                    int(
                        clientes[
                            "nro documento"
                        ]
                        .duplicated()
                        .sum()
                    ),
            },
            {
                "metrica":
                    "clientes_con_telefono",
                "valor":
                    int(
                        clientes[
                            "telefono"
                        ]
                        .notna()
                        .sum()
                    ),
            },
        ]
    )

    return {
        "retail":
            retail,

        "taller":
            taller,

        "clientes":
            clientes,

        "auditoria_clientes":
            auditoria_clientes,

        "historia_preventiva":
            historia_preventiva,

        "auditoria":
            auditoria,

        "auditoria_mantenimientos":
            auditoria_mantenimientos,

        "calidad_datos":
            calidad_datos,
    }