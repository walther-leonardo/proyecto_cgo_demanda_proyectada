from __future__ import annotations

import numpy as np
import pandas as pd

from motor.demanda import (
    VENTANA_VISITA_DIAS,
    asignar_visitas_analiticas,
    consolidar_visitas_preventivas,
    reconstruir_secuencia_preventiva,
    construir_auditoria_visitas,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

TOLERANCIA_PUNTUALIDAD_DIAS = 30

KM_1K = 1
KM_INICIO_CICLO = 5
PASO_CICLO_KM = 5


# ============================================================
# VISITAS Y SECUENCIA CANÓNICA
# ============================================================

def construir_historia_canonica_retencion(
    historia_preventiva: pd.DataFrame,
    ventana_dias: int = VENTANA_VISITA_DIAS,
) -> dict:
    """
    Construye la historia preventiva utilizada por Retención
    reutilizando exactamente las reglas canónicas del
    Motor 04 — Demanda.

    Retención NO define por separado:
    - qué constituye una visita;
    - cómo se consolidan órdenes;
    - cómo se interpreta la secuencia;
    - cómo se clasifican saltos, repeticiones o retrocesos.
    """

    registros_con_visita = (
        asignar_visitas_analiticas(
            historia_preventiva=historia_preventiva,
            ventana_dias=ventana_dias,
        )
    )

    visitas = (
        consolidar_visitas_preventivas(
            registros_con_visita
        )
    )

    secuencia = (
        reconstruir_secuencia_preventiva(
            visitas
        )
    )

    auditoria_visitas = (
        construir_auditoria_visitas(
            historia_preventiva=historia_preventiva,
            registros_con_visita=registros_con_visita,
            visitas=visitas,
            secuencia=secuencia,
        )
    )

    return {
        "registros_con_visita":
            registros_con_visita,

        "visitas_analiticas":
            visitas,

        "secuencia_preventiva":
            secuencia,

        "auditoria_visitas":
            auditoria_visitas,
    }


# ============================================================
# CICLOS COMPARABLES DE RETENCIÓN
# ============================================================

def construir_ciclos_retencion(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye oportunidades de retorno a partir de la
    secuencia preventiva canónica.

    Reglas:
    - 1K es un preventivo especial.
    - El ciclo comparable comienza en 5K.
    - Para cada visita de ciclo se busca la siguiente visita
      preventiva observada del mismo VIN.
    - El mantenimiento esperado se determina con la misma
      lógica de Motor 04: +5K desde 5K en adelante.
    """

    if secuencia.empty:
        return pd.DataFrame()

    ciclos = secuencia.loc[
        secuencia[
            "mantenimiento_km"
        ].ge(KM_INICIO_CICLO)
    ].copy()

    ciclos = ciclos.loc[
        (
            ciclos[
                "mantenimiento_km"
            ]
            % PASO_CICLO_KM
        ).eq(0)
    ].copy()

    ciclos = (
        ciclos
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    grupo = ciclos.groupby(
        "vin",
        sort=False,
    )

    ciclos[
        "fecha_siguiente_observada"
    ] = (
        grupo[
            "fecha_visita"
        ]
        .shift(-1)
    )

    ciclos[
        "km_siguiente_observado"
    ] = (
        grupo[
            "mantenimiento_km"
        ]
        .shift(-1)
    )

    ciclos[
        "km_esperado_siguiente"
    ] = (
        ciclos[
            "mantenimiento_km"
        ]
        + PASO_CICLO_KM
    )

    ciclos[
        "fecha_esperada_siguiente"
    ] = (
        ciclos[
            "fecha_visita"
        ]
        + pd.DateOffset(
            months=6
        )
    )

    ciclos[
        "dias_vs_fecha_esperada"
    ] = (
        ciclos[
            "fecha_siguiente_observada"
        ]
        -
        ciclos[
            "fecha_esperada_siguiente"
        ]
    ).dt.days

    return ciclos


# ============================================================
# KPI DE RETENCIÓN
# ============================================================

def agregar_kpis_retencion(
    ciclos: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construye los tres KPI oficiales:

    1. Retorno
    2. Adherencia
    3. Puntualidad

    Una oportunidad es madura cuando la fecha esperada
    del siguiente mantenimiento ya ocurrió respecto de
    la fecha máxima disponible en Taller.
    """

    if ciclos.empty:
        return ciclos.copy()

    resultado = ciclos.copy()

    fecha_max_datos = pd.Timestamp(
        fecha_max_datos
    ).normalize()

    resultado[
        "evaluacion_madura"
    ] = (
        resultado[
            "fecha_esperada_siguiente"
        ]
        .le(fecha_max_datos)
    )

    mask_retorno = (
        resultado[
            "fecha_siguiente_observada"
        ]
        .notna()
    )

    mask_sin_retorno = (
        ~mask_retorno
    )

    mask_maduro = (
        resultado[
            "evaluacion_madura"
        ]
        .fillna(False)
    )

    # --------------------------------------------------------
    # KPI 1 — RETORNO
    # --------------------------------------------------------

    resultado[
        "kpi_retorno"
    ] = "NO_EVALUABLE"

    resultado.loc[
        mask_retorno,
        "kpi_retorno",
    ] = "RETORNO"

    resultado.loc[
        mask_sin_retorno
        & mask_maduro,
        "kpi_retorno",
    ] = "NO_RETORNO"

    # --------------------------------------------------------
    # KPI 2 — ADHERENCIA
    # --------------------------------------------------------

    resultado[
        "kpi_adherencia_ciclo"
    ] = "NO_EVALUABLE"

    mask_adherencia = (
        mask_retorno
        &
        resultado[
            "km_siguiente_observado"
        ].eq(
            resultado[
                "km_esperado_siguiente"
            ]
        )
    )

    resultado.loc[
        mask_adherencia,
        "kpi_adherencia_ciclo",
    ] = "SI"

    resultado.loc[
        mask_retorno
        & ~mask_adherencia,
        "kpi_adherencia_ciclo",
    ] = "NO"

    resultado.loc[
        mask_sin_retorno
        & mask_maduro,
        "kpi_adherencia_ciclo",
    ] = "NO"

    # --------------------------------------------------------
    # KPI 3 — PUNTUALIDAD
    # --------------------------------------------------------

    resultado[
        "kpi_puntualidad"
    ] = "NO_APLICA"

    dias = (
        resultado[
            "dias_vs_fecha_esperada"
        ]
    )

    resultado.loc[
        mask_adherencia
        &
        dias.lt(
            -TOLERANCIA_PUNTUALIDAD_DIAS
        ),
        "kpi_puntualidad",
    ] = "ADELANTADO"

    resultado.loc[
        mask_adherencia
        &
        dias.between(
            -TOLERANCIA_PUNTUALIDAD_DIAS,
            TOLERANCIA_PUNTUALIDAD_DIAS,
            inclusive="both",
        ),
        "kpi_puntualidad",
    ] = "EN_FECHA"

    resultado.loc[
        mask_adherencia
        &
        dias.gt(
            TOLERANCIA_PUNTUALIDAD_DIAS
        ),
        "kpi_puntualidad",
    ] = "TARDIO"

    return resultado


# ============================================================
# RESULTADO AUXILIAR DE TRANSICIÓN
# ============================================================

def agregar_resultado_transicion(
    ciclos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clasificación auxiliar para visualizaciones.

    No reemplaza Retorno / Adherencia / Puntualidad.
    """

    if ciclos.empty:
        return ciclos.copy()

    resultado = ciclos.copy()

    resultado[
        "resultado_transicion"
    ] = "OTRO"

    resultado.loc[
        resultado[
            "kpi_retorno"
        ].eq("NO_EVALUABLE"),
        "resultado_transicion",
    ] = "NO_EVALUABLE"

    resultado.loc[
        resultado[
            "kpi_retorno"
        ].eq("NO_RETORNO"),
        "resultado_transicion",
    ] = "NO_RETORNO"

    resultado.loc[
        resultado[
            "kpi_retorno"
        ].eq("RETORNO")
        &
        resultado[
            "km_siguiente_observado"
        ].gt(
            resultado[
                "km_esperado_siguiente"
            ]
        ),
        "resultado_transicion",
    ] = "RETORNO_CON_SALTO"

    resultado.loc[
        resultado[
            "kpi_retorno"
        ].eq("RETORNO")
        &
        resultado[
            "km_siguiente_observado"
        ].lt(
            resultado[
                "mantenimiento_km"
            ]
        ),
        "resultado_transicion",
    ] = "RETORNO_CON_RETROCESO"

    resultado.loc[
        resultado[
            "kpi_puntualidad"
        ].eq("ADELANTADO"),
        "resultado_transicion",
    ] = "CUMPLE_ADELANTADO"

    resultado.loc[
        resultado[
            "kpi_puntualidad"
        ].eq("EN_FECHA"),
        "resultado_transicion",
    ] = "CUMPLE_EN_FECHA"

    resultado.loc[
        resultado[
            "kpi_puntualidad"
        ].eq("TARDIO"),
        "resultado_transicion",
    ] = "CUMPLE_TARDIO"

    return resultado


# ============================================================
# RESUMEN POR VIN
# ============================================================

def construir_resumen_vin(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Una fila por VIN utilizando exclusivamente la secuencia
    preventiva canónica de Motor 04.
    """

    if secuencia.empty:
        return pd.DataFrame()

    resumen = (
        secuencia
        .groupby(
            "vin",
            as_index=False,
        )
        .agg(
            parque=(
                "parque",
                "last",
            ),

            modelo=(
                "modelo",
                "last",
            ),

            anio_vehiculo=(
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

            fecha_primera_visita=(
                "fecha_visita",
                "min",
            ),

            fecha_ultima_visita=(
                "fecha_visita",
                "max",
            ),

            visitas_preventivas=(
                "nro_visita_analitica",
                "count",
            ),

            cantidad_saltos=(
                "es_salto_mantenimiento",
                "sum",
            ),

            cantidad_retrocesos=(
                "es_retroceso",
                "sum",
            ),

            cantidad_repeticiones=(
                "es_repeticion",
                "sum",
            ),

            cantidad_inconsistencias=(
                "es_inconsistencia_secuencia",
                "sum",
            ),
        )
    )

    return resumen


# ============================================================
# RESUMEN KPI POR PARQUE
# ============================================================

def construir_resumen_kpis(
    ciclos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume Retorno, Adherencia y Puntualidad por parque.
    """

    if ciclos.empty:
        return pd.DataFrame()

    resumen = (
        ciclos
        .groupby(
            "parque",
            as_index=False,
        )
        .agg(
            oportunidades=(
                "kpi_retorno",
                lambda s:
                    s.isin(
                        [
                            "RETORNO",
                            "NO_RETORNO",
                        ]
                    ).sum(),
            ),

            retornos=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "RETORNO"
                    ).sum(),
            ),

            no_retornos=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "NO_RETORNO"
                    ).sum(),
            ),

            no_evaluables=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "NO_EVALUABLE"
                    ).sum(),
            ),

            adherentes=(
                "kpi_adherencia_ciclo",
                lambda s:
                    s.eq("SI").sum(),
            ),

            adelantados=(
                "kpi_puntualidad",
                lambda s:
                    s.eq(
                        "ADELANTADO"
                    ).sum(),
            ),

            en_fecha=(
                "kpi_puntualidad",
                lambda s:
                    s.eq(
                        "EN_FECHA"
                    ).sum(),
            ),

            tardios=(
                "kpi_puntualidad",
                lambda s:
                    s.eq(
                        "TARDIO"
                    ).sum(),
            ),
        )
    )

    resumen[
        "tasa_retorno"
    ] = np.where(
        resumen[
            "oportunidades"
        ].gt(0),
        resumen[
            "retornos"
        ]
        /
        resumen[
            "oportunidades"
        ],
        np.nan,
    )

    resumen[
        "tasa_adherencia"
    ] = np.where(
        resumen[
            "retornos"
        ].gt(0),
        resumen[
            "adherentes"
        ]
        /
        resumen[
            "retornos"
        ],
        np.nan,
    )

    resumen[
        "tasa_puntualidad"
    ] = np.where(
        resumen[
            "adherentes"
        ].gt(0),
        resumen[
            "en_fecha"
        ]
        /
        resumen[
            "adherentes"
        ],
        np.nan,
    )

    return resumen


# ============================================================
# RETENCIÓN POR HITO
# ============================================================

def construir_retencion_por_hito(
    ciclos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula los KPI por mantenimiento esperado.

    hito_km utiliza la misma unidad canónica de Motor 04:

        10 = 10K
        15 = 15K
        20 = 20K
    """

    if ciclos.empty:
        return pd.DataFrame()

    resultado = (
        ciclos
        .groupby(
            [
                "parque",
                "km_esperado_siguiente",
            ],
            as_index=False,
        )
        .agg(
            oportunidades=(
                "kpi_retorno",
                lambda s:
                    s.isin(
                        [
                            "RETORNO",
                            "NO_RETORNO",
                        ]
                    ).sum(),
            ),

            retornos=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "RETORNO"
                    ).sum(),
            ),

            no_retornos=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "NO_RETORNO"
                    ).sum(),
            ),

            no_evaluables=(
                "kpi_retorno",
                lambda s:
                    s.eq(
                        "NO_EVALUABLE"
                    ).sum(),
            ),

            adherentes=(
                "kpi_adherencia_ciclo",
                lambda s:
                    s.eq("SI").sum(),
            ),

            en_fecha=(
                "kpi_puntualidad",
                lambda s:
                    s.eq(
                        "EN_FECHA"
                    ).sum(),
            ),
        )
    )

    resultado = resultado.rename(
        columns={
            "km_esperado_siguiente":
                "hito_km"
        }
    )

    resultado[
        "tasa_retorno"
    ] = np.where(
        resultado[
            "oportunidades"
        ].gt(0),
        resultado[
            "retornos"
        ]
        /
        resultado[
            "oportunidades"
        ],
        np.nan,
    )

    resultado[
        "tasa_adherencia"
    ] = np.where(
        resultado[
            "retornos"
        ].gt(0),
        resultado[
            "adherentes"
        ]
        /
        resultado[
            "retornos"
        ],
        np.nan,
    )

    resultado[
        "tasa_puntualidad"
    ] = np.where(
        resultado[
            "adherentes"
        ].gt(0),
        resultado[
            "en_fecha"
        ]
        /
        resultado[
            "adherentes"
        ],
        np.nan,
    )

    return (
        resultado
        .sort_values(
            [
                "parque",
                "hito_km",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# AUDITORÍA
# ============================================================

def auditar_retencion(
    secuencia: pd.DataFrame,
    ciclos: pd.DataFrame,
    auditoria_visitas: dict,
) -> pd.DataFrame:
    """
    Consolida los principales controles de Retención.
    """

    registros = [
        {
            "metrica": "preventivos_base",
            "valor": auditoria_visitas[
                "preventivos_base"
            ],
        },
        {
            "metrica": "preventivos_con_km",
            "valor": auditoria_visitas[
                "preventivos_con_km"
            ],
        },
        {
            "metrica": "visitas_analiticas",
            "valor": auditoria_visitas[
                "visitas_analiticas"
            ],
        },
        {
            "metrica": "registros_consolidados",
            "valor": auditoria_visitas[
                "registros_consolidados"
            ],
        },
        {
            "metrica": "vin_preventivos",
            "valor": secuencia[
                "vin"
            ].nunique(),
        },
        {
            "metrica": "eventos_ciclo",
            "valor": len(ciclos),
        },
        {
            "metrica": "retornos",
            "valor": int(
                ciclos[
                    "kpi_retorno"
                ]
                .eq("RETORNO")
                .sum()
            ),
        },
        {
            "metrica": "no_retornos",
            "valor": int(
                ciclos[
                    "kpi_retorno"
                ]
                .eq("NO_RETORNO")
                .sum()
            ),
        },
        {
            "metrica": "no_evaluables",
            "valor": int(
                ciclos[
                    "kpi_retorno"
                ]
                .eq("NO_EVALUABLE")
                .sum()
            ),
        },
        {
            "metrica": "saltos_secuencia",
            "valor": int(
                secuencia[
                    "es_salto_mantenimiento"
                ]
                .sum()
            ),
        },
        {
            "metrica": "retrocesos_secuencia",
            "valor": int(
                secuencia[
                    "es_retroceso"
                ]
                .sum()
            ),
        },
        {
            "metrica": "repeticiones_secuencia",
            "valor": int(
                secuencia[
                    "es_repeticion"
                ]
                .sum()
            ),
        },
    ]

    return pd.DataFrame(
        registros
    )


# ============================================================
# PIPELINE PRINCIPAL MOTOR 05
# ============================================================

def construir_motor_retencion(
    historia_preventiva: pd.DataFrame,
    fecha_max_datos: pd.Timestamp,
    ventana_dias: int = VENTANA_VISITA_DIAS,
) -> dict:
    """
    Punto de entrada oficial del Motor 05 — Retención.

    Reutiliza las definiciones estructurales y de secuencia
    del Motor 04 y aplica sobre ellas exclusivamente las
    métricas propias de Retención.
    """

    # --------------------------------------------------------
    # 1. Historia canónica Motor 04
    # --------------------------------------------------------

    historia = (
        construir_historia_canonica_retencion(
            historia_preventiva=
                historia_preventiva,
            ventana_dias=
                ventana_dias,
        )
    )

    registros_con_visita = (
        historia[
            "registros_con_visita"
        ]
    )

    visitas = (
        historia[
            "visitas_analiticas"
        ]
    )

    secuencia = (
        historia[
            "secuencia_preventiva"
        ]
    )

    auditoria_visitas = (
        historia[
            "auditoria_visitas"
        ]
    )

    # --------------------------------------------------------
    # 2. Oportunidades de ciclo
    # --------------------------------------------------------

    ciclos = (
        construir_ciclos_retencion(
            secuencia
        )
    )

    # --------------------------------------------------------
    # 3. KPI Retorno / Adherencia / Puntualidad
    # --------------------------------------------------------

    ciclos = (
        agregar_kpis_retencion(
            ciclos=ciclos,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    # --------------------------------------------------------
    # 4. Clasificación auxiliar
    # --------------------------------------------------------

    ciclos = (
        agregar_resultado_transicion(
            ciclos
        )
    )

    # --------------------------------------------------------
    # 5. Resumen VIN
    # --------------------------------------------------------

    resumen_vin = (
        construir_resumen_vin(
            secuencia
        )
    )

    # --------------------------------------------------------
    # 6. KPI por parque
    # --------------------------------------------------------

    resumen_kpis = (
        construir_resumen_kpis(
            ciclos
        )
    )

    # --------------------------------------------------------
    # 7. Retención por hito
    # --------------------------------------------------------

    retencion_por_hito = (
        construir_retencion_por_hito(
            ciclos
        )
    )

    # --------------------------------------------------------
    # 8. Auditoría
    # --------------------------------------------------------

    auditoria_retencion = (
        auditar_retencion(
            secuencia=secuencia,
            ciclos=ciclos,
            auditoria_visitas=
                auditoria_visitas,
        )
    )

    return {
        "registros_con_visita":
            registros_con_visita,

        "visitas_analiticas":
            visitas,

        "secuencia_preventiva":
            secuencia,

        "auditoria_visitas":
            auditoria_visitas,

        "ciclos_retencion":
            ciclos,

        "resumen_vin":
            resumen_vin,

        "resumen_kpis":
            resumen_kpis,

        "retencion_por_hito":
            retencion_por_hito,

        "auditoria_retencion":
            auditoria_retencion,
    }