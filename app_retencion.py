from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from main_retencion import ejecutar_motor_retencion
from motor_retencion.cohortes import (
    construir_matriz_cohorte_retorno,
)
from motor_retencion.definiciones import (
    obtener_definiciones_retencion,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="CGO — Retención",
    page_icon="🐔",
    layout="wide",
)


# ============================================================
# MOTOR CACHEADO
# ============================================================

@st.cache_resource(
    ttl=120,
    show_spinner=False,
)
def cargar_motor_retencion() -> dict:
    """
    Mantiene el resultado completo del Motor 05 en memoria.

    Los cambios de filtros o navegación no vuelven a ejecutar
    el procesamiento pesado mientras el recurso permanezca
    cacheado.
    """

    return ejecutar_motor_retencion(
        log_callback=None,
        generar_reporte=False,
    )


# ============================================================
# PALETA VISUAL
# ============================================================

# Parque general / indicadores globales
COLOR_GENERAL = "#1A73E8"

# Identidad comercial PanaAutos
COLOR_PANA = "#D93025"

# Parque captado / NOPANA
COLOR_NOPANA = "#3C4043"

# Paleta para gráficos con múltiples series
GOOGLE_COLORS = [
    "#1A73E8",  # azul
    "#EA4335",  # rojo
    "#FBBC05",  # amarillo
    "#34A853",  # verde
    "#A142F4",  # morado
    "#00ACC1",  # cyan
    "#FF6D01",  # naranja
]


COLORES_PARQUE = {
    "PANA": COLOR_PANA,
    "NOPANA": COLOR_NOPANA,
}


ESTADOS_VIGENTES = {
    "EN_FECHA",
    "FUTURO_RECIENTE",
    "FUTURO_PROXIMO",
    "FUTURO_LEJANO",
    "SERVICIO_MUY_RECIENTE",
}


# ============================================================
# HELPERS — FORMATO
# ============================================================

def fmt_int(
    valor,
) -> str:
    """
    Formatea enteros con separador de miles.
    """

    if valor is None or pd.isna(valor):
        return "0"

    return f"{int(valor):,}"


def formato_porcentaje(
    valor,
    decimales: int = 1,
) -> str:
    """
    Formatea una proporción 0-1 como porcentaje.
    """

    if valor is None or pd.isna(valor):
        return "N/A"

    return f"{valor:.{decimales}%}"


def safe_div(
    numerador,
    denominador,
):
    """
    División segura.
    """

    if (
        denominador is None
        or pd.isna(denominador)
        or denominador == 0
    ):
        return np.nan

    return (
        numerador
        /
        denominador
    )


def render_bloque_texto(
    titulo: str,
    lineas: list[str],
) -> None:
    """
    Renderiza información gerencial en texto compacto.

    Se usa st.text para conservar alineación sin generar una
    tabla con grandes separaciones entre columnas.
    """

    st.markdown(
        f"**{titulo}**"
    )

    st.text(
        "\n".join(
            lineas
        )
    )


# ============================================================
# HELPERS — FUENTES Y FILTROS
# ============================================================

