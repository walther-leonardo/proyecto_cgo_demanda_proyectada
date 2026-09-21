from __future__ import annotations

from datetime import datetime
from typing import Callable

import pandas as pd


from m365.config import (
    SITE_NAME,
    DRIVE_NAME,
    INPUT_FOLDER,
    RETAIL_FILE,
    TALLER_FILE,
    CLIENTES_FILE,
)
from m365.sharepoint import SharePoint
from m365.excel import read_excel

from motor.datos import preparar_datos

from motor_retencion.retencion import (
    construir_motor_retencion,
)
from motor_retencion.cohortes import (
    construir_cohortes_retencion,
)

from motor_retencion.snowball import (
    construir_snowball_retencion,
)

from motor_retencion.clientes import (
    construir_analisis_clientes,
)

from motor_retencion.exportacion import (
    generar_excel_retencion,
    generar_nombre_reporte_retencion,
)


from motor.demanda import (
    construir_historial_analitico,
)

from motor_retencion.pana import (
    construir_analisis_pana,
)

# ============================================================
# TIPOS
# ============================================================

LogCallback = Callable[[str], None]


# ============================================================
# LOG
# ============================================================

def _registrar_log(
    logs: list[str],
    mensaje: str,
    callback: LogCallback | None = None,
) -> None:
    """
    Guarda un mensaje de ejecución y opcionalmente lo envía
    a un callback.

    Terminal:
        callback=print

    Streamlit:
        podrá utilizarse posteriormente para mostrar
        progreso en tiempo real.
    """

    hora = datetime.now().strftime(
        "%H:%M:%S"
    )

    mensaje_formateado = (
        f"{hora} {mensaje}"
    )

    logs.append(
        mensaje_formateado
    )

    if callback is not None:
        callback(
            mensaje_formateado
        )


# ============================================================
# SHAREPOINT / EXCEL
# ============================================================

def cargar_archivo_excel(
    sharepoint: SharePoint,
    drive_id: str,
    carpeta: str,
    nombre_archivo: str,
) -> pd.DataFrame:
    """
    Descarga un Excel desde SharePoint completamente en
    memoria y lo convierte a DataFrame.
    """

    ruta = (
        f"{carpeta}/"
        f"{nombre_archivo}"
    )

    archivo = (
        sharepoint.download_file_by_path(
            drive_id=drive_id,
            file_path=ruta,
        )
    )

    return read_excel(
        archivo
    )


# ============================================================
# MOTOR CGO — RETENCIÓN
# ============================================================

