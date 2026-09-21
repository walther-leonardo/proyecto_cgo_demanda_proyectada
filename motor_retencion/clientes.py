from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

MIN_OPORTUNIDADES_RANKING = 3

UMBRAL_RETENCION_ALTA = 0.80
UMBRAL_CONTINUIDAD_CLIENTE_VIN = 0.75

MIN_VISITAS_RECURRENCIA = 3
MIN_VISITAS_ALTA_RECURRENCIA = 5

MIN_VIN_MULTIVEHICULO = 2


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
            f"Faltan columnas en {nombre}: "
            f"{faltantes}"
        )


def _normalizar_documento(
    serie: pd.Series,
) -> pd.Series:
    """
    Normaliza documento como texto sin convertirlo
    a valor numérico.
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


def _division_segura(
    numerador: pd.Series,
    denominador: pd.Series,
) -> pd.Series:
    """
    Divide únicamente cuando el denominador es positivo.
    """

    return pd.Series(
        np.where(
            denominador.gt(0),
            numerador / denominador,
            np.nan,
        ),
        index=numerador.index,
        dtype="float64",
    )


# ============================================================
# MAESTRO DE CLIENTES
# ============================================================

def preparar_maestro_clientes(
    clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepara una fila única por nro documento para
    enriquecer los resultados analíticos.
    """

    _validar_columnas(
        clientes,
        [
            "nro documento",
            "nombre",
            "telefono",
            "correo",
        ],
        "clientes",
    )

    maestro = clientes[
        [
            "nro documento",
            "nombre",
            "telefono",
            "correo",
        ]
    ].copy()

    maestro[
        "nro documento"
    ] = _normalizar_documento(
        maestro[
            "nro documento"
        ]
    )

    maestro = (
        maestro
        .dropna(
            subset=[
                "nro documento",
            ]
        )
        .drop_duplicates(
            subset=[
                "nro documento",
            ],
            keep="last",
        )
        .rename(
            columns={
                "nro documento":
                    "nro_documento",
            }
        )
        .reset_index(drop=True)
    )

    return maestro


# ============================================================
# BASE VISITA - CLIENTE
# ============================================================