def enriquecer_fuentes(
    resultado: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepara las bases ligeras que utilizará el dashboard.

    No reconstruye historia ni ciclos.
    """

    base_demanda = (
        resultado[
            "base_demanda"
        ]
        .copy()
    )

    ciclos = (
        resultado[
            "ciclos_retencion"
        ]
        .copy()
    )

    columnas_base = [
        columna
        for columna in [
            "vin",
            "modelo",
            "parque",
            "tipo_historial",
            "cliente_encontrado",
            "estado_mas_inmediata",
        ]
        if columna
        in base_demanda.columns
    ]

    mapa_vin = (
        base_demanda[
            columnas_base
        ]
        .drop_duplicates(
            subset=["vin"]
        )
        .copy()
    )

    if (
        "modelo"
        not in ciclos.columns
        and "modelo"
        in mapa_vin.columns
    ):

        ciclos = ciclos.merge(
            mapa_vin[
                [
                    "vin",
                    "modelo",
                ]
            ],
            on="vin",
            how="left",
            validate="many_to_one",
        )

    if (
        "parque"
        not in ciclos.columns
        and "parque"
        in mapa_vin.columns
    ):

        ciclos = ciclos.merge(
            mapa_vin[
                [
                    "vin",
                    "parque",
                ]
            ],
            on="vin",
            how="left",
            validate="many_to_one",
        )

    if "modelo" in base_demanda.columns:

        base_demanda[
            "modelo"
        ] = (
            base_demanda[
                "modelo"
            ]
            .fillna(
                "SIN MODELO"
            )
            .astype(str)
        )

    if "modelo" in ciclos.columns:

        ciclos[
            "modelo"
        ] = (
            ciclos[
                "modelo"
            ]
            .fillna(
                "SIN MODELO"
            )
            .astype(str)
        )

    return (
        base_demanda,
        ciclos,
    )


def aplicar_filtro_modelo(
    base_demanda: pd.DataFrame,
    ciclos: pd.DataFrame,
    modelos_sel: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aplica el filtro por modelo sin volver a ejecutar motores.
    """

    if not modelos_sel:

        return (
            base_demanda.copy(),
            ciclos.copy(),
        )

    base_filtrada = (
        base_demanda.loc[
            base_demanda[
                "modelo"
            ].isin(
                modelos_sel
            )
        ]
        .copy()
    )

    vin_validos = set(
        base_filtrada[
            "vin"
        ]
        .dropna()
        .unique()
    )

    ciclos_filtrados = (
        ciclos.loc[
            ciclos[
                "vin"
            ].isin(
                vin_validos
            )
        ]
        .copy()
    )

    return (
        base_filtrada,
        ciclos_filtrados,
    )


def aplicar_filtros_ciclos(
    df: pd.DataFrame,
    parques: list[str],
    modelos: list[str],
    sedes: list[str],
    asesores: list[str],
    hitos: list[int],
) -> pd.DataFrame:
    """
    Aplica filtros ligeros sobre ciclos_retencion.
    """

    filtrado = df.copy()

    if parques:

        filtrado = filtrado.loc[
            filtrado[
                "parque"
            ].isin(
                parques
            )
        ]

    if modelos:

        filtrado = filtrado.loc[
            filtrado[
                "modelo"
            ].isin(
                modelos
            )
        ]

    if sedes:

        filtrado = filtrado.loc[
            filtrado[
                "sede"
            ].isin(
                sedes
            )
        ]

    if asesores:

        filtrado = filtrado.loc[
            filtrado[
                "asesor"
            ].isin(
                asesores
            )
        ]

    if hitos:

        km_esperado = pd.to_numeric(
            filtrado[
                "km_esperado_siguiente"
            ],
            errors="coerce",
        )

        filtrado = filtrado.loc[
            km_esperado.isin(
                hitos
            )
        ]

    return filtrado


# ============================================================
# HELPERS — RETENCIÓN
# ============================================================

def construir_resumen_retencion(
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
            observed=True,
        )
        .agg(
            oportunidades=(
                "kpi_retorno",
                lambda serie:
                    serie.isin(
                        [
                            "RETORNO",
                            "NO_RETORNO",
                        ]
                    ).sum(),
            ),

            retornos=(
                "kpi_retorno",
                lambda serie:
                    serie.eq(
                        "RETORNO"
                    ).sum(),
            ),

            no_retornos=(
                "kpi_retorno",
                lambda serie:
                    serie.eq(
                        "NO_RETORNO"
                    ).sum(),
            ),

            no_evaluables=(
                "kpi_retorno",
                lambda serie:
                    serie.eq(
                        "NO_EVALUABLE"
                    ).sum(),
            ),

            adherentes=(
                "kpi_adherencia_ciclo",
                lambda serie:
                    serie.eq(
                        "SI"
                    ).sum(),
            ),

            adelantados=(
                "kpi_puntualidad",
                lambda serie:
                    serie.eq(
                        "ADELANTADO"
                    ).sum(),
            ),

            en_fecha=(
                "kpi_puntualidad",
                lambda serie:
                    serie.eq(
                        "EN_FECHA"
                    ).sum(),
            ),

            tardios=(
                "kpi_puntualidad",
                lambda serie:
                    serie.eq(
                        "TARDIO"
                    ).sum(),
            ),
        )
        .reset_index()
    )

    resumen[
        "tasa_retorno"
    ] = resumen.apply(
        lambda fila:
            safe_div(
                fila[
                    "retornos"
                ],
                fila[
                    "oportunidades"
                ],
            ),
        axis=1,
    )

    resumen[
        "tasa_adherencia"
    ] = resumen.apply(
        lambda fila:
            safe_div(
                fila[
                    "adherentes"
                ],
                fila[
                    "retornos"
                ],
            ),
        axis=1,
    )

    resumen[
        "tasa_puntualidad"
    ] = resumen.apply(
        lambda fila:
            safe_div(
                fila[
                    "en_fecha"
                ],
                fila[
                    "adherentes"
                ],
            ),
        axis=1,
    )

    return resumen


def calcular_kpis_desde_ciclos(
    ciclos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Alias semántico para las otras vistas del dashboard.
    """

    return construir_resumen_retencion(
        ciclos
    )


def detectar_columna_hito(
    df: pd.DataFrame,
) -> str | None:
    """
    Localiza la columna que representa el siguiente hito.
    """

    candidatos = [
        "hito_km",
        "km_esperado_siguiente",
        "mantenimiento_esperado_desde_anterior",
    ]

    for columna in candidatos:

        if columna in df.columns:
            return columna

    return None


def construir_retencion_hito_filtrada(
    ciclos: pd.DataFrame,
    km_minimo: int = 10,
    km_maximo: int = 50,
) -> pd.DataFrame:
    """
    Retención por hito para un subconjunto ya filtrado.
    """

    if ciclos.empty:
        return pd.DataFrame()

    columna_hito = detectar_columna_hito(
        ciclos
    )

    if columna_hito is None:
        return pd.DataFrame()

    base = (
        ciclos.loc[
            ciclos[
                "kpi_retorno"
            ].isin(
                [
                    "RETORNO",
                    "NO_RETORNO",
                ]
            )
        ]
        .copy()
    )

    base[
        columna_hito
    ] = pd.to_numeric(
        base[
            columna_hito
        ],
        errors="coerce",
    )

    base = base.loc[
        base[
            columna_hito
        ].between(
            km_minimo,
            km_maximo,
        )
    ].copy()

    if base.empty:
        return pd.DataFrame()

    resumen = (
        base
        .groupby(
            [
                "parque",
                columna_hito,
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            oportunidades=(
                "kpi_retorno",
                "size",
            ),

            retornos=(
                "kpi_retorno",
                lambda serie:
                    serie.eq(
                        "RETORNO"
                    ).sum(),
            ),
        )
    )

    resumen[
        "tasa_retorno"
    ] = (
        resumen[
            "retornos"
        ]
        /
        resumen[
            "oportunidades"
        ]
    )

    resumen = resumen.rename(
        columns={
            columna_hito:
                "hito_km",
        }
    )

    resumen[
        "hito"
    ] = (
        resumen[
            "hito_km"
        ]
        .astype(int)
        .astype(str)
        + "K"
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


def calcular_retencion_por_hito(
    ciclos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Versión sin límite superior utilizada por la página
    Retención por KM.
    """

    if ciclos.empty:
        return pd.DataFrame()

    columna_hito = detectar_columna_hito(
        ciclos
    )

    if columna_hito is None:
        return pd.DataFrame()

    base = (
        ciclos.loc[
            ciclos[
                "kpi_retorno"
            ].isin(
                [
                    "RETORNO",
                    "NO_RETORNO",
                ]
            )
        ]
        .copy()
    )

    if base.empty:
        return pd.DataFrame()

    base[
        "hito_km"
    ] = pd.to_numeric(
        base[
            columna_hito
        ],
        errors="coerce",
    )

    base = base.loc[
        base[
            "hito_km"
        ].notna()
    ].copy()

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
            oportunidades=(
                "vin",
                "size",
            ),

            retornos=(
                "kpi_retorno",
                lambda serie:
                    serie.eq(
                        "RETORNO"
                    ).sum(),
            ),
        )
    )

    resumen[
        "tasa_retorno"
    ] = (
        resumen[
            "retornos"
        ]
        /
        resumen[
            "oportunidades"
        ]
    )

    resumen[
        "hito"
    ] = (
        resumen[
            "hito_km"
        ]
        .astype(int)
        .astype(str)
        + "K"
    )

    return resumen


