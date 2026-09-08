from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from main import ejecutar_motor


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="CGO — Demanda Proyectada",
    page_icon="🚗",
    layout="wide",
)


PERSPECTIVAS = {
    "Política": {
        "fecha": "fecha_politica",
        "estado": "estado_politica",
        "dias_hasta": "dias_hasta_politica",
        "dias_atraso": "dias_atraso_politica",
    },
    "Histórica": {
        "fecha": "fecha_historica",
        "estado": "estado_historico",
        "dias_hasta": "dias_hasta_historico",
        "dias_atraso": "dias_atraso_historico",
    },
    "Más inmediata": {
        "fecha": "fecha_mas_inmediata",
        "estado": "estado_mas_inmediata",
        "dias_hasta": "dias_hasta_mas_inmediata",
        "dias_atraso": "dias_atraso_mas_inmediata",
    },
}


ORDEN_ESTADOS = [
    "VENCIDO_LEJANO",
    "VENCIDO_CERCANO",
    "VENCIDO_RECIENTE",
    "EN_FECHA",
    "SERVICIO_MUY_RECIENTE",
    "FUTURO_RECIENTE",
    "FUTURO_PROXIMO",
    "FUTURO_LEJANO",
    "SIN_FECHA_ESTIMABLE",
]


COLUMNAS_TABLA = [
    "vin",
    "placa",
    "modelo",
    "año",
    "parque",
    "sede",
    "asesor",
    "nombre",
    "nro_documento",
    "telefono",
    "correo",
    "fecha_ultima_visita",
    "kilometraje_atendido",
    "kilometraje_siguiente_ciclo",
    "kilometraje_esperado_actual",
    "fecha_objetivo",
    "estado_demanda",
    "dias_hasta_proxima_visita",
    "dias_atraso",
    "tipo_historial",
    "fuente_cliente",
]


# ============================================================
# HELPERS
# ============================================================

def inicializar_estado() -> None:
    """
    Inicializa las variables persistentes de Streamlit.
    """

    if "resultado_motor" not in st.session_state:
        st.session_state.resultado_motor = None

    if "ultima_actualizacion" not in st.session_state:
        st.session_state.ultima_actualizacion = None


def ejecutar_actualizacion() -> None:
    """
    Ejecuta el motor y muestra los logs en vivo.
    """

    panel_estado = st.status(
        "Ejecutando actualización...",
        expanded=True,
    )

    def mostrar_log(
        mensaje: str,
    ) -> None:
        panel_estado.write(
            mensaje
        )

    try:
        resultado = ejecutar_motor(
            log_callback=mostrar_log,
            generar_reporte=True,
        )

        st.session_state.resultado_motor = (
            resultado
        )

        base_demanda = resultado[
            "base_demanda"
        ]

        if not base_demanda.empty:
            st.session_state.ultima_actualizacion = (
                base_demanda[
                    "fecha_generacion"
                ]
                .max()
            )

        panel_estado.update(
            label="Actualización completada",
            state="complete",
            expanded=False,
        )

        st.success(
            "Demanda actualizada correctamente."
        )

    except Exception as error:
        panel_estado.update(
            label="Error durante la actualización",
            state="error",
            expanded=True,
        )

        st.error(
            f"No se pudo completar el proceso: {error}"
        )

        raise


def aplicar_perspectiva(
    base: pd.DataFrame,
    perspectiva: str,
) -> pd.DataFrame:
    """
    Selecciona las columnas ya calculadas por el motor
    correspondientes a la perspectiva elegida.

    Streamlit no recalcula lógica de negocio.
    """

    configuracion = (
        PERSPECTIVAS[
            perspectiva
        ]
    )

    resultado = base.copy()

    resultado[
        "fecha_objetivo"
    ] = resultado[
        configuracion["fecha"]
    ]

    resultado[
        "estado_demanda"
    ] = resultado[
        configuracion["estado"]
    ]

    resultado[
        "dias_hasta_proxima_visita"
    ] = resultado[
        configuracion["dias_hasta"]
    ]

    resultado[
        "dias_atraso"
    ] = resultado[
        configuracion["dias_atraso"]
    ]

    return resultado


def ordenar_opciones(
    serie: pd.Series,
) -> list:
    """
    Genera opciones únicas ordenadas para filtros.
    """

    return sorted(
        serie
        .dropna()
        .unique()
        .tolist()
    )


