from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

KM_1K = 1
KM_5K = 5
KM_MIN_CICLO_COMPARABLE = 10

MESES_HITO_1K = 1
MESES_HITO_5K = 6

MESES_SNAPSHOTS = 36

MESES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


# ============================================================
# HELPERS
# ============================================================

def _etiqueta_periodo(
    fecha,
) -> str:
    """
    Convierte una fecha/periodo en etiqueta comercial.

    Ejemplo:
        2026-03 -> Mar-26
    """

    if pd.isna(fecha):
        return "SIN_FECHA"

    periodo = pd.Period(
        fecha,
        freq="M",
    )

    return (
        f"{MESES_ES[periodo.month]}-"
        f"{str(periodo.year)[-2:]}"
    )


def _validar_columnas(
    df: pd.DataFrame,
    columnas: list[str],
    nombre: str,
) -> None:
    """
    Valida el contrato mínimo requerido de un DataFrame.
    """

    faltantes = [
        columna
        for columna in columnas
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Faltan columnas en {nombre}: "
            f"{faltantes}"
        )


def _primera_fecha_hito(
    secuencia: pd.DataFrame,
    mantenimiento_km: int,
) -> pd.DataFrame:
    """
    Devuelve la primera visita analítica de un hito
    específico por VIN.
    """

    resultado = (
        secuencia.loc[
            secuencia[
                "mantenimiento_km"
            ].eq(mantenimiento_km),
            [
                "vin",
                "fecha_visita",
            ],
        ]
        .sort_values(
            [
                "vin",
                "fecha_visita",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=["vin"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return resultado


# ============================================================
# PARQUE PANA DE REFERENCIA
# ============================================================

def construir_parque_pana_cohortes(
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una fila por VIN vendido por PanaAutos.

    Esta base aporta:
    - fecha de entrega;
    - modelo;
    - año;
    - sede;
    - asesor;
    - documento, cuando está disponible.
    """

    columnas_requeridas = [
        "vin",
        "fecha_entrega",
        "modelo",
        "año",
        "sede",
        "asesor",
    ]

    _validar_columnas(
        df=retail,
        columnas=columnas_requeridas,
        nombre="retail",
    )

    columnas = (
        columnas_requeridas.copy()
    )

    if "nro documento" in retail.columns:
        columnas.append(
            "nro documento"
        )

    parque = (
        retail[
            columnas
        ]
        .dropna(
            subset=[
                "vin",
                "fecha_entrega",
            ]
        )
        .sort_values(
            [
                "vin",
                "fecha_entrega",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=["vin"],
            keep="last",
        )
        .copy()
    )

    parque[
        "fecha_entrega"
    ] = pd.to_datetime(
        parque[
            "fecha_entrega"
        ],
        errors="coerce",
    )

    parque[
        "cohorte_entrega_mes"
    ] = (
        parque[
            "fecha_entrega"
        ]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    parque[
        "parque"
    ] = "PANA"

    return (
        parque
        .reset_index(drop=True)
    )


# ============================================================
# OPORTUNIDAD 1K
# ============================================================

def construir_oportunidad_1k(
    parque_pana: pd.DataFrame,
    secuencia: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construye la oportunidad ENTREGA -> 1K.

    Política:
        fecha esperada = entrega + 1 mes.

    Retención:
        se considera retorno cuando existe un 1K
        preventivo analítico observado.
    """

    primer_1k = (
        _primera_fecha_hito(
            secuencia=secuencia,
            mantenimiento_km=KM_1K,
        )
        .rename(
            columns={
                "fecha_visita":
                    "fecha_retorno",
            }
        )
    )

    base = (
        parque_pana.copy()
    )

    base = base.merge(
        primer_1k,
        on="vin",
        how="left",
        validate="one_to_one",
    )

    base[
        "hito_km"
    ] = KM_1K

    base[
        "tipo_oportunidad"
    ] = "DESDE_ENTREGA"

    base[
        "fecha_origen"
    ] = (
        base[
            "fecha_entrega"
        ]
    )

    base[
        "fecha_esperada"
    ] = (
        base[
            "fecha_entrega"
        ]
        +
        pd.DateOffset(
            months=MESES_HITO_1K
        )
    )

    base[
        "retuvo"
    ] = (
        base[
            "fecha_retorno"
        ]
        .notna()
        .astype("int8")
    )

    base[
        "adherencia"
    ] = pd.NA

    base[
        "puntualidad"
    ] = pd.NA

    base[
        "oportunidad_madura"
    ] = (
        base[
            "fecha_esperada"
        ]
        .le(fecha_max_datos)
    )

    return base


# ============================================================
# OPORTUNIDAD 5K
# ============================================================

def construir_oportunidad_5k(
    parque_pana: pd.DataFrame,
    secuencia: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construye la oportunidad ENTREGA -> 5K.

    Política:
        fecha esperada = entrega + 6 meses.

    El 1K no reinicia el reloj.

    Retención:
        se considera retorno cuando existe un 5K
        preventivo analítico observado.
    """

    primer_5k = (
        _primera_fecha_hito(
            secuencia=secuencia,
            mantenimiento_km=KM_5K,
        )
        .rename(
            columns={
                "fecha_visita":
                    "fecha_retorno",
            }
        )
    )

    base = (
        parque_pana.copy()
    )

    base = base.merge(
        primer_5k,
        on="vin",
        how="left",
        validate="one_to_one",
    )

    base[
        "hito_km"
    ] = KM_5K

    base[
        "tipo_oportunidad"
    ] = "DESDE_ENTREGA"

    base[
        "fecha_origen"
    ] = (
        base[
            "fecha_entrega"
        ]
    )

    base[
        "fecha_esperada"
    ] = (
        base[
            "fecha_entrega"
        ]
        +
        pd.DateOffset(
            months=MESES_HITO_5K
        )
    )

    base[
        "retuvo"
    ] = (
        base[
            "fecha_retorno"
        ]
        .notna()
        .astype("int8")
    )

    base[
        "adherencia"
    ] = pd.NA

    base[
        "puntualidad"
    ] = pd.NA

    base[
        "oportunidad_madura"
    ] = (
        base[
            "fecha_esperada"
        ]
        .le(fecha_max_datos)
    )

    return base


# ============================================================
# OPORTUNIDADES DE CICLO 10K+
# ============================================================

def construir_oportunidades_ciclo(
    ciclos_retencion: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construye las oportunidades 10K+ utilizando directamente
    el Motor 05 validado.

    Retención flexible:
        RETORNO implica que el vehículo volvió a un
        mantenimiento de ciclo posterior.

    Adherencia:
        indica si volvió exactamente al hito esperado.

    Por ejemplo:
        5K -> 15K

        Retención  = sí
        Adherencia = no
    """

    columnas_requeridas = [
        "vin",
        "parque",
        "modelo",
        "año",
        "sede",
        "asesor",
        "fecha_visita",
        "mantenimiento_km",
        "km_esperado_siguiente",
        "fecha_esperada_siguiente",
        "fecha_siguiente_observada",
        "kpi_retorno",
        "kpi_adherencia_ciclo",
        "kpi_puntualidad",
    ]

    _validar_columnas(
        df=ciclos_retencion,
        columnas=columnas_requeridas,
        nombre="ciclos_retencion",
    )

    base = (
        ciclos_retencion[
            columnas_requeridas
        ]
        .copy()
    )

    base = base.rename(
        columns={
            "fecha_visita":
                "fecha_origen",

            "km_esperado_siguiente":
                "hito_km",

            "fecha_esperada_siguiente":
                "fecha_esperada",

            "fecha_siguiente_observada":
                "fecha_retorno",
        }
    )

    base = base.loc[
        base[
            "hito_km"
        ].ge(
            KM_MIN_CICLO_COMPARABLE
        )
    ].copy()

    base[
        "tipo_oportunidad"
    ] = "TRANSICION_CICLO"

    base[
        "retuvo"
    ] = (
        base[
            "kpi_retorno"
        ]
        .eq("RETORNO")
        .astype("int8")
    )

    base[
        "adherencia"
    ] = (
        base[
            "kpi_adherencia_ciclo"
        ]
        .eq("SI")
        .astype("int8")
    )

    base[
        "puntualidad"
    ] = (
        base[
            "kpi_puntualidad"
        ]
        .eq("EN_FECHA")
        .astype("int8")
    )

    base[
        "oportunidad_madura"
    ] = (
        base[
            "fecha_esperada"
        ]
        .le(fecha_max_datos)
    )

    # --------------------------------------------------------
    # Una sola oportunidad por VIN + parque + hito.
    #
    # La versión final del Notebook 03 aplicaba este mismo
    # principio para evitar doble conteo.
    #
    # Si un VIN genera más de una oportunidad para un hito
    # por repetición o retroceso, conservamos la oportunidad
    # cronológicamente más reciente.
    # --------------------------------------------------------

    base = (
        base
        .sort_values(
            [
                "vin",
                "parque",
                "hito_km",
                "fecha_esperada",
                "fecha_origen",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "vin",
                "parque",
                "hito_km",
            ],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return base


# ============================================================
# METADATA PANA PARA OPORTUNIDADES DE CICLO
# ============================================================

def agregar_cohorte_entrega(
    oportunidades: pd.DataFrame,
    parque_pana: pd.DataFrame,
) -> pd.DataFrame:
    """
    Incorpora fecha y cohorte de entrega cuando el VIN
    pertenece al parque PANA.

    Para NOPANA permanecerán vacías, porque no conocemos
    su fecha de venta original.
    """

    entrega = (
        parque_pana[
            [
                "vin",
                "fecha_entrega",
                "cohorte_entrega_mes",
            ]
        ]
        .copy()
    )

    resultado = oportunidades.merge(
        entrega,
        on="vin",
        how="left",
        validate="many_to_one",
    )

    return resultado


# ============================================================
# NORMALIZAR CONTRATO DE OPORTUNIDADES
# ============================================================

def estandarizar_oportunidades(
    base: pd.DataFrame,
) -> pd.DataFrame:
    """
    Deja todas las oportunidades bajo el mismo contrato
    analítico para cohortes y Streamlit.
    """

    resultado = (
        base.copy()
    )

    for columna in [
        "fecha_entrega",
        "fecha_origen",
        "fecha_esperada",
        "fecha_retorno",
        "cohorte_entrega_mes",
    ]:

        if columna not in resultado.columns:
            resultado[columna] = pd.NaT

        resultado[
            columna
        ] = pd.to_datetime(
            resultado[
                columna
            ],
            errors="coerce",
        )

    for columna in [
        "modelo",
        "año",
        "sede",
        "asesor",
    ]:

        if columna not in resultado.columns:
            resultado[columna] = pd.NA

    # --------------------------------------------------------
    # Cohorte gerencial:
    # mes de la oportunidad esperada.
    # --------------------------------------------------------

    resultado[
        "cohorte_mes"
    ] = (
        resultado[
            "fecha_esperada"
        ]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    # --------------------------------------------------------
    # Mes real del retorno.
    # --------------------------------------------------------

    resultado[
        "retorno_mes"
    ] = (
        resultado[
            "fecha_retorno"
        ]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    resultado[
        "cohorte_txt"
    ] = (
        resultado[
            "cohorte_mes"
        ]
        .map(
            _etiqueta_periodo
        )
    )

    resultado[
        "retorno_mes_txt"
    ] = (
        resultado[
            "retorno_mes"
        ]
        .map(
            _etiqueta_periodo
        )
    )

    resultado[
        "hito_km"
    ] = (
        pd.to_numeric(
            resultado[
                "hito_km"
            ],
            errors="coerce",
        )
        .astype("Int64")
    )

    resultado[
        "retuvo"
    ] = (
        pd.to_numeric(
            resultado[
                "retuvo"
            ],
            errors="coerce",
        )
        .fillna(0)
        .astype("int8")
    )

    resultado[
        "oportunidad_madura"
    ] = (
        resultado[
            "oportunidad_madura"
        ]
        .fillna(False)
        .astype(bool)
    )

    return resultado


# ============================================================
# BASE MAESTRA DE OPORTUNIDADES
# ============================================================

def construir_base_oportunidades(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    ciclos_retencion: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construye la base maestra para análisis de cohortes.

    Contiene:
    - 1K PANA;
    - 5K PANA;
    - 10K+ PANA y NOPANA.

    Unidad:
        una oportunidad por VIN + parque + hito.
    """

    fecha_max_datos = pd.Timestamp(
        fecha_max_datos
    ).normalize()

    parque_pana = (
        construir_parque_pana_cohortes(
            retail
        )
    )

    op_1k = (
        construir_oportunidad_1k(
            parque_pana=parque_pana,
            secuencia=secuencia,
            fecha_max_datos=fecha_max_datos,
        )
    )

    op_5k = (
        construir_oportunidad_5k(
            parque_pana=parque_pana,
            secuencia=secuencia,
            fecha_max_datos=fecha_max_datos,
        )
    )

    op_ciclo = (
        construir_oportunidades_ciclo(
            ciclos_retencion=
                ciclos_retencion,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    op_ciclo = (
        agregar_cohorte_entrega(
            oportunidades=op_ciclo,
            parque_pana=parque_pana,
        )
    )

    columnas_salida = [
        "vin",
        "parque",
        "modelo",
        "año",
        "sede",
        "asesor",
        "fecha_entrega",
        "cohorte_entrega_mes",
        "hito_km",
        "tipo_oportunidad",
        "fecha_origen",
        "fecha_esperada",
        "fecha_retorno",
        "retuvo",
        "adherencia",
        "puntualidad",
        "oportunidad_madura",
    ]

    bases = []

    for base in [
        op_1k,
        op_5k,
        op_ciclo,
    ]:

        temp = base.copy()

        for columna in columnas_salida:
            if columna not in temp.columns:
                temp[
                    columna
                ] = pd.NA

        bases.append(
            temp[
                columnas_salida
            ]
        )

    oportunidades = pd.concat(
        bases,
        ignore_index=True,
    )

    oportunidades = (
        estandarizar_oportunidades(
            oportunidades
        )
    )

    # --------------------------------------------------------
    # Control crítico de unicidad
    # --------------------------------------------------------

    duplicados = (
        oportunidades
        .duplicated(
            subset=[
                "vin",
                "parque",
                "hito_km",
            ]
        )
    )

    if duplicados.any():

        muestra = (
            oportunidades.loc[
                duplicados,
                [
                    "vin",
                    "parque",
                    "hito_km",
                ],
            ]
            .head(10)
        )

        raise ValueError(
            "La base de oportunidades contiene duplicados "
            "VIN + parque + hito.\n"
            f"{muestra.to_string(index=False)}"
        )

    return (
        oportunidades
        .sort_values(
            [
                "parque",
                "hito_km",
                "cohorte_mes",
                "vin",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )


# ============================================================
# BASE EVALUABLE
# ============================================================

def construir_base_evaluable(
    oportunidades: pd.DataFrame,
) -> pd.DataFrame:
    """
    Excluye oportunidades que todavía no han alcanzado
    su fecha esperada.

    No evaluable NO equivale a pérdida.
    """

    return (
        oportunidades.loc[
            oportunidades[
                "oportunidad_madura"
            ]
        ]
        .copy()
        .reset_index(drop=True)
    )


# ============================================================
# RETENCIÓN POR HITO
# ============================================================

def construir_retencion_hitos(
    base_evaluable: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume retención flexible por parque y hito.
    """

    if base_evaluable.empty:
        return pd.DataFrame()

    resumen = (
        base_evaluable
        .groupby(
            [
                "parque",
                "hito_km",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            oportunidades_evaluables=(
                "vin",
                "size",
            ),

            vehiculos_unicos=(
                "vin",
                "nunique",
            ),

            retornos=(
                "retuvo",
                "sum",
            ),
        )
    )

    resumen[
        "no_retorno"
    ] = (
        resumen[
            "oportunidades_evaluables"
        ]
        -
        resumen[
            "retornos"
        ]
    )

    resumen[
        "tasa_retencion"
    ] = (
        resumen[
            "retornos"
        ]
        /
        resumen[
            "oportunidades_evaluables"
        ]
    )

    return (
        resumen
        .sort_values(
            [
                "parque",
                "hito_km",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# RETENCIÓN POR COHORTE + HITO
# ============================================================

def construir_retencion_cohorte_hito(
    base_evaluable: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la tabla gerencial:

        COHORTE
        RETORNÓ
        FALTA
        TOTAL
        % RETENCIÓN

    La cohorte corresponde al mes en que el mantenimiento
    era esperado.
    """

    if base_evaluable.empty:
        return pd.DataFrame()

    resumen = (
        base_evaluable
        .groupby(
            [
                "parque",
                "hito_km",
                "cohorte_mes",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            total=(
                "vin",
                "size",
            ),

            retornos=(
                "retuvo",
                "sum",
            ),
        )
    )

    resumen[
        "falta"
    ] = (
        resumen[
            "total"
        ]
        -
        resumen[
            "retornos"
        ]
    )

    resumen[
        "tasa_retencion"
    ] = np.where(
        resumen[
            "total"
        ].gt(0),
        resumen[
            "retornos"
        ]
        /
        resumen[
            "total"
        ],
        np.nan,
    )

    resumen[
        "cohorte_txt"
    ] = (
        resumen[
            "cohorte_mes"
        ]
        .map(
            _etiqueta_periodo
        )
    )

    return (
        resumen
        .sort_values(
            [
                "parque",
                "hito_km",
                "cohorte_mes",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# MATRIZ COHORTE × MES DE RETORNO
# ============================================================

def construir_matriz_cohorte_retorno(
    base_evaluable: pd.DataFrame,
    parque: str,
    hito_km: int,
) -> pd.DataFrame:
    """
    Construye la matriz equivalente a la visualización
    gerencial del Excel.

    Filas:
        mes en que correspondía el mantenimiento.

    Columnas:
        mes real en que ocurrió el retorno.

    Incluye a la izquierda:
        RETORNÓ
        FALTA
        TOTAL
        % RETENCIÓN

    Esta función se utilizará dinámicamente desde Streamlit.
    """

    base = base_evaluable.loc[
        base_evaluable[
            "parque"
        ].eq(parque)
        &
        base_evaluable[
            "hito_km"
        ].eq(hito_km)
    ].copy()

    if base.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Resumen lateral
    # --------------------------------------------------------

    resumen = (
        base
        .groupby(
            "cohorte_mes",
            as_index=False,
            observed=True,
        )
        .agg(
            total=(
                "vin",
                "size",
            ),

            retornos=(
                "retuvo",
                "sum",
            ),
        )
    )

    resumen[
        "falta"
    ] = (
        resumen[
            "total"
        ]
        -
        resumen[
            "retornos"
        ]
    )

    resumen[
        "tasa_retencion"
    ] = np.where(
        resumen[
            "total"
        ].gt(0),
        resumen[
            "retornos"
        ]
        /
        resumen[
            "total"
        ],
        np.nan,
    )

    # --------------------------------------------------------
    # Distribución temporal de retornos
    # --------------------------------------------------------

    retornos = base.loc[
        base[
            "retuvo"
        ].eq(1)
        &
        base[
            "retorno_mes"
        ].notna()
    ].copy()

    if retornos.empty:

        matriz = (
            resumen.copy()
        )

    else:

        temporal = (
            retornos
            .groupby(
                [
                    "cohorte_mes",
                    "retorno_mes",
                ],
                observed=True,
            )
            .size()
            .unstack(
                fill_value=0
            )
        )

        temporal.columns = [
            _etiqueta_periodo(
                columna
            )
            for columna in temporal.columns
        ]

        temporal = (
            temporal
            .reset_index()
        )

        matriz = resumen.merge(
            temporal,
            on="cohorte_mes",
            how="left",
            validate="one_to_one",
        )

    # --------------------------------------------------------
    # Etiqueta de cohorte
    # --------------------------------------------------------

    matriz.insert(
        0,
        "COHORTE",
        matriz[
            "cohorte_mes"
        ]
        .map(
            _etiqueta_periodo
        ),
    )

    matriz = matriz.rename(
        columns={
            "retornos":
                "RETORNÓ",

            "falta":
                "FALTA",

            "total":
                "TOTAL",

            "tasa_retencion":
                "% RETENCIÓN",
        }
    )

    matriz = matriz.drop(
        columns=[
            "cohorte_mes",
        ]
    )

    columnas_fijas = [
        "COHORTE",
        "RETORNÓ",
        "FALTA",
        "TOTAL",
        "% RETENCIÓN",
    ]

    columnas_meses = [
        columna
        for columna in matriz.columns
        if columna
        not in columnas_fijas
    ]

    # Columnas temporales ya llegan cronológicamente
    # desde el pivot, pero garantizamos orden de salida.
    matriz = matriz[
        columnas_fijas
        +
        columnas_meses
    ]

    return matriz


# ============================================================
# SNAPSHOTS MENSUALES
# ============================================================

def construir_snapshots_hitos(
    oportunidades: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    meses: int = MESES_SNAPSHOTS,
) -> pd.DataFrame:
    """
    Reconstruye cómo se veía la retención al cierre de cada
    mes sin utilizar información futura.

    Si un retorno ocurrió después del snapshot, para ese
    snapshot todavía se considera no observado.
    """

    if oportunidades.empty:
        return pd.DataFrame()

    fecha_max_datos = pd.Timestamp(
        fecha_max_datos
    ).normalize()

    ultimo_snapshot = (
        fecha_max_datos
        .to_period("M")
        .to_timestamp("M")
    )

    primer_snapshot = (
        ultimo_snapshot
        -
        pd.DateOffset(
            months=meses - 1
        )
    )

    snapshots = pd.date_range(
        start=primer_snapshot,
        end=ultimo_snapshot,
        freq="ME",
    )

    # El último corte no debe superar la información real.
    snapshots = pd.DatetimeIndex(
        [
            min(
                fecha,
                fecha_max_datos,
            )
            for fecha in snapshots
        ]
    ).drop_duplicates()

    resultados = []

    for fecha_snapshot in snapshots:

        base = oportunidades.loc[
            oportunidades[
                "fecha_esperada"
            ]
            .le(
                fecha_snapshot
            )
        ].copy()

        if base.empty:
            continue

        base[
            "retuvo_snapshot"
        ] = (
            base[
                "fecha_retorno"
            ]
            .notna()
            &
            base[
                "fecha_retorno"
            ]
            .le(
                fecha_snapshot
            )
        ).astype("int8")

        resumen = (
            base
            .groupby(
                [
                    "parque",
                    "hito_km",
                ],
                as_index=False,
                observed=True,
            )
            .agg(
                oportunidades_evaluables=(
                    "vin",
                    "size",
                ),

                retornos=(
                    "retuvo_snapshot",
                    "sum",
                ),
            )
        )

        resumen[
            "no_retorno"
        ] = (
            resumen[
                "oportunidades_evaluables"
            ]
            -
            resumen[
                "retornos"
            ]
        )

        resumen[
            "tasa_retencion"
        ] = (
            resumen[
                "retornos"
            ]
            /
            resumen[
                "oportunidades_evaluables"
            ]
        )

        resumen[
            "fecha_snapshot"
        ] = (
            fecha_snapshot
        )

        resultados.append(
            resumen
        )

    if not resultados:
        return pd.DataFrame()

    snapshots_df = pd.concat(
        resultados,
        ignore_index=True,
    )

    snapshots_df = (
        snapshots_df
        .sort_values(
            [
                "parque",
                "hito_km",
                "fecha_snapshot",
            ]
        )
        .reset_index(drop=True)
    )

    snapshots_df[
        "tasa_snapshot_anterior"
    ] = (
        snapshots_df
        .groupby(
            [
                "parque",
                "hito_km",
            ]
        )[
            "tasa_retencion"
        ]
        .shift(1)
    )

    snapshots_df[
        "variacion_pp"
    ] = (
        (
            snapshots_df[
                "tasa_retencion"
            ]
            -
            snapshots_df[
                "tasa_snapshot_anterior"
            ]
        )
        *
        100
    )

    return snapshots_df


# ============================================================
# AUDITORÍA
# ============================================================

def auditar_cohortes(
    oportunidades: pd.DataFrame,
    base_evaluable: pd.DataFrame,
) -> pd.DataFrame:
    """
    Controles estructurales del módulo de cohortes.
    """

    duplicados = int(
        oportunidades
        .duplicated(
            [
                "vin",
                "parque",
                "hito_km",
            ]
        )
        .sum()
    )

    oportunidades_pana = int(
        oportunidades[
            "parque"
        ]
        .eq("PANA")
        .sum()
    )

    oportunidades_nopana = int(
        oportunidades[
            "parque"
        ]
        .eq("NOPANA")
        .sum()
    )

    return pd.DataFrame(
        [
            {
                "metrica":
                    "oportunidades_totales",

                "valor":
                    len(oportunidades),
            },
            {
                "metrica":
                    "oportunidades_evaluables",

                "valor":
                    len(base_evaluable),
            },
            {
                "metrica":
                    "oportunidades_no_maduras",

                "valor":
                    len(oportunidades)
                    -
                    len(base_evaluable),
            },
            {
                "metrica":
                    "oportunidades_pana",

                "valor":
                    oportunidades_pana,
            },
            {
                "metrica":
                    "oportunidades_nopana",

                "valor":
                    oportunidades_nopana,
            },
            {
                "metrica":
                    "vin_unicos",

                "valor":
                    oportunidades[
                        "vin"
                    ]
                    .nunique(),
            },
            {
                "metrica":
                    "duplicados_vin_parque_hito",

                "valor":
                    duplicados,
            },
            {
                "metrica":
                    "hitos_disponibles",

                "valor":
                    oportunidades[
                        "hito_km"
                    ]
                    .nunique(),
            },
        ]
    )


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def construir_cohortes_retencion(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    ciclos_retencion: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> dict:
    """
    Punto de entrada oficial del módulo de Cohortes.

    Produce:
    - parque PANA;
    - base maestra de oportunidades;
    - oportunidades evaluables;
    - retención por hito;
    - retención por cohorte + hito;
    - snapshots mensuales;
    - auditoría.

    La matriz temporal se construirá dinámicamente desde
    Streamlit mediante construir_matriz_cohorte_retorno().
    """

    parque_pana = (
        construir_parque_pana_cohortes(
            retail
        )
    )

    oportunidades = (
        construir_base_oportunidades(
            retail=retail,
            secuencia=secuencia,
            ciclos_retencion=
                ciclos_retencion,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    base_evaluable = (
        construir_base_evaluable(
            oportunidades
        )
    )

    retencion_hitos = (
        construir_retencion_hitos(
            base_evaluable
        )
    )

    retencion_cohorte_hito = (
        construir_retencion_cohorte_hito(
            base_evaluable
        )
    )

    snapshots_hitos = (
        construir_snapshots_hitos(
            oportunidades=
                oportunidades,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    auditoria = (
        auditar_cohortes(
            oportunidades=
                oportunidades,
            base_evaluable=
                base_evaluable,
        )
    )

    return {
        "parque_pana":
            parque_pana,

        "oportunidades":
            oportunidades,

        "base_evaluable":
            base_evaluable,

        "retencion_hitos":
            retencion_hitos,

        "retencion_cohorte_hito":
            retencion_cohorte_hito,

        "snapshots_hitos":
            snapshots_hitos,

        "auditoria_cohortes":
            auditoria,
    }