def construir_base_visita_cliente(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la relación histórica:

        VIN + visita preventiva + cliente asociado.

    El cliente es el nro documento representativo de la
    visita analítica definido por Motor 04.

    Una visita con múltiples documentos permanece marcada
    para auditoría.
    """

    columnas_requeridas = [
        "vin",
        "parque",
        "fecha_visita",
        "mantenimiento_km",
        "modelo",
        "año",
        "sede",
        "asesor",
        "nro documento",
        "nro_visita_analitica",
        "comportamiento",
        "visita_documento_multiple",
    ]

    _validar_columnas(
        secuencia,
        columnas_requeridas,
        "secuencia",
    )

    columnas = (
        columnas_requeridas.copy()
    )

    columnas_opcionales = [
        "documentos_distintos_visita",
        "n_documentos_distintos_visita",
        "visita_km_multiple",
    ]

    for columna in columnas_opcionales:

        if columna in secuencia.columns:
            columnas.append(
                columna
            )

    base = (
        secuencia[
            columnas
        ]
        .copy()
        .rename(
            columns={
                "nro documento":
                    "nro_documento",
            }
        )
    )

    base[
        "nro_documento"
    ] = _normalizar_documento(
        base[
            "nro_documento"
        ]
    )

    base[
        "cliente_identificado"
    ] = (
        base[
            "nro_documento"
        ]
        .notna()
    )

    base = (
        base
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

    return base


# ============================================================
# OPORTUNIDADES ATRIBUIDAS A CLIENTE
# ============================================================

def construir_oportunidades_cliente(
    ciclos_retencion: pd.DataFrame,
) -> pd.DataFrame:
    """
    Atribuye cada oportunidad de retención al cliente
    registrado en la visita origen.

    También identifica el documento registrado en la
    siguiente visita del mismo ciclo.

    Esto permite distinguir:

        vehículo volvió
        !=
        mismo cliente volvió con ese VIN
    """

    columnas_requeridas = [
        "vin",
        "parque",
        "fecha_visita",
        "mantenimiento_km",
        "km_esperado_siguiente",
        "fecha_siguiente_observada",
        "km_siguiente_observado",
        "kpi_retorno",
        "kpi_adherencia_ciclo",
        "kpi_puntualidad",
        "nro documento",
        "modelo",
        "año",
        "sede",
        "asesor",
    ]

    _validar_columnas(
        ciclos_retencion,
        columnas_requeridas,
        "ciclos_retencion",
    )

    base = (
        ciclos_retencion
        .copy()
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

    base[
        "nro_documento_origen"
    ] = _normalizar_documento(
        base[
            "nro documento"
        ]
    )

    # --------------------------------------------------------
    # Documento del siguiente mantenimiento de ciclo
    #
    # Se calcula sobre exactamente la misma secuencia filtrada
    # utilizada por Motor 05 para sus shifts de retorno.
    # --------------------------------------------------------

    base[
        "nro_documento_retorno"
    ] = (
        base
        .groupby(
            "vin",
            sort=False,
        )[
            "nro_documento_origen"
        ]
        .shift(-1)
    )

    base[
        "cliente_origen_identificado"
    ] = (
        base[
            "nro_documento_origen"
        ]
        .notna()
    )

    base[
        "cliente_retorno_identificado"
    ] = (
        base[
            "nro_documento_retorno"
        ]
        .notna()
    )

    base[
        "vehiculo_retorno"
    ] = (
        base[
            "kpi_retorno"
        ]
        .eq("RETORNO")
    )

    base[
        "misma_persona_en_retorno"
    ] = (
        base[
            "vehiculo_retorno"
        ]
        &
        base[
            "nro_documento_origen"
        ]
        .notna()
        &
        base[
            "nro_documento_retorno"
        ]
        .notna()
        &
        base[
            "nro_documento_origen"
        ]
        .eq(
            base[
                "nro_documento_retorno"
            ]
        )
    )

    base[
        "cambio_cliente_en_retorno"
    ] = (
        base[
            "vehiculo_retorno"
        ]
        &
        base[
            "nro_documento_origen"
        ]
        .notna()
        &
        base[
            "nro_documento_retorno"
        ]
        .notna()
        &
        ~base[
            "nro_documento_origen"
        ]
        .eq(
            base[
                "nro_documento_retorno"
            ]
        )
    )

    base[
        "adherencia"
    ] = (
        base[
            "kpi_adherencia_ciclo"
        ]
        .eq("SI")
    )

    base[
        "puntual"
    ] = (
        base[
            "kpi_puntualidad"
        ]
        .eq("EN_FECHA")
    )

    base[
        "oportunidad_evaluable"
    ] = (
        base[
            "kpi_retorno"
        ]
        .isin(
            [
                "RETORNO",
                "NO_RETORNO",
            ]
        )
    )

    return base


# ============================================================
# RESUMEN POR VIN
# ============================================================

def construir_resumen_vin_clientes(
    base_visitas: pd.DataFrame,
    oportunidades_cliente: pd.DataFrame,
) -> pd.DataFrame:
    """
    Analiza la retención del vehículo independientemente
    de cuántos clientes hayan estado asociados.

    Responde especialmente al escenario:

        un VIN cumple bien sus mantenimientos aunque
        distintas personas lo hayan llevado.
    """

    visitas = (
        base_visitas
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

            sede_ultima=(
                "sede",
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
                "vin",
                "size",
            ),

            clientes_asociados=(
                "nro_documento",
                "nunique",
            ),

            visitas_sin_cliente=(
                "cliente_identificado",
                lambda s:
                    (~s).sum(),
            ),

            visitas_documento_multiple=(
                "visita_documento_multiple",
                "sum",
            ),
        )
    )

    evaluables = oportunidades_cliente.loc[
        oportunidades_cliente[
            "oportunidad_evaluable"
        ]
    ].copy()

    if evaluables.empty:

        visitas[
            "oportunidades_evaluables"
        ] = 0

        visitas[
            "retornos"
        ] = 0

        visitas[
            "tasa_retorno_vehiculo"
        ] = np.nan

        visitas[
            "cambios_cliente_retorno"
        ] = 0

        return visitas

    comportamiento = (
        evaluables
        .groupby(
            "vin",
            as_index=False,
        )
        .agg(
            oportunidades_evaluables=(
                "vin",
                "size",
            ),

            retornos=(
                "vehiculo_retorno",
                "sum",
            ),

            adherencias=(
                "adherencia",
                "sum",
            ),

            puntualidades=(
                "puntual",
                "sum",
            ),

            retornos_mismo_cliente=(
                "misma_persona_en_retorno",
                "sum",
            ),

            cambios_cliente_retorno=(
                "cambio_cliente_en_retorno",
                "sum",
            ),
        )
    )

    resultado = visitas.merge(
        comportamiento,
        on="vin",
        how="left",
        validate="one_to_one",
    )

    columnas_conteo = [
        "oportunidades_evaluables",
        "retornos",
        "adherencias",
        "puntualidades",
        "retornos_mismo_cliente",
        "cambios_cliente_retorno",
    ]

    for columna in columnas_conteo:

        resultado[
            columna
        ] = (
            resultado[
                columna
            ]
            .fillna(0)
            .astype(int)
        )

    resultado[
        "tasa_retorno_vehiculo"
    ] = _division_segura(
        resultado[
            "retornos"
        ],
        resultado[
            "oportunidades_evaluables"
        ],
    )

    resultado[
        "tasa_cambio_cliente_entre_retornos"
    ] = _division_segura(
        resultado[
            "cambios_cliente_retorno"
        ],
        resultado[
            "retornos"
        ],
    )

    # --------------------------------------------------------
    # PERFIL 1
    # Vehículo fiel aunque cambie el cliente asociado
    # --------------------------------------------------------

    resultado[
        "perfil_vehiculo_fiel_cambio_cliente"
    ] = (
        resultado[
            "oportunidades_evaluables"
        ].ge(
            MIN_OPORTUNIDADES_RANKING
        )
        &
        resultado[
            "tasa_retorno_vehiculo"
        ].ge(
            UMBRAL_RETENCION_ALTA
        )
        &
        resultado[
            "clientes_asociados"
        ].ge(2)
    )

    return resultado


# ============================================================
# RESUMEN CLIENTE + VIN
# ============================================================

def construir_resumen_cliente_vin(
    base_visitas: pd.DataFrame,
    oportunidades_cliente: pd.DataFrame,
    maestro_clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Analiza la estabilidad de la relación:

        cliente + vehículo.
    """

    visitas = (
        base_visitas.loc[
            base_visitas[
                "nro_documento"
            ]
            .notna()
        ]
        .groupby(
            [
                "nro_documento",
                "vin",
            ],
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

            fecha_primera_visita=(
                "fecha_visita",
                "min",
            ),

            fecha_ultima_visita=(
                "fecha_visita",
                "max",
            ),

            visitas_preventivas=(
                "vin",
                "size",
            ),
        )
    )

    oportunidades = (
        oportunidades_cliente.loc[
            oportunidades_cliente[
                "nro_documento_origen"
            ]
            .notna()
            &
            oportunidades_cliente[
                "oportunidad_evaluable"
            ]
        ]
        .groupby(
            [
                "nro_documento_origen",
                "vin",
            ],
            as_index=False,
        )
        .agg(
            oportunidades_evaluables=(
                "vin",
                "size",
            ),

            vehiculo_retorno=(
                "vehiculo_retorno",
                "sum",
            ),

            mismo_cliente_retorno=(
                "misma_persona_en_retorno",
                "sum",
            ),

            cambio_cliente_retorno=(
                "cambio_cliente_en_retorno",
                "sum",
            ),

            adherencias=(
                "adherencia",
                "sum",
            ),

            puntualidades=(
                "puntual",
                "sum",
            ),
        )
        .rename(
            columns={
                "nro_documento_origen":
                    "nro_documento",
            }
        )
    )

    resultado = visitas.merge(
        oportunidades,
        on=[
            "nro_documento",
            "vin",
        ],
        how="left",
        validate="one_to_one",
    )

    columnas_conteo = [
        "oportunidades_evaluables",
        "vehiculo_retorno",
        "mismo_cliente_retorno",
        "cambio_cliente_retorno",
        "adherencias",
        "puntualidades",
    ]

    for columna in columnas_conteo:

        resultado[
            columna
        ] = (
            resultado[
                columna
            ]
            .fillna(0)
            .astype(int)
        )

    resultado[
        "tasa_retorno_vehiculo"
    ] = _division_segura(
        resultado[
            "vehiculo_retorno"
        ],
        resultado[
            "oportunidades_evaluables"
        ],
    )

    resultado[
        "tasa_continuidad_cliente_vin"
    ] = _division_segura(
        resultado[
            "mismo_cliente_retorno"
        ],
        resultado[
            "vehiculo_retorno"
        ],
    )

    resultado[
        "tasa_adherencia"
    ] = _division_segura(
        resultado[
            "adherencias"
        ],
        resultado[
            "vehiculo_retorno"
        ],
    )

    resultado[
        "tasa_puntualidad"
    ] = _division_segura(
        resultado[
            "puntualidades"
        ],
        resultado[
            "adherencias"
        ],
    )

    resultado = resultado.merge(
        maestro_clientes,
        on="nro_documento",
        how="left",
        validate="many_to_one",
    )

    # --------------------------------------------------------
    # PERFIL 2
    # Cliente fiel a su vehículo
    # --------------------------------------------------------

    resultado[
        "perfil_cliente_fiel_su_vehiculo"
    ] = (
        resultado[
            "visitas_preventivas"
        ].ge(
            MIN_VISITAS_RECURRENCIA
        )
        &
        resultado[
            "oportunidades_evaluables"
        ].ge(
            MIN_OPORTUNIDADES_RANKING
        )
        &
        resultado[
            "tasa_retorno_vehiculo"
        ].ge(
            UMBRAL_RETENCION_ALTA
        )
        &
        resultado[
            "tasa_continuidad_cliente_vin"
        ].ge(
            UMBRAL_CONTINUIDAD_CLIENTE_VIN
        )
    )

    return resultado


# ============================================================
# CADENCIA GLOBAL DEL CLIENTE
# ============================================================

def construir_cadencia_cliente(
    base_visitas: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula recurrencia cronológica del cliente a PanaAutos
    sin importar qué VIN utilizó en cada visita.
    """

    base = (
        base_visitas.loc[
            base_visitas[
                "nro_documento"
            ]
            .notna()
        ]
        .sort_values(
            [
                "nro_documento",
                "fecha_visita",
                "vin",
            ],
            kind="stable",
        )
        .copy()
    )

    if base.empty:
        return pd.DataFrame()

    base[
        "fecha_visita_cliente_anterior"
    ] = (
        base
        .groupby(
            "nro_documento",
            sort=False,
        )[
            "fecha_visita"
        ]
        .shift(1)
    )

    base[
        "vin_visita_cliente_anterior"
    ] = (
        base
        .groupby(
            "nro_documento",
            sort=False,
        )[
            "vin"
        ]
        .shift(1)
    )

    base[
        "dias_desde_visita_cliente"
    ] = (
        base[
            "fecha_visita"
        ]
        -
        base[
            "fecha_visita_cliente_anterior"
        ]
    ).dt.days

    base[
        "cambio_vin_desde_visita_anterior"
    ] = (
        base[
            "vin_visita_cliente_anterior"
        ]
        .notna()
        &
        base[
            "vin"
        ]
        .ne(
            base[
                "vin_visita_cliente_anterior"
            ]
        )
    )

    resumen = (
        base
        .groupby(
            "nro_documento",
            as_index=False,
        )
        .agg(
            mediana_dias_entre_visitas=(
                "dias_desde_visita_cliente",
                "median",
            ),

            promedio_dias_entre_visitas=(
                "dias_desde_visita_cliente",
                "mean",
            ),

            cambios_vin_entre_visitas=(
                "cambio_vin_desde_visita_anterior",
                "sum",
            ),
        )
    )

    return resumen


# ============================================================
# RESUMEN GLOBAL DEL CLIENTE
# ============================================================

def construir_resumen_cliente(
    base_visitas: pd.DataFrame,
    oportunidades_cliente: pd.DataFrame,
    maestro_clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Analiza al cliente independientemente del VIN.

    Esta perspectiva permite encontrar clientes que siguen
    vinculados comercialmente a PanaAutos aunque utilicen
    distintos vehículos.
    """

    visitas_cliente = (
        base_visitas.loc[
            base_visitas[
                "nro_documento"
            ]
            .notna()
        ]
        .groupby(
            "nro_documento",
            as_index=False,
        )
        .agg(
            visitas_preventivas=(
                "vin",
                "size",
            ),

            vin_distintos=(
                "vin",
                "nunique",
            ),

            fecha_primera_visita=(
                "fecha_visita",
                "min",
            ),

            fecha_ultima_visita=(
                "fecha_visita",
                "max",
            ),

            sedes_distintas=(
                "sede",
                "nunique",
            ),

            modelos_distintos=(
                "modelo",
                "nunique",
            ),

            visitas_documento_multiple=(
                "visita_documento_multiple",
                "sum",
            ),
        )
    )

    oportunidades = (
        oportunidades_cliente.loc[
            oportunidades_cliente[
                "nro_documento_origen"
            ]
            .notna()
            &
            oportunidades_cliente[
                "oportunidad_evaluable"
            ]
        ]
        .groupby(
            "nro_documento_origen",
            as_index=False,
        )
        .agg(
            oportunidades_evaluables=(
                "vin",
                "size",
            ),

            vehiculos_retornaron=(
                "vehiculo_retorno",
                "sum",
            ),

            mismo_cliente_retorno=(
                "misma_persona_en_retorno",
                "sum",
            ),

            cambios_cliente_retorno=(
                "cambio_cliente_en_retorno",
                "sum",
            ),

            adherencias=(
                "adherencia",
                "sum",
            ),

            puntualidades=(
                "puntual",
                "sum",
            ),
        )
        .rename(
            columns={
                "nro_documento_origen":
                    "nro_documento",
            }
        )
    )

    resultado = visitas_cliente.merge(
        oportunidades,
        on="nro_documento",
        how="left",
        validate="one_to_one",
    )

    columnas_conteo = [
        "oportunidades_evaluables",
        "vehiculos_retornaron",
        "mismo_cliente_retorno",
        "cambios_cliente_retorno",
        "adherencias",
        "puntualidades",
    ]

    for columna in columnas_conteo:

        resultado[
            columna
        ] = (
            resultado[
                columna
            ]
            .fillna(0)
            .astype(int)
        )

    resultado[
        "tasa_retorno_vehiculo_atribuida"
    ] = _division_segura(
        resultado[
            "vehiculos_retornaron"
        ],
        resultado[
            "oportunidades_evaluables"
        ],
    )

    resultado[
        "tasa_continuidad_mismo_cliente"
    ] = _division_segura(
        resultado[
            "mismo_cliente_retorno"
        ],
        resultado[
            "vehiculos_retornaron"
        ],
    )

    resultado[
        "tasa_adherencia"
    ] = _division_segura(
        resultado[
            "adherencias"
        ],
        resultado[
            "vehiculos_retornaron"
        ],
    )

    resultado[
        "tasa_puntualidad"
    ] = _division_segura(
        resultado[
            "puntualidades"
        ],
        resultado[
            "adherencias"
        ],
    )

    resultado[
        "dias_relacion"
    ] = (
        resultado[
            "fecha_ultima_visita"
        ]
        -
        resultado[
            "fecha_primera_visita"
        ]
    ).dt.days

    cadencia = construir_cadencia_cliente(
        base_visitas
    )

    resultado = resultado.merge(
        cadencia,
        on="nro_documento",
        how="left",
        validate="one_to_one",
    )

    resultado = resultado.merge(
        maestro_clientes,
        on="nro_documento",
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # PERFIL 3
    # Cliente fiel a PanaAutos aunque cambie de vehículo
    # --------------------------------------------------------

    resultado[
        "perfil_cliente_fiel_panautos"
    ] = (
        resultado[
            "vin_distintos"
        ].ge(
            MIN_VIN_MULTIVEHICULO
        )
        &
        resultado[
            "visitas_preventivas"
        ].ge(
            MIN_VISITAS_RECURRENCIA
        )
    )

    # --------------------------------------------------------
    # PERFIL 4
    # Cliente multivehículo de alta recurrencia
    #
    # Es un perfil más exigente que el anterior.
    # --------------------------------------------------------

    resultado[
        "perfil_multivehiculo_alta_recurrencia"
    ] = (
        resultado[
            "vin_distintos"
        ].ge(
            MIN_VIN_MULTIVEHICULO
        )
        &
        resultado[
            "visitas_preventivas"
        ].ge(
            MIN_VISITAS_ALTA_RECURRENCIA
        )
        &
        resultado[
            "oportunidades_evaluables"
        ].ge(
            MIN_OPORTUNIDADES_RANKING
        )
        &
        resultado[
            "tasa_retorno_vehiculo_atribuida"
        ].ge(
            UMBRAL_RETENCION_ALTA
        )
    )

    return resultado


# ============================================================
# RANKING DE CLIENTES
# ============================================================

def construir_ranking_clientes(
    resumen_cliente: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye rankings separados por métrica.

    No crea un score compuesto arbitrario.

    Esto permite que Streamlit tenga un selector como:

        - Retención
        - Continuidad
        - Adherencia
        - Puntualidad
        - Visitas
        - VIN distintos
    """

    if resumen_cliente.empty:
        return pd.DataFrame()

    configuracion = [
        (
            "RETENCION",
            "tasa_retorno_vehiculo_atribuida",
            True,
        ),
        (
            "CONTINUIDAD_CLIENTE",
            "tasa_continuidad_mismo_cliente",
            True,
        ),
        (
            "ADHERENCIA",
            "tasa_adherencia",
            True,
        ),
        (
            "PUNTUALIDAD",
            "tasa_puntualidad",
            True,
        ),
        (
            "VISITAS_PREVENTIVAS",
            "visitas_preventivas",
            False,
        ),
        (
            "VIN_DISTINTOS",
            "vin_distintos",
            False,
        ),
    ]

    resultados = []

    for (
        metrica,
        columna,
        requiere_minimo,
    ) in configuracion:

        base = resumen_cliente.copy()

        if requiere_minimo:

            base = base.loc[
                base[
                    "oportunidades_evaluables"
                ]
                .ge(
                    MIN_OPORTUNIDADES_RANKING
                )
            ].copy()

        base = base.loc[
            base[
                columna
            ]
            .notna()
        ].copy()

        if base.empty:
            continue

        base = (
            base
            .sort_values(
                [
                    columna,
                    "visitas_preventivas",
                    "oportunidades_evaluables",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
                kind="stable",
            )
            .reset_index(drop=True)
        )

        base[
            "ranking"
        ] = (
            np.arange(
                1,
                len(base) + 1
            )
        )

        base[
            "metrica_ranking"
        ] = metrica

        base[
            "valor_ranking"
        ] = (
            base[
                columna
            ]
        )

        resultados.append(
            base
        )

    if not resultados:
        return pd.DataFrame()

    return pd.concat(
        resultados,
        ignore_index=True,
    )


# ============================================================
# RESUMEN DE PERFILES COMERCIALES
# ============================================================

def construir_resumen_perfiles(
    resumen_vin: pd.DataFrame,
    resumen_cliente_vin: pd.DataFrame,
    resumen_cliente: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume los cuatro perfiles comerciales acordados.
    """

    perfiles = [
        {
            "perfil":
                "VEHICULO_FIEL_CAMBIO_CLIENTE",

            "descripcion":
                (
                    "Vehículo con alta retención pese a "
                    "tener varios clientes asociados."
                ),

            "cantidad":
                int(
                    resumen_vin[
                        "perfil_vehiculo_fiel_cambio_cliente"
                    ]
                    .sum()
                ),
        },
        {
            "perfil":
                "CLIENTE_FIEL_SU_VEHICULO",

            "descripcion":
                (
                    "Cliente con relación estable y "
                    "recurrente con un mismo VIN."
                ),

            "cantidad":
                int(
                    resumen_cliente_vin[
                        "perfil_cliente_fiel_su_vehiculo"
                    ]
                    .sum()
                ),
        },
        {
            "perfil":
                "CLIENTE_MULTIVEHICULO_RECURRENTE",

            "descripcion":
                (
                    "Cliente recurrente asociado históricamente "
                    "a más de un VIN."
                ),

            "cantidad":
                int(
                    resumen_cliente[
                        "perfil_cliente_fiel_panautos"
                    ]
                    .sum()
                ),
        },
        {
            "perfil":
                "CLIENTE_MULTIVEHICULO_ALTA_FIDELIDAD",

            "descripcion":
                (
                    "Cliente con múltiples VIN, alta recurrencia "
                    "y buen nivel de retorno."
                ),

            "cantidad":
                int(
                    resumen_cliente[
                        "perfil_multivehiculo_alta_recurrencia"
                    ]
                    .sum()
                ),
        },
    ]

    return pd.DataFrame(
        perfiles
    )


# ============================================================
# AUDITORÍA
# ============================================================

def auditar_clientes(
    base_visitas: pd.DataFrame,
    oportunidades_cliente: pd.DataFrame,
    resumen_cliente: pd.DataFrame,
) -> pd.DataFrame:
    """
    Auditoría de cobertura y consistencia del módulo.
    """

    visitas_total = len(
        base_visitas
    )

    visitas_con_cliente = int(
        base_visitas[
            "cliente_identificado"
        ]
        .sum()
    )

    visitas_sin_cliente = (
        visitas_total
        -
        visitas_con_cliente
    )

    visitas_documento_multiple = int(
        base_visitas[
            "visita_documento_multiple"
        ]
        .sum()
    )

    oportunidades_evaluables = (
        oportunidades_cliente.loc[
            oportunidades_cliente[
                "oportunidad_evaluable"
            ]
        ]
    )

    oportunidades_con_cliente = int(
        oportunidades_evaluables[
            "cliente_origen_identificado"
        ]
        .sum()
    )

    cambios_cliente = int(
        oportunidades_evaluables[
            "cambio_cliente_en_retorno"
        ]
        .sum()
    )

    retornos_mismo_cliente = int(
        oportunidades_evaluables[
            "misma_persona_en_retorno"
        ]
        .sum()
    )

    return pd.DataFrame(
        [
            {
                "metrica":
                    "visitas_analiticas",

                "valor":
                    visitas_total,
            },
            {
                "metrica":
                    "visitas_con_cliente",

                "valor":
                    visitas_con_cliente,
            },
            {
                "metrica":
                    "visitas_sin_cliente",

                "valor":
                    visitas_sin_cliente,
            },
            {
                "metrica":
                    "visitas_documento_multiple",

                "valor":
                    visitas_documento_multiple,
            },
            {
                "metrica":
                    "clientes_unicos",

                "valor":
                    resumen_cliente[
                        "nro_documento"
                    ]
                    .nunique(),
            },
            {
                "metrica":
                    "oportunidades_evaluables",

                "valor":
                    len(
                        oportunidades_evaluables
                    ),
            },
            {
                "metrica":
                    "oportunidades_con_cliente_origen",

                "valor":
                    oportunidades_con_cliente,
            },
            {
                "metrica":
                    "retornos_mismo_cliente",

                "valor":
                    retornos_mismo_cliente,
            },
            {
                "metrica":
                    "retornos_cambio_cliente",

                "valor":
                    cambios_cliente,
            },
        ]
    )


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def construir_analisis_clientes(
    secuencia: pd.DataFrame,
    ciclos_retencion: pd.DataFrame,
    clientes: pd.DataFrame,
) -> dict:
    """
    Punto de entrada oficial del análisis de clientes.

    Construye tres perspectivas:

    1. VIN
       Retención del vehículo independientemente de quién
       lo llevó.

    2. Cliente + VIN
       Continuidad de una persona concreta con un vehículo.

    3. Cliente
       Recurrencia comercial independientemente del VIN.

    Además construye:
    - rankings;
    - cuatro perfiles comerciales;
    - auditoría.
    """

    # --------------------------------------------------------
    # 1. Maestro clientes
    # --------------------------------------------------------

    maestro_clientes = (
        preparar_maestro_clientes(
            clientes
        )
    )

    # --------------------------------------------------------
    # 2. Visita histórica + cliente
    # --------------------------------------------------------

    base_visita_cliente = (
        construir_base_visita_cliente(
            secuencia
        )
    )

    # --------------------------------------------------------
    # 3. Oportunidades atribuidas
    # --------------------------------------------------------

    oportunidades_cliente = (
        construir_oportunidades_cliente(
            ciclos_retencion
        )
    )

    # --------------------------------------------------------
    # 4. Perspectiva VIN
    # --------------------------------------------------------

    resumen_vin = (
        construir_resumen_vin_clientes(
            base_visitas=
                base_visita_cliente,
            oportunidades_cliente=
                oportunidades_cliente,
        )
    )

    # --------------------------------------------------------
    # 5. Perspectiva Cliente + VIN
    # --------------------------------------------------------

    resumen_cliente_vin = (
        construir_resumen_cliente_vin(
            base_visitas=
                base_visita_cliente,
            oportunidades_cliente=
                oportunidades_cliente,
            maestro_clientes=
                maestro_clientes,
        )
    )

    # --------------------------------------------------------
    # 6. Perspectiva Cliente
    # --------------------------------------------------------

    resumen_cliente = (
        construir_resumen_cliente(
            base_visitas=
                base_visita_cliente,
            oportunidades_cliente=
                oportunidades_cliente,
            maestro_clientes=
                maestro_clientes,
        )
    )

    # --------------------------------------------------------
    # 7. Rankings
    # --------------------------------------------------------

    ranking_clientes = (
        construir_ranking_clientes(
            resumen_cliente
        )
    )

    # --------------------------------------------------------
    # 8. Perfiles comerciales
    # --------------------------------------------------------

    perfiles_comerciales = (
        construir_resumen_perfiles(
            resumen_vin=
                resumen_vin,
            resumen_cliente_vin=
                resumen_cliente_vin,
            resumen_cliente=
                resumen_cliente,
        )
    )

    # --------------------------------------------------------
    # 9. Auditoría
    # --------------------------------------------------------

    auditoria_clientes = (
        auditar_clientes(
            base_visitas=
                base_visita_cliente,
            oportunidades_cliente=
                oportunidades_cliente,
            resumen_cliente=
                resumen_cliente,
        )
    )

    return {
        "maestro_clientes":
            maestro_clientes,

        "base_visita_cliente":
            base_visita_cliente,

        "oportunidades_cliente":
            oportunidades_cliente,

        "resumen_vin_clientes":
            resumen_vin,

        "resumen_cliente_vin":
            resumen_cliente_vin,

        "resumen_cliente":
            resumen_cliente,

        "ranking_clientes":
            ranking_clientes,

        "perfiles_comerciales":
            perfiles_comerciales,

        "auditoria_clientes":
            auditoria_clientes,
    }