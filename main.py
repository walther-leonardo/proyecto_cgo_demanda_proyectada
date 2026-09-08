from __future__ import annotations

from datetime import datetime
from typing import Callable

import pandas as pd

from m365.config import (
    SITE_NAME,
    DRIVE_NAME,
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    RETAIL_FILE,
    TALLER_FILE,
    CLIENTES_FILE,
)
from m365.sharepoint import SharePoint
from m365.excel import read_excel

from motor.datos import preparar_datos
from motor.demanda import construir_historial_analitico
from motor.exportacion import (
    generar_excel_demanda,
    generar_nombre_reporte,
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

    PowerShell:
        callback=print

    Streamlit:
        posteriormente podremos utilizar un callback que
        actualice un contenedor visual en tiempo real.
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
# MOTOR CGO
# ============================================================

def ejecutar_motor(
    log_callback: LogCallback | None = None,
    generar_reporte: bool = True,
) -> dict:
    """
    Ejecuta de punta a punta el Motor CGO de Demanda
    Proyectada.

    Flujo:
    1. Conectar SharePoint.
    2. Cargar Retail, Taller y Clientes.
    3. Preparar y auditar fuentes.
    4. Construir historial y demanda proyectada.
    5. Generar Excel.
    6. Subir Excel a SharePoint.
    7. Retornar resultados para otros consumidores
       como Streamlit.

    Parameters
    ----------
    log_callback:
        Función opcional que recibe cada mensaje de log.
        Permite mostrar progreso en terminal o Streamlit.

    generar_reporte:
        Si es True genera y sube el Excel a SharePoint.
        Si es False ejecuta el motor sin exportar.

    Returns
    -------
    dict
        Resultados operacionales, auditorías y logs.
    """

    logs: list[str] = []

    _registrar_log(
        logs,
        "🚀 Iniciando Motor CGO — Demanda Proyectada",
        log_callback,
    )

    # ========================================================
    # SHAREPOINT
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
            f"No se encontró el site "
            f"'{SITE_NAME}'."
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
            f"No se encontró el drive "
            f"'{DRIVE_NAME}'."
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
    # FUENTES
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
    # PREPARACIÓN
    # ========================================================

    _registrar_log(
        logs,
        "🔄 Preparando y auditando datos...",
        log_callback,
    )

    datos = preparar_datos(
        retail_raw=retail,
        taller_raw=taller,
        clientes_raw=clientes,
    )

    retail_preparado = (
        datos["retail"]
    )

    taller_preparado = (
        datos["taller"]
    )

    clientes_preparado = (
        datos["clientes"]
    )

    historia_preventiva = (
        datos["historia_preventiva"]
    )

    auditoria = (
        datos["auditoria"]
    )

    auditoria_mantenimientos = (
        datos[
            "auditoria_mantenimientos"
        ]
    )

    calidad_datos = (
        datos["calidad_datos"]
    )

    _registrar_log(
        logs,
        (
            "🟢 Preparación completada: "
            f"{len(historia_preventiva):,} "
            "preventivos utilizables"
        ),
        log_callback,
    )

    # ========================================================
    # MOTOR DE DEMANDA
    # ========================================================

    _registrar_log(
        logs,
        (
            "🔄 Reconstruyendo historial "
            "preventivo..."
        ),
        log_callback,
    )

    historial = (
        construir_historial_analitico(
            historia_preventiva=
                historia_preventiva,
            retail=
                retail_preparado,
            clientes=
                clientes_preparado,
        )
    )

    base_demanda = (
        historial[
            "base_demanda"
        ]
    )

    auditoria_base_demanda = (
        historial[
            "auditoria_base_demanda"
        ]
    )

    _registrar_log(
        logs,
        (
            "🟢 BASE_DEMANDA construida: "
            f"{len(base_demanda):,} VIN"
        ),
        log_callback,
    )

    _registrar_log(
        logs,
        (
            "🟢 VIN duplicados: "
            f"{base_demanda['vin'].duplicated().sum():,}"
        ),
        log_callback,
    )

    # ========================================================
    # REPORTE EXCEL
    # ========================================================

    nombre_reporte = None
    ruta_sharepoint = None
    archivo_excel = None

    if generar_reporte:

        _registrar_log(
            logs,
            "🔄 Generando reporte Excel...",
            log_callback,
        )

        fecha_reporte = datetime.now()

        nombre_reporte = (
            generar_nombre_reporte(
                fecha_reporte
            )
        )

        archivo_excel = (
            generar_excel_demanda(
                base_demanda=
                    base_demanda,
                calidad_datos=
                    calidad_datos,
                auditoria_base_demanda=
                    auditoria_base_demanda,
                fecha_generacion=
                    fecha_reporte,
            )
        )

        ruta_sharepoint = (
            f"{OUTPUT_FOLDER}/"
            f"{nombre_reporte}"
        )

        _registrar_log(
            logs,
            (
                "🔄 Subiendo reporte "
                "a SharePoint..."
            ),
            log_callback,
        )

        sharepoint.upload_file_by_path(
            drive_id=drive_id,
            file_path=ruta_sharepoint,
            file_content=archivo_excel,
        )

        _registrar_log(
            logs,
            (
                f"🟢 Reporte generado: "
                f"{nombre_reporte}"
            ),
            log_callback,
        )

        _registrar_log(
            logs,
            (
                f"🟢 Guardado en: "
                f"{ruta_sharepoint}"
            ),
            log_callback,
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    _registrar_log(
        logs,
        "✅ Motor CGO ejecutado correctamente",
        log_callback,
    )

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

        # ----------------------------------------------------
        # Auditorías iniciales
        # ----------------------------------------------------
        "auditoria":
            auditoria,

        "auditoria_mantenimientos":
            auditoria_mantenimientos,

        "calidad_datos":
            calidad_datos,

        # ----------------------------------------------------
        # Motor analítico completo
        # ----------------------------------------------------
        "historial":
            historial,

        "base_demanda":
            base_demanda,

        "auditoria_base_demanda":
            auditoria_base_demanda,

        # ----------------------------------------------------
        # Reporte
        # ----------------------------------------------------
        "archivo_excel":
            archivo_excel,

        "nombre_reporte":
            nombre_reporte,

        "ruta_sharepoint":
            ruta_sharepoint,

        # ----------------------------------------------------
        # Log para interfaz
        # ----------------------------------------------------
        "logs":
            logs,
    }


# ============================================================
# DIAGNÓSTICO DE DESARROLLO
# ============================================================

def imprimir_diagnostico(
    resultado: dict,
) -> None:
    """
    Muestra en terminal las auditorías detalladas.

    Esta función queda separada del motor para que Streamlit
    no dependa de prints de desarrollo.
    """

    datos_historial = (
        resultado[
            "historial"
        ]
    )

    historia_preventiva = (
        resultado[
            "historia_preventiva"
        ]
    )

    auditoria = (
        resultado[
            "auditoria"
        ]
    )

    auditoria_mantenimientos = (
        resultado[
            "auditoria_mantenimientos"
        ]
    )

    base_demanda = (
        resultado[
            "base_demanda"
        ]
    )

    # ========================================================
    # AUDITORÍA INICIAL
    # ========================================================

    print()
    print("=" * 70)
    print("AUDITORÍA INICIAL")
    print("=" * 70)

    for indicador, valor in auditoria.items():

        print(
            f"{indicador:<42} : "
            f"{valor:,}"
        )

    # ========================================================
    # PARQUE
    # ========================================================

    print()
    print(
        "DISTRIBUCIÓN DEL PARQUE — PREVENTIVOS"
    )
    print("-" * 70)

    print(
        historia_preventiva[
            "parque"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    # ========================================================
    # MANTENIMIENTOS
    # ========================================================

    print()
    print(
        "MANTENIMIENTOS INTERPRETADOS"
    )
    print("-" * 70)

    print(
        historia_preventiva[
            "mantenimiento_km"
        ]
        .value_counts(
            dropna=False
        )
        .sort_index()
        .to_string()
    )

    print()
    print(
        "SERVICIO2 SIN KM INTERPRETABLE"
    )
    print("-" * 70)

    valores_sin_km = (
        auditoria_mantenimientos[
            "valores_sin_km"
        ]
    )

    if valores_sin_km.empty:

        print(
            "🟢 Todos los preventivos "
            "tienen KM interpretable."
        )

    else:

        print(
            valores_sin_km.to_string(
                index=False
            )
        )

    # ========================================================
    # VISITAS ANALÍTICAS
    # ========================================================

    print()
    print(
        "AUDITORÍA DE VISITAS ANALÍTICAS"
    )
    print("-" * 70)

    auditoria_visitas = (
        datos_historial[
            "auditoria_visitas"
        ]
    )

    for indicador, valor in (
        auditoria_visitas.items()
    ):

        print(
            f"{indicador:<42} : "
            f"{valor:,}"
        )

    # ========================================================
    # COBERTURA HISTÓRICA
    # ========================================================

    print()
    print(
        "COBERTURA REAL DE "
        "PROYECCIÓN HISTÓRICA"
    )
    print("-" * 70)

    print(
        datos_historial[
            "cobertura_proyeccion_historica"
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # POLÍTICA
    # ========================================================

    print()
    print(
        "AUDITORÍA DE FECHA POLÍTICA"
    )
    print("-" * 70)

    print(
        datos_historial[
            "auditoria_politica"
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # ESTADOS
    # ========================================================

    print()
    print(
        "AUDITORÍA DE ESTADOS TEMPORALES"
    )
    print("-" * 70)

    print(
        datos_historial[
            "auditoria_estados"
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # BASE DEMANDA
    # ========================================================

    print()
    print(
        "AUDITORÍA BASE_DEMANDA"
    )
    print("-" * 70)

    print(
        resultado[
            "auditoria_base_demanda"
        ]
        .to_string(
            index=False
        )
    )

    # ========================================================
    # MUESTRA
    # ========================================================

    print()
    print(
        "MUESTRA BASE_DEMANDA"
    )
    print("-" * 70)

    columnas_muestra = [
        "vin",
        "placa",
        "modelo",
        "parque",
        "nro_documento",
        "nombre",
        "telefono",
        "fuente_cliente",
        "tipo_historial",
        "fecha_ultima_visita",
        "kilometraje_atendido",
        "kilometraje_siguiente_ciclo",
        "kilometraje_esperado_actual",
        "fecha_historica",
        "fecha_politica",
        "estado_historico",
        "estado_politica",
    ]

    print(
        base_demanda[
            columnas_muestra
        ]
        .head(15)
        .to_string(
            index=False
        )
    )


# ============================================================
# EJECUCIÓN DESDE TERMINAL
# ============================================================

def main() -> None:
    """
    Entrada para ejecución manual:

        py main.py
    """

    print()
    print("=" * 70)
    print("CGO — DEMANDA PROYECTADA")
    print("=" * 70)

    resultado = ejecutar_motor(
        log_callback=print,
        generar_reporte=True,
    )

    imprimir_diagnostico(
        resultado
    )

    print()
    print("=" * 70)
    print(
        "✅ PROCESO COMPLETADO"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()