# ============================================================
# HELPERS — PARQUE Y CALIDAD
# ============================================================

def construir_estado_parque_actual(
    base_demanda: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clasifica el parque actual como Vigente / Vencido.
    """

    if (
        base_demanda.empty
        or "estado_mas_inmediata"
        not in base_demanda.columns
    ):
        return pd.DataFrame()

    base = base_demanda.copy()

    base[
        "estado_parque"
    ] = np.where(
        base[
            "estado_mas_inmediata"
        ].isin(
            ESTADOS_VIGENTES
        ),
        "Vigente",
        "Vencido",
    )

    resumen = (
        base
        .groupby(
            [
                "parque",
                "estado_parque",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            vin=(
                "vin",
                "nunique",
            )
        )
    )

    return resumen


def construir_bloques_resumen(
    base_demanda: pd.DataFrame,
    ciclos: pd.DataFrame,
    resumen_retencion: pd.DataFrame,
) -> tuple[
    list[str],
    list[str],
    list[str],
]:
    """
    Construye los tres bloques de texto del Resumen Ejecutivo.
    """

    # --------------------------------------------------------
    # 1. RETENCIÓN
    # --------------------------------------------------------

    lineas_retencion = []

    for parque in [
        "PANA",
        "NOPANA",
    ]:

        fila = (
            resumen_retencion.loc[
                resumen_retencion[
                    "parque"
                ].eq(
                    parque
                )
            ]
        )

        if fila.empty:
            continue

        fila = fila.iloc[0]

        lineas_retencion.append(
            (
                f"{parque:<7} | "
                f"Evaluables: "
                f"{fmt_int(fila['oportunidades']):>7} | "
                f"Retornos: "
                f"{fmt_int(fila['retornos']):>7} | "
                f"Retención: "
                f"{formato_porcentaje(fila['tasa_retorno']):>6}"
            )
        )

    # --------------------------------------------------------
    # 2. CALIDAD / COBERTURA DE DATOS
    # --------------------------------------------------------

    total_vin = (
        base_demanda[
            "vin"
        ]
        .nunique()
    )

    vin_con_historial = 0
    vin_sin_historial = 0

    if (
        "tipo_historial"
        in base_demanda.columns
    ):

        tipo = (
            base_demanda[
                "tipo_historial"
            ]
            .astype(str)
        )

        vin_con_historial = int(
            tipo.eq(
                "CON_HISTORIAL_PREVENTIVO"
            )
            .sum()
        )

        vin_sin_historial = int(
            tipo.eq(
                "SIN_HISTORIAL_PREVENTIVO"
            )
            .sum()
        )

    lineas_datos = [
        (
            "VIN analizados              : "
            f"{fmt_int(total_vin)}"
        ),
        (
            "VIN con historial preventivo: "
            f"{fmt_int(vin_con_historial)}"
        ),
        (
            "VIN sin historial preventivo: "
            f"{fmt_int(vin_sin_historial)}"
        ),
        (
            "Oportunidades evaluables    : "
            f"{fmt_int(
                ciclos[
                    'kpi_retorno'
                ].isin(
                    [
                        'RETORNO',
                        'NO_RETORNO',
                    ]
                ).sum()
            )}"
        ),
        (
            "Oportunidades no evaluables : "
            f"{fmt_int(
                ciclos[
                    'kpi_retorno'
                ].eq(
                    'NO_EVALUABLE'
                ).sum()
            )}"
        ),
    ]

    # --------------------------------------------------------
    # 3. CALIDAD DE CICLOS
    # --------------------------------------------------------

    lineas_ciclos = []

    if (
        "comportamiento"
        in ciclos.columns
    ):

        conteo = (
            ciclos[
                "comportamiento"
            ]
            .value_counts(
                dropna=False
            )
            .to_dict()
        )

        total_eventos = len(
            ciclos
        )

        def porcentaje_evento(
            nombre: str,
        ) -> str:

            return formato_porcentaje(
                safe_div(
                    conteo.get(
                        nombre,
                        0,
                    ),
                    total_eventos,
                )
            )

        lineas_ciclos = [
            (
                "Eventos de ciclo           : "
                f"{fmt_int(total_eventos)}"
            ),
            (
                "SIGUE_CICLO                : "
                f"{fmt_int(conteo.get('SIGUE_CICLO', 0)):>7} "
                f"({porcentaje_evento('SIGUE_CICLO')})"
            ),
            (
                "SALTA_MANTENIMIENTOS       : "
                f"{fmt_int(conteo.get('SALTA_MANTENIMIENTOS', 0)):>7} "
                f"({porcentaje_evento('SALTA_MANTENIMIENTOS')})"
            ),
            (
                "REPITE_MANTENIMIENTO       : "
                f"{fmt_int(conteo.get('REPITE_MANTENIMIENTO', 0)):>7} "
                f"({porcentaje_evento('REPITE_MANTENIMIENTO')})"
            ),
            (
                "RETROCESO                  : "
                f"{fmt_int(conteo.get('RETROCESO', 0)):>7} "
                f"({porcentaje_evento('RETROCESO')})"
            ),
        ]

    return (
        lineas_retencion,
        lineas_datos,
        lineas_ciclos,
    )


# ============================================================
# HELPERS — SNAPSHOTS
# ============================================================

def obtener_ultimo_snapshot(
    snapshot: pd.DataFrame,
) -> pd.DataFrame:
    """
    Obtiene el último snapshot disponible por parque.
    """

    if snapshot.empty:
        return pd.DataFrame()

    fecha = (
        snapshot[
            "snapshot"
        ]
        .max()
    )

    return (
        snapshot.loc[
            snapshot[
                "snapshot"
            ].eq(
                fecha
            )
        ]
        .copy()
        .reset_index(drop=True)
    )


# ============================================================
# HELPERS — GRÁFICOS
# ============================================================

def grafico_linea_retencion(
    df: pd.DataFrame,
    titulo: str,
):
    """
    Gráfico estándar de Retención por KM.

    PANA siempre rojo y NOPANA siempre gris oscuro.
    """

    if df.empty:
        return None

    figura = px.line(
        df,
        x="hito_km",
        y="tasa_retorno",
        color="parque",
        markers=True,
        color_discrete_map=
            COLORES_PARQUE,
        labels={
            "hito_km":
                "Mantenimiento",
            "tasa_retorno":
                "Retención",
            "parque":
                "Parque",
        },
        title=titulo,
    )

    figura.update_traces(
        line=dict(
            width=3,
        ),
        marker=dict(
            size=8,
        ),
    )

    figura.update_yaxes(
        tickformat=".0%",
        range=[
            0,
            1,
        ],
    )

    valores_km = sorted(
        df[
            "hito_km"
        ]
        .dropna()
        .unique()
    )

    figura.update_xaxes(
        tickvals=
            valores_km,

        ticktext=[
            f"{int(km)}K"
            for km
            in valores_km
        ],
    )

    figura.update_layout(
        hovermode=
            "x unified",

        legend_title_text=
            "",

        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),

        plot_bgcolor=
            "rgba(0,0,0,0)",

        paper_bgcolor=
            "rgba(0,0,0,0)",
    )

    return figura



#🐶

# ============================================================
# CARGA
# ============================================================

st.title("CGO — Retención")

st.caption(
    "Centro de Gestión Operacional — Post Venta"
)

with st.spinner(
    "Construyendo análisis de retención..."
):
    resultado = cargar_motor_retencion()


# ============================================================
# FUENTES
# ============================================================

fecha_max = pd.to_datetime(
    resultado[
        "fecha_max_datos"
    ]
)

resumen_kpis = (
    resultado[
        "resumen_kpis"
    ]
)

ciclos_retencion = (
    resultado[
        "ciclos_retencion"
    ]
)

snapshot_parque = (
    resultado[
        "snapshot_parque_general"
    ]
)

snapshot_total = (
    resultado[
        "snapshot_parque_total"
    ]
)

matriz_pana = (
    resultado[
        "matriz_pana"
    ]
)

detalle_pana = (
    resultado[
        "detalle_pana"
    ]
)

base_demanda = (
    resultado[
        "base_demanda"
    ]
)

base_evaluable = (
    resultado[
        "base_evaluable"
    ]
)

retencion_cohorte_hito = (
    resultado[
        "retencion_cohorte_hito"
    ]
)

snapshots_hitos = (
    resultado[
        "snapshots_hitos"
    ]
)

ranking_clientes = (
    resultado[
        "ranking_clientes"
    ]
)

resumen_cliente = (
    resultado[
        "resumen_cliente"
    ]
)

perfiles_comerciales = (
    resultado[
        "perfiles_comerciales"
    ]
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "CGO — Retención"
    )

    pagina = st.radio(
        "Vista",
        [
            "📊 Resumen ejecutivo",
            "🚗 Parque PANA",
            "🔧 Retención por KM",
            "📅 Cohortes",
            "❄️ Snowball",
            "👥 Clientes",
            "ℹ️ Metodología",
        ],
    )

    st.divider()

    st.caption(
        (
            "Datos actualizados al "
            f"{fecha_max:%d/%m/%Y}"
        )
    )

    if st.button(
        "🔄 Actualizar datos",
        use_container_width=True,
    ):

        cargar_motor_retencion.clear()

        st.rerun()


#🐶
# ============================================================
# 1. RESUMEN EJECUTIVO
# ============================================================

if pagina == "📊 Resumen ejecutivo":

    st.header(
        "Resumen ejecutivo"
    )

    st.caption(
        (
            "Lectura consolidada del parque, "
            "retención y comportamiento preventivo."
        )
    )

    # ========================================================
    # BASES DE TRABAJO
    # ========================================================

    (
        base_resumen,
        ciclos_resumen,
    ) = enriquecer_fuentes(
        resultado
    )

    # ========================================================
    # FILTRO POR MODELO
    # ========================================================

    modelos_disponibles = sorted(
        base_resumen[
            "modelo"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    col_filtro, col_espacio = (
        st.columns(
            [
                2,
                5,
            ]
        )
    )

    with col_filtro:

        modelos_seleccionados = (
            st.multiselect(
                "Modelo",
                options=
                    modelos_disponibles,

                default=[],

                placeholder=
                    "Todos los modelos",
            )
        )

    (
        base_filtrada,
        ciclos_filtrados,
    ) = aplicar_filtro_modelo(
        base_demanda=
            base_resumen,

        ciclos=
            ciclos_resumen,

        modelos_sel=
            modelos_seleccionados,
    )

    # ========================================================
    # KPI
    # ========================================================

    resumen_retencion = (
        construir_resumen_retencion(
            ciclos_filtrados
        )
    )

    parque_total = (
        base_filtrada[
            "vin"
        ]
        .nunique()
    )

    parque_pana = (
        base_filtrada.loc[
            base_filtrada[
                "parque"
            ].eq(
                "PANA"
            ),
            "vin",
        ]
        .nunique()
    )

    fila_pana = (
        resumen_retencion.loc[
            resumen_retencion[
                "parque"
            ].eq(
                "PANA"
            )
        ]
    )

    fila_nopana = (
        resumen_retencion.loc[
            resumen_retencion[
                "parque"
            ].eq(
                "NOPANA"
            )
        ]
    )

    tasa_pana = (
        fila_pana[
            "tasa_retorno"
        ].iloc[0]
        if not fila_pana.empty
        else np.nan
    )

    tasa_nopana = (
        fila_nopana[
            "tasa_retorno"
        ].iloc[0]
        if not fila_nopana.empty
        else np.nan
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    col1.metric(
        "Parque comercial",
        fmt_int(
            parque_total
        ),
    )

    col2.metric(
        "Parque PANA",
        fmt_int(
            parque_pana
        ),
    )

    col3.metric(
        "Retención PANA",
        formato_porcentaje(
            tasa_pana
        ),
    )

    col4.metric(
        "Retención NOPANA",
        formato_porcentaje(
            tasa_nopana
        ),
    )

    # ========================================================
    # LECTURA EJECUTIVA
    # ========================================================

    st.divider()

    st.subheader(
        "Lectura ejecutiva"
    )

    (
        lineas_retencion,
        lineas_datos,
        lineas_ciclos,
    ) = construir_bloques_resumen(
        base_demanda=
            base_filtrada,

        ciclos=
            ciclos_filtrados,

        resumen_retencion=
            resumen_retencion,
    )

    col_retencion, col_datos, col_ciclos = (
        st.columns(3)
    )

    with col_retencion:

        render_bloque_texto(
            "Retención",
            lineas_retencion,
        )

    with col_datos:

        render_bloque_texto(
            "Calidad / cobertura de datos",
            lineas_datos,
        )

    with col_ciclos:

        render_bloque_texto(
            "Calidad de los ciclos",
            lineas_ciclos,
        )

    # ========================================================
    # RETENCIÓN POR KM
    # ========================================================

    st.divider()

    st.subheader(
        "¿Cómo cambia la retención según el mantenimiento?"
    )

    df_hitos = (
        construir_retencion_hito_filtrada(
            ciclos=
                ciclos_filtrados,

            km_minimo=10,
            km_maximo=50,
        )
    )

    figura_retencion = (
        grafico_linea_retencion(
            df=
                df_hitos,

            titulo=
                "Retención por mantenimiento",
        )
    )

    if figura_retencion is None:

        st.info(
            (
                "No existen suficientes oportunidades "
                "para los filtros seleccionados."
            )
        )

    else:

        st.plotly_chart(
            figura_retencion,
            use_container_width=True,
        )

    # ========================================================
    # ESTADO ACTUAL DEL PARQUE
    # ========================================================

    st.subheader(
        "¿Cómo está compuesto el parque actualmente?"
    )

    estado_parque = (
        construir_estado_parque_actual(
            base_filtrada
        )
    )

    if estado_parque.empty:

        st.info(
            (
                "No existe información suficiente para "
                "clasificar el estado actual del parque."
            )
        )

    else:

        figura_estado = px.bar(
            estado_parque,
            x=
                "estado_parque",

            y=
                "vin",

            color=
                "parque",

            barmode=
                "group",

            text=
                "vin",

            color_discrete_map=
                COLORES_PARQUE,

            labels={
                "estado_parque":
                    "Estado",

                "vin":
                    "VIN",

                "parque":
                    "Parque",
            },
        )

        figura_estado.update_traces(
            textposition=
                "outside"
        )

        figura_estado.update_layout(
            height=420,

            legend_title_text=
                "",

            xaxis_title=
                "",

            yaxis_title=
                "VIN",

            plot_bgcolor=
                "rgba(0,0,0,0)",

            paper_bgcolor=
                "rgba(0,0,0,0)",

            margin=dict(
                l=20,
                r=20,
                t=20,
                b=20,
            ),
        )

        st.plotly_chart(
            figura_estado,
            use_container_width=True,
        )

# ============================================================
# 2. PARQUE PANA
# ============================================================

elif pagina == "🚗 Parque PANA":

    st.header(
        "Parque PANA"
    )

    st.caption(
        (
            "Trayectoria histórica y situación actual "
            "del parque vendido por PanaAutos."
        )
    )

    col1, col2, col3 = (
        st.columns(
            [
                2,
                2,
                2,
            ]
        )
    )

    modelos_pana = sorted(
        matriz_pana[
            "Modelo"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    modelo_pana = col1.multiselect(
        "Modelo",
        modelos_pana,
    )

    situacion = col2.selectbox(
        "Situación",
        [
            "Todos",
            "Con atraso",
            "Próximos 30 días",
            "Con saltos",
        ],
    )

    limite_km = col3.selectbox(
        "Mostrar hasta",
        [
            30,
            50,
            80,
            150,
        ],
        index=1,
        format_func=lambda valor:
            f"{valor}K",
    )

    vista_pana = (
        matriz_pana.copy()
    )

    if modelo_pana:

        vista_pana = vista_pana.loc[
            vista_pana[
                "Modelo"
            ].isin(
                modelo_pana
            )
        ]

    # --------------------------------------------------------
    # Filtro operacional
    # --------------------------------------------------------

    if situacion != "Todos":

        detalle_filtro = (
            detalle_pana.copy()
        )

        if modelo_pana:

            detalle_filtro = (
                detalle_filtro.loc[
                    detalle_filtro[
                        "modelo"
                    ].isin(
                        modelo_pana
                    )
                ]
            )

        if situacion == "Con atraso":

            vins = (
                detalle_filtro.loc[
                    detalle_filtro[
                        "estado_hito"
                    ].eq(
                        "ACTUAL_ATRASADO"
                    ),
                    "vin",
                ]
                .unique()
            )

        elif situacion == "Próximos 30 días":

            vins = (
                detalle_filtro.loc[
                    detalle_filtro[
                        "estado_hito"
                    ].eq(
                        "ACTUAL_FUTURO"
                    )
                    &
                    pd.to_numeric(
                        detalle_filtro[
                            "dias_hasta_politica"
                        ],
                        errors="coerce",
                    ).between(
                        0,
                        30,
                    ),
                    "vin",
                ]
                .unique()
            )

        else:

            vins = (
                detalle_filtro.loc[
                    detalle_filtro[
                        "estado_hito"
                    ].eq(
                        "SALTADO"
                    ),
                    "vin",
                ]
                .unique()
            )

        vista_pana = vista_pana.loc[
            vista_pana[
                "VIN"
            ].isin(vins)
        ]

    # --------------------------------------------------------
    # Columnas KM
    # --------------------------------------------------------

    columnas_fijas = [
        "Fecha entrega",
        "VIN",
        "Placa",
        "Modelo",
        "Nro documento",
        "Nombre cliente",
    ]

    hitos = [1]

    hitos.extend(
        range(
            5,
            limite_km + 1,
            5,
        )
    )

    columnas_km = [
        f"{km}K"
        for km in hitos
        if f"{km}K"
        in vista_pana.columns
    ]

    columnas_mostrar = (
        columnas_fijas
        +
        columnas_km
    )

    st.caption(
        (
            f"{len(vista_pana):,} vehículos "
            "en la selección."
        )
    )

    st.dataframe(
        vista_pana[
            columnas_mostrar
        ],
        use_container_width=True,
        hide_index=True,
        height=620,
    )

    with st.expander(
        "¿Cómo interpretar la matriz?"
    ):

        st.markdown(
            """
**✔️ (186)** — mantenimiento realizado; 186 días desde su ancla preventiva anterior.  
**❌** — existe evidencia de que ese mantenimiento fue saltado.  
**-8** — el mantenimiento actual lleva 8 días de atraso frente a la fecha política.  
**15** — faltan 15 días para la fecha política del mantenimiento actual.  

Un mantenimiento atrasado **no se marca como ❌** hasta que exista evidencia posterior de que efectivamente fue omitido.
"""
        )


# ============================================================
# 3. RETENCIÓN POR KM
# ============================================================

elif pagina == "🔧 Retención por KM":

    st.header(
        "Retención por mantenimiento"
    )

    st.caption(
        (
            "¿En qué parte del ciclo preventivo "
            "estamos perdiendo más vehículos?"
        )
    )

    base = (
        ciclos_retencion.copy()
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    parques_disponibles = sorted(
        base[
            "parque"
        ]
        .dropna()
        .unique()
    )

    parques = col1.multiselect(
        "Parque",
        parques_disponibles,
        default=parques_disponibles,
    )

    modelos_disponibles = sorted(
        base[
            "modelo"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    modelos = col2.multiselect(
        "Modelo",
        modelos_disponibles,
    )

    hitos_disponibles = sorted(
        pd.to_numeric(
            base[
                "km_esperado_siguiente"
            ],
            errors="coerce",
        )
        .dropna()
        .astype(int)
        .unique()
    )

    hitos = col3.multiselect(
        "Mantenimiento",
        hitos_disponibles,
        default=[
            km
            for km in hitos_disponibles
            if 10 <= km <= 50
        ],
        format_func=lambda km:
            f"{km}K",
    )

    col4, col5 = (
        st.columns(2)
    )

    sedes_disponibles = sorted(
        base[
            "sede"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    sedes = col4.multiselect(
        "Sede",
        sedes_disponibles,
    )

    asesores_disponibles = sorted(
        base[
            "asesor"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    asesores = col5.multiselect(
        "Asesor",
        asesores_disponibles,
    )

    filtrado = aplicar_filtros_ciclos(
        df=base,
        parques=parques,
        modelos=modelos,
        sedes=sedes,
        asesores=asesores,
        hitos=hitos,
    )

    st.caption(
        (
            f"{len(filtrado):,} oportunidades "
            "en la selección."
        )
    )

    kpis_filtrados = (
        calcular_kpis_desde_ciclos(
            filtrado
        )
    )

    if not kpis_filtrados.empty:

        columnas = st.columns(
            len(
                kpis_filtrados
            )
        )

        for posicion, (
            _,
            fila,
        ) in enumerate(
            kpis_filtrados.iterrows()
        ):

            columnas[
                posicion
            ].metric(
                (
                    "Retención "
                    f"{fila['parque']}"
                ),
                formato_porcentaje(
                    fila[
                        "tasa_retorno"
                    ]
                ),
            )

    resumen_hitos = (
        calcular_retencion_por_hito(
            filtrado
        )
    )

    figura = grafico_linea_retencion(
        resumen_hitos,
        "Tasa de retención por mantenimiento",
    )

    if figura is not None:

        st.plotly_chart(
            figura,
            use_container_width=True,
        )

    else:

        st.info(
            "No existen oportunidades para los filtros seleccionados."
        )

    st.subheader(
        "Detalle por mantenimiento"
    )

    if not resumen_hitos.empty:

        tabla_hitos = (
            resumen_hitos[
                [
                    "parque",
                    "hito",
                    "oportunidades",
                    "retornos",
                    "tasa_retorno",
                ]
            ]
            .copy()
        )

        tabla_hitos[
            "tasa_retorno"
        ] = (
            tabla_hitos[
                "tasa_retorno"
            ]
            .map(
                formato_porcentaje
            )
        )

        st.dataframe(
            tabla_hitos,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 4. COHORTES
# ============================================================

elif pagina == "📅 Cohortes":

    st.header(
        "Cohortes de retención"
    )

    st.caption(
        (
            "¿Los vehículos que debían regresar "
            "en cada periodo realmente regresaron "
            "y cuándo lo hicieron?"
        )
    )

    col1, col2 = (
        st.columns(2)
    )

    parques_cohorte = sorted(
        base_evaluable[
            "parque"
        ]
        .dropna()
        .unique()
    )

    parque_cohorte = col1.selectbox(
        "Parque",
        parques_cohorte,
        index=(
            parques_cohorte.index(
                "PANA"
            )
            if "PANA"
            in parques_cohorte
            else 0
        ),
    )

    hitos_cohorte = sorted(
        base_evaluable.loc[
            base_evaluable[
                "parque"
            ].eq(
                parque_cohorte
            ),
            "hito_km",
        ]
        .dropna()
        .astype(int)
        .unique()
    )

    hito_cohorte = col2.selectbox(
        "Mantenimiento",
        hitos_cohorte,
        index=(
            hitos_cohorte.index(10)
            if 10
            in hitos_cohorte
            else 0
        ),
        format_func=lambda km:
            f"{km}K",
    )

    tabla_cohortes = (
        retencion_cohorte_hito.loc[
            retencion_cohorte_hito[
                "parque"
            ].eq(
                parque_cohorte
            )
            &
            retencion_cohorte_hito[
                "hito_km"
            ].eq(
                hito_cohorte
            )
        ]
        .copy()
    )

    if not tabla_cohortes.empty:

        figura_cohortes = px.line(
            tabla_cohortes,
            x="cohorte_mes",
            y="tasa_retencion",
            markers=True,
            labels={
                "cohorte_mes":
                    "Mes de oportunidad",
                "tasa_retencion":
                    "Retención",
            },
            title=(
                "Evolución de la retención "
                "por cohorte"
            ),
        )

        figura_cohortes.update_yaxes(
            tickformat=".0%"
        )

        figura_cohortes.update_layout(
            hovermode="x unified",
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            figura_cohortes,
            use_container_width=True,
        )

    st.subheader(
        "Matriz de Cohorte y Mes de Retorno"
    )

    matriz_cohorte = (
        construir_matriz_cohorte_retorno(
            base_evaluable=
                base_evaluable,
            parque=
                parque_cohorte,
            hito_km=
                hito_cohorte,
        )
    )

    if matriz_cohorte.empty:

        st.info(
            "No existen datos para esta selección."
        )

    else:

        matriz_vista = (
            matriz_cohorte.copy()
        )

        if (
            "% RETENCIÓN"
            in matriz_vista.columns
        ):

            matriz_vista[
                "% RETENCIÓN"
            ] = (
                matriz_vista[
                    "% RETENCIÓN"
                ]
                .map(
                    formato_porcentaje
                )
            )

        st.dataframe(
            matriz_vista,
            use_container_width=True,
            hide_index=True,
            height=600,
        )

        st.caption(
            (
                "Las columnas mensuales muestran "
                "en qué mes calendario se materializó "
                "el retorno de cada cohorte."
            )
        )


# ============================================================
# 5. SNOWBALL
# ============================================================

elif pagina == "❄️ Snowball":

    st.header(
        "Efecto Snowball"
    )

    st.caption(
        (
            "¿El parque vigente está creciendo "
            "o perdiendo vehículos más rápido "
            "de lo que logramos incorporar y reactivar?"
        )
    )

    ultimo_snapshot = (
        obtener_ultimo_snapshot(
            snapshot_parque
        )
    )

    if not ultimo_snapshot.empty:

        pana_actual = (
            ultimo_snapshot.loc[
                ultimo_snapshot[
                    "parque"
                ].eq("PANA")
            ]
        )

        if not pana_actual.empty:

            pana_actual = (
                pana_actual.iloc[0]
            )

            col1, col2, col3, col4 = (
                st.columns(4)
            )

            col1.metric(
                "Parque PANA vigente",
                (
                    f"{int(pana_actual['parque_vigente']):,}"
                ),
            )

            col2.metric(
                "Altas del mes",
                (
                    f"{int(pana_actual['altas_mes']):,}"
                ),
            )

            col3.metric(
                "Reactivaciones",
                (
                    f"{int(pana_actual['reactivaciones_mes']):,}"
                ),
            )

            col4.metric(
                "Nuevos vencidos",
                (
                    f"{int(pana_actual['nuevos_vencidos_mes']):,}"
                ),
                delta=(
                    f"{int(pana_actual['variacion_vigente']):+d} "
                    "variación neta"
                ),
            )

    st.subheader(
        "¿Qué explica el cambio mensual del parque vigente?"
    )

    snowball_pana = (
        snapshot_parque.loc[
            snapshot_parque[
                "parque"
            ].eq("PANA")
        ]
        .sort_values(
            "snapshot"
        )
        .copy()
    )

    if not snowball_pana.empty:

        figura_flujo = go.Figure()

        figura_flujo.add_bar(
            x=snowball_pana[
                "snapshot"
            ],
            y=snowball_pana[
                "altas_mes"
            ],
            name="Altas",
        )

        figura_flujo.add_bar(
            x=snowball_pana[
                "snapshot"
            ],
            y=snowball_pana[
                "reactivaciones_mes"
            ],
            name="Reactivaciones",
        )

        figura_flujo.add_bar(
            x=snowball_pana[
                "snapshot"
            ],
            y=(
                -snowball_pana[
                    "nuevos_vencidos_mes"
                ]
            ),
            name="Nuevos vencidos",
        )

        figura_flujo.update_layout(
            barmode="relative",
            xaxis_title="",
            yaxis_title="VIN",
            legend_title_text="",
            hovermode="x unified",
            margin=dict(
                l=20,
                r=20,
                t=20,
                b=20,
            ),
        )

        st.plotly_chart(
            figura_flujo,
            use_container_width=True,
        )

    st.subheader(
        "Índice Snowball — Base 100"
    )

    if not snapshot_parque.empty:

        figura_indice = px.line(
            snapshot_parque,
            x="snapshot",
            y="indice_snowball",
            color="parque",
            markers=True,
            labels={
                "snapshot":
                    "Periodo",
                "indice_snowball":
                    "Índice",
                "parque":
                    "Parque",
            },
        )

        figura_indice.add_hline(
            y=100,
            line_dash="dash",
        )

        figura_indice.update_layout(
            hovermode="x unified",
            legend_title_text="",
            margin=dict(
                l=20,
                r=20,
                t=20,
                b=20,
            ),
        )

        st.plotly_chart(
            figura_indice,
            use_container_width=True,
        )

        st.caption(
            (
                "Base 100 representa el parque vigente "
                "del primer snapshot. "
                "Este índice no es una tasa de retención."
            )
        )


# ============================================================
# 6. CLIENTES
# ============================================================

elif pagina == "👥 Clientes":

    st.header(
        "Clientes"
    )

    st.warning(
        (
            "La información de clientes utilizada actualmente "
            "es dummy. Esta sección valida la metodología; "
            "no debe interpretarse todavía como conclusión "
            "comercial sobre clientes reales."
        ),
        icon="⚠️",
    )

    st.subheader(
        "Perfiles comerciales"
    )

    st.dataframe(
        perfiles_comerciales,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Ranking de clientes"
    )

    metricas_ranking = {
        "Retención":
            "RETENCION",
        "Continuidad con el mismo cliente":
            "CONTINUIDAD_CLIENTE",
        "Adherencia":
            "ADHERENCIA",
        "Puntualidad":
            "PUNTUALIDAD",
        "Visitas preventivas":
            "VISITAS_PREVENTIVAS",
        "VIN distintos":
            "VIN_DISTINTOS",
    }

    metrica_nombre = st.selectbox(
        "Ordenar por",
        list(
            metricas_ranking.keys()
        ),
    )

    metrica_codigo = (
        metricas_ranking[
            metrica_nombre
        ]
    )

    ranking_filtrado = (
        ranking_clientes.loc[
            ranking_clientes[
                "metrica_ranking"
            ].eq(
                metrica_codigo
            )
        ]
        .head(25)
        .copy()
    )

    columnas_ranking = [
        "ranking",
        "nro_documento",
        "nombre",
        "visitas_preventivas",
        "vin_distintos",
        "oportunidades_evaluables",
        "vehiculos_retornaron",
        "tasa_retorno_vehiculo_atribuida",
        "tasa_continuidad_mismo_cliente",
        "tasa_adherencia",
        "tasa_puntualidad",
    ]

    columnas_ranking = [
        columna
        for columna
        in columnas_ranking
        if columna
        in ranking_filtrado.columns
    ]

    st.dataframe(
        ranking_filtrado[
            columnas_ranking
        ],
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            "tasa_retorno_vehiculo_atribuida":
                st.column_config.NumberColumn(
                    "Retención",
                    format="%.1%%",
                ),
            "tasa_continuidad_mismo_cliente":
                st.column_config.NumberColumn(
                    "Continuidad",
                    format="%.1%%",
                ),
            "tasa_adherencia":
                st.column_config.NumberColumn(
                    "Adherencia",
                    format="%.1%%",
                ),
            "tasa_puntualidad":
                st.column_config.NumberColumn(
                    "Puntualidad",
                    format="%.1%%",
                ),
        },
    )


# ============================================================
# 7. METODOLOGÍA
# ============================================================

elif pagina == "ℹ️ Metodología":

    st.header(
        "Metodología y definiciones"
    )

    st.caption(
        (
            "Registro de las reglas e interpretaciones "
            "utilizadas por el Motor 05."
        )
    )

    definiciones = (
        obtener_definiciones_retencion()
    )

    categorias = sorted(
        definiciones[
            "categoria"
        ]
        .dropna()
        .unique()
    )

    categoria = st.multiselect(
        "Categoría",
        categorias,
    )

    texto = st.text_input(
        "Buscar concepto o definición",
        placeholder=(
            "Ej.: retorno, Snowball, cohorte..."
        ),
    )

    vista_definiciones = (
        definiciones.copy()
    )

    if categoria:

        vista_definiciones = (
            vista_definiciones.loc[
                vista_definiciones[
                    "categoria"
                ].isin(
                    categoria
                )
            ]
        )

    if texto.strip():

        patron = texto.strip()

        mask = (
            vista_definiciones[
                "concepto"
            ]
            .astype(str)
            .str.contains(
                patron,
                case=False,
                na=False,
            )
            |
            vista_definiciones[
                "definicion"
            ]
            .astype(str)
            .str.contains(
                patron,
                case=False,
                na=False,
            )
        )

        vista_definiciones = (
            vista_definiciones.loc[
                mask
            ]
        )

    st.dataframe(
        vista_definiciones,
        use_container_width=True,
        hide_index=True,
        height=650,
    )