def filtrar_base(
    base: pd.DataFrame,
    sedes: list,
    modelos: list,
    parques: list,
    estados: list,
) -> pd.DataFrame:
    """
    Aplica los filtros seleccionados por el usuario.
    """

    resultado = base.copy()

    if sedes:
        resultado = resultado.loc[
            resultado[
                "sede"
            ].isin(
                sedes
            )
        ]

    if modelos:
        resultado = resultado.loc[
            resultado[
                "modelo"
            ].isin(
                modelos
            )
        ]

    if parques:
        resultado = resultado.loc[
            resultado[
                "parque"
            ].isin(
                parques
            )
        ]

    if estados:
        resultado = resultado.loc[
            resultado[
                "estado_demanda"
            ].isin(
                estados
            )
        ]

    return resultado


def generar_excel_filtrado(
    dataframe: pd.DataFrame,
) -> bytes:
    """
    Genera una descarga Excel simple del resultado filtrado.
    """

    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="DEMANDA_FILTRADA",
            index=False,
        )

    buffer.seek(0)

    return buffer.getvalue()


def formatear_fecha(
    valor,
) -> str:
    """
    Formatea fecha para encabezados.
    """

    if pd.isna(valor):
        return "Sin actualización"

    return pd.Timestamp(
        valor
    ).strftime(
        "%d/%m/%Y %H:%M"
    )


# ============================================================
# APP
# ============================================================

