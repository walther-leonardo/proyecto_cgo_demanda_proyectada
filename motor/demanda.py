from __future__ import annotations

import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

VENTANA_VISITA_DIAS = 7

MIN_INTERVALOS_VIN = 3
MIN_REFERENCIAS_SEGMENTO = 20

COMPORTAMIENTOS_INCONSISTENTES = {
    "REPITE_MANTENIMIENTO",
    "RETROCESO",
    "SECUENCIA_NO_ESTANDAR",
}


# ============================================================
# HELPERS DE MANTENIMIENTO
# ============================================================

def _km_a_numero(
    valor,
) -> int | None:
    """
    Convierte un nivel de mantenimiento a entero
    cuando sea posible.
    """

    if pd.isna(valor):
        return None

    return int(
        round(
            float(valor)
        )
    )


def _etiqueta_km(
    valor,
) -> str:
    """
    Convierte un mantenimiento numérico a etiqueta comercial.

    Ejemplos:
        1  -> 1K
        5  -> 5K
        20 -> 20K
    """

    km = _km_a_numero(
        valor
    )

    if km is None:
        return "SIN_KM"

    return f"{km}K"


def _siguiente_mantenimiento_km(
    mantenimiento_actual,
) -> int | None:
    """
    Define el siguiente nivel preventivo esperado.

    Regla:
        1K  -> 5K
        5K  -> 10K
        10K -> 15K
        ...
    """

    km = _km_a_numero(
        mantenimiento_actual
    )

    if km is None:
        return None

    if km == 1:
        return 5

    return km + 5


