import pandas as pd

from m365.config import (
    SITE_NAME,
    DRIVE_NAME,
    INPUT_FOLDER,
    RETAIL_FILE,
    TALLER_FILE,
    CLIENTES_FILE,
)
from m365.config import OUTPUT_FOLDER
from m365.sharepoint import SharePoint
from m365.excel import read_excel
from motor.datos import preparar_datos
from motor.demanda import construir_historial_analitico

from datetime import datetime

from motor.exportacion import (
    generar_excel_demanda,
    generar_nombre_reporte,
)



def cargar_archivo_excel(
    sharepoint: SharePoint,
    drive_id: str,
    carpeta: str,
    nombre_archivo: str,
) -> pd.DataFrame:

    ruta = f"{carpeta}/{nombre_archivo}"

    archivo = sharepoint.download_file_by_path(
        drive_id=drive_id,
        file_path=ruta,
    )

    return read_excel(archivo)


def main():

    print("=" * 70)
    print("CGO — DEMANDA PROYECTADA")
    print("=" * 70)

    sharepoint = SharePoint()

    # ------------------------------------------------------
    # Site
    # ------------------------------------------------------

    site = sharepoint.get_site(SITE_NAME)

    if site is None:
        raise RuntimeError(
            f"No se encontró el site '{SITE_NAME}'."
        )

    print(f"🟢 Site: {site['displayName']}")

    # ------------------------------------------------------
    # Document Library
    # ------------------------------------------------------

    drive = sharepoint.get_drive(
        site_id=site["id"],
        drive_name=DRIVE_NAME,
    )

    if drive is None:
        raise RuntimeError(
            f"No se encontró el drive '{DRIVE_NAME}'."
        )

    drive_id = drive["id"]

    print(f"🟢 Drive: {drive['name']}")

    # ------------------------------------------------------
    # Fuentes
    # ------------------------------------------------------

    retail = cargar_archivo_excel(
        sharepoint,
        drive_id,
        INPUT_FOLDER,
        RETAIL_FILE,
    )

    taller = cargar_archivo_excel(
        sharepoint,
        drive_id,
        INPUT_FOLDER,
        TALLER_FILE,
    )

    clientes = cargar_archivo_excel(
        sharepoint,
        drive_id,
        INPUT_FOLDER,
        CLIENTES_FILE,
    )

    # ------------------------------------------------------
    # Resultado
    # ------------------------------------------------------

    print()
    print("FUENTES CARGADAS")
    print("-" * 70)

    print(
        f"🟢 retail.xlsx   : "
        f"{len(retail):,} filas × {len(retail.columns)} columnas"
    )

    print(
        f"🟢 taller.xlsx   : "
        f"{len(taller):,} filas × {len(taller.columns)} columnas"
    )

    print(
        f"🟢 clientes.xlsx : "
        f"{len(clientes):,} filas × {len(clientes.columns)} columnas"
    )

    print()
    print("COLUMNAS RETAIL")
    print(retail.columns.tolist())

    print()
    print("COLUMNAS TALLER")
    print(taller.columns.tolist())

    print()
    print("COLUMNAS CLIENTES")
    print(clientes.columns.tolist())

    print()
    print("=" * 70)
    print("🟢 CONEXIÓN Y LECTURA SHAREPOINT — OK")
    print("=" * 70)


    # ------------------------------------------------------
    # Preparación del motor
    # ------------------------------------------------------

    datos = preparar_datos(
        retail_raw=retail,
        taller_raw=taller,
        clientes_raw=clientes,
    )

    retail_preparado = datos["retail"]
    taller_preparado = datos["taller"]
    clientes_preparado = datos["clientes"]
    historia_preventiva = datos["historia_preventiva"]
    auditoria = datos["auditoria"]
    auditoria_mantenimientos = datos["auditoria_mantenimientos"]
    calidad_datos = datos["calidad_datos"]

    # ------------------------------------------------------
    # Auditoría
    # ------------------------------------------------------

    print()
    print("AUDITORÍA INICIAL")
    print("-" * 70)

    for indicador, valor in auditoria.items():
        print(
            f"{indicador:<42} : {valor:,}"
        )

    print()
    print("DISTRIBUCIÓN DEL PARQUE — PREVENTIVOS")
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

    print()
    print("MANTENIMIENTOS INTERPRETADOS")
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
    print("SERVICIO2 SIN KM INTERPRETABLE")
    print("-" * 70)

    valores_sin_km = auditoria_mantenimientos["valores_sin_km"]

    if valores_sin_km.empty:
        print(
            "🟢 Todos los preventivos tienen KM interpretable."
        )
    else:
        print(
            valores_sin_km.to_string(
                index=False
            )
        )


    print()
    print("KILOMETRAJES CON MUY POCOS REGISTROS")
    print("-" * 70)

    kilometrajes_raros = auditoria_mantenimientos[
        "kilometrajes_raros"
    ]

    if kilometrajes_raros.empty:
        print(
            "🟢 No se detectaron niveles poco frecuentes."
        )
    else:
        print(
            kilometrajes_raros.to_string(
                index=False
            )
        )

    print()
    print("=" * 70)
    print("🟢 PASO 02 — PREPARACIÓN DE DATOS COMPLETADA")
    print("=" * 70)


    # ------------------------------------------------------
    # Historial preventivo analítico
    # ------------------------------------------------------

    historial = construir_historial_analitico(
        historia_preventiva=historia_preventiva,
        retail=retail_preparado,
        clientes=clientes_preparado,
    )

    visitas_analiticas = historial[
        "visitas_analiticas"
    ]

    secuencia_preventiva = historial[
        "secuencia_preventiva"
    ]

    trayectorias = historial[
        "trayectorias"
    ]

    auditoria_visitas = historial[
        "auditoria_visitas"
    ]

    intervalos_historicos = historial[
    "intervalos_historicos"
    ]

    resumen_intervalos = historial[
        "resumen_intervalos"
    ]   

    referencias_historicas = historial[
        "referencias_historicas"
    ]

    auditoria_referencias = historial[
        "auditoria_referencias"
    ]

    proyeccion_historica = historial[
    "proyeccion_historica"
    ]

    cobertura_proyeccion_historica = historial[
        "cobertura_proyeccion_historica"
    ]

    pana_sin_historial = historial[
        "pana_sin_historial"
    ]

    proyeccion_pana_sin_historial = historial[
        "proyeccion_pana_sin_historial"
    ]

    intervalos_entrega_1k = historial[
        "intervalos_entrega_1k"
    ]

    proyeccion_con_politica = historial[
        "proyeccion_con_politica"
    ]

    proyeccion_pana_sin_historial = historial[
        "proyeccion_pana_sin_historial"
    ]

    auditoria_politica = historial[
        "auditoria_politica"
    ]


    proyeccion_con_estados = historial[
        "proyeccion_con_estados"
    ]

    proyeccion_pana_sin_historial = historial[
        "proyeccion_pana_sin_historial"
    ]

    auditoria_estados = historial[
        "auditoria_estados"
    ]


    base_demanda = historial[
        "base_demanda"
    ]

    auditoria_base_demanda = historial[
        "auditoria_base_demanda"
    ]




    # ------------------------------------------------------
    # GENERACIÓN DEL REPORTE EXCEL
    # ------------------------------------------------------

    print()
    print("=" * 70)
    print("GENERACIÓN DE REPORTE")
    print("=" * 70)

    fecha_generacion = datetime.now()

    nombre_reporte = (
        generar_nombre_reporte(
            fecha_generacion
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
                fecha_generacion,
        )
    )

    ruta_sharepoint = (
        f"{OUTPUT_FOLDER}/"
        f"{nombre_reporte}"
    )

    sharepoint.upload_file_by_path(
        drive_id=drive_id,
        file_path=ruta_sharepoint,
        file_content=archivo_excel,
    )

    print(
        f"🟢 Reporte generado : "
        f"{nombre_reporte}"
    )

    print(
        f"🟢 SharePoint       : "
        f"{ruta_sharepoint}"
    )

    print(
        f"🟢 Registros        : "
        f"{len(base_demanda):,}"
    )

    print()
    print("=" * 70)
    print("🟢 MOTOR CGO EJECUTADO CORRECTAMENTE")
    print("=" * 70)






    print()
    print("AUDITORÍA DE VISITAS ANALÍTICAS")
    print("-" * 70)

    for indicador, valor in auditoria_visitas.items():
        print(
            f"{indicador:<42} : {valor:,}"
        )


    print()
    print("COMPORTAMIENTO DE LAS VISITAS")
    print("-" * 70)

    print(
        secuencia_preventiva[
            "comportamiento"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


    print()
    print("EJEMPLOS DE TRAYECTORIAS")
    print("-" * 70)

    columnas_trayectoria = [
        "vin",
        "parque",
        "visitas_preventivas",
        "trayectoria_observada",
        "trayectoria_esperada",
        "trayectoria_completa",
        "cantidad_saltos",
        "cantidad_retrocesos",
        "cantidad_repeticiones",
    ]

    print(
        trayectorias[
            columnas_trayectoria
        ]
        .head(10)
        .to_string(
            index=False
        )
    )


    print()
    print("=" * 70)
    print("🟢 PASO 03 — HISTORIAL ANALÍTICO COMPLETADO")
    print("=" * 70)


    print()
    print("INTERVALOS HISTÓRICOS")
    print("-" * 70)

    total_intervalos = len(
        intervalos_historicos
    )

    intervalos_validos = int(
        intervalos_historicos[
            "intervalo_valido_referencia"
        ].sum()
    )

    intervalos_no_validos = (
        total_intervalos
        -
        intervalos_validos
    )

    print(
        f"Transiciones observadas        : "
        f"{total_intervalos:,}"
    )

    print(
        f"Intervalos válidos referencia  : "
        f"{intervalos_validos:,}"
    )

    print(
        f"Intervalos no usados referencia: "
        f"{intervalos_no_validos:,}"
    )


    print()
    print("REFERENCIAS POR TRANSICIÓN")
    print("-" * 70)

    print(
        resumen_intervalos[
            [
                "parque",
                "transicion",
                "observaciones",
                "vin_unicos",
                "dias_mediana",
                "dias_promedio",
                "dias_minimo",
                "dias_maximo",
            ]
        ]
        .to_string(
            index=False
        )
    )


    print()
    print("COBERTURA DE REFERENCIAS HISTÓRICAS")
    print("-" * 70)

    print(
        auditoria_referencias.to_string(
            index=False
        )
    )


    print()
    print("COBERTURA REAL DE PROYECCIÓN HISTÓRICA")
    print("-" * 70)

    print(
        cobertura_proyeccion_historica.to_string(
            index=False
        )
    )


    print()
    print("EJEMPLOS DE PROYECCIÓN HISTÓRICA")
    print("-" * 70)

    columnas = [
        "vin",
        "parque",
        "modelo",
        "sede",
        "kilometraje_atendido",
        "kilometraje_esperado",
        "fecha_ultima_visita",
        "dias_historicos_estimados",
        "fecha_historica",
        "metodo_historico",
        "n_referencias_historicas",
    ]

    print(
        proyeccion_historica[
            columnas
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    print()
    print("PANA SIN HISTORIAL PREVENTIVO")
    print("-" * 70)

    print(
        f"VIN PANA sin preventivo      : "
        f"{len(pana_sin_historial):,}"
    )

    print(
        f"Referencias ENTREGA → 1K     : "
        f"{len(intervalos_entrega_1k):,}"
    )

    con_fecha = int(
        proyeccion_pana_sin_historial[
            "fecha_historica"
        ]
        .notna()
        .sum()
    )

    sin_fecha = (
        len(
            proyeccion_pana_sin_historial
        )
        -
        con_fecha
    )

    print(
        f"Con fecha histórica          : "
        f"{con_fecha:,}"
    )

    print(
        f"Sin fecha histórica          : "
        f"{sin_fecha:,}"
    )


    print()
    print("MÉTODOS PANA SIN HISTORIAL")
    print("-" * 70)

    print(
        proyeccion_pana_sin_historial[
            "metodo_historico"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


    print()
    print("EJEMPLOS PANA SIN HISTORIAL")
    print("-" * 70)

    columnas = [
    "vin",
    "modelo",
    "año",
    "sede",
    "fecha_entrega",
    "kilometraje_siguiente_ciclo",
    "kilometraje_esperado_actual",
    "dias_historicos_estimados",
    "fecha_historica",
    "metodo_historico",
    "n_referencias_historicas",
    ]

    print(
        proyeccion_pana_sin_historial[
            columnas
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    print()
    print("AUDITORÍA DE FECHA POLÍTICA")
    print("-" * 70)

    print(
        auditoria_politica.to_string(
            index=False
        )
    )

    print()
    print("EJEMPLOS — HISTÓRICA VS POLÍTICA")
    print("-" * 70)

    columnas = [
        "vin",
        "parque",
        "kilometraje_atendido",
        "kilometraje_esperado",
        "fecha_ultima_visita",
        "fecha_historica",
        "fecha_politica",
        "regla_politica",
    ]

    print(
        proyeccion_con_politica[
            columnas
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    print()
    print("AUDITORÍA DE ESTADOS TEMPORALES")
    print("-" * 70)

    print(
        auditoria_estados.to_string(
            index=False
        )
    )

    print()
    print("EJEMPLOS DE ESTADOS")
    print("-" * 70)

    columnas = [
        "vin",
        "parque",
        "fecha_ultima_visita",
        "fecha_historica",
        "fecha_politica",
        "fecha_mas_inmediata",
        "dias_hasta_historico",
        "estado_historico",
        "dias_hasta_politica",
        "estado_politica",
        "dias_hasta_mas_inmediata",
        "estado_mas_inmediata",
    ]

    print(
        proyeccion_con_estados[
            columnas
        ]
        .tail(20)
        .to_string(
            index=False
        )
    )

    print()
    print("AUDITORÍA BASE_DEMANDA")
    print("-" * 70)

    print(
        auditoria_base_demanda.to_string(
            index=False
        )
    )

    print()
    print("DISTRIBUCIÓN FUENTE CLIENTE")
    print("-" * 70)

    print(
        base_demanda[
            "fuente_cliente"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


    print()
    print("MUESTRA BASE_DEMANDA")
    print("-" * 70)

    columnas = [
        "vin",
        "placa",
        "modelo",
        "parque",
        "nro_documento",
        "nombre",
        "telefono",
        "correo",
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
            columnas
        ]
        .head(15)
        .to_string(
            index=False
        )
    )


    print()
    print("VALIDACIÓN KILOMETRAJE ESPERADO ACTUAL")
    print("-" * 70)

    placas_validacion = [
        "D8Q304",
        "AHQ122",
    ]

    columnas_validacion = [
        "vin",
        "placa",
        "fecha_ultima_visita",
        "kilometraje_atendido",
        "kilometraje_siguiente_ciclo",
        "kilometraje_esperado_actual",
        "fecha_politica",
        "fecha_generacion",
    ]

    print(
        base_demanda.loc[
            base_demanda[
                "placa"
            ].isin(
                placas_validacion
            ),
            columnas_validacion,
        ]
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()