def main() -> None:

    inicializar_estado()

    # ========================================================
    # ENCABEZADO
    # ========================================================

    encabezado_izquierda, encabezado_derecha = (
        st.columns(
            [
                4,
                1,
            ],
            vertical_alignment="center",
        )
    )

    with encabezado_izquierda:

        st.title(
            "CGO — Demanda Proyectada"
        )

        st.caption(
            "Proyección de demanda de mantenimiento "
            "preventivo | PanaAutos"
        )

    with encabezado_derecha:

        ejecutar = st.button(
            "▶ Actualizar demanda",
            type="primary",
            use_container_width=True,
        )

    if ejecutar:
        ejecutar_actualizacion()

    resultado = (
        st.session_state
        .resultado_motor
    )

    # ========================================================
    # ESTADO SIN EJECUCIÓN
    # ========================================================

    if resultado is None:

        st.info(
            "Presiona **Actualizar demanda** para cargar "
            "las fuentes desde SharePoint y ejecutar el "
            "motor CGO."
        )

        st.stop()

    base_demanda = (
        resultado[
            "base_demanda"
        ]
        .copy()
    )

    # ========================================================
    # INFORMACIÓN DE ACTUALIZACIÓN
    # ========================================================

    st.caption(
        "Última actualización: "
        f"**{formatear_fecha(st.session_state.ultima_actualizacion)}**"
        " · "
        f"Reporte: **{resultado['nombre_reporte']}**"
    )

    st.divider()

    # ========================================================
    # FILTROS
    # ========================================================

    st.subheader(
        "Filtros"
    )

    filtro_perspectiva, filtro_sede, filtro_modelo, \
        filtro_parque, filtro_estado = st.columns(
            [
                1.2,
                1.3,
                1.5,
                1,
                1.6,
            ]
        )

    with filtro_perspectiva:

        perspectiva = st.selectbox(
            "Perspectiva",
            options=list(
                PERSPECTIVAS.keys()
            ),
            index=0,
        )

    base_perspectiva = (
        aplicar_perspectiva(
            base=base_demanda,
            perspectiva=perspectiva,
        )
    )

    with filtro_sede:

        sedes = st.multiselect(
            "Sede",
            options=ordenar_opciones(
                base_perspectiva[
                    "sede"
                ]
            ),
            placeholder="Todas",
        )

    with filtro_modelo:

        modelos = st.multiselect(
            "Modelo",
            options=ordenar_opciones(
                base_perspectiva[
                    "modelo"
                ]
            ),
            placeholder="Todos",
        )

    with filtro_parque:

        parques = st.multiselect(
            "Parque",
            options=ordenar_opciones(
                base_perspectiva[
                    "parque"
                ]
            ),
            placeholder="Todos",
        )

    estados_disponibles = [
        estado
        for estado in ORDEN_ESTADOS
        if estado
        in set(
            base_perspectiva[
                "estado_demanda"
            ]
            .dropna()
            .unique()
        )
    ]

    with filtro_estado:

        estados = st.multiselect(
            "Estado",
            options=estados_disponibles,
            placeholder="Todos",
        )

    base_filtrada = filtrar_base(
        base=base_perspectiva,
        sedes=sedes,
        modelos=modelos,
        parques=parques,
        estados=estados,
    )

    # ========================================================
    # KPIs
    # ========================================================

    st.divider()

    total = len(
        base_filtrada
    )

    vencidos = int(
        base_filtrada[
            "estado_demanda"
        ]
        .isin(
            [
                "VENCIDO_LEJANO",
                "VENCIDO_CERCANO",
                "VENCIDO_RECIENTE",
            ]
        )
        .sum()
    )

    en_fecha = int(
        base_filtrada[
            "estado_demanda"
        ]
        .eq(
            "EN_FECHA"
        )
        .sum()
    )

    proximos = int(
        base_filtrada[
            "estado_demanda"
        ]
        .isin(
            [
                "FUTURO_RECIENTE",
                "FUTURO_PROXIMO",
            ]
        )
        .sum()
    )

    kpi_total, kpi_vencidos, kpi_fecha, kpi_proximos = (
        st.columns(4)
    )

    kpi_total.metric(
        "Vehículos",
        f"{total:,}",
    )

    kpi_vencidos.metric(
        "Vencidos",
        f"{vencidos:,}",
    )

    kpi_fecha.metric(
        "En fecha",
        f"{en_fecha:,}",
    )

    kpi_proximos.metric(
        "Próximos",
        f"{proximos:,}",
    )

    # ========================================================
    # TABLA
    # ========================================================

    st.divider()

    titulo_tabla, accion_descarga = (
        st.columns(
            [
                4,
                1,
            ],
            vertical_alignment="center",
        )
    )

    with titulo_tabla:

        st.subheader(
            "Demanda"
        )

        st.caption(
            f"{len(base_filtrada):,} registros "
            f"· Perspectiva: {perspectiva}"
        )

    columnas_existentes = [
        columna
        for columna in COLUMNAS_TABLA
        if columna in base_filtrada.columns
    ]

    tabla = (
        base_filtrada[
            columnas_existentes
        ]
        .copy()
    )

    tabla = tabla.sort_values(
        [
            "fecha_objetivo",
            "vin",
        ],
        na_position="last",
    )

    with accion_descarga:

        archivo_filtrado = (
            generar_excel_filtrado(
                tabla
            )
        )

        st.download_button(
            label="⬇ Descargar filtrado",
            data=archivo_filtrado,
            file_name=(
                "DEMANDA_FILTRADA.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "fecha_ultima_visita":
                st.column_config.DateColumn(
                    "Última visita",
                    format="DD/MM/YYYY",
                ),

            "fecha_objetivo":
                st.column_config.DateColumn(
                    "Fecha objetivo",
                    format="DD/MM/YYYY",
                ),

            "kilometraje_atendido":
                st.column_config.NumberColumn(
                    "Último mantenimiento",
                    format="%dK",
                ),

            "kilometraje_siguiente_ciclo":
                st.column_config.NumberColumn(
                    "Siguiente ciclo",
                    format="%dK",
                ),

            "kilometraje_esperado_actual":
                st.column_config.NumberColumn(
                    "Esperado actual",
                    format="%dK",
                ),

            "dias_hasta_proxima_visita":
                st.column_config.NumberColumn(
                    "Días hasta",
                ),

            "dias_atraso":
                st.column_config.NumberColumn(
                    "Días atraso",
                ),
        },
    )

    # ========================================================
    # LOG DE EJECUCIÓN
    # ========================================================

    st.divider()

    with st.expander(
        "Detalle de ejecución",
        expanded=False,
    ):

        for mensaje in resultado[
            "logs"
        ]:
            st.text(
                mensaje
            )

        if resultado[
            "ruta_sharepoint"
        ]:

            st.caption(
                "Reporte generado en SharePoint:"
            )

            st.code(
                resultado[
                    "ruta_sharepoint"
                ],
                language=None,
            )


if __name__ == "__main__":
    main()