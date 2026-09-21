from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

KM_INICIAL = 1
KM_PRIMER_CICLO = 5
PASO_KM = 5


# ============================================================
# HELPERS
# ============================================================

def _validar_columnas(
    df: pd.DataFrame,
    columnas: list[str],
    nombre: str,
) -> None:
    """
    Valida el contrato mínimo requerido.
    """

    faltantes = [
        columna
        for columna in columnas
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Faltan columnas en {nombre}: {faltantes}"
        )


def _km_numero(
    valor,
) -> int | None:
    """
    Convierte un mantenimiento a entero cuando sea posible.
    """

    if pd.isna(valor):
        return None

    return int(
        round(
            float(valor)
        )
    )


def _crear_hitos(
    km_maximo: int,
) -> list[int]:
    """
    Construye:

        1K, 5K, 10K, 15K, ...

    hasta el máximo solicitado.
    """

    if km_maximo < 1:
        return []

    hitos = [1]

    if km_maximo >= 5:

        hitos.extend(
            range(
                5,
                km_maximo + 1,
                PASO_KM,
            )
        )

    return hitos


def _etiqueta_hito(
    km: int,
) -> str:
    """
    Convierte 15 -> 15K.
    """

    return f"{km}K"


# ============================================================
# RETAIL PANA
# ============================================================