def ejecutar_motor_retencion(
    log_callback: LogCallback | None = None,
    generar_reporte: bool = False,
) -> dict:
    """
    Ejecuta de punta a punta el Motor 05 — Retención.

    Flujo:
    1. Conectar SharePoint.
    2. Cargar Retail, Taller y Clientes.
    3. Preparar fuentes con la lógica canónica del Motor 04.
    4. Construir el estado operacional de Demanda.
    5. Construir Retención.
    6. Construir Cohortes.
    7. Construir Snowball.
    8. Construir análisis de Clientes.
    9. Construir matriz operacional PANA.
    10. Generar Excel opcionalmente.
    """

    logs: list[str] = []

    _registrar_log(
        logs,
        "🚀 Iniciando Motor CGO — Retención",
        log_callback,
    )

    # ========================================================
    # 1. SHAREPOINT
    # ========================================================

    sharepoint = SharePoint()

    _registrar_log(
        logs,
        "🔄 Conectando con SharePoint...",
        log_callback,
    )

    site = sharepoint.get_site(
        SITE_NAME
    )

    if site is None:
        raise RuntimeError(
            f"No se encontró el site '{SITE_NAME}'."
        )

    _registrar_log(
        logs,
        (
            f"🟢 Site conectado: "
            f"{site['displayName']}"
        ),
        log_callback,
    )

    drive = sharepoint.get_drive(
        site_id=site["id"],
        drive_name=DRIVE_NAME,
    )

    if drive is None:
        raise RuntimeError(
            f"No se encontró el drive '{DRIVE_NAME}'."
        )

    drive_id = drive["id"]

    _registrar_log(
        logs,
        (
            f"🟢 Biblioteca conectada: "
            f"{drive['name']}"
        ),
        log_callback,
    )

    # ========================================================
    # 2. FUENTES
    # ========================================================

    _registrar_log(
        logs,
        "🔄 Cargando fuentes...",
        log_callback,
    )

    retail = cargar_archivo_excel(
        sharepoint=sharepoint,
        drive_id=drive_id,
        carpeta=INPUT_FOLDER,
        nombre_archivo=RETAIL_FILE,
    )

    _registrar_log(
        logs,
        (
            f"🟢 {RETAIL_FILE}: "
            f"{len(retail):,} registros"
        ),
        log_callback,
    )

    taller = cargar_archivo_excel(
        sharepoint=sharepoint,
        drive_id=drive_id,
        carpeta=INPUT_FOLDER,
        nombre_archivo=TALLER_FILE,
    )

    _registrar_log(
        logs,
        (
            f"🟢 {TALLER_FILE}: "
            f"{len(taller):,} registros"
        ),
        log_callback,
    )

    clientes = cargar_archivo_excel(
        sharepoint=sharepoint,
        drive_id=drive_id,
        carpeta=INPUT_FOLDER,
        nombre_archivo=CLIENTES_FILE,
    )

    _registrar_log(
        logs,
        (
            f"🟢 {CLIENTES_FILE}: "
            f"{len(clientes):,} registros"
        ),
        log_callback,
    )

    # ========================================================
    # 3. PREPARACIÓN CANÓNICA — MOTOR 04
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Preparando fuentes con la lógica "
            "canónica del Motor 04..."
        ),
        log_callback,
    )

    datos = preparar_datos(
        retail_raw=retail,
        taller_raw=taller,
        clientes_raw=clientes,
    )

    retail_preparado = datos["retail"]
    taller_preparado = datos["taller"]
    clientes_preparado = datos["clientes"]

    historia_preventiva = (
        datos["historia_preventiva"]
    )

    auditoria = (
        datos["auditoria"]
    )

    auditoria_mantenimientos = (
        datos["auditoria_mantenimientos"]
    )

    calidad_datos = (
        datos["calidad_datos"]
    )

    _registrar_log(
        logs,
        (
            "🟢 Historia preventiva canónica: "
            f"{len(historia_preventiva):,} registros"
        ),
        log_callback,
    )

    # ========================================================
    # 4. FECHA MÁXIMA DE INFORMACIÓN
    # ========================================================

    fecha_max_datos = (
        taller_preparado[
            "fecha_orden"
        ]
        .max()
    )

    if pd.isna(fecha_max_datos):
        raise ValueError(
            "No fue posible determinar la fecha máxima "
            "disponible de Taller."
        )

    fecha_max_datos = pd.Timestamp(
        fecha_max_datos
    ).normalize()

    _registrar_log(
        logs,
        (
            "🟢 Fecha máxima de datos: "
            f"{fecha_max_datos:%Y-%m-%d}"
        ),
        log_callback,
    )

    # ========================================================
    # 5. ESTADO OPERACIONAL — MOTOR 04
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo estado operacional "
            "desde Motor 04..."
        ),
        log_callback,
    )
    #🐶


    historial_demanda = (
        construir_historial_analitico(
            historia_preventiva=historia_preventiva,
            retail=retail_preparado,
            clientes=clientes_preparado,
        )
    )


    #🐶
    base_demanda = (
        historial_demanda[
            "base_demanda"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 Estado operacional construido: "
            f"{len(base_demanda):,} VIN"
        ),
        log_callback,
    )

    # ========================================================
    # 6. MOTOR 05 — RETENCIÓN
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo visitas, secuencia "
            "y KPI de retención..."
        ),
        log_callback,
    )

    motor = construir_motor_retencion(
        historia_preventiva=
            historia_preventiva,
        fecha_max_datos=
            fecha_max_datos,
    )

    registros_con_visita = (
        motor["registros_con_visita"]
    )

    visitas_analiticas = (
        motor["visitas_analiticas"]
    )

    secuencia_preventiva = (
        motor["secuencia_preventiva"]
    )

    auditoria_visitas = (
        motor["auditoria_visitas"]
    )

    ciclos_retencion = (
        motor["ciclos_retencion"]
    )

    resumen_vin = (
        motor["resumen_vin"]
    )

    resumen_kpis = (
        motor["resumen_kpis"]
    )

    retencion_por_hito = (
        motor["retencion_por_hito"]
    )

    auditoria_retencion = (
        motor["auditoria_retencion"]
    )

    _registrar_log(
        logs,
        (
            "🟢 Visitas analíticas: "
            f"{len(visitas_analiticas):,}"
        ),
        log_callback,
    )

    _registrar_log(
        logs,
        (
            "🟢 VIN con historial preventivo: "
            f"{secuencia_preventiva['vin'].nunique():,}"
        ),
        log_callback,
    )

    _registrar_log(
        logs,
        (
            "🟢 Oportunidades de ciclo: "
            f"{len(ciclos_retencion):,}"
        ),
        log_callback,
    )

    # ========================================================
    # 7. COHORTES
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo oportunidades, "
            "cohortes y snapshots..."
        ),
        log_callback,
    )

    cohortes = (
        construir_cohortes_retencion(
            retail=
                retail_preparado,
            secuencia=
                secuencia_preventiva,
            ciclos_retencion=
                ciclos_retencion,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    oportunidades = (
        cohortes["oportunidades"]
    )

    base_evaluable = (
        cohortes["base_evaluable"]
    )

    retencion_hitos_cohortes = (
        cohortes[
            "retencion_hitos"
        ]
    )

    retencion_cohorte_hito = (
        cohortes[
            "retencion_cohorte_hito"
        ]
    )

    snapshots_hitos = (
        cohortes[
            "snapshots_hitos"
        ]
    )

    auditoria_cohortes = (
        cohortes[
            "auditoria_cohortes"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 Cohortes construidas: "
            f"{len(base_evaluable):,} "
            "oportunidades evaluables"
        ),
        log_callback,
    )

    # ========================================================
    # 8. SNOWBALL
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo parque comercial "
            "y efecto Snowball..."
        ),
        log_callback,
    )

    snowball = (
        construir_snowball_retencion(
            retail=
                retail_preparado,
            secuencia=
                secuencia_preventiva,
            fecha_max_datos=
                fecha_max_datos,
        )
    )

    parque_comercial = (
        snowball["parque_comercial"]
    )

    snapshot_parque_general = (
        snowball[
            "snapshot_parque_general"
        ]
    )

    snapshot_parque_total = (
        snowball[
            "snapshot_parque_total"
        ]
    )

    snapshot_segmentacion = (
        snowball[
            "snapshot_segmentacion"
        ]
    )

    ultimo_estado_vin = (
        snowball[
            "ultimo_estado_vin"
        ]
    )

    auditoria_snowball = (
        snowball[
            "auditoria_snowball"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 Snowball construido: "
            f"{len(parque_comercial):,} "
            "VIN en parque comercial"
        ),
        log_callback,
    )

    # ========================================================
    # 9. CLIENTES
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo análisis de clientes "
            "y perfiles comerciales..."
        ),
        log_callback,
    )

    analisis_clientes = (
        construir_analisis_clientes(
            secuencia=
                secuencia_preventiva,
            ciclos_retencion=
                ciclos_retencion,
            clientes=
                clientes_preparado,
        )
    )

    base_visita_cliente = (
        analisis_clientes[
            "base_visita_cliente"
        ]
    )

    oportunidades_cliente = (
        analisis_clientes[
            "oportunidades_cliente"
        ]
    )

    resumen_vin_clientes = (
        analisis_clientes[
            "resumen_vin_clientes"
        ]
    )

    resumen_cliente_vin = (
        analisis_clientes[
            "resumen_cliente_vin"
        ]
    )

    resumen_cliente = (
        analisis_clientes[
            "resumen_cliente"
        ]
    )

    ranking_clientes = (
        analisis_clientes[
            "ranking_clientes"
        ]
    )

    perfiles_comerciales = (
        analisis_clientes[
            "perfiles_comerciales"
        ]
    )

    auditoria_clientes = (
        analisis_clientes[
            "auditoria_clientes"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 Análisis clientes construido: "
            f"{len(resumen_cliente):,} "
            "clientes con historia preventiva"
        ),
        log_callback,
    )

    # ========================================================
    # 10. PARQUE PANA
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Construyendo matriz operacional "
            "del Parque PANA..."
        ),
        log_callback,
    )

    analisis_pana = (
        construir_analisis_pana(
            retail=
                retail_preparado,
            secuencia=
                secuencia_preventiva,
            base_demanda=
                base_demanda,
            km_maximo_matriz=50,
        )
    )

    matriz_pana = (
        analisis_pana[
            "matriz_pana"
        ]
    )

    detalle_pana = (
        analisis_pana[
            "detalle_pana"
        ]
    )

    auditoria_pana = (
        analisis_pana[
            "auditoria_pana"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 Matriz PANA construida: "
            f"{len(matriz_pana):,} VIN"
        ),
        log_callback,
    )

    # ========================================================
    # 11. REPORTE EXCEL OPCIONAL
    # ========================================================

    archivo_excel = None
    nombre_reporte = None

    if generar_reporte:

        _registrar_log(
            logs,
            "🔄 Generando Excel de Retención...",
            log_callback,
        )

        fecha_reporte = datetime.now()

        nombre_reporte = (
            generar_nombre_reporte_retencion(
                fecha_reporte
            )
        )

        resultado_exportacion = {
            "fecha_max_datos":
                fecha_max_datos,

            "secuencia_preventiva":
                secuencia_preventiva,

            "ciclos_retencion":
                ciclos_retencion,

            "resumen_kpis":
                resumen_kpis,

            "retencion_por_hito":
                retencion_por_hito,

            "oportunidades":
                oportunidades,

            "retencion_cohorte_hito":
                retencion_cohorte_hito,

            "snapshot_parque_general":
                snapshot_parque_general,

            "snapshot_parque_total":
                snapshot_parque_total,

            "resumen_cliente":
                resumen_cliente,

            "resumen_cliente_vin":
                resumen_cliente_vin,

            "perfiles_comerciales":
                perfiles_comerciales,

            "auditoria_retencion":
                auditoria_retencion,

            "auditoria_cohortes":
                auditoria_cohortes,

            "auditoria_snowball":
                auditoria_snowball,

            "auditoria_clientes":
                auditoria_clientes,
        }

        archivo_excel = (
            generar_excel_retencion(
                resultado=
                    resultado_exportacion,
                fecha_generacion=
                    fecha_reporte,
            )
        )

        _registrar_log(
            logs,
            (
                "🟢 Excel preparado: "
                f"{nombre_reporte}"
            ),
            log_callback,
        )

    # ========================================================
    # 12. FINALIZACIÓN
    # ========================================================

    _registrar_log(
        logs,
        (
            "✅ Motor CGO — Retención "
            "ejecutado correctamente"
        ),
        log_callback,
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    return {
        # ----------------------------------------------------
        # Conexión
        # ----------------------------------------------------

        "site":
            site,

        "drive":
            drive,

        "drive_id":
            drive_id,

        # ----------------------------------------------------
        # Fuentes originales
        # ----------------------------------------------------

        "retail_raw":
            retail,

        "taller_raw":
            taller,

        "clientes_raw":
            clientes,

        # ----------------------------------------------------
        # Fuentes preparadas
        # ----------------------------------------------------

        "retail":
            retail_preparado,

        "taller":
            taller_preparado,

        "clientes":
            clientes_preparado,

        "historia_preventiva":
            historia_preventiva,

        "fecha_max_datos":
            fecha_max_datos,

        # ----------------------------------------------------
        # Auditorías Motor 04
        # ----------------------------------------------------

        "auditoria":
            auditoria,

        "auditoria_mantenimientos":
            auditoria_mantenimientos,

        "calidad_datos":
            calidad_datos,

        # ----------------------------------------------------
        # Estado operacional Motor 04
        # ----------------------------------------------------

        "historial_demanda":
            historial_demanda,

        "base_demanda":
            base_demanda,

        # ----------------------------------------------------
        # Historia canónica
        # ----------------------------------------------------

        "registros_con_visita":
            registros_con_visita,

        "visitas_analiticas":
            visitas_analiticas,

        "secuencia_preventiva":
            secuencia_preventiva,

        "auditoria_visitas":
            auditoria_visitas,

        # ----------------------------------------------------
        # Retención
        # ----------------------------------------------------

        "ciclos_retencion":
            ciclos_retencion,

        "resumen_vin":
            resumen_vin,

        "resumen_kpis":
            resumen_kpis,

        "retencion_por_hito":
            retencion_por_hito,

        "auditoria_retencion":
            auditoria_retencion,

        # ----------------------------------------------------
        # Cohortes
        # ----------------------------------------------------

        "cohortes":
            cohortes,

        "oportunidades":
            oportunidades,

        "base_evaluable":
            base_evaluable,

        "retencion_hitos_cohortes":
            retencion_hitos_cohortes,

        "retencion_cohorte_hito":
            retencion_cohorte_hito,

        "snapshots_hitos":
            snapshots_hitos,

        "auditoria_cohortes":
            auditoria_cohortes,

        # ----------------------------------------------------
        # Snowball
        # ----------------------------------------------------

        "snowball":
            snowball,

        "parque_comercial":
            parque_comercial,

        "snapshot_parque_general":
            snapshot_parque_general,

        "snapshot_parque_total":
            snapshot_parque_total,

        "snapshot_segmentacion":
            snapshot_segmentacion,

        "ultimo_estado_vin":
            ultimo_estado_vin,

        "auditoria_snowball":
            auditoria_snowball,

        # ----------------------------------------------------
        # Clientes
        # ----------------------------------------------------

        "analisis_clientes":
            analisis_clientes,

        "base_visita_cliente":
            base_visita_cliente,

        "oportunidades_cliente":
            oportunidades_cliente,

        "resumen_vin_clientes":
            resumen_vin_clientes,

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

        # ----------------------------------------------------
        # Parque PANA
        # ----------------------------------------------------

        "analisis_pana":
            analisis_pana,

        "matriz_pana":
            matriz_pana,

        "detalle_pana":
            detalle_pana,

        "auditoria_pana":
            auditoria_pana,

        # ----------------------------------------------------
        # Exportación
        # ----------------------------------------------------

        "archivo_excel":
            archivo_excel,

        "nombre_reporte":
            nombre_reporte,

        # ----------------------------------------------------
        # Logs
        # ----------------------------------------------------

        "logs":
            logs,
    }

# ============================================================
# DIAGNÓSTICO DE DESARROLLO
# ============================================================

def imprimir_diagnostico_retencion(
    resultado: dict,
) -> None:
    """
    Muestra las auditorías principales del Motor 05.

    La primera sección valida explícitamente que la historia
    utilizada por Retención sea la misma historia canónica
    definida por el Motor 04.
    """

    historia_preventiva = (
        resultado[
            "historia_preventiva"
        ]
    )

    secuencia = (
        resultado[
            "secuencia_preventiva"
        ]
    )

    visitas = (
        resultado[
            "visitas_analiticas"
        ]
    )

    auditoria_visitas = (
        resultado[
            "auditoria_visitas"
        ]
    )

    ciclos = (
        resultado[
            "ciclos_retencion"
        ]
    )

    resumen_vin = (
        resultado[
            "resumen_vin"
        ]
    )

    resumen_kpis = (
        resultado[
            "resumen_kpis"
        ]
    )

    retencion_por_hito = (
        resultado[
            "retencion_por_hito"
        ]
    )

    auditoria_retencion = (
        resultado[
            "auditoria_retencion"
        ]
    )

    fecha_max_datos = (
        resultado[
            "fecha_max_datos"
        ]
    )

    # ========================================================
    # FUENTES
    # ========================================================

    print()
    print("=" * 72)
    print("FUENTES")
    print("=" * 72)

    print(
        f"Retail             : "
        f"{len(resultado['retail_raw']):,}"
    )

    print(
        f"Taller             : "
        f"{len(resultado['taller_raw']):,}"
    )

    print(
        f"Clientes           : "
        f"{len(resultado['clientes_raw']):,}"
    )

    print(
        f"Fecha máxima datos : "
        f"{fecha_max_datos:%Y-%m-%d}"
    )

    # ========================================================
    # HISTORIA CANÓNICA
    # ========================================================

    print()
    print("=" * 72)
    print(
        "VALIDACIÓN HISTORIA CANÓNICA — MOTOR 04 / MOTOR 05"
    )
    print("=" * 72)

    print(
        f"Preventivos base                  : "
        f"{auditoria_visitas['preventivos_base']:,}"
    )

    print(
        f"Preventivos con KM                : "
        f"{auditoria_visitas['preventivos_con_km']:,}"
    )

    print(
        f"Preventivos excluidos sin KM      : "
        f"{auditoria_visitas['preventivos_excluidos_sin_km']:,}"
    )

    print(
        f"Visitas analíticas                : "
        f"{auditoria_visitas['visitas_analiticas']:,}"
    )

    print(
        f"Registros consolidados            : "
        f"{auditoria_visitas['registros_consolidados']:,}"
    )

    print(
        f"Visitas múltiples registros       : "
        f"{auditoria_visitas['visitas_con_multiples_registros']:,}"
    )

    print(
        f"Visitas con KM múltiple           : "
        f"{auditoria_visitas['visitas_con_km_multiple']:,}"
    )

    print(
        f"VIN con historial preventivo      : "
        f"{auditoria_visitas['vin_con_historial_preventivo']:,}"
    )

    # ========================================================
    # COMPORTAMIENTO CANÓNICO
    # ========================================================

    print()
    print("=" * 72)
    print("COMPORTAMIENTO PREVENTIVO CANÓNICO")
    print("=" * 72)

    print(
        f"PRIMERA_VISITA                    : "
        f"{auditoria_visitas['primera_visita']:,}"
    )

    print(
        f"SIGUE_CICLO                       : "
        f"{auditoria_visitas['sigue_ciclo']:,}"
    )

    print(
        f"SALTA_MANTENIMIENTOS              : "
        f"{auditoria_visitas['salta_mantenimientos']:,}"
    )

    print(
        f"REPITE_MANTENIMIENTO              : "
        f"{auditoria_visitas['repite_mantenimiento']:,}"
    )

    print(
        f"RETROCESO                         : "
        f"{auditoria_visitas['retroceso']:,}"
    )

    print(
        f"SECUENCIA_NO_ESTANDAR             : "
        f"{auditoria_visitas['secuencia_no_estandar']:,}"
    )

    # ========================================================
    # PARQUE PREVENTIVO
    # ========================================================

    print()
    print("=" * 72)
    print("DISTRIBUCIÓN DEL PARQUE — VISITAS ANALÍTICAS")
    print("=" * 72)

    print(
        visitas[
            "parque"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    # ========================================================
    # MANTENIMIENTOS OBSERVADOS
    # ========================================================

    print()
    print("=" * 72)
    print("MANTENIMIENTOS — VISITAS ANALÍTICAS")
    print("=" * 72)

    print(
        visitas[
            "mantenimiento_km"
        ]
        .value_counts(
            dropna=False
        )
        .sort_index()
        .to_string()
    )

    # ========================================================
    # RETENCIÓN
    # ========================================================

    print()
    print("=" * 72)
    print("MOTOR 05 — OPORTUNIDADES DE RETENCIÓN")
    print("=" * 72)

    print(
        f"Oportunidades de ciclo construidas : "
        f"{len(ciclos):,}"
    )

    print(
        f"VIN en oportunidades de ciclo      : "
        f"{ciclos['vin'].nunique():,}"
    )

    print()
    print(
        ciclos[
            "kpi_retorno"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    # ========================================================
    # KPI POR PARQUE
    # ========================================================

    print()
    print("=" * 72)
    print("KPI DE RETENCIÓN POR PARQUE")
    print("=" * 72)

    vista_kpis = (
        resumen_kpis.copy()
    )

    for columna in [
        "tasa_retorno",
        "tasa_adherencia",
        "tasa_puntualidad",
    ]:

        if columna in vista_kpis.columns:

            vista_kpis[
                columna
            ] = (
                vista_kpis[
                    columna
                ]
                .map(
                    lambda valor:
                        f"{valor:.1%}"
                        if pd.notna(valor)
                        else "N/A"
                )
            )

    print(
        vista_kpis.to_string(
            index=False
        )
    )

    # ========================================================
    # RETENCIÓN POR HITO
    # ========================================================

    print()
    print("=" * 72)
    print("RETENCIÓN POR HITO")
    print("=" * 72)

    vista_hitos = (
        retencion_por_hito.copy()
    )

    for columna in [
        "tasa_retorno",
        "tasa_adherencia",
        "tasa_puntualidad",
    ]:

        if columna in vista_hitos.columns:

            vista_hitos[
                columna
            ] = (
                vista_hitos[
                    columna
                ]
                .map(
                    lambda valor:
                        f"{valor:.1%}"
                        if pd.notna(valor)
                        else "N/A"
                )
            )

    print(
        vista_hitos.to_string(
            index=False
        )
    )

    # ========================================================
    # AUDITORÍA RETENCIÓN
    # ========================================================

    print()
    print("=" * 72)
    print("AUDITORÍA MOTOR 05")
    print("=" * 72)

    print(
        auditoria_retencion.to_string(
            index=False
        )
    )

    # ========================================================
    # MUESTRA DE SECUENCIA
    # ========================================================

    print()
    print("=" * 72)
    print("MUESTRA DE SECUENCIA PREVENTIVA")
    print("=" * 72)

    columnas_muestra = [
        "vin",
        "parque",
        "modelo",
        "sede",
        "fecha_visita",
        "mantenimiento_km",
        "mantenimiento_anterior",
        "mantenimiento_esperado_desde_anterior",
        "comportamiento",
        "dias_desde_visita_anterior",
    ]

    print(
        secuencia[
            columnas_muestra
        ]
        .head(20)
        .to_string(
            index=False
        )
    )

    # ========================================================
    # RESUMEN VIN
    # ========================================================

    print()
    print("=" * 72)
    print("MUESTRA RESUMEN VIN")
    print("=" * 72)

    columnas_resumen = [
        "vin",
        "parque",
        "modelo",
        "anio_vehiculo",
        "sede",
        "fecha_primera_visita",
        "fecha_ultima_visita",
        "visitas_preventivas",
        "cantidad_saltos",
        "cantidad_retrocesos",
        "cantidad_repeticiones",
        "cantidad_inconsistencias",
    ]

    columnas_disponibles = [
        columna
        for columna in columnas_resumen
        if columna in resumen_vin.columns
    ]

    print(
        resumen_vin[
            columnas_disponibles
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("AUDITORÍA DE COHORTES")
    print("=" * 72)

    print(
        resultado[
            "auditoria_cohortes"
        ]
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("RETENCIÓN PANA — 1K A 50K")
    print("=" * 72)

    vista = (
        resultado[
            "retencion_hitos_cohortes"
        ]
    )

    vista = vista.loc[
        vista[
            "parque"
        ].eq("PANA")
        &
        vista[
            "hito_km"
        ].le(50)
    ].copy()

    vista[
        "tasa_retencion"
    ] = (
        vista[
            "tasa_retencion"
        ]
        .map(
            lambda valor:
                f"{valor:.1%}"
                if pd.notna(valor)
                else "N/A"
        )
    )

    print(
        vista.to_string(
            index=False
        )
    )


# ============================================================
# EJECUCIÓN DESDE TERMINAL
# ============================================================

def main() -> None:
    """
    Entrada manual:

        py main_retencion.py
    """

    print()
    print("=" * 72)
    print("CGO — RETENCIÓN")
    print("=" * 72)

    resultado = ejecutar_motor_retencion(
        log_callback=print,
        generar_reporte=False,
    )

    # ========================================================
    # DIAGNÓSTICO BASE
    # ========================================================

    imprimir_diagnostico_retencion(
        resultado
    )

    # ========================================================
    # SNOWBALL
    # ========================================================

    print()
    print("=" * 72)
    print("AUDITORÍA SNOWBALL")
    print("=" * 72)

    print(
        resultado[
            "auditoria_snowball"
        ]
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("SNOWBALL — ÚLTIMO SNAPSHOT")
    print("=" * 72)

    snapshot = (
        resultado[
            "snapshot_parque_general"
        ]
    )

    ultimo = (
        snapshot[
            "snapshot"
        ]
        .max()
    )

    vista_snowball = (
        snapshot.loc[
            snapshot[
                "snapshot"
            ].eq(ultimo)
        ]
        .copy()
    )

    vista_snowball[
        "tasa_parque_vigente"
    ] = (
        vista_snowball[
            "tasa_parque_vigente"
        ]
        .map(
            lambda valor:
                f"{valor:.1%}"
                if pd.notna(valor)
                else "N/A"
        )
    )

    columnas_snowball = [
        "snapshot",
        "parque",
        "parque_acumulado",
        "parque_vigente",
        "parque_vencido",
        "tasa_parque_vigente",
        "altas_mes",
        "reactivaciones_mes",
        "nuevos_vencidos_mes",
        "variacion_vigente",
        "indice_snowball",
    ]

    print(
        vista_snowball[
            columnas_snowball
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # CLIENTES
    # ========================================================

    print()
    print("=" * 72)
    print("AUDITORÍA CLIENTES")
    print("=" * 72)

    print(
        resultado[
            "auditoria_clientes"
        ]
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("PERFILES COMERCIALES")
    print("=" * 72)

    print(
        resultado[
            "perfiles_comerciales"
        ]
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("TOP 10 CLIENTES — RETENCIÓN")
    print("=" * 72)

    ranking = (
        resultado[
            "ranking_clientes"
        ]
    )

    top = (
        ranking.loc[
            ranking[
                "metrica_ranking"
            ].eq(
                "RETENCION"
            )
        ]
        .head(10)
        .copy()
    )

    columnas_top = [
        "ranking",
        "nro_documento",
        "nombre",
        "visitas_preventivas",
        "vin_distintos",
        "oportunidades_evaluables",
        "vehiculos_retornaron",
        "tasa_retorno_vehiculo_atribuida",
        "tasa_continuidad_mismo_cliente",
    ]

    print(
        top[
            columnas_top
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # PARQUE PANA
    # ========================================================

    print()
    print("=" * 72)
    print("AUDITORÍA PARQUE PANA")
    print("=" * 72)

    print(
        resultado[
            "auditoria_pana"
        ]
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("MATRIZ PANA — MUESTRA")
    print("=" * 72)

    print(
        resultado[
            "matriz_pana"
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    # ========================================================
    # FIN
    # ========================================================

    print()
    print("=" * 72)
    print(
        "✅ PROCESO DE RETENCIÓN COMPLETADO"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