def _serie_valores_distintos(
    serie: pd.Series,
) -> str:
    """
    Genera una representación auditable de los valores
    distintos presentes dentro de una visita.
    """

    valores = (
        serie
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    if not valores:
        return ""

    return " | ".join(
        str(valor)
        for valor in valores
    )


def _serie_km_distintos(
    serie: pd.Series,
) -> str:
    """
    Genera una representación comercial de los KM
    distintos existentes dentro de una visita.
    """

    valores = (
        serie
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    return " | ".join(
        _etiqueta_km(
            valor
        )
        for valor in valores
    )


def _avanzar_mantenimiento_por_ciclos(
    mantenimiento_base,
    ciclos: int,
) -> int | None:
    """
    Avanza un mantenimiento una cantidad determinada de
    ciclos preventivos.

    Respeta la transición especial:
        1K -> 5K

    Desde 5K en adelante:
        +5K por ciclo.
    """

    actual = _km_a_numero(
        mantenimiento_base
    )

    if actual is None:
        return None

    for _ in range(
        max(
            ciclos,
            0,
        )
    ):

        actual = (
            _siguiente_mantenimiento_km(
                actual
            )
        )

        if actual is None:
            return None

    return actual


# ============================================================
# ASIGNACIÓN DE VISITAS ANALÍTICAS
# ============================================================

def _asignar_visitas_por_vin(
    grupo: pd.DataFrame,
    ventana_dias: int,
) -> pd.DataFrame:
    """
    Asigna un número de visita analítica dentro de un VIN.

    La ventana se calcula desde la primera fecha de cada
    visita para evitar un encadenamiento indefinido.

    Ejemplo con ventana de 7 días:

        01/01 -> visita 1
        07/01 -> visita 1
        14/01 -> visita 2
    """

    grupo = (
        grupo
        .sort_values(
            [
                "fecha_orden",
                "Id doc",
            ]
        )
        .copy()
    )

    numeros_visita = []

    numero_visita = 0
    inicio_visita = None

    for fecha in grupo[
        "fecha_orden"
    ]:

        if inicio_visita is None:

            numero_visita += 1
            inicio_visita = fecha

        else:

            dias_desde_inicio = (
                fecha
                -
                inicio_visita
            ).days

            if dias_desde_inicio > ventana_dias:

                numero_visita += 1
                inicio_visita = fecha

        numeros_visita.append(
            numero_visita
        )

    grupo[
        "nro_visita_analitica"
    ] = numeros_visita

    return grupo


def asignar_visitas_analiticas(
    historia_preventiva: pd.DataFrame,
    ventana_dias: int = VENTANA_VISITA_DIAS,
) -> pd.DataFrame:
    """
    Toma los preventivos con KM interpretable y asigna
    una visita analítica a cada registro.

    Los preventivos sin KM permanecen en la auditoría,
    pero no participan en la secuencia preventiva.
    """

    base = historia_preventiva.loc[
        historia_preventiva[
            "mantenimiento_km"
        ].notna()
    ].copy()

    base = (
        base
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

    grupos = []

    for _, grupo in base.groupby(
        "vin",
        sort=False,
    ):

        grupos.append(
            _asignar_visitas_por_vin(
                grupo=grupo,
                ventana_dias=ventana_dias,
            )
        )

    if not grupos:
        return base

    resultado = (
        pd.concat(
            grupos,
            ignore_index=True,
        )
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

    return resultado


# ============================================================
# CONSOLIDACIÓN DE VISITAS
# ============================================================

def consolidar_visitas_preventivas(
    registros_con_visita: pd.DataFrame,
) -> pd.DataFrame:
    """
    Consolida todas las órdenes pertenecientes a una misma
    visita analítica.

    Se utiliza la última orden de la visita como registro
    representativo para:

    - mantenimiento KM;
    - cliente;
    - placa;
    - modelo;
    - sede;
    - asesor;
    - número de orden.

    La fecha analítica de la visita será la primera fecha
    observada dentro de la ventana.
    """

    filas = []

    columnas_representativas = [
        "Id doc",
        "doc ref",
        "placa",
        "modelo",
        "año",
        "sede",
        "asesor",
        "nro documento",
        "mantenimiento_km",
        "servicio2",
        "parque",
    ]

    for (
        vin,
        nro_visita,
    ), grupo in registros_con_visita.groupby(
        [
            "vin",
            "nro_visita_analitica",
        ],
        sort=False,
    ):

        grupo = (
            grupo
            .sort_values(
                [
                    "fecha_orden",
                    "Id doc",
                ]
            )
        )

        representante = (
            grupo.iloc[-1]
        )

        fila = {
            "vin":
                vin,

            "nro_visita_analitica":
                int(
                    nro_visita
                ),

            "fecha_visita":
                grupo[
                    "fecha_orden"
                ].min(),

            "fecha_ultima_orden_visita":
                grupo[
                    "fecha_orden"
                ].max(),

            "n_registros_visita":
                len(
                    grupo
                ),

            "n_ordenes_visita":
                grupo[
                    "Id doc"
                ].nunique(
                    dropna=True
                ),

            "n_km_distintos_visita":
                grupo[
                    "mantenimiento_km"
                ].nunique(
                    dropna=True
                ),

            "n_documentos_distintos_visita":
                grupo[
                    "nro documento"
                ].nunique(
                    dropna=True
                ),

            "n_placas_distintas_visita":
                grupo[
                    "placa"
                ].nunique(
                    dropna=True
                ),

            "km_distintos_visita":
                _serie_km_distintos(
                    grupo[
                        "mantenimiento_km"
                    ]
                ),

            "documentos_distintos_visita":
                _serie_valores_distintos(
                    grupo[
                        "nro documento"
                    ]
                ),

            "placas_distintas_visita":
                _serie_valores_distintos(
                    grupo[
                        "placa"
                    ]
                ),
        }

        for columna in columnas_representativas:

            fila[
                columna
            ] = representante[
                columna
            ]

        filas.append(
            fila
        )

    visitas = pd.DataFrame(
        filas
    )

    if visitas.empty:
        return visitas

    visitas[
        "visita_km_multiple"
    ] = (
        visitas[
            "n_km_distintos_visita"
        ]
        > 1
    )

    visitas[
        "visita_documento_multiple"
    ] = (
        visitas[
            "n_documentos_distintos_visita"
        ]
        > 1
    )

    visitas[
        "visita_placa_multiple"
    ] = (
        visitas[
            "n_placas_distintas_visita"
        ]
        > 1
    )

    visitas = (
        visitas
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return visitas


# ============================================================
# COMPORTAMIENTO DE SECUENCIA
# ============================================================

def _clasificar_comportamiento(
    mantenimiento_anterior,
    mantenimiento_actual,
) -> str:
    """
    Clasifica la transición preventiva observada.
    """

    anterior = _km_a_numero(
        mantenimiento_anterior
    )

    actual = _km_a_numero(
        mantenimiento_actual
    )

    if anterior is None:
        return "PRIMERA_VISITA"

    if actual is None:
        return "SIN_KM"

    if actual == anterior:
        return "REPITE_MANTENIMIENTO"

    if actual < anterior:
        return "RETROCESO"

    esperado = (
        _siguiente_mantenimiento_km(
            anterior
        )
    )

    if actual == esperado:
        return "SIGUE_CICLO"

    if (
        esperado is not None
        and actual > esperado
    ):
        return "SALTA_MANTENIMIENTOS"

    return "SECUENCIA_NO_ESTANDAR"


def reconstruir_secuencia_preventiva(
    visitas: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconstruye cronológicamente el historial preventivo
    por VIN.
    """

    if visitas.empty:
        return visitas.copy()

    secuencia = (
        visitas
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ]
        )
        .copy()
    )

    grupo_vin = (
        secuencia.groupby(
            "vin",
            sort=False,
        )
    )

    secuencia[
        "visita_numero"
    ] = (
        grupo_vin
        .cumcount()
        + 1
    )

    secuencia[
        "visitas_previas"
    ] = (
        secuencia[
            "visita_numero"
        ]
        - 1
    )

    secuencia[
        "fecha_visita_anterior"
    ] = (
        grupo_vin[
            "fecha_visita"
        ]
        .shift(1)
    )

    secuencia[
        "mantenimiento_anterior"
    ] = (
        grupo_vin[
            "mantenimiento_km"
        ]
        .shift(1)
    )

    secuencia[
        "dias_desde_visita_anterior"
    ] = (
        secuencia[
            "fecha_visita"
        ]
        -
        secuencia[
            "fecha_visita_anterior"
        ]
    ).dt.days

    secuencia[
        "mantenimiento_esperado_desde_anterior"
    ] = (
        secuencia[
            "mantenimiento_anterior"
        ]
        .apply(
            _siguiente_mantenimiento_km
        )
    )

    secuencia[
        "comportamiento"
    ] = [
        _clasificar_comportamiento(
            anterior,
            actual,
        )
        for anterior, actual in zip(
            secuencia[
                "mantenimiento_anterior"
            ],
            secuencia[
                "mantenimiento_km"
            ],
        )
    ]

    secuencia[
        "es_primera_visita"
    ] = (
        secuencia[
            "comportamiento"
        ]
        .eq(
            "PRIMERA_VISITA"
        )
    )

    secuencia[
        "es_salto_mantenimiento"
    ] = (
        secuencia[
            "comportamiento"
        ]
        .eq(
            "SALTA_MANTENIMIENTOS"
        )
    )

    secuencia[
        "es_retroceso"
    ] = (
        secuencia[
            "comportamiento"
        ]
        .eq(
            "RETROCESO"
        )
    )

    secuencia[
        "es_repeticion"
    ] = (
        secuencia[
            "comportamiento"
        ]
        .eq(
            "REPITE_MANTENIMIENTO"
        )
    )

    secuencia[
        "es_inconsistencia_secuencia"
    ] = (
        secuencia[
            "comportamiento"
        ]
        .isin(
            COMPORTAMIENTOS_INCONSISTENTES
        )
    )

    return (
        secuencia
        .reset_index(
            drop=True
        )
    )


# ============================================================
# TRAYECTORIAS
# ============================================================

def _construir_trayectoria_observada(
    grupo: pd.DataFrame,
) -> str:
    """
    Ejemplo:
        1K → 5K → 15K → 20K
    """

    return " → ".join(
        _etiqueta_km(
            valor
        )
        for valor in grupo[
            "mantenimiento_km"
        ]
    )


def _crear_secuencia_esperada_km(
    grupo: pd.DataFrame,
) -> list[int]:
    """
    Construye la secuencia preventiva teórica.

    PANA:
        comienza desde 1K.

    NOPANA:
        comienza desde el primer mantenimiento observado,
        porque no conocemos su historia anterior.
    """

    km_observados = [
        _km_a_numero(
            valor
        )
        for valor in grupo[
            "mantenimiento_km"
        ]
        if pd.notna(
            valor
        )
    ]

    if not km_observados:
        return []

    parque = (
        grupo[
            "parque"
        ]
        .iloc[-1]
    )

    if parque == "PANA":
        inicio = 1
    else:
        inicio = km_observados[0]

    limite = max(
        km_observados
    )

    siguiente_limite = (
        _siguiente_mantenimiento_km(
            limite
        )
    )

    if siguiente_limite is not None:
        limite = siguiente_limite

    secuencia = [
        inicio
    ]

    actual = inicio

    while actual < limite:

        siguiente = (
            _siguiente_mantenimiento_km(
                actual
            )
        )

        if siguiente is None:
            break

        if siguiente <= actual:
            break

        secuencia.append(
            siguiente
        )

        actual = siguiente

    return secuencia


def _construir_trayectoria_esperada(
    grupo: pd.DataFrame,
) -> str:
    """
    Construye la trayectoria preventiva esperada.
    """

    secuencia = (
        _crear_secuencia_esperada_km(
            grupo
        )
    )

    return " → ".join(
        _etiqueta_km(
            valor
        )
        for valor in secuencia
    )


def _construir_trayectoria_completa(
    grupo: pd.DataFrame,
    fecha_entrega: pd.Timestamp | None,
) -> str:
    """
    Construye una trayectoria temporal legible.

    Ejemplo:
        ENTREGA →(30)→ 1K →(150)→ 5K →(360)→ 20K
        →(e)→ 5K

    Repetición, retroceso y secuencia no estándar
    se marcan como "(e)".

    Los saltos conservan los días reales observados.
    """

    grupo = (
        grupo
        .sort_values(
            "fecha_visita"
        )
    )

    partes = []

    primera_fila = (
        grupo.iloc[0]
    )

    primera_fecha = (
        primera_fila[
            "fecha_visita"
        ]
    )

    primera_etiqueta = (
        _etiqueta_km(
            primera_fila[
                "mantenimiento_km"
            ]
        )
    )

    if (
        fecha_entrega is not None
        and pd.notna(
            fecha_entrega
        )
    ):

        dias_entrega = (
            primera_fecha
            -
            fecha_entrega
        ).days

        partes.append(
            "ENTREGA"
        )

        if dias_entrega < 0:

            partes.append(
                "→(e)→"
            )

        else:

            partes.append(
                f"→({dias_entrega})→"
            )

        partes.append(
            primera_etiqueta
        )

    else:

        partes.append(
            primera_etiqueta
        )

    filas = list(
        grupo.itertuples(
            index=False
        )
    )

    for fila in filas[1:]:

        comportamiento = (
            fila.comportamiento
        )

        etiqueta = (
            _etiqueta_km(
                fila.mantenimiento_km
            )
        )

        if (
            comportamiento
            in COMPORTAMIENTOS_INCONSISTENTES
        ):

            partes.append(
                "→(e)→"
            )

        else:

            dias = (
                fila.dias_desde_visita_anterior
            )

            if pd.isna(
                dias
            ):

                partes.append(
                    "→(?)→"
                )

            else:

                partes.append(
                    f"→({int(dias)})→"
                )

        partes.append(
            etiqueta
        )

    return " ".join(
        partes
    )


def construir_trayectorias_vin(
    secuencia: pd.DataFrame,
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Genera una fila resumen de trayectoria por VIN.
    """

    if secuencia.empty:
        return pd.DataFrame()

    fechas_entrega = (
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
            subset=[
                "vin",
            ],
            keep="last",
        )
        .set_index(
            "vin"
        )[
            "fecha_entrega"
        ]
        .to_dict()
    )

    filas = []

    for vin, grupo in secuencia.groupby(
        "vin",
        sort=False,
    ):

        grupo = (
            grupo
            .sort_values(
                "fecha_visita"
            )
        )

        parque = (
            grupo[
                "parque"
            ]
            .iloc[-1]
        )

        fecha_entrega = (
            fechas_entrega.get(
                vin
            )
            if parque == "PANA"
            else None
        )

        inconsistencias = (
            grupo.loc[
                grupo[
                    "es_inconsistencia_secuencia"
                ],
                "comportamiento",
            ]
        )

        ultima_inconsistencia = (
            inconsistencias.iloc[-1]
            if not inconsistencias.empty
            else pd.NA
        )

        ultima_fila = (
            grupo.iloc[-1]
        )

        siguiente_km = (
            _siguiente_mantenimiento_km(
                ultima_fila[
                    "mantenimiento_km"
                ]
            )
        )

        filas.append(
            {
                "vin":
                    vin,

                "parque":
                    parque,

                "visitas_preventivas":
                    len(
                        grupo
                    ),

                "fecha_primera_visita":
                    grupo[
                        "fecha_visita"
                    ].min(),

                "fecha_ultima_visita":
                    grupo[
                        "fecha_visita"
                    ].max(),

                "kilometraje_primera_visita":
                    grupo[
                        "mantenimiento_km"
                    ].iloc[0],

                "kilometraje_ultima_visita":
                    ultima_fila[
                        "mantenimiento_km"
                    ],

                "kilometraje_esperado":
                    siguiente_km,

                "cantidad_saltos":
                    int(
                        grupo[
                            "es_salto_mantenimiento"
                        ].sum()
                    ),

                "cantidad_retrocesos":
                    int(
                        grupo[
                            "es_retroceso"
                        ].sum()
                    ),

                "cantidad_repeticiones":
                    int(
                        grupo[
                            "es_repeticion"
                        ].sum()
                    ),

                "cantidad_inconsistencias":
                    int(
                        grupo[
                            "es_inconsistencia_secuencia"
                        ].sum()
                    ),

                "tiene_inconsistencia_secuencia":
                    bool(
                        grupo[
                            "es_inconsistencia_secuencia"
                        ].any()
                    ),

                "ultima_inconsistencia":
                    ultima_inconsistencia,

                "trayectoria_observada":
                    _construir_trayectoria_observada(
                        grupo
                    ),

                "trayectoria_esperada":
                    _construir_trayectoria_esperada(
                        grupo
                    ),

                "trayectoria_completa":
                    _construir_trayectoria_completa(
                        grupo=grupo,
                        fecha_entrega=fecha_entrega,
                    ),
            }
        )

    return (
        pd.DataFrame(
            filas
        )
        .sort_values(
            "vin"
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# AUDITORÍA DE VISITAS
# ============================================================

def construir_auditoria_visitas(
    historia_preventiva: pd.DataFrame,
    registros_con_visita: pd.DataFrame,
    visitas: pd.DataFrame,
    secuencia: pd.DataFrame,
) -> dict:
    """
    Resume el efecto de transformar órdenes preventivas
    en visitas analíticas.
    """

    preventivos_con_km = len(
        registros_con_visita
    )

    visitas_analiticas = len(
        visitas
    )

    return {
        "preventivos_base":
            len(
                historia_preventiva
            ),

        "preventivos_con_km":
            preventivos_con_km,

        "preventivos_excluidos_sin_km":
            (
                len(
                    historia_preventiva
                )
                -
                preventivos_con_km
            ),

        "visitas_analiticas":
            visitas_analiticas,

        "registros_consolidados":
            (
                preventivos_con_km
                -
                visitas_analiticas
            ),

        "visitas_con_multiples_registros":
            int(
                (
                    visitas[
                        "n_registros_visita"
                    ]
                    > 1
                ).sum()
            ),

        "visitas_con_km_multiple":
            int(
                visitas[
                    "visita_km_multiple"
                ].sum()
            ),

        "visitas_con_documento_multiple":
            int(
                visitas[
                    "visita_documento_multiple"
                ].sum()
            ),

        "visitas_con_placa_multiple":
            int(
                visitas[
                    "visita_placa_multiple"
                ].sum()
            ),

        "vin_con_historial_preventivo":
            int(
                visitas[
                    "vin"
                ].nunique()
            ),

        "primera_visita":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "PRIMERA_VISITA"
                ).sum()
            ),

        "sigue_ciclo":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "SIGUE_CICLO"
                ).sum()
            ),

        "salta_mantenimientos":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "SALTA_MANTENIMIENTOS"
                ).sum()
            ),

        "repite_mantenimiento":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "REPITE_MANTENIMIENTO"
                ).sum()
            ),

        "retroceso":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "RETROCESO"
                ).sum()
            ),

        "secuencia_no_estandar":
            int(
                (
                    secuencia[
                        "comportamiento"
                    ]
                    == "SECUENCIA_NO_ESTANDAR"
                ).sum()
            ),
    }


# ============================================================
# INTERVALOS HISTÓRICOS VÁLIDOS
# ============================================================