def construir_base_pana(
    retail: pd.DataFrame,
    base_demanda: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la cabecera de la matriz PANA.

    Retail aporta la fecha original de entrega.
    BASE_DEMANDA aporta la situación operacional actual
    del VIN y el cliente actualmente asociado.
    """

    _validar_columnas(
        retail,
        [
            "vin",
            "fecha_entrega",
            "modelo",
        ],
        "retail",
    )

    _validar_columnas(
        base_demanda,
        [
            "vin",
            "parque",
            "placa",
            "modelo",
            "nro_documento",
            "nombre",
            "kilometraje_esperado_actual",
            "fecha_politica",
            "fecha_generacion",
        ],
        "base_demanda",
    )

    retail_pana = (
        retail.loc[
            retail["vin"].notna(),
            [
                "vin",
                "fecha_entrega",
                "modelo",
            ],
        ]
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

    demanda_pana = (
        base_demanda.loc[
            base_demanda[
                "parque"
            ].eq("PANA"),
            [
                "vin",
                "placa",
                "modelo",
                "nro_documento",
                "nombre",
                "kilometraje_esperado_actual",
                "fecha_politica",
                "fecha_generacion",
                "estado_politica",
            ],
        ]
        .copy()
    )

    base = retail_pana.merge(
        demanda_pana,
        on="vin",
        how="left",
        suffixes=(
            "_retail",
            "_actual",
        ),
        validate="one_to_one",
    )

    base[
        "modelo"
    ] = (
        base[
            "modelo_actual"
        ]
        .combine_first(
            base[
                "modelo_retail"
            ]
        )
    )

    base[
        "fecha_entrega"
    ] = pd.to_datetime(
        base[
            "fecha_entrega"
        ],
        errors="coerce",
    )

    base[
        "fecha_politica"
    ] = pd.to_datetime(
        base[
            "fecha_politica"
        ],
        errors="coerce",
    )

    base[
        "fecha_generacion"
    ] = pd.to_datetime(
        base[
            "fecha_generacion"
        ],
        errors="coerce",
    )

    return (
        base[
            [
                "vin",
                "fecha_entrega",
                "placa",
                "modelo",
                "nro_documento",
                "nombre",
                "kilometraje_esperado_actual",
                "fecha_politica",
                "fecha_generacion",
                "estado_politica",
            ]
        ]
        .sort_values(
            [
                "fecha_entrega",
                "vin",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )


# ============================================================
# HISTORIA REAL POR HITO
# ============================================================

def construir_historia_hitos_pana(
    secuencia: pd.DataFrame,
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una fila por:

        VIN + hito efectivamente realizado.

    Para 1K:
        días = visita - entrega.

    Para 5K+:
        días = visita - preventivo anterior observado.

    Si un mismo hito aparece más de una vez, conserva la
    primera ejecución histórica de ese hito para la matriz.
    """

    _validar_columnas(
        secuencia,
        [
            "vin",
            "parque",
            "fecha_visita",
            "mantenimiento_km",
            "fecha_visita_anterior",
            "dias_desde_visita_anterior",
        ],
        "secuencia",
    )

    pana = (
        secuencia.loc[
            secuencia[
                "parque"
            ].eq("PANA")
        ]
        .copy()
    )

    entregas = (
        retail.loc[
            retail[
                "vin"
            ].notna(),
            [
                "vin",
                "fecha_entrega",
            ],
        ]
        .drop_duplicates(
            subset=["vin"],
            keep="last",
        )
    )

    pana = pana.merge(
        entregas,
        on="vin",
        how="left",
        validate="many_to_one",
    )

    pana[
        "hito_km"
    ] = (
        pd.to_numeric(
            pana[
                "mantenimiento_km"
            ],
            errors="coerce",
        )
        .round()
        .astype("Int64")
    )

    pana[
        "dias_desde_ancla"
    ] = (
        pana[
            "dias_desde_visita_anterior"
        ]
    )

    # --------------------------------------------------------
    # 1K usa entrega como ancla
    # --------------------------------------------------------

    mask_1k = (
        pana[
            "hito_km"
        ].eq(1)
        &
        pana[
            "fecha_entrega"
        ].notna()
    )

    pana.loc[
        mask_1k,
        "dias_desde_ancla",
    ] = (
        pana.loc[
            mask_1k,
            "fecha_visita",
        ]
        -
        pana.loc[
            mask_1k,
            "fecha_entrega",
        ]
    ).dt.days

    pana = (
        pana
        .dropna(
            subset=[
                "hito_km",
                "fecha_visita",
            ]
        )
        .sort_values(
            [
                "vin",
                "hito_km",
                "fecha_visita",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "vin",
                "hito_km",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return pana[
        [
            "vin",
            "hito_km",
            "fecha_visita",
            "dias_desde_ancla",
        ]
    ]


# ============================================================
# HITOS SALTADOS
# ============================================================

def construir_hitos_saltados_pana(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identifica mantenimientos omitidos con evidencia real.

    Ejemplos:

        5K -> 15K
            genera 10K como SALTADO.

        10K -> 25K
            genera 15K y 20K como SALTADOS.

    No infiere saltos solo por atraso temporal.
    """

    _validar_columnas(
        secuencia,
        [
            "vin",
            "parque",
            "mantenimiento_anterior",
            "mantenimiento_km",
            "comportamiento",
        ],
        "secuencia",
    )

    saltos = (
        secuencia.loc[
            secuencia[
                "parque"
            ].eq("PANA")
            &
            secuencia[
                "comportamiento"
            ].eq(
                "SALTA_MANTENIMIENTOS"
            )
        ]
        .copy()
    )

    filas = []

    for fila in saltos.itertuples(
        index=False
    ):

        anterior = _km_numero(
            fila.mantenimiento_anterior
        )

        actual = _km_numero(
            fila.mantenimiento_km
        )

        if (
            anterior is None
            or actual is None
            or actual <= anterior
        ):
            continue

        # ----------------------------------------------------
        # Transición especial 1K -> 5K
        # ----------------------------------------------------

        if anterior == 1:
            siguiente = 5
        else:
            siguiente = (
                anterior
                + PASO_KM
            )

        while siguiente < actual:

            filas.append(
                {
                    "vin":
                        fila.vin,

                    "hito_km":
                        siguiente,
                }
            )

            siguiente += PASO_KM

    if not filas:
        return pd.DataFrame(
            columns=[
                "vin",
                "hito_km",
            ]
        )

    return (
        pd.DataFrame(
            filas
        )
        .drop_duplicates(
            subset=[
                "vin",
                "hito_km",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# ESTADO ACTUAL
# ============================================================

def construir_estado_actual_pana(
    base_pana: pd.DataFrame,
) -> pd.DataFrame:
    """
    Determina el hito actualmente esperado y los días
    respecto de su fecha política.

    Convención visual:

        negativo = días de atraso
        positivo = días restantes
        cero     = fecha política actual
    """

    base = (
        base_pana.copy()
    )

    base[
        "hito_actual_km"
    ] = (
        pd.to_numeric(
            base[
                "kilometraje_esperado_actual"
            ],
            errors="coerce",
        )
        .round()
        .astype("Int64")
    )

    base[
        "dias_hasta_politica"
    ] = (
        base[
            "fecha_politica"
        ]
        -
        base[
            "fecha_generacion"
        ]
    ).dt.days.astype(
        "Int64"
    )

    return base[
        [
            "vin",
            "hito_actual_km",
            "dias_hasta_politica",
            "fecha_politica",
            "estado_politica",
        ]
    ]


# ============================================================
# MATRIZ DETALLADA PANA
# ============================================================

def construir_matriz_pana(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    base_demanda: pd.DataFrame,
    km_maximo: int | None = None,
) -> pd.DataFrame:
    """
    Construye la matriz operacional solicitada por Gerencia.

    Semántica:

        ✔️ (186)
            mantenimiento realizado;
            186 días desde la ancla anterior.

        ❌
            mantenimiento efectivamente saltado.

        -8
            mantenimiento actualmente esperado;
            8 días de atraso político.

        15
            mantenimiento actualmente esperado;
            faltan 15 días para su fecha política.

    Las columnas posteriores al mantenimiento actual
    permanecen vacías.
    """

    base_pana = construir_base_pana(
        retail=retail,
        base_demanda=base_demanda,
    )

    historia = (
        construir_historia_hitos_pana(
            secuencia=secuencia,
            retail=retail,
        )
    )

    saltados = (
        construir_hitos_saltados_pana(
            secuencia
        )
    )

    actual = (
        construir_estado_actual_pana(
            base_pana
        )
    )

    # --------------------------------------------------------
    # Determinar KM máximo a mostrar
    # --------------------------------------------------------

    max_historia = (
        historia[
            "hito_km"
        ]
        .max()
        if not historia.empty
        else 0
    )

    max_actual = (
        actual[
            "hito_actual_km"
        ]
        .max()
        if not actual.empty
        else 0
    )

    max_detectado = max(
        int(max_historia)
        if pd.notna(max_historia)
        else 0,
        int(max_actual)
        if pd.notna(max_actual)
        else 0,
    )

    if km_maximo is None:
        km_maximo = max_detectado

    km_maximo = max(
        int(km_maximo),
        1,
    )

    hitos = _crear_hitos(
        km_maximo
    )

    # --------------------------------------------------------
    # Diccionarios para acceso rápido
    # --------------------------------------------------------

    historia_lookup = {
        (
            fila.vin,
            int(fila.hito_km),
        ): fila
        for fila in historia.itertuples(
            index=False
        )
    }

    saltados_lookup = set(
        zip(
            saltados[
                "vin"
            ],
            saltados[
                "hito_km"
            ],
        )
    )

    actual_lookup = {
        fila.vin: fila
        for fila in actual.itertuples(
            index=False
        )
    }

    # --------------------------------------------------------
    # Construcción de la matriz
    # --------------------------------------------------------

    filas = []

    for vehiculo in base_pana.itertuples(
        index=False
    ):

        fila_salida = {
            "Fecha entrega":
                vehiculo.fecha_entrega,

            "VIN":
                vehiculo.vin,

            "Placa":
                vehiculo.placa,

            "Modelo":
                vehiculo.modelo,

            "Nro documento":
                vehiculo.nro_documento,

            "Nombre cliente":
                vehiculo.nombre,
        }

        estado_actual = (
            actual_lookup.get(
                vehiculo.vin
            )
        )

        hito_actual = (
            _km_numero(
                estado_actual.hito_actual_km
            )
            if estado_actual is not None
            else None
        )

        dias_actuales = (
            estado_actual.dias_hasta_politica
            if estado_actual is not None
            else pd.NA
        )

        for hito in hitos:

            columna = (
                _etiqueta_hito(
                    hito
                )
            )

            clave = (
                vehiculo.vin,
                hito,
            )

            # ------------------------------------------------
            # 1. Hito efectivamente realizado
            # ------------------------------------------------

            if clave in historia_lookup:

                evento = (
                    historia_lookup[
                        clave
                    ]
                )

                dias = (
                    evento.dias_desde_ancla
                )

                if pd.notna(dias):

                    fila_salida[
                        columna
                    ] = (
                        f"✔️ ({int(dias)})"
                    )

                else:

                    fila_salida[
                        columna
                    ] = "✔️"

                continue

            # ------------------------------------------------
            # 2. Hito efectivamente saltado
            # ------------------------------------------------

            if clave in saltados_lookup:

                fila_salida[
                    columna
                ] = "❌"

                continue

            # ------------------------------------------------
            # 3. Hito actualmente esperado
            # ------------------------------------------------

            if (
                hito_actual is not None
                and hito == hito_actual
                and pd.notna(
                    dias_actuales
                )
            ):

                fila_salida[
                    columna
                ] = str(
                    int(
                        dias_actuales
                    )
                )

                continue

            # ------------------------------------------------
            # 4. Sin evento / aún no corresponde
            # ------------------------------------------------

            fila_salida[
                columna
            ] = ""

        filas.append(
            fila_salida
        )

    matriz = pd.DataFrame(
        filas
    )

    return (
        matriz
        .sort_values(
            [
                "Fecha entrega",
                "VIN",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )


# ============================================================
# BASE LARGA PARA STREAMLIT
# ============================================================

def construir_detalle_pana_largo(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    base_demanda: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una versión larga y estructurada de la matriz.

    Streamlit utilizará esta base para filtros, tooltips y
    estilos sin tener que interpretar strings de la matriz.
    """

    base_pana = construir_base_pana(
        retail=retail,
        base_demanda=base_demanda,
    )

    historia = construir_historia_hitos_pana(
        secuencia=secuencia,
        retail=retail,
    )

    saltados = construir_hitos_saltados_pana(
        secuencia
    )

    actual = construir_estado_actual_pana(
        base_pana
    )

    partes = []

    # --------------------------------------------------------
    # Realizados
    # --------------------------------------------------------

    if not historia.empty:

        realizados = (
            historia.copy()
        )

        realizados[
            "estado_hito"
        ] = "REALIZADO"

        partes.append(
            realizados
        )

    # --------------------------------------------------------
    # Saltados
    # --------------------------------------------------------

    if not saltados.empty:

        saltos = (
            saltados.copy()
        )

        saltos[
            "estado_hito"
        ] = "SALTADO"

        saltos[
            "fecha_visita"
        ] = pd.NaT

        saltos[
            "dias_desde_ancla"
        ] = pd.NA

        partes.append(
            saltos
        )

    # --------------------------------------------------------
    # Actual
    # --------------------------------------------------------

    actual_largo = (
        actual.loc[
            actual[
                "hito_actual_km"
            ]
            .notna()
        ]
        .rename(
            columns={
                "hito_actual_km":
                    "hito_km",
            }
        )
        .copy()
    )

    actual_largo[
        "estado_hito"
    ] = np.where(
        actual_largo[
            "dias_hasta_politica"
        ].lt(0),
        "ACTUAL_ATRASADO",
        "ACTUAL_FUTURO",
    )

    actual_largo[
        "fecha_visita"
    ] = pd.NaT

    actual_largo[
        "dias_desde_ancla"
    ] = pd.NA

    partes.append(
        actual_largo
    )

    if not partes:
        return pd.DataFrame()

    detalle = pd.concat(
        partes,
        ignore_index=True,
        sort=False,
    )

    detalle = detalle.merge(
        base_pana[
            [
                "vin",
                "fecha_entrega",
                "placa",
                "modelo",
                "nro_documento",
                "nombre",
            ]
        ],
        on="vin",
        how="left",
        validate="many_to_one",
    )

    return (
        detalle
        .sort_values(
            [
                "fecha_entrega",
                "vin",
                "hito_km",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )


# ============================================================
# AUDITORÍA
# ============================================================

def auditar_matriz_pana(
    base_pana: pd.DataFrame,
    historia: pd.DataFrame,
    saltados: pd.DataFrame,
    detalle: pd.DataFrame,
) -> pd.DataFrame:
    """
    Controles básicos de consistencia.
    """

    return pd.DataFrame(
        [
            {
                "metrica":
                    "vin_pana",

                "valor":
                    base_pana[
                        "vin"
                    ]
                    .nunique(),
            },
            {
                "metrica":
                    "hitos_realizados",

                "valor":
                    len(
                        historia
                    ),
            },
            {
                "metrica":
                    "hitos_saltados_detectados",

                "valor":
                    len(
                        saltados
                    ),
            },
            {
                "metrica":
                    "vin_con_hitos_saltados",

                "valor":
                    saltados[
                        "vin"
                    ]
                    .nunique()
                    if not saltados.empty
                    else 0,
            },
            {
                "metrica":
                    "duplicados_detalle_vin_hito_estado",

                "valor":
                    int(
                        detalle
                        .duplicated(
                            subset=[
                                "vin",
                                "hito_km",
                                "estado_hito",
                            ]
                        )
                        .sum()
                    ),
            },
        ]
    )


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def construir_analisis_pana(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    base_demanda: pd.DataFrame,
    km_maximo_matriz: int | None = None,
) -> dict:
    """
    Punto de entrada oficial de la vista Parque PANA.
    """

    base_pana = construir_base_pana(
        retail=retail,
        base_demanda=base_demanda,
    )

    historia = construir_historia_hitos_pana(
        secuencia=secuencia,
        retail=retail,
    )

    saltados = construir_hitos_saltados_pana(
        secuencia
    )

    matriz = construir_matriz_pana(
        retail=retail,
        secuencia=secuencia,
        base_demanda=base_demanda,
        km_maximo=km_maximo_matriz,
    )

    detalle = construir_detalle_pana_largo(
        retail=retail,
        secuencia=secuencia,
        base_demanda=base_demanda,
    )

    auditoria = auditar_matriz_pana(
        base_pana=base_pana,
        historia=historia,
        saltados=saltados,
        detalle=detalle,
    )

    return {
        "base_pana":
            base_pana,

        "historia_hitos_pana":
            historia,

        "hitos_saltados_pana":
            saltados,

        "matriz_pana":
            matriz,

        "detalle_pana":
            detalle,

        "auditoria_pana":
            auditoria,
    }