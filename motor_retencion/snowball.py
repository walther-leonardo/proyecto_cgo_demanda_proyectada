from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

MESES_SNOWBALL = 36
MESES_VIGENCIA = 6


# ============================================================
# HELPERS
# ============================================================

def _validar_columnas(
    df: pd.DataFrame,
    columnas: list[str],
    nombre: str,
) -> None:
    """
    Valida que un DataFrame contenga las columnas mínimas
    requeridas por el módulo Snowball.
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


def _fin_mes(
    fecha,
) -> pd.Timestamp:
    """
    Lleva una fecha al último día de su mes.
    """

    return (
        pd.Timestamp(fecha)
        .to_period("M")
        .to_timestamp("M")
    )


# ============================================================
# PARQUE COMERCIAL BASE
# ============================================================

def construir_parque_comercial(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye el parque comercial observado.

    PANA:
        todos los VIN vendidos en Retail.

    NOPANA:
        VIN observados en la historia preventiva que no
        pertenecen a Retail.

    Para cada VIN se define una fecha de alta comercial:

    PANA:
        fecha_entrega.

    NOPANA:
        primera visita preventiva analítica observada.
    """

    _validar_columnas(
        retail,
        [
            "vin",
            "fecha_entrega",
            "modelo",
            "año",
            "sede",
            "asesor",
        ],
        "retail",
    )

    _validar_columnas(
        secuencia,
        [
            "vin",
            "parque",
            "fecha_visita",
            "modelo",
            "año",
            "sede",
            "asesor",
        ],
        "secuencia",
    )

    # --------------------------------------------------------
    # PANA
    # --------------------------------------------------------

    columnas_retail = [
        "vin",
        "fecha_entrega",
        "modelo",
        "año",
        "sede",
        "asesor",
    ]

    if "nro documento" in retail.columns:
        columnas_retail.append(
            "nro documento"
        )

    pana = (
        retail[
            columnas_retail
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

    pana[
        "parque"
    ] = "PANA"

    pana[
        "fecha_alta_comercial"
    ] = pd.to_datetime(
        pana[
            "fecha_entrega"
        ],
        errors="coerce",
    )

    # --------------------------------------------------------
    # NOPANA
    # --------------------------------------------------------

    nopana_base = (
        secuencia.loc[
            secuencia[
                "parque"
            ].eq("NOPANA")
        ]
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ],
            kind="stable",
        )
    )

    nopana = (
        nopana_base
        .groupby(
            "vin",
            as_index=False,
            sort=False,
        )
        .agg(
            fecha_alta_comercial=(
                "fecha_visita",
                "min",
            ),

            modelo=(
                "modelo",
                "last",
            ),

            año=(
                "año",
                "last",
            ),

            sede=(
                "sede",
                "last",
            ),

            asesor=(
                "asesor",
                "last",
            ),
        )
    )

    nopana[
        "parque"
    ] = "NOPANA"

    nopana[
        "fecha_entrega"
    ] = pd.NaT

    if "nro documento" in pana.columns:

        nopana[
            "nro documento"
        ] = pd.NA

    # --------------------------------------------------------
    # Contrato común
    # --------------------------------------------------------

    columnas_salida = [
        "vin",
        "parque",
        "fecha_alta_comercial",
        "fecha_entrega",
        "modelo",
        "año",
        "sede",
        "asesor",
    ]

    if "nro documento" in pana.columns:
        columnas_salida.append(
            "nro documento"
        )

    for columna in columnas_salida:

        if columna not in pana.columns:
            pana[columna] = pd.NA

        if columna not in nopana.columns:
            nopana[columna] = pd.NA

    parque = pd.concat(
        [
            pana[
                columnas_salida
            ],
            nopana[
                columnas_salida
            ],
        ],
        ignore_index=True,
    )

    if parque[
        "vin"
    ].duplicated().any():

        raise ValueError(
            "El parque comercial contiene VIN duplicados."
        )

    return (
        parque
        .sort_values(
            [
                "parque",
                "fecha_alta_comercial",
                "vin",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# ANCLAS PREVENTIVAS
# ============================================================

def construir_anclas_preventivas(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una tabla cronológica de visitas preventivas
    por VIN.

    Estas visitas funcionan como anclas para saber si un
    vehículo estaba vigente en cada snapshot histórico.
    """

    columnas = [
        "vin",
        "parque",
        "fecha_visita",
        "modelo",
        "año",
        "sede",
        "asesor",
        "mantenimiento_km",
    ]

    _validar_columnas(
        secuencia,
        columnas,
        "secuencia",
    )

    anclas = (
        secuencia[
            columnas
        ]
        .dropna(
            subset=[
                "vin",
                "fecha_visita",
            ]
        )
        .sort_values(
            [
                "vin",
                "fecha_visita",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return anclas


# ============================================================
# REACTIVACIONES HISTÓRICAS
# ============================================================

def construir_reactivaciones(
    anclas: pd.DataFrame,
    meses_vigencia: int = MESES_VIGENCIA,
) -> pd.DataFrame:
    """
    Identifica visitas que reactivan un VIN que ya había
    vencido.

    Una visita es reactivación cuando:

        fecha visita actual
        >
        fecha visita anterior + meses_vigencia

    La primera visita nunca es reactivación.
    """

    if anclas.empty:
        return pd.DataFrame()

    resultado = (
        anclas.copy()
    )

    resultado[
        "fecha_visita_anterior"
    ] = (
        resultado
        .groupby(
            "vin",
            sort=False,
        )[
            "fecha_visita"
        ]
        .shift(1)
    )

    resultado[
        "fecha_vencimiento_anterior"
    ] = (
        resultado[
            "fecha_visita_anterior"
        ]
        +
        pd.DateOffset(
            months=meses_vigencia
        )
    )

    resultado[
        "es_reactivacion"
    ] = (
        resultado[
            "fecha_visita_anterior"
        ]
        .notna()
        &
        resultado[
            "fecha_visita"
        ]
        .gt(
            resultado[
                "fecha_vencimiento_anterior"
            ]
        )
    )

    return resultado


# ============================================================
# ESTADO DEL VIN EN UN SNAPSHOT
# ============================================================

def construir_estado_snapshot(
    parque_comercial: pd.DataFrame,
    anclas: pd.DataFrame,
    fecha_snapshot: pd.Timestamp,
    meses_vigencia: int = MESES_VIGENCIA,
) -> pd.DataFrame:
    """
    Reconstruye el estado de cada VIN en una fecha histórica.

    Vigente:
        tuvo una visita preventiva cuya vigencia de 6 meses
        todavía alcanzaba al snapshot.

    PANA sin visitas:
        puede existir en parque acumulado desde la entrega,
        pero permanece vencido/no vigente si ya transcurrió
        la ventana sin una visita preventiva.

    NOPANA:
        entra al parque desde su primera visita preventiva.
    """

    fecha_snapshot = pd.Timestamp(
        fecha_snapshot
    ).normalize()

    parque = parque_comercial.loc[
        parque_comercial[
            "fecha_alta_comercial"
        ]
        .le(
            fecha_snapshot
        )
    ].copy()

    if parque.empty:
        return parque

    visitas_hasta_snapshot = (
        anclas.loc[
            anclas[
                "fecha_visita"
            ]
            .le(
                fecha_snapshot
            )
        ]
        .sort_values(
            [
                "vin",
                "fecha_visita",
            ],
            kind="stable",
        )
        .groupby(
            "vin",
            as_index=False,
        )
        .tail(1)
        .loc[
            :,
            [
                "vin",
                "fecha_visita",
            ],
        ]
        .rename(
            columns={
                "fecha_visita":
                    "ultima_visita_snapshot",
            }
        )
    )

    estado = parque.merge(
        visitas_hasta_snapshot,
        on="vin",
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # Ancla de vigencia
    #
    # Si existe preventivo:
    #     última visita preventiva.
    #
    # Si PANA aún no tuvo preventivo:
    #     fecha de entrega.
    # --------------------------------------------------------

    estado[
        "fecha_ancla_vigencia"
    ] = (
        estado[
            "ultima_visita_snapshot"
        ]
    )

    mask_pana_sin_visita = (
        estado[
            "parque"
        ].eq("PANA")
        &
        estado[
            "ultima_visita_snapshot"
        ]
        .isna()
    )

    estado.loc[
        mask_pana_sin_visita,
        "fecha_ancla_vigencia",
    ] = (
        estado.loc[
            mask_pana_sin_visita,
            "fecha_entrega",
        ]
    )

    estado[
        "fecha_vencimiento"
    ] = (
        estado[
            "fecha_ancla_vigencia"
        ]
        +
        pd.DateOffset(
            months=meses_vigencia
        )
    )

    estado[
        "vigente"
    ] = (
        estado[
            "fecha_ancla_vigencia"
        ]
        .notna()
        &
        estado[
            "fecha_vencimiento"
        ]
        .ge(
            fecha_snapshot
        )
    )

    estado[
        "estado_parque"
    ] = np.where(
        estado[
            "vigente"
        ],
        "VIGENTE",
        "VENCIDO",
    )

    estado[
        "snapshot"
    ] = fecha_snapshot

    return estado


# ============================================================
# SNAPSHOTS DEL PARQUE
# ============================================================

def construir_snapshots_parque(
    parque_comercial: pd.DataFrame,
    anclas: pd.DataFrame,
    reactivaciones: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    meses: int = MESES_SNOWBALL,
    meses_vigencia: int = MESES_VIGENCIA,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construye snapshots mensuales del parque comercial.

    Devuelve:
    - snapshot general por parque;
    - último estado de cada VIN.
    """

    fecha_max_datos = pd.Timestamp(
        fecha_max_datos
    ).normalize()

    ultimo_snapshot = _fin_mes(
        fecha_max_datos
    )

    primer_snapshot = (
        ultimo_snapshot
        -
        pd.DateOffset(
            months=meses - 1
        )
    )

    fechas_snapshot = pd.date_range(
        start=primer_snapshot,
        end=ultimo_snapshot,
        freq="ME",
    )

    # Si el último mes está incompleto usamos la fecha real
    # disponible, no un día futuro.
    fechas_snapshot = [
        min(
            fecha,
            fecha_max_datos,
        )
        for fecha in fechas_snapshot
    ]

    fechas_snapshot = sorted(
        set(
            pd.Timestamp(
                fecha
            ).normalize()
            for fecha in fechas_snapshot
        )
    )

    filas_resumen = []
    estados = []

    for fecha_snapshot in fechas_snapshot:

        estado = (
            construir_estado_snapshot(
                parque_comercial=
                    parque_comercial,
                anclas=
                    anclas,
                fecha_snapshot=
                    fecha_snapshot,
                meses_vigencia=
                    meses_vigencia,
            )
        )

        if estado.empty:
            continue

        estados.append(
            estado
        )

        mes_inicio = (
            pd.Timestamp(
                fecha_snapshot
            )
            .to_period("M")
            .to_timestamp()
        )

        # ----------------------------------------------------
        # Altas del mes
        # ----------------------------------------------------

        altas = (
            parque_comercial.loc[
                parque_comercial[
                    "fecha_alta_comercial"
                ]
                .between(
                    mes_inicio,
                    fecha_snapshot,
                    inclusive="both",
                )
            ]
            .groupby(
                "parque"
            )[
                "vin"
            ]
            .nunique()
        )

        # ----------------------------------------------------
        # Reactivaciones del mes
        # ----------------------------------------------------

        reactivaciones_mes = (
            reactivaciones.loc[
                reactivaciones[
                    "es_reactivacion"
                ]
                &
                reactivaciones[
                    "fecha_visita"
                ]
                .between(
                    mes_inicio,
                    fecha_snapshot,
                    inclusive="both",
                )
            ]
            .groupby(
                "parque"
            )[
                "vin"
            ]
            .nunique()
        )

        # ----------------------------------------------------
        # Resumen por parque
        # ----------------------------------------------------

        for parque, grupo in estado.groupby(
            "parque",
            sort=False,
        ):

            parque_acumulado = (
                grupo[
                    "vin"
                ]
                .nunique()
            )

            parque_vigente = (
                grupo.loc[
                    grupo[
                        "vigente"
                    ],
                    "vin",
                ]
                .nunique()
            )

            parque_vencido = (
                parque_acumulado
                -
                parque_vigente
            )

            filas_resumen.append(
                {
                    "snapshot":
                        fecha_snapshot,

                    "parque":
                        parque,

                    "parque_acumulado":
                        int(
                            parque_acumulado
                        ),

                    "parque_vigente":
                        int(
                            parque_vigente
                        ),

                    "parque_vencido":
                        int(
                            parque_vencido
                        ),

                    "altas_mes":
                        int(
                            altas.get(
                                parque,
                                0,
                            )
                        ),

                    "reactivaciones_mes":
                        int(
                            reactivaciones_mes.get(
                                parque,
                                0,
                            )
                        ),
                }
            )

    if not filas_resumen:
        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    resumen = pd.DataFrame(
        filas_resumen
    )

    resumen = (
        resumen
        .sort_values(
            [
                "parque",
                "snapshot",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Nuevos vencidos y saldo
    #
    # Identidad:
    #
    # Vigente_t
    # =
    # Vigente_t-1
    # + altas
    # + reactivaciones
    # - nuevos vencidos
    # --------------------------------------------------------

    resumen[
        "parque_vigente_anterior"
    ] = (
        resumen
        .groupby(
            "parque"
        )[
            "parque_vigente"
        ]
        .shift(1)
    )

    resumen[
        "nuevos_vencidos_mes"
    ] = (
        resumen[
            "parque_vigente_anterior"
        ]
        +
        resumen[
            "altas_mes"
        ]
        +
        resumen[
            "reactivaciones_mes"
        ]
        -
        resumen[
            "parque_vigente"
        ]
    )

    # El primer snapshot no tiene snapshot anterior.
    resumen.loc[
        resumen[
            "parque_vigente_anterior"
        ]
        .isna(),
        "nuevos_vencidos_mes",
    ] = np.nan

    resumen[
        "saldo_flujo_vigente"
    ] = (
        resumen[
            "altas_mes"
        ]
        +
        resumen[
            "reactivaciones_mes"
        ]
        -
        resumen[
            "nuevos_vencidos_mes"
        ]
    )

    resumen[
        "variacion_vigente"
    ] = (
        resumen[
            "parque_vigente"
        ]
        -
        resumen[
            "parque_vigente_anterior"
        ]
    )

    resumen[
        "tasa_parque_vigente"
    ] = np.where(
        resumen[
            "parque_acumulado"
        ].gt(0),
        resumen[
            "parque_vigente"
        ]
        /
        resumen[
            "parque_acumulado"
        ],
        np.nan,
    )

    # --------------------------------------------------------
    # Índice Snowball base 100
    #
    # Cada parque parte de 100 en su primer snapshot.
    # --------------------------------------------------------

    resumen[
        "parque_vigente_base"
    ] = (
        resumen
        .groupby(
            "parque"
        )[
            "parque_vigente"
        ]
        .transform("first")
    )

    resumen[
        "indice_snowball"
    ] = np.where(
        resumen[
            "parque_vigente_base"
        ].gt(0),
        (
            resumen[
                "parque_vigente"
            ]
            /
            resumen[
                "parque_vigente_base"
            ]
            *
            100
        ),
        np.nan,
    )

    # --------------------------------------------------------
    # Último estado VIN
    # --------------------------------------------------------

    todos_estados = pd.concat(
        estados,
        ignore_index=True,
    )

    ultimo_snapshot_real = (
        resumen[
            "snapshot"
        ]
        .max()
    )

    ultimo_estado_vin = (
        todos_estados.loc[
            todos_estados[
                "snapshot"
            ].eq(
                ultimo_snapshot_real
            )
        ]
        .copy()
        .reset_index(drop=True)
    )

    return (
        resumen,
        ultimo_estado_vin,
    )


# ============================================================
# TOTAL PANA + NOPANA
# ============================================================

def construir_snapshot_total(
    snapshot_general: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la evolución consolidada TOTAL.
    """

    if snapshot_general.empty:
        return pd.DataFrame()

    total = (
        snapshot_general
        .groupby(
            "snapshot",
            as_index=False,
        )
        .agg(
            parque_acumulado=(
                "parque_acumulado",
                "sum",
            ),

            parque_vigente=(
                "parque_vigente",
                "sum",
            ),

            parque_vencido=(
                "parque_vencido",
                "sum",
            ),

            altas_mes=(
                "altas_mes",
                "sum",
            ),

            reactivaciones_mes=(
                "reactivaciones_mes",
                "sum",
            ),

            nuevos_vencidos_mes=(
                "nuevos_vencidos_mes",
                "sum",
            ),

            saldo_flujo_vigente=(
                "saldo_flujo_vigente",
                "sum",
            ),

            variacion_vigente=(
                "variacion_vigente",
                "sum",
            ),
        )
    )

    total[
        "parque"
    ] = "TOTAL"

    total[
        "tasa_parque_vigente"
    ] = np.where(
        total[
            "parque_acumulado"
        ].gt(0),
        total[
            "parque_vigente"
        ]
        /
        total[
            "parque_acumulado"
        ],
        np.nan,
    )

    base = (
        total[
            "parque_vigente"
        ]
        .iloc[0]
    )

    total[
        "indice_snowball"
    ] = np.where(
        base > 0,
        (
            total[
                "parque_vigente"
            ]
            /
            base
            *
            100
        ),
        np.nan,
    )

    return total


# ============================================================
# SEGMENTACIÓN
# ============================================================

def construir_snapshot_segmentacion(
    ultimo_estado_vin: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume el último estado del parque por dimensiones
    comerciales.

    Dimensiones disponibles:
    - parque;
    - modelo;
    - sede;
    - asesor;
    - año.
    """

    if ultimo_estado_vin.empty:
        return pd.DataFrame()

    dimensiones = [
        "parque",
        "modelo",
        "sede",
        "asesor",
        "año",
    ]

    resultados = []

    for dimension in dimensiones:

        if dimension not in ultimo_estado_vin.columns:
            continue

        columnas_grupo = (
            ["parque"]
            if dimension == "parque"
            else [
                "parque",
                dimension,
            ]
        )

        resumen = (
            ultimo_estado_vin
            .groupby(
                columnas_grupo,
                as_index=False,
                dropna=False,
                observed=True,
            )
            .agg(
                parque_acumulado=(
                    "vin",
                    "nunique",
                ),

                parque_vigente=(
                    "vigente",
                    "sum",
                ),
            )
        )

        resumen[
            "parque_vencido"
        ] = (
            resumen[
                "parque_acumulado"
            ]
            -
            resumen[
                "parque_vigente"
            ]
        )

        resumen[
            "tasa_parque_vigente"
        ] = np.where(
            resumen[
                "parque_acumulado"
            ].gt(0),
            resumen[
                "parque_vigente"
            ]
            /
            resumen[
                "parque_acumulado"
            ],
            np.nan,
        )

        resumen[
            "dimension"
        ] = dimension.upper()

        if dimension == "parque":

            resumen[
                "segmento"
            ] = (
                resumen[
                    "parque"
                ]
                .astype("string")
            )

        else:

            resumen[
                "segmento"
            ] = (
                resumen[
                    dimension
                ]
                .astype("string")
            )

        resultados.append(
            resumen[
                [
                    "parque",
                    "dimension",
                    "segmento",
                    "parque_acumulado",
                    "parque_vigente",
                    "parque_vencido",
                    "tasa_parque_vigente",
                ]
            ]
        )

    if not resultados:
        return pd.DataFrame()

    return (
        pd.concat(
            resultados,
            ignore_index=True,
        )
    )


# ============================================================
# VALIDACIONES
# ============================================================

def auditar_snowball(
    parque_comercial: pd.DataFrame,
    snapshot_general: pd.DataFrame,
    ultimo_estado_vin: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ejecuta controles estructurales del efecto Snowball.
    """

    reconciliacion = (
        snapshot_general[
            "parque_acumulado"
        ]
        .eq(
            snapshot_general[
                "parque_vigente"
            ]
            +
            snapshot_general[
                "parque_vencido"
            ]
        )
        .all()
    )

    tasas_validas = (
        snapshot_general[
            "tasa_parque_vigente"
        ]
        .dropna()
        .between(
            0,
            1,
            inclusive="both",
        )
        .all()
    )

    monotono = True

    for _, grupo in snapshot_general.groupby(
        "parque"
    ):

        valores = (
            grupo
            .sort_values(
                "snapshot"
            )[
                "parque_acumulado"
            ]
            .to_numpy()
        )

        if len(
            valores
        ) > 1:

            if np.any(
                np.diff(
                    valores
                ) < 0
            ):

                monotono = False
                break

    vin_ultimo_duplicado = int(
        ultimo_estado_vin[
            "vin"
        ]
        .duplicated()
        .sum()
    )

    return pd.DataFrame(
        [
            {
                "control":
                    "parque_reconcilia",

                "resultado":
                    bool(
                        reconciliacion
                    ),
            },
            {
                "control":
                    "tasas_en_rango",

                "resultado":
                    bool(
                        tasas_validas
                    ),
            },
            {
                "control":
                    "parque_acumulado_monotono",

                "resultado":
                    bool(
                        monotono
                    ),
            },
            {
                "control":
                    "vin_duplicados_ultimo_snapshot",

                "resultado":
                    vin_ultimo_duplicado,
            },
            {
                "control":
                    "parque_comercial_total",

                "resultado":
                    len(
                        parque_comercial
                    ),
            },
            {
                "control":
                    "snapshots",

                "resultado":
                    snapshot_general[
                        "snapshot"
                    ]
                    .nunique(),
            },
        ]
    )


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def construir_snowball_retencion(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    meses: int = MESES_SNOWBALL,
    meses_vigencia: int = MESES_VIGENCIA,
) -> dict:
    """
    Punto de entrada oficial del módulo Snowball.

    Produce:
    - parque comercial;
    - anclas preventivas;
    - reactivaciones;
    - snapshots por parque;
    - snapshot TOTAL;
    - segmentación del último snapshot;
    - último estado por VIN;
    - auditoría.
    """

    parque_comercial = (
        construir_parque_comercial(
            retail=retail,
            secuencia=secuencia,
        )
    )

    anclas = (
        construir_anclas_preventivas(
            secuencia
        )
    )

    reactivaciones = (
        construir_reactivaciones(
            anclas
        )
    )

    (
        snapshot_general,
        ultimo_estado_vin,
    ) = (
        construir_snapshots_parque(
            parque_comercial=
                parque_comercial,
            anclas=
                anclas,
            reactivaciones=
                reactivaciones,
            fecha_max_datos=
                fecha_max_datos,
            meses=
                meses,
            meses_vigencia=
                meses_vigencia,
        )
    )

    snapshot_total = (
        construir_snapshot_total(
            snapshot_general
        )
    )

    snapshot_segmentacion = (
        construir_snapshot_segmentacion(
            ultimo_estado_vin
        )
    )

    auditoria = (
        auditar_snowball(
            parque_comercial=
                parque_comercial,
            snapshot_general=
                snapshot_general,
            ultimo_estado_vin=
                ultimo_estado_vin,
        )
    )

    return {
        "parque_comercial":
            parque_comercial,

        "anclas":
            anclas,

        "reactivaciones":
            reactivaciones,

        "snapshot_parque_general":
            snapshot_general,

        "snapshot_parque_total":
            snapshot_total,

        "snapshot_segmentacion":
            snapshot_segmentacion,

        "ultimo_estado_vin":
            ultimo_estado_vin,

        "auditoria_snowball":
            auditoria,
    }