def construir_intervalos_historicos(
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye todas las transiciones preventivas observadas.

    Una referencia histórica válida requiere:

    - transición SIGUE_CICLO;
    - días positivos entre visitas;
    - KM único en la visita origen;
    - KM único en la visita destino.

    Saltos, repeticiones y retrocesos permanecen en el
    historial, pero no alimentan las medianas normales.
    """

    if secuencia.empty:
        return pd.DataFrame()

    intervalos = (
        secuencia
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ]
        )
        .copy()
    )

    grupo_vin = (
        intervalos.groupby(
            "vin",
            sort=False,
        )
    )

    intervalos[
        "visita_km_multiple_anterior"
    ] = (
        grupo_vin[
            "visita_km_multiple"
        ]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    intervalos[
        "sede_anterior"
    ] = (
        grupo_vin[
            "sede"
        ]
        .shift(1)
    )

    intervalos[
        "km_origen"
    ] = (
        intervalos[
            "mantenimiento_anterior"
        ]
    )

    intervalos[
        "km_destino"
    ] = (
        intervalos[
            "mantenimiento_km"
        ]
    )

    etiqueta_origen = (
        intervalos[
            "km_origen"
        ]
        .apply(
            lambda valor:
                _etiqueta_km(
                    valor
                )
                if pd.notna(
                    valor
                )
                else pd.NA
        )
        .astype(
            "string"
        )
    )

    etiqueta_destino = (
        intervalos[
            "km_destino"
        ]
        .apply(
            lambda valor:
                _etiqueta_km(
                    valor
                )
                if pd.notna(
                    valor
                )
                else pd.NA
        )
        .astype(
            "string"
        )
    )

    intervalos[
        "transicion"
    ] = (
        etiqueta_origen
        +
        " → "
        +
        etiqueta_destino
    )

    intervalos[
        "intervalo_valido_referencia"
    ] = (
        intervalos[
            "comportamiento"
        ]
        .eq(
            "SIGUE_CICLO"
        )
        &
        intervalos[
            "dias_desde_visita_anterior"
        ]
        .gt(0)
        &
        ~intervalos[
            "visita_km_multiple"
        ]
        &
        ~intervalos[
            "visita_km_multiple_anterior"
        ]
    )

    return (
        intervalos.loc[
            intervalos[
                "fecha_visita_anterior"
            ].notna(),
            [
                "vin",
                "parque",
                "modelo",
                "sede",
                "sede_anterior",
                "fecha_visita_anterior",
                "fecha_visita",
                "km_origen",
                "km_destino",
                "transicion",
                "dias_desde_visita_anterior",
                "comportamiento",
                "visita_km_multiple_anterior",
                "visita_km_multiple",
                "intervalo_valido_referencia",
            ],
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


# ============================================================
# RESUMEN DE INTERVALOS
# ============================================================

def resumir_intervalos_historicos(
    intervalos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume las transiciones normales disponibles.

    Todavía no aplica jerarquías ni mínimos de muestra.
    """

    if intervalos.empty:
        return pd.DataFrame()

    validos = intervalos.loc[
        intervalos[
            "intervalo_valido_referencia"
        ]
    ].copy()

    if validos.empty:
        return pd.DataFrame()

    resumen = (
        validos
        .groupby(
            [
                "parque",
                "km_origen",
                "km_destino",
                "transicion",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(
            observaciones=(
                "vin",
                "size",
            ),
            vin_unicos=(
                "vin",
                "nunique",
            ),
            dias_mediana=(
                "dias_desde_visita_anterior",
                "median",
            ),
            dias_promedio=(
                "dias_desde_visita_anterior",
                "mean",
            ),
            dias_minimo=(
                "dias_desde_visita_anterior",
                "min",
            ),
            dias_maximo=(
                "dias_desde_visita_anterior",
                "max",
            ),
        )
    )

    resumen[
        "dias_mediana"
    ] = (
        resumen[
            "dias_mediana"
        ]
        .round(1)
    )

    resumen[
        "dias_promedio"
    ] = (
        resumen[
            "dias_promedio"
        ]
        .round(1)
    )

    return (
        resumen
        .sort_values(
            [
                "parque",
                "km_origen",
                "km_destino",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# REFERENCIAS HISTÓRICAS JERÁRQUICAS
# ============================================================

def preparar_intervalos_para_referencias(
    intervalos_historicos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Conserva únicamente los intervalos aptos para construir
    referencias históricas.
    """

    if intervalos_historicos.empty:
        return pd.DataFrame()

    base = intervalos_historicos.loc[
        intervalos_historicos[
            "intervalo_valido_referencia"
        ]
    ].copy()

    base[
        "modelo"
    ] = (
        base[
            "modelo"
        ]
        .astype(
            "string"
        )
        .str.strip()
        .str.upper()
    )

    base[
        "sede_referencia"
    ] = (
        base[
            "sede_anterior"
        ]
        .astype(
            "string"
        )
        .str.strip()
        .str.upper()
    )

    base[
        "dias_intervalo"
    ] = pd.to_numeric(
        base[
            "dias_desde_visita_anterior"
        ],
        errors="coerce",
    )

    base = base.loc[
        base[
            "dias_intervalo"
        ].gt(0)
    ].copy()

    return (
        base
        .reset_index(
            drop=True
        )
    )


def construir_referencia_vin(
    intervalos_validos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula la cadencia histórica propia de cada VIN.

    Para VIN_PROPIO se utilizan todos sus intervalos normales
    válidos.

    La referencia será elegible cuando existan al menos
    MIN_INTERVALOS_VIN intervalos.
    """

    if intervalos_validos.empty:
        return pd.DataFrame()

    referencia = (
        intervalos_validos
        .groupby(
            "vin",
            as_index=False,
        )
        .agg(
            dias_mediana=(
                "dias_intervalo",
                "median",
            ),
            observaciones=(
                "dias_intervalo",
                "size",
            ),
        )
    )

    referencia[
        "elegible"
    ] = (
        referencia[
            "observaciones"
        ]
        >= MIN_INTERVALOS_VIN
    )

    referencia[
        "dias_mediana"
    ] = (
        referencia[
            "dias_mediana"
        ]
        .round()
        .astype(
            "Int64"
        )
    )

    return referencia


def construir_tabla_referencia(
    intervalos_validos: pd.DataFrame,
    columnas_grupo: list[str],
    nombre_metodo: str,
) -> pd.DataFrame:
    """
    Construye una tabla de referencias segmentadas.
    """

    if intervalos_validos.empty:
        return pd.DataFrame()

    referencia = (
        intervalos_validos
        .groupby(
            columnas_grupo,
            as_index=False,
            dropna=False,
        )
        .agg(
            dias_mediana=(
                "dias_intervalo",
                "median",
            ),
            observaciones=(
                "dias_intervalo",
                "size",
            ),
            vin_unicos=(
                "vin",
                "nunique",
            ),
        )
    )

    referencia[
        "elegible"
    ] = (
        referencia[
            "observaciones"
        ]
        >= MIN_REFERENCIAS_SEGMENTO
    )

    referencia[
        "metodo"
    ] = nombre_metodo

    referencia[
        "dias_mediana"
    ] = (
        referencia[
            "dias_mediana"
        ]
        .round()
        .astype(
            "Int64"
        )
    )

    return referencia


def construir_referencias_historicas(
    intervalos_historicos: pd.DataFrame,
) -> dict:
    """
    Construye las capas jerárquicas de referencia.

    Jerarquía:

    1. VIN propio
    2. Parque + Modelo + Transición + Sede
    3. Parque + Modelo + Transición
    4. Parque + Transición
    5. Transición general
    """

    base = (
        preparar_intervalos_para_referencias(
            intervalos_historicos
        )
    )

    referencia_vin = (
        construir_referencia_vin(
            base
        )
    )

    referencia_parque_modelo_transicion_sede = (
        construir_tabla_referencia(
            intervalos_validos=base,
            columnas_grupo=[
                "parque",
                "modelo",
                "km_origen",
                "km_destino",
                "sede_referencia",
            ],
            nombre_metodo=(
                "PARQUE_MODELO_TRANSICION_SEDE"
            ),
        )
    )

    referencia_parque_modelo_transicion = (
        construir_tabla_referencia(
            intervalos_validos=base,
            columnas_grupo=[
                "parque",
                "modelo",
                "km_origen",
                "km_destino",
            ],
            nombre_metodo=(
                "PARQUE_MODELO_TRANSICION"
            ),
        )
    )

    referencia_parque_transicion = (
        construir_tabla_referencia(
            intervalos_validos=base,
            columnas_grupo=[
                "parque",
                "km_origen",
                "km_destino",
            ],
            nombre_metodo=(
                "PARQUE_TRANSICION"
            ),
        )
    )

    referencia_transicion_general = (
        construir_tabla_referencia(
            intervalos_validos=base,
            columnas_grupo=[
                "km_origen",
                "km_destino",
            ],
            nombre_metodo=(
                "TRANSICION_GENERAL"
            ),
        )
    )

    return {
        "intervalos_validos":
            base,

        "referencia_vin":
            referencia_vin,

        "referencia_parque_modelo_transicion_sede":
            referencia_parque_modelo_transicion_sede,

        "referencia_parque_modelo_transicion":
            referencia_parque_modelo_transicion,

        "referencia_parque_transicion":
            referencia_parque_transicion,

        "referencia_transicion_general":
            referencia_transicion_general,
    }


# ============================================================
# AUDITORÍA DE COBERTURA DE REFERENCIAS
# ============================================================

def auditar_referencias_historicas(
    referencias: dict,
) -> pd.DataFrame:
    """
    Resume cuántas referencias existen y cuántas cumplen
    el mínimo de muestra de cada nivel jerárquico.
    """

    configuracion = [
        (
            "VIN_PROPIO",
            referencias[
                "referencia_vin"
            ],
        ),
        (
            "PARQUE_MODELO_TRANSICION_SEDE",
            referencias[
                "referencia_parque_modelo_transicion_sede"
            ],
        ),
        (
            "PARQUE_MODELO_TRANSICION",
            referencias[
                "referencia_parque_modelo_transicion"
            ],
        ),
        (
            "PARQUE_TRANSICION",
            referencias[
                "referencia_parque_transicion"
            ],
        ),
        (
            "TRANSICION_GENERAL",
            referencias[
                "referencia_transicion_general"
            ],
        ),
    ]

    filas = []

    for nivel, tabla in configuracion:

        if tabla.empty:

            total = 0
            elegibles = 0

        else:

            total = len(
                tabla
            )

            elegibles = int(
                tabla[
                    "elegible"
                ].sum()
            )

        filas.append(
            {
                "nivel":
                    nivel,

                "referencias_totales":
                    total,

                "referencias_elegibles":
                    elegibles,

                "referencias_no_elegibles":
                    total
                    -
                    elegibles,
            }
        )

    return pd.DataFrame(
        filas
    )


# ============================================================
# ESTADO ACTUAL DEL VIN
# ============================================================

def construir_estado_actual_vin(
    secuencia: pd.DataFrame,
    trayectorias: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una fila por VIN utilizando su última visita
    preventiva analítica.

    Esta tabla representa el estado actual observado del
    vehículo antes de aplicar la proyección histórica.
    """

    if secuencia.empty:
        return pd.DataFrame()

    ultima_visita = (
        secuencia
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ]
        )
        .groupby(
            "vin",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    columnas_estado = [
        "vin",
        "parque",
        "placa",
        "modelo",
        "año",
        "sede",
        "asesor",
        "nro documento",
        "Id doc",
        "doc ref",
        "fecha_visita",
        "mantenimiento_km",
        "visita_numero",
        "visitas_previas",
        "comportamiento",
        "es_primera_visita",
        "es_salto_mantenimiento",
        "es_retroceso",
        "es_repeticion",
        "visita_km_multiple",
        "dias_desde_visita_anterior",
    ]

    estado = (
        ultima_visita[
            columnas_estado
        ]
        .copy()
        .rename(
            columns={
                "Id doc":
                    "nro_orden_servicio",

                "fecha_visita":
                    "fecha_ultima_visita",

                "mantenimiento_km":
                    "kilometraje_atendido",

                "comportamiento":
                    "comportamiento_ultimo",
            }
        )
    )

    estado[
        "kilometraje_esperado"
    ] = (
        estado[
            "kilometraje_atendido"
        ]
        .apply(
            _siguiente_mantenimiento_km
        )
    )

    columnas_trayectoria = [
        "vin",
        "visitas_preventivas",
        "cantidad_saltos",
        "cantidad_retrocesos",
        "cantidad_repeticiones",
        "cantidad_inconsistencias",
        "tiene_inconsistencia_secuencia",
        "ultima_inconsistencia",
        "trayectoria_observada",
        "trayectoria_esperada",
        "trayectoria_completa",
    ]

    estado = estado.merge(
        trayectorias[
            columnas_trayectoria
        ],
        on="vin",
        how="left",
        validate="one_to_one",
    )

    estado[
        "km_origen_proyeccion"
    ] = (
        estado[
            "kilometraje_atendido"
        ]
    )

    estado[
        "km_destino_proyeccion"
    ] = (
        estado[
            "kilometraje_esperado"
        ]
    )

    return (
        estado
        .sort_values(
            "vin"
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# HELPERS PARA ASIGNACIÓN DE REFERENCIAS
# ============================================================

def _buscar_referencia_unica(
    tabla: pd.DataFrame,
    filtros: dict,
) -> pd.Series | None:
    """
    Busca una referencia elegible que coincida exactamente
    con los filtros entregados.

    Devuelve una sola fila o None.
    """

    if tabla.empty:
        return None

    mascara = pd.Series(
        True,
        index=tabla.index,
    )

    for columna, valor in filtros.items():

        if pd.isna(valor):

            mascara &= (
                tabla[
                    columna
                ].isna()
            )

        else:

            mascara &= (
                tabla[
                    columna
                ]
                .eq(valor)
            )

    mascara &= (
        tabla[
            "elegible"
        ]
    )

    resultado = (
        tabla.loc[
            mascara
        ]
    )

    if resultado.empty:
        return None

    return resultado.iloc[0]


def _asignar_referencia_historica_fila(
    fila: pd.Series,
    referencias: dict,
) -> dict:
    """
    Aplica la jerarquía histórica a un VIN concreto.

    Jerarquía:
    1. VIN propio
    2. Parque + Modelo + Transición + Sede
    3. Parque + Modelo + Transición
    4. Parque + Transición
    5. Transición general
    6. Sin referencia
    """

    vin = fila[
        "vin"
    ]

    parque = fila[
        "parque"
    ]

    modelo = fila[
        "modelo"
    ]

    sede = fila[
        "sede"
    ]

    km_origen = fila[
        "km_origen_proyeccion"
    ]

    km_destino = fila[
        "km_destino_proyeccion"
    ]

    # --------------------------------------------------------
    # 1. VIN propio
    # --------------------------------------------------------

    referencia_vin = (
        referencias[
            "referencia_vin"
        ]
    )

    ref = _buscar_referencia_unica(
        referencia_vin,
        {
            "vin":
                vin,
        },
    )

    if ref is not None:

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                "VIN_PROPIO",

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    # --------------------------------------------------------
    # 2. Parque + Modelo + Transición + Sede
    # --------------------------------------------------------

    tabla = referencias[
        "referencia_parque_modelo_transicion_sede"
    ]

    ref = _buscar_referencia_unica(
        tabla,
        {
            "parque":
                parque,

            "modelo":
                modelo,

            "km_origen":
                km_origen,

            "km_destino":
                km_destino,

            "sede_referencia":
                sede,
        },
    )

    if ref is not None:

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                (
                    "PARQUE_MODELO_TRANSICION_SEDE"
                ),

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    # --------------------------------------------------------
    # 3. Parque + Modelo + Transición
    # --------------------------------------------------------

    tabla = referencias[
        "referencia_parque_modelo_transicion"
    ]

    ref = _buscar_referencia_unica(
        tabla,
        {
            "parque":
                parque,

            "modelo":
                modelo,

            "km_origen":
                km_origen,

            "km_destino":
                km_destino,
        },
    )

    if ref is not None:

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                (
                    "PARQUE_MODELO_TRANSICION"
                ),

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    # --------------------------------------------------------
    # 4. Parque + Transición
    # --------------------------------------------------------

    tabla = referencias[
        "referencia_parque_transicion"
    ]

    ref = _buscar_referencia_unica(
        tabla,
        {
            "parque":
                parque,

            "km_origen":
                km_origen,

            "km_destino":
                km_destino,
        },
    )

    if ref is not None:

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                "PARQUE_TRANSICION",

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    # --------------------------------------------------------
    # 5. Transición general
    # --------------------------------------------------------

    tabla = referencias[
        "referencia_transicion_general"
    ]

    ref = _buscar_referencia_unica(
        tabla,
        {
            "km_origen":
                km_origen,

            "km_destino":
                km_destino,
        },
    )

    if ref is not None:

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                "TRANSICION_GENERAL",

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    # --------------------------------------------------------
    # 6. Sin referencia
    # --------------------------------------------------------

    return {
        "dias_historicos_estimados":
            pd.NA,

        "metodo_historico":
            "SIN_REFERENCIA_HISTORICA",

        "n_referencias_historicas":
            0,
    }


# ============================================================
# PROYECCIÓN HISTÓRICA
# ============================================================

def proyectar_fecha_historica(
    estado_actual: pd.DataFrame,
    referencias: dict,
) -> pd.DataFrame:
    """
    Asigna a cada VIN actual la mejor referencia histórica
    disponible y calcula su fecha histórica proyectada.
    """

    if estado_actual.empty:
        return estado_actual.copy()

    resultado = (
        estado_actual.copy()
    )

    asignaciones = [
        _asignar_referencia_historica_fila(
            fila=fila,
            referencias=referencias,
        )
        for _, fila in resultado.iterrows()
    ]

    asignaciones_df = (
        pd.DataFrame(
            asignaciones,
            index=resultado.index,
        )
    )

    resultado = pd.concat(
        [
            resultado,
            asignaciones_df,
        ],
        axis=1,
    )

    resultado[
        "dias_historicos_estimados"
    ] = (
        resultado[
            "dias_historicos_estimados"
        ]
        .astype(
            "Int64"
        )
    )

    resultado[
        "n_referencias_historicas"
    ] = (
        resultado[
            "n_referencias_historicas"
        ]
        .astype(
            "Int64"
        )
    )

    resultado[
        "fecha_historica"
    ] = (
        resultado[
            "fecha_ultima_visita"
        ]
        +
        pd.to_timedelta(
            resultado[
                "dias_historicos_estimados"
            ],
            unit="D",
        )
    )

    return resultado


# ============================================================
# AUDITORÍA DE COBERTURA SOBRE VIN ACTUALES
# ============================================================

def auditar_cobertura_proyeccion_historica(
    proyeccion_historica: pd.DataFrame,
) -> pd.DataFrame:
    """
    Mide la cobertura REAL de la jerarquía sobre los VIN
    que actualmente tienen historial preventivo.
    """

    if proyeccion_historica.empty:
        return pd.DataFrame()

    total = len(
        proyeccion_historica
    )

    resumen = (
        proyeccion_historica[
            "metodo_historico"
        ]
        .value_counts(
            dropna=False
        )
        .rename_axis(
            "metodo_historico"
        )
        .reset_index(
            name="vin"
        )
    )

    resumen[
        "porcentaje"
    ] = (
        resumen[
            "vin"
        ]
        /
        total
        *
        100
    ).round(2)

    return resumen


# ============================================================
# REFERENCIAS PANA — ENTREGA A 1K
# ============================================================

def construir_intervalos_entrega_1k(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye observaciones históricas ENTREGA -> 1K
    para vehículos PANA.

    Solo utiliza VIN cuyo primer preventivo analítico
    observado fue 1K y cuya fecha de visita es posterior
    o igual a la fecha de entrega.
    """

    if retail.empty or secuencia.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Datos Retail por VIN
    # --------------------------------------------------------

    retail_vin = (
        retail.loc[
            retail["vin"].notna(),
            [
                "vin",
                "modelo",
                "sede",
                "fecha_entrega",
            ],
        ]
        .drop_duplicates(
            subset=["vin"],
            keep="last",
        )
        .rename(
            columns={
                "modelo":
                    "modelo_retail",

                "sede":
                    "sede_retail",
            }
        )
    )

    # --------------------------------------------------------
    # Primera visita preventiva observada por VIN
    # --------------------------------------------------------

    primera_visita = (
        secuencia
        .sort_values(
            [
                "vin",
                "fecha_visita",
                "nro_visita_analitica",
            ]
        )
        .groupby(
            "vin",
            as_index=False,
        )
        .head(1)
        .loc[
            :,
            [
                "vin",
                "parque",
                "fecha_visita",
                "mantenimiento_km",
            ],
        ]
        .copy()
    )

    # --------------------------------------------------------
    # Solo PANA cuya primera visita fue 1K
    # --------------------------------------------------------

    base = primera_visita.loc[
        primera_visita["parque"].eq("PANA")
        &
        primera_visita[
            "mantenimiento_km"
        ].eq(1)
    ].copy()

    base = base.merge(
        retail_vin,
        on="vin",
        how="inner",
        validate="one_to_one",
    )

    base = base.loc[
        base["fecha_entrega"].notna()
    ].copy()

    base[
        "dias_entrega_1k"
    ] = (
        base["fecha_visita"]
        -
        base["fecha_entrega"]
    ).dt.days

    # Solo intervalos temporalmente coherentes
    base = base.loc[
        base["dias_entrega_1k"].ge(0)
    ].copy()

    return (
        base
        .sort_values(
            "vin"
        )
        .reset_index(
            drop=True
        )
    )


def construir_referencias_entrega_1k(
    intervalos_entrega_1k: pd.DataFrame,
) -> dict:
    """
    Construye referencias históricas para PANA sin
    historial preventivo.

    Jerarquía:
    1. Modelo + Sede
    2. Modelo
    3. PANA general
    """

    if intervalos_entrega_1k.empty:

        return {
            "modelo_sede":
                pd.DataFrame(),

            "modelo":
                pd.DataFrame(),

            "general":
                pd.DataFrame(),
        }

    base = (
        intervalos_entrega_1k
        .copy()
    )

    # --------------------------------------------------------
    # Modelo + sede
    # --------------------------------------------------------

    referencia_modelo_sede = (
        base
        .groupby(
            [
                "modelo_retail",
                "sede_retail",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(
            dias_mediana=(
                "dias_entrega_1k",
                "median",
            ),
            observaciones=(
                "vin",
                "size",
            ),
            vin_unicos=(
                "vin",
                "nunique",
            ),
        )
    )

    referencia_modelo_sede[
        "elegible"
    ] = (
        referencia_modelo_sede[
            "observaciones"
        ]
        >= MIN_REFERENCIAS_SEGMENTO
    )

    referencia_modelo_sede[
        "dias_mediana"
    ] = (
        referencia_modelo_sede[
            "dias_mediana"
        ]
        .round()
        .astype("Int64")
    )

    # --------------------------------------------------------
    # Modelo
    # --------------------------------------------------------

    referencia_modelo = (
        base
        .groupby(
            "modelo_retail",
            as_index=False,
            dropna=False,
        )
        .agg(
            dias_mediana=(
                "dias_entrega_1k",
                "median",
            ),
            observaciones=(
                "vin",
                "size",
            ),
            vin_unicos=(
                "vin",
                "nunique",
            ),
        )
    )

    referencia_modelo[
        "elegible"
    ] = (
        referencia_modelo[
            "observaciones"
        ]
        >= MIN_REFERENCIAS_SEGMENTO
    )

    referencia_modelo[
        "dias_mediana"
    ] = (
        referencia_modelo[
            "dias_mediana"
        ]
        .round()
        .astype("Int64")
    )

    # --------------------------------------------------------
    # PANA general
    # --------------------------------------------------------

    general = pd.DataFrame(
        {
            "dias_mediana": [
                int(
                    round(
                        base[
                            "dias_entrega_1k"
                        ].median()
                    )
                )
            ],

            "observaciones": [
                len(base)
            ],

            "vin_unicos": [
                base[
                    "vin"
                ].nunique()
            ],
        }
    )

    general[
        "elegible"
    ] = (
        general[
            "observaciones"
        ]
        >= MIN_REFERENCIAS_SEGMENTO
    )

    return {
        "modelo_sede":
            referencia_modelo_sede,

        "modelo":
            referencia_modelo,

        "general":
            general,
    }


# ============================================================
# PANA SIN HISTORIAL PREVENTIVO
# ============================================================

def construir_pana_sin_historial(
    retail: pd.DataFrame,
    secuencia: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identifica vehículos PANA vendidos por Retail que nunca
    tuvieron una visita preventiva analítica.

    Para este universo:
    - parque = PANA
    - kilometraje atendido = NA
    - kilometraje esperado = 1K
    - ancla temporal = fecha de entrega
    """

    if retail.empty:
        return pd.DataFrame()

    vin_con_preventivo = set(
        secuencia.loc[
            secuencia["vin"].notna(),
            "vin",
        ].unique()
    )

    pana = (
        retail.loc[
            retail["vin"].notna()
            &
            ~retail[
                "vin"
            ].isin(
                vin_con_preventivo
            )
        ]
        .copy()
    )

    pana = (
        pana
        .drop_duplicates(
            subset=["vin"],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    pana[
        "parque"
    ] = "PANA"

    pana[
        "kilometraje_atendido"
    ] = pd.NA

    pana[
        "kilometraje_esperado"
    ] = 1

    pana[
        "fecha_ultima_visita"
    ] = pd.NaT

    pana[
        "visitas_preventivas"
    ] = 0

    pana[
        "es_primera_visita"
    ] = True

    return pana


# ============================================================
# ASIGNACIÓN HISTÓRICA — PANA SIN HISTORIAL
# ============================================================

def _buscar_referencia_entrega_1k(
    fila: pd.Series,
    referencias: dict,
) -> dict:
    """
    Selecciona la mejor referencia ENTREGA -> 1K para
    un PANA sin historial preventivo.
    """

    modelo = fila[
        "modelo"
    ]

    sede = fila[
        "sede"
    ]

    # --------------------------------------------------------
    # 1. Modelo + sede
    # --------------------------------------------------------

    tabla = referencias[
        "modelo_sede"
    ]

    if not tabla.empty:

        mascara = (
            tabla[
                "modelo_retail"
            ].eq(modelo)
            &
            tabla[
                "sede_retail"
            ].eq(sede)
            &
            tabla[
                "elegible"
            ]
        )

        resultado = tabla.loc[
            mascara
        ]

        if not resultado.empty:

            ref = resultado.iloc[0]

            return {
                "dias_historicos_estimados":
                    int(
                        ref[
                            "dias_mediana"
                        ]
                    ),

                "metodo_historico":
                    "PANA_ENTREGA_1K_MODELO_SEDE",

                "n_referencias_historicas":
                    int(
                        ref[
                            "observaciones"
                        ]
                    ),
            }

    # --------------------------------------------------------
    # 2. Modelo
    # --------------------------------------------------------

    tabla = referencias[
        "modelo"
    ]

    if not tabla.empty:

        mascara = (
            tabla[
                "modelo_retail"
            ].eq(modelo)
            &
            tabla[
                "elegible"
            ]
        )

        resultado = tabla.loc[
            mascara
        ]

        if not resultado.empty:

            ref = resultado.iloc[0]

            return {
                "dias_historicos_estimados":
                    int(
                        ref[
                            "dias_mediana"
                        ]
                    ),

                "metodo_historico":
                    "PANA_ENTREGA_1K_MODELO",

                "n_referencias_historicas":
                    int(
                        ref[
                            "observaciones"
                        ]
                    ),
            }

    # --------------------------------------------------------
    # 3. General PANA
    # --------------------------------------------------------

    tabla = referencias[
        "general"
    ]

    if (
        not tabla.empty
        and bool(
            tabla.iloc[0][
                "elegible"
            ]
        )
    ):

        ref = tabla.iloc[0]

        return {
            "dias_historicos_estimados":
                int(
                    ref[
                        "dias_mediana"
                    ]
                ),

            "metodo_historico":
                "PANA_ENTREGA_1K_GENERAL",

            "n_referencias_historicas":
                int(
                    ref[
                        "observaciones"
                    ]
                ),
        }

    return {
        "dias_historicos_estimados":
            pd.NA,

        "metodo_historico":
            "SIN_REFERENCIA_HISTORICA",

        "n_referencias_historicas":
            0,
    }


def proyectar_pana_sin_historial(
    pana_sin_historial: pd.DataFrame,
    referencias_entrega_1k: dict,
) -> pd.DataFrame:
    """
    Proyecta históricamente el primer mantenimiento 1K de
    los PANA sin historial preventivo.
    """

    if pana_sin_historial.empty:
        return pana_sin_historial.copy()

    resultado = (
        pana_sin_historial
        .copy()
    )

    asignaciones = [
        _buscar_referencia_entrega_1k(
            fila=fila,
            referencias=
                referencias_entrega_1k,
        )
        for _, fila in resultado.iterrows()
    ]

    asignaciones_df = pd.DataFrame(
        asignaciones,
        index=resultado.index,
    )

    resultado = pd.concat(
        [
            resultado,
            asignaciones_df,
        ],
        axis=1,
    )

    resultado[
        "dias_historicos_estimados"
    ] = (
        resultado[
            "dias_historicos_estimados"
        ]
        .astype("Int64")
    )

    resultado[
        "n_referencias_historicas"
    ] = (
        resultado[
            "n_referencias_historicas"
        ]
        .astype("Int64")
    )

    resultado[
        "fecha_historica"
    ] = (
        resultado[
            "fecha_entrega"
        ]
        +
        pd.to_timedelta(
            resultado[
                "dias_historicos_estimados"
            ],
            unit="D",
        )
    )

    return resultado


# ============================================================
# PROYECCIÓN POR POLÍTICA COMERCIAL
# ============================================================

def construir_fecha_politica_con_historial(
    proyeccion_historica: pd.DataFrame,
    retail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula la fecha política de vehículos que ya cuentan
    con historial preventivo.

    Reglas:

    PANA:
        - Si el último mantenimiento es 1K:
          el siguiente 5K vence a los 6 meses desde entrega.
          El 1K no reinicia el reloj.

        - Desde 5K en adelante:
          cada mantenimiento preventivo reinicia el ciclo
          de 6 meses.

    NOPANA:
        - Al no conocerse la fecha de entrega, el ciclo se
          calcula desde el último preventivo observado:
          + 6 meses.
    """

    if proyeccion_historica.empty:
        return proyeccion_historica.copy()

    resultado = (
        proyeccion_historica
        .copy()
    )

    # --------------------------------------------------------
    # Fecha entrega PANA
    # --------------------------------------------------------

    entregas = (
        retail.loc[
            retail["vin"].notna(),
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

    resultado = resultado.merge(
        entregas,
        on="vin",
        how="left",
        validate="one_to_one",
    )

    resultado[
        "fecha_politica"
    ] = pd.NaT

    resultado[
        "regla_politica"
    ] = pd.Series(
        pd.NA,
        index=resultado.index,
        dtype="string",
    )

    # --------------------------------------------------------
    # 1. PANA cuyo último preventivo fue 1K
    # --------------------------------------------------------

    mask_pana_1k = (
        resultado[
            "parque"
        ].eq("PANA")
        &
        resultado[
            "kilometraje_atendido"
        ].eq(1)
        &
        resultado[
            "fecha_entrega"
        ].notna()
    )

    resultado.loc[
        mask_pana_1k,
        "fecha_politica",
    ] = (
        resultado.loc[
            mask_pana_1k,
            "fecha_entrega",
        ]
        +
        pd.DateOffset(
            months=6
        )
    )

    resultado.loc[
        mask_pana_1k,
        "regla_politica",
    ] = "PANA_1K_A_5K_DESDE_ENTREGA_6_MESES"

    # --------------------------------------------------------
    # 2. PANA desde 5K en adelante
    # --------------------------------------------------------

    mask_pana_ciclo = (
        resultado[
            "parque"
        ].eq("PANA")
        &
        resultado[
            "kilometraje_atendido"
        ].gt(1)
        &
        resultado[
            "fecha_ultima_visita"
        ].notna()
    )

    resultado.loc[
        mask_pana_ciclo,
        "fecha_politica",
    ] = (
        resultado.loc[
            mask_pana_ciclo,
            "fecha_ultima_visita",
        ]
        +
        pd.DateOffset(
            months=6
        )
    )

    resultado.loc[
        mask_pana_ciclo,
        "regla_politica",
    ] = "PANA_CICLO_6_MESES"

    # --------------------------------------------------------
    # 3. NOPANA con preventivo
    # --------------------------------------------------------

    mask_nopana = (
        resultado[
            "parque"
        ].eq("NOPANA")
        &
        resultado[
            "fecha_ultima_visita"
        ].notna()
    )

    resultado.loc[
        mask_nopana,
        "fecha_politica",
    ] = (
        resultado.loc[
            mask_nopana,
            "fecha_ultima_visita",
        ]
        +
        pd.DateOffset(
            months=6
        )
    )

    resultado.loc[
        mask_nopana,
        "regla_politica",
    ] = "NOPANA_ULTIMO_PREVENTIVO_6_MESES"

    return resultado


def construir_fecha_politica_pana_sin_historial(
    proyeccion_pana_sin_historial: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula la política para PANA que nunca tuvo un
    preventivo observado.

    Regla:
        ENTREGA -> 1K
        1 mes desde fecha de entrega.
    """

    if proyeccion_pana_sin_historial.empty:
        return (
            proyeccion_pana_sin_historial
            .copy()
        )

    resultado = (
        proyeccion_pana_sin_historial
        .copy()
    )

    resultado[
        "fecha_politica"
    ] = (
        resultado[
            "fecha_entrega"
        ]
        +
        pd.DateOffset(
            months=1
        )
    )

    resultado[
        "regla_politica"
    ] = "PANA_ENTREGA_A_1K_1_MES"

    return resultado


# ============================================================
# AUDITORÍA DE POLÍTICA
# ============================================================

def auditar_proyeccion_politica(
    con_historial: pd.DataFrame,
    pana_sin_historial: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume la aplicación de las reglas de política.
    """

    bases = [
        con_historial[
            [
                "vin",
                "regla_politica",
                "fecha_politica",
            ]
        ],
        pana_sin_historial[
            [
                "vin",
                "regla_politica",
                "fecha_politica",
            ]
        ],
    ]

    total = pd.concat(
        bases,
        ignore_index=True,
    )

    resumen = (
        total
        .groupby(
            "regla_politica",
            dropna=False,
        )
        .agg(
            vin=(
                "vin",
                "size",
            ),
            con_fecha_politica=(
                "fecha_politica",
                lambda x:
                    x.notna().sum(),
            ),
        )
        .reset_index()
    )

    return resumen


# ============================================================
# ESTADOS TEMPORALES DE DEMANDA
# ============================================================

def _normalizar_fecha_generacion(
    fecha_generacion=None,
) -> pd.Timestamp:
    """
    Normaliza la fecha utilizada como corte de la proyección.

    Si no se recibe una fecha explícita, utiliza la fecha
    local de ejecución del motor.
    """

    if fecha_generacion is None:
        return pd.Timestamp.today().normalize()

    return pd.Timestamp(
        fecha_generacion
    ).normalize()


def _clasificar_estado_temporal(
    fecha_objetivo,
    fecha_generacion: pd.Timestamp,
    fecha_ultima_visita=None,
) -> str:
    """
    Clasifica temporalmente una fecha objetivo respecto
    de la fecha de generación del motor.

    Prioridad:
    1. Sin fecha
    2. Estados vencidos
    3. En fecha
    4. Servicio muy reciente
    5. Estados futuros
    """

    if pd.isna(
        fecha_objetivo
    ):
        return "SIN_FECHA_ESTIMABLE"

    fecha_objetivo = pd.Timestamp(
        fecha_objetivo
    ).normalize()

    dias_hasta = (
        fecha_objetivo
        -
        fecha_generacion
    ).days

    # --------------------------------------------------------
    # Vencidos
    # --------------------------------------------------------

    if dias_hasta <= -180:
        return "VENCIDO_LEJANO"

    if -179 <= dias_hasta <= -31:
        return "VENCIDO_CERCANO"

    if -30 <= dias_hasta <= -8:
        return "VENCIDO_RECIENTE"

    # --------------------------------------------------------
    # Ventana actual ±7 días
    # --------------------------------------------------------

    if -7 <= dias_hasta <= 7:
        return "EN_FECHA"

    # --------------------------------------------------------
    # Regla especial: servicio muy reciente
    # --------------------------------------------------------

    if pd.notna(
        fecha_ultima_visita
    ):

        fecha_ultima_visita = pd.Timestamp(
            fecha_ultima_visita
        ).normalize()

        dias_desde_visita = (
            fecha_generacion
            -
            fecha_ultima_visita
        ).days

        if (
            0 <= dias_desde_visita <= 30
            and dias_hasta > 7
        ):
            return "SERVICIO_MUY_RECIENTE"

    # --------------------------------------------------------
    # Futuros
    # --------------------------------------------------------

    if 8 <= dias_hasta <= 30:
        return "FUTURO_RECIENTE"

    if 31 <= dias_hasta <= 150:
        return "FUTURO_PROXIMO"

    if dias_hasta > 150:
        return "FUTURO_LEJANO"

    return "SIN_FECHA_ESTIMABLE"


def _agregar_estado_perspectiva(
    base: pd.DataFrame,
    columna_fecha: str,
    sufijo: str,
    fecha_generacion: pd.Timestamp,
) -> pd.DataFrame:
    """
    Agrega días hasta objetivo, días de atraso y estado
    para una perspectiva determinada.
    """

    resultado = (
        base.copy()
    )

    columna_dias = (
        f"dias_hasta_{sufijo}"
    )

    columna_atraso = (
        f"dias_atraso_{sufijo}"
    )

    columna_estado = (
        f"estado_{sufijo}"
    )

    resultado[
        columna_dias
    ] = (
        resultado[
            columna_fecha
        ]
        -
        fecha_generacion
    ).dt.days.astype(
        "Int64"
    )

    resultado[
        columna_atraso
    ] = (
        -resultado[
            columna_dias
        ]
    ).clip(
        lower=0
    ).astype(
        "Int64"
    )

    resultado[
        columna_estado
    ] = [
        _clasificar_estado_temporal(
            fecha_objetivo=
                fecha_objetivo,
            fecha_generacion=
                fecha_generacion,
            fecha_ultima_visita=
                fecha_ultima_visita,
        )
        for (
            fecha_objetivo,
            fecha_ultima_visita,
        ) in zip(
            resultado[
                columna_fecha
            ],
            resultado[
                "fecha_ultima_visita"
            ],
        )
    ]

    return resultado


def agregar_estados_temporales(
    base: pd.DataFrame,
    fecha_generacion=None,
) -> pd.DataFrame:
    """
    Construye las tres perspectivas temporales:

    - histórica;
    - política;
    - más inmediata.

    El motor conserva las tres. Streamlit decidirá después
    cuál perspectiva mostrar como fecha objetivo comercial.
    """

    if base.empty:
        return base.copy()

    resultado = (
        base.copy()
    )

    fecha_corte = (
        _normalizar_fecha_generacion(
            fecha_generacion
        )
    )

    resultado[
        "fecha_generacion"
    ] = fecha_corte

    # --------------------------------------------------------
    # Fecha más inmediata
    # --------------------------------------------------------

    resultado[
        "fecha_mas_inmediata"
    ] = (
        resultado[
            [
                "fecha_historica",
                "fecha_politica",
            ]
        ]
        .min(
            axis=1
        )
    )

    # --------------------------------------------------------
    # Diferencia entre histórica y política
    # --------------------------------------------------------

    resultado[
        "diferencia_historica_politica_dias"
    ] = (
        resultado[
            "fecha_historica"
        ]
        -
        resultado[
            "fecha_politica"
        ]
    ).dt.days.astype(
        "Int64"
    )

    # --------------------------------------------------------
    # Perspectiva histórica
    # --------------------------------------------------------

    resultado = (
        _agregar_estado_perspectiva(
            base=resultado,
            columna_fecha=
                "fecha_historica",
            sufijo=
                "historico",
            fecha_generacion=
                fecha_corte,
        )
    )

    # --------------------------------------------------------
    # Perspectiva política
    # --------------------------------------------------------

    resultado = (
        _agregar_estado_perspectiva(
            base=resultado,
            columna_fecha=
                "fecha_politica",
            sufijo=
                "politica",
            fecha_generacion=
                fecha_corte,
        )
    )

    # --------------------------------------------------------
    # Perspectiva más inmediata
    # --------------------------------------------------------

    resultado = (
        _agregar_estado_perspectiva(
            base=resultado,
            columna_fecha=
                "fecha_mas_inmediata",
            sufijo=
                "mas_inmediata",
            fecha_generacion=
                fecha_corte,
        )
    )

    return resultado


# ============================================================
# AUDITORÍA DE ESTADOS TEMPORALES
# ============================================================

def auditar_estados_temporales(
    con_historial: pd.DataFrame,
    pana_sin_historial: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resume la distribución de estados para las tres
    perspectivas disponibles.
    """

    bases = [
        con_historial,
        pana_sin_historial,
    ]

    universo = pd.concat(
        bases,
        ignore_index=True,
    )

    configuracion = [
        (
            "HISTORICA",
            "estado_historico",
        ),
        (
            "POLITICA",
            "estado_politica",
        ),
        (
            "MAS_INMEDIATA",
            "estado_mas_inmediata",
        ),
    ]

    filas = []

    total = len(
        universo
    )

    for perspectiva, columna in configuracion:

        conteo = (
            universo[
                columna
            ]
            .value_counts(
                dropna=False
            )
        )

        for estado, cantidad in conteo.items():

            filas.append(
                {
                    "perspectiva":
                        perspectiva,

                    "estado":
                        estado,

                    "vin":
                        int(
                            cantidad
                        ),

                    "porcentaje":
                        round(
                            cantidad
                            /
                            total
                            *
                            100,
                            2,
                        ),
                }
            )

    return pd.DataFrame(
        filas
    )


# ============================================================
# CLIENTE ACTUAL
# ============================================================

def enriquecer_cliente_actual(
    base: pd.DataFrame,
    clientes: pd.DataFrame,
    fuente_cliente: str,
) -> pd.DataFrame:
    """
    Enriquece el documento del cliente actual con la
    información vigente disponible en clientes.xlsx.

    La selección del documento ya viene determinada por
    el origen de la base:

    - ULTIMO_PREVENTIVO:
      documento registrado en la última visita preventiva.

    - RETAIL:
      documento registrado en la venta, utilizado para
      PANA sin historial preventivo.
    """

    if base.empty:
        return base.copy()

    resultado = (
        base
        .copy()
    )

    resultado = resultado.rename(
        columns={
            "nro documento":
                "nro_documento",
        }
    )

    resultado[
        "fuente_cliente"
    ] = fuente_cliente

    maestro_clientes = (
        clientes[
            [
                "nro documento",
                "nombre",
                "telefono",
                "correo",
            ]
        ]
        .copy()
        .rename(
            columns={
                "nro documento":
                    "nro_documento",
            }
        )
    )

    resultado = resultado.merge(
        maestro_clientes,
        on="nro_documento",
        how="left",
        validate="many_to_one",
    )

    resultado[
        "cliente_encontrado"
    ] = (
        resultado[
            "nombre"
        ].notna()
        |
        resultado[
            "telefono"
        ].notna()
        |
        resultado[
            "correo"
        ].notna()
    )

    return resultado


# ============================================================
# UNIFICACIÓN DEL UNIVERSO DE DEMANDA
# ============================================================

def construir_base_demanda(
    con_historial: pd.DataFrame,
    pana_sin_historial: pd.DataFrame,
    clientes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una sola fila operacional por VIN.

    Incluye:
    - PANA con historial;
    - NOPANA con historial;
    - PANA sin historial.

    NOPANA sin historial no forma parte del universo porque
    no dispone de ancla preventiva válida.
    """

    # --------------------------------------------------------
    # 1. Vehículos con historial
    # --------------------------------------------------------

    base_historial = (
        enriquecer_cliente_actual(
            base=con_historial,
            clientes=clientes,
            fuente_cliente=
                "ULTIMO_PREVENTIVO",
        )
    )

    base_historial[
        "tipo_historial"
    ] = "CON_HISTORIAL_PREVENTIVO"

    # --------------------------------------------------------
    # 2. PANA sin historial
    # --------------------------------------------------------

    base_sin_historial = (
        enriquecer_cliente_actual(
            base=pana_sin_historial,
            clientes=clientes,
            fuente_cliente=
                "RETAIL",
        )
    )

    base_sin_historial[
        "tipo_historial"
    ] = "SIN_HISTORIAL_PREVENTIVO"

    # --------------------------------------------------------
    # 3. Estandarizar columnas que no existen en PANA
    #    sin historial
    # --------------------------------------------------------

    columnas_default = {
        "placa":
            pd.NA,

        "nro_orden_servicio":
            pd.NA,

        "doc ref":
            pd.NA,

        "fecha_ultima_visita":
            pd.NaT,

        "kilometraje_atendido":
            pd.NA,

        "comportamiento_ultimo":
            "SIN_HISTORIAL",

        "cantidad_saltos":
            0,

        "cantidad_retrocesos":
            0,

        "cantidad_repeticiones":
            0,

        "cantidad_inconsistencias":
            0,

        "tiene_inconsistencia_secuencia":
            False,

        "ultima_inconsistencia":
            pd.NA,

        "trayectoria_observada":
            pd.NA,

        "trayectoria_esperada":
            "1K → 5K",

        "trayectoria_completa":
            "ENTREGA → 1K",
    }

    for (
        columna,
        valor_default,
    ) in columnas_default.items():

        if columna not in base_sin_historial.columns:
            base_sin_historial[
                columna
            ] = valor_default

    # --------------------------------------------------------
    # 4. Columnas operacionales definitivas
    # --------------------------------------------------------

    columnas_salida = [
        # Vehículo
        "vin",
        "placa",
        "modelo",
        "año",
        "parque",

        # Cliente actual
        "nro_documento",
        "nombre",
        "telefono",
        "correo",
        "fuente_cliente",
        "cliente_encontrado",

        # Situación histórica
        "tipo_historial",
        "fecha_entrega",
        "fecha_ultima_visita",
        "nro_orden_servicio",
        "doc ref",
        "sede",
        "asesor",
        "visitas_preventivas",
        "kilometraje_atendido",
        "kilometraje_siguiente_ciclo",
        "kilometraje_esperado_actual",
        "comportamiento_ultimo",

        # Comportamiento
        "cantidad_saltos",
        "cantidad_retrocesos",
        "cantidad_repeticiones",
        "cantidad_inconsistencias",
        "tiene_inconsistencia_secuencia",
        "ultima_inconsistencia",

        # Trayectorias
        "trayectoria_observada",
        "trayectoria_esperada",
        "trayectoria_completa",

        # Proyección histórica
        "dias_historicos_estimados",
        "fecha_historica",
        "metodo_historico",
        "n_referencias_historicas",

        # Política
        "fecha_politica",
        "regla_politica",

        # Comparación
        "fecha_mas_inmediata",
        "diferencia_historica_politica_dias",

        # Perspectiva histórica
        "dias_hasta_historico",
        "dias_atraso_historico",
        "estado_historico",

        # Perspectiva política
        "dias_hasta_politica",
        "dias_atraso_politica",
        "estado_politica",

        # Perspectiva más inmediata
        "dias_hasta_mas_inmediata",
        "dias_atraso_mas_inmediata",
        "estado_mas_inmediata",

        # Generación
        "fecha_generacion",
    ]

    # --------------------------------------------------------
    # 5. Garantizar mismo contrato entre ambas bases
    # --------------------------------------------------------

    for columna in columnas_salida:

        if columna not in base_historial.columns:
            base_historial[
                columna
            ] = pd.NA

        if columna not in base_sin_historial.columns:
            base_sin_historial[
                columna
            ] = pd.NA

    # --------------------------------------------------------
    # 6. Unión del universo
    # --------------------------------------------------------

    base_demanda = pd.concat(
        [
            base_historial[
                columnas_salida
            ],
            base_sin_historial[
                columnas_salida
            ],
        ],
        ignore_index=True,
    )

    # --------------------------------------------------------
    # 7. Control estructural
    # --------------------------------------------------------

    if base_demanda[
        "vin"
    ].duplicated().any():

        duplicados = int(
            base_demanda[
                "vin"
            ]
            .duplicated(
                keep=False
            )
            .sum()
        )

        raise ValueError(
            "BASE_DEMANDA contiene VIN duplicados. "
            f"Registros involucrados: {duplicados:,}"
        )

    return (
        base_demanda
        .sort_values(
            [
                "parque",
                "sede",
                "vin",
            ],
            na_position="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# AUDITORÍA DE BASE DEMANDA
# ============================================================

def auditar_base_demanda(
    base_demanda: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ejecuta controles básicos sobre la base operacional
    consolidada.
    """

    if base_demanda.empty:
        return pd.DataFrame()

    total = len(
        base_demanda
    )

    controles = [
        (
            "TOTAL_VIN",
            total,
        ),
        (
            "VIN_DUPLICADOS",
            int(
                base_demanda[
                    "vin"
                ].duplicated().sum()
            ),
        ),
        (
            "PANA",
            int(
                base_demanda[
                    "parque"
                ].eq(
                    "PANA"
                ).sum()
            ),
        ),
        (
            "NOPANA",
            int(
                base_demanda[
                    "parque"
                ].eq(
                    "NOPANA"
                ).sum()
            ),
        ),
        (
            "CON_HISTORIAL_PREVENTIVO",
            int(
                base_demanda[
                    "tipo_historial"
                ]
                .eq(
                    "CON_HISTORIAL_PREVENTIVO"
                )
                .sum()
            ),
        ),
        (
            "SIN_HISTORIAL_PREVENTIVO",
            int(
                base_demanda[
                    "tipo_historial"
                ]
                .eq(
                    "SIN_HISTORIAL_PREVENTIVO"
                )
                .sum()
            ),
        ),
        (
            "DOCUMENTO_VACIO",
            int(
                base_demanda[
                    "nro_documento"
                ].isna().sum()
            ),
        ),
        (
            "CLIENTE_NO_ENCONTRADO",
            int(
                (
                    ~base_demanda[
                        "cliente_encontrado"
                    ]
                ).sum()
            ),
        ),
        (
            "FECHA_HISTORICA_VACIA",
            int(
                base_demanda[
                    "fecha_historica"
                ].isna().sum()
            ),
        ),
        (
            "FECHA_POLITICA_VACIA",
            int(
                base_demanda[
                    "fecha_politica"
                ].isna().sum()
            ),
        ),
    ]

    filas = []

    for indicador, casos in controles:

        filas.append(
            {
                "indicador":
                    indicador,

                "casos":
                    casos,

                "total_base":
                    total,

                "porcentaje":
                    round(
                        casos
                        /
                        total
                        *
                        100,
                        2,
                    ),
            }
        )

    return pd.DataFrame(
        filas
    )


# ============================================================
# 
# ============================================================

def agregar_kilometraje_esperado_actual(
    base: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula el nivel preventivo esperado a la fecha de
    generación.

    Conserva dos conceptos:

    - kilometraje_siguiente_ciclo:
      siguiente mantenimiento inmediatamente posterior al
      último observado.

    - kilometraje_esperado_actual:
      mantenimiento aproximado que correspondería al vehículo
      considerando el tiempo transcurrido hasta hoy.

    Para avanzar el ciclo se utiliza la cadencia temporal
    de política de 6 meses.

    Si la fecha del siguiente ciclo todavía no ha vencido,
    ambos valores coinciden.

    Si la fecha ya pasó, se avanza un ciclo por cada bloque
    de 6 meses, considerando también el ciclo actualmente
    en curso.
    """

    if base.empty:
        return base.copy()

    resultado = (
        base.copy()
    )

    # El campo existente pasa a representar explícitamente
    # el siguiente ciclo inmediatamente posterior.
    resultado = resultado.rename(
        columns={
            "kilometraje_esperado":
                "kilometraje_siguiente_ciclo",
        }
    )

    resultado[
        "kilometraje_esperado_actual"
    ] = (
        resultado[
            "kilometraje_siguiente_ciclo"
        ]
        .copy()
    )

    fecha_generacion = pd.to_datetime(
        resultado[
            "fecha_generacion"
        ],
        errors="coerce",
    )

    fecha_politica = pd.to_datetime(
        resultado[
            "fecha_politica"
        ],
        errors="coerce",
    )

    kilometrajes_actuales = []

    for (
        km_siguiente,
        fecha_objetivo,
        fecha_corte,
    ) in zip(
        resultado[
            "kilometraje_siguiente_ciclo"
        ],
        fecha_politica,
        fecha_generacion,
    ):

        km_siguiente = _km_a_numero(
            km_siguiente
        )

        if (
            km_siguiente is None
            or pd.isna(fecha_objetivo)
            or pd.isna(fecha_corte)
        ):

            kilometrajes_actuales.append(
                km_siguiente
            )
            continue

        # Si el siguiente mantenimiento todavía no vence,
        # ese sigue siendo el mantenimiento esperado.
        if fecha_corte <= fecha_objetivo:

            kilometrajes_actuales.append(
                km_siguiente
            )
            continue

        # ----------------------------------------------------
        # Meses transcurridos desde la fecha política que
        # correspondía al siguiente mantenimiento.
        # ----------------------------------------------------

        meses_transcurridos = (
            (
                fecha_corte.year
                -
                fecha_objetivo.year
            )
            * 12
            +
            (
                fecha_corte.month
                -
                fecha_objetivo.month
            )
        )

        # Ajuste cuando todavía no se alcanzó el día del mes.
        if (
            fecha_corte.day
            <
            fecha_objetivo.day
        ):
            meses_transcurridos -= 1

        # El km_siguiente ya representa el primer ciclo.
        # Por eso calculamos cuántos ciclos ADICIONALES
        # corresponden después de esa fecha.
        ciclos_adicionales = (
            meses_transcurridos
            // 6
            +
            1
        )

        km_actual = (
            _avanzar_mantenimiento_por_ciclos(
                mantenimiento_base=
                    km_siguiente,
                ciclos=
                    ciclos_adicionales,
            )
        )

        kilometrajes_actuales.append(
            km_actual
        )

    resultado[
        "kilometraje_esperado_actual"
    ] = pd.Series(
        kilometrajes_actuales,
        index=resultado.index,
        dtype="Int64",
    )

    return resultado

# ============================================================
# PIPELINE FINAL DEL HISTORIAL ANALÍTICO
# ============================================================

def construir_historial_analitico(
    historia_preventiva: pd.DataFrame,
    retail: pd.DataFrame,
    clientes: pd.DataFrame,
    ventana_dias: int = VENTANA_VISITA_DIAS,
) -> dict:
    """
    Punto de entrada oficial del historial preventivo.

    Construye:

    1. visitas analíticas;
    2. secuencia preventiva;
    3. trayectorias por VIN;
    4. auditoría de visitas;
    5. intervalos históricos;
    6. resumen de intervalos;
    7. referencias históricas jerárquicas;
    8. auditoría de cobertura.
    """

    # --------------------------------------------------------
    # 1. Asignar registros a visitas
    # --------------------------------------------------------

    registros_con_visita = (
        asignar_visitas_analiticas(
            historia_preventiva=
                historia_preventiva,
            ventana_dias=
                ventana_dias,
        )
    )

    # --------------------------------------------------------
    # 2. Consolidar órdenes
    # --------------------------------------------------------

    visitas = (
        consolidar_visitas_preventivas(
            registros_con_visita
        )
    )

    # --------------------------------------------------------
    # 3. Reconstruir secuencia
    # --------------------------------------------------------

    secuencia = (
        reconstruir_secuencia_preventiva(
            visitas
        )
    )

    # --------------------------------------------------------
    # 4. Construir trayectorias
    # --------------------------------------------------------

    trayectorias = (
        construir_trayectorias_vin(
            secuencia=secuencia,
            retail=retail,
        )
    )

    # --------------------------------------------------------
    # 5. Auditoría de visitas
    # --------------------------------------------------------

    auditoria_visitas = (
        construir_auditoria_visitas(
            historia_preventiva=
                historia_preventiva,
            registros_con_visita=
                registros_con_visita,
            visitas=
                visitas,
            secuencia=
                secuencia,
        )
    )

    # --------------------------------------------------------
    # 6. Intervalos históricos
    # --------------------------------------------------------

    intervalos_historicos = (
        construir_intervalos_historicos(
            secuencia
        )
    )

    # --------------------------------------------------------
    # 7. Resumen descriptivo
    # --------------------------------------------------------

    resumen_intervalos = (
        resumir_intervalos_historicos(
            intervalos_historicos
        )
    )

    # --------------------------------------------------------
    # 8. Referencias históricas
    # --------------------------------------------------------

    referencias_historicas = (
        construir_referencias_historicas(
            intervalos_historicos
        )
    )

    # --------------------------------------------------------
    # 9. Auditoría de cobertura
    # --------------------------------------------------------

    auditoria_referencias = (
        auditar_referencias_historicas(
            referencias_historicas
        )
    )

    # --------------------------------------------------------
    # 10. Estado actual de cada VIN
    # --------------------------------------------------------

    estado_actual = (
        construir_estado_actual_vin(
            secuencia=secuencia,
            trayectorias=trayectorias,
        )
    )

    # --------------------------------------------------------
    # 11. Proyección histórica
    # --------------------------------------------------------

    proyeccion_historica = (
        proyectar_fecha_historica(
            estado_actual=estado_actual,
            referencias=referencias_historicas,
        )
    )

    # --------------------------------------------------------
    # 12. Cobertura real de la proyección
    # --------------------------------------------------------

    cobertura_proyeccion_historica = (
        auditar_cobertura_proyeccion_historica(
            proyeccion_historica
        )
    )

    # --------------------------------------------------------
    # 13. PANA: referencias ENTREGA -> 1K
    # --------------------------------------------------------

    intervalos_entrega_1k = (
        construir_intervalos_entrega_1k(
            retail=retail,
            secuencia=secuencia,
        )
    )

    referencias_entrega_1k = (
        construir_referencias_entrega_1k(
            intervalos_entrega_1k
        )
    )

    # --------------------------------------------------------
    # 14. PANA sin historial preventivo
    # --------------------------------------------------------

    pana_sin_historial = (
        construir_pana_sin_historial(
            retail=retail,
            secuencia=secuencia,
        )
    )

    proyeccion_pana_sin_historial = (
        proyectar_pana_sin_historial(
            pana_sin_historial=
                pana_sin_historial,
            referencias_entrega_1k=
                referencias_entrega_1k,
        )
    )

    # --------------------------------------------------------
    # 15. Política — VIN con historial
    # --------------------------------------------------------

    proyeccion_con_politica = (
        construir_fecha_politica_con_historial(
            proyeccion_historica=
                proyeccion_historica,
            retail=retail,
        )
    )

    # --------------------------------------------------------
    # 16. Política — PANA sin historial
    # --------------------------------------------------------

    proyeccion_pana_sin_historial = (
        construir_fecha_politica_pana_sin_historial(
            proyeccion_pana_sin_historial
        )
    )

    # --------------------------------------------------------
    # 17. Estados temporales — VIN con historial
    # --------------------------------------------------------

    proyeccion_con_estados = (
        agregar_estados_temporales(
            proyeccion_con_politica
        )
    )

    # --------------------------------------------------------
    # 18. Estados temporales — PANA sin historial
    # --------------------------------------------------------

    proyeccion_pana_sin_historial = (
        agregar_estados_temporales(
            proyeccion_pana_sin_historial
        )
    )


    proyeccion_con_estados = (
        agregar_kilometraje_esperado_actual(
            proyeccion_con_estados
        )
    )

    proyeccion_pana_sin_historial = (
        agregar_kilometraje_esperado_actual(
            proyeccion_pana_sin_historial
        )
    )

    # --------------------------------------------------------
    # Base operacional consolidada
    # --------------------------------------------------------

    base_demanda = (
        construir_base_demanda(
            con_historial=
                proyeccion_con_estados,
            pana_sin_historial=
                proyeccion_pana_sin_historial,
            clientes=
                clientes,
        )
    )

    auditoria_base_demanda = (
        auditar_base_demanda(
            base_demanda
        )
    )

    # --------------------------------------------------------
    # 19. Auditoría de estados
    # --------------------------------------------------------

    auditoria_estados = (
        auditar_estados_temporales(
            con_historial=
                proyeccion_con_estados,
            pana_sin_historial=
                proyeccion_pana_sin_historial,
        )
    )

    # --------------------------------------------------------
    # 20. Auditoría de política
    # --------------------------------------------------------

    auditoria_politica = (
        auditar_proyeccion_politica(
            con_historial=
                proyeccion_con_politica,
            pana_sin_historial=
                proyeccion_pana_sin_historial,
        )
    )

    # --------------------------------------------------------
    # 21. Resultado
    # --------------------------------------------------------

    return {
        "registros_con_visita":
            registros_con_visita,

        "visitas_analiticas":
            visitas,

        "secuencia_preventiva":
            secuencia,

        "trayectorias":
            trayectorias,

        "auditoria_visitas":
            auditoria_visitas,

        "intervalos_historicos":
            intervalos_historicos,

        "resumen_intervalos":
            resumen_intervalos,

        "referencias_historicas":
            referencias_historicas,

        "auditoria_referencias":
            auditoria_referencias,

        "estado_actual":
            estado_actual,

        "proyeccion_historica":
            proyeccion_historica,

        "cobertura_proyeccion_historica":
            cobertura_proyeccion_historica,

        "intervalos_entrega_1k":
            intervalos_entrega_1k,

        "referencias_entrega_1k":
            referencias_entrega_1k,

        "pana_sin_historial":
            pana_sin_historial,

        # "proyeccion_pana_sin_historial":
        #    proyeccion_pana_sin_historial,

        "proyeccion_con_politica":
            proyeccion_con_politica,

        "proyeccion_pana_sin_historial":
            proyeccion_pana_sin_historial,

        "auditoria_politica":
            auditoria_politica,

        "proyeccion_con_estados":
            proyeccion_con_estados,

        "auditoria_estados":
            auditoria_estados,

        "base_demanda":
            base_demanda,

        "auditoria_base_demanda":
            auditoria_base_demanda,


    }