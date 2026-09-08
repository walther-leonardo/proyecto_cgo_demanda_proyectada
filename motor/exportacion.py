from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


# ============================================================
# CONFIGURACIÓN DEL REPORTE
# ============================================================

NOMBRE_HOJA_BASE = "BASE_DEMANDA"
NOMBRE_HOJA_CALIDAD = "CALIDAD_DATOS"
NOMBRE_HOJA_METADATA = "METADATA"
NOMBRE_HOJA_DEFINICIONES = "DEFINICIONES"

# ============================================================
# METADATA
# ============================================================

def construir_metadata_reporte(
    base_demanda: pd.DataFrame,
    auditoria_base_demanda: pd.DataFrame,
    fecha_generacion: datetime | None = None,
) -> pd.DataFrame:
    """
    Construye información técnica y de negocio que permite
    identificar cómo fue generado el reporte.
    """

    if fecha_generacion is None:
        fecha_generacion = datetime.now()

    total_vin = len(
        base_demanda
    )

    pana = int(
        base_demanda[
            "parque"
        ]
        .eq("PANA")
        .sum()
    )

    nopana = int(
        base_demanda[
            "parque"
        ]
        .eq("NOPANA")
        .sum()
    )

    con_historial = int(
        base_demanda[
            "tipo_historial"
        ]
        .eq(
            "CON_HISTORIAL_PREVENTIVO"
        )
        .sum()
    )

    sin_historial = int(
        base_demanda[
            "tipo_historial"
        ]
        .eq(
            "SIN_HISTORIAL_PREVENTIVO"
        )
        .sum()
    )

    sin_fecha_historica = int(
        base_demanda[
            "fecha_historica"
        ]
        .isna()
        .sum()
    )

    sin_fecha_politica = int(
        base_demanda[
            "fecha_politica"
        ]
        .isna()
        .sum()
    )

    filas = [
        {
            "categoria": "GENERACION",
            "parametro": "fecha_generacion",
            "valor": fecha_generacion.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        },
        {
            "categoria": "FUENTE",
            "parametro": "retail",
            "valor": "retail.xlsx",
        },
        {
            "categoria": "FUENTE",
            "parametro": "taller",
            "valor": "taller.xlsx",
        },
        {
            "categoria": "FUENTE",
            "parametro": "clientes",
            "valor": "clientes.xlsx",
        },
        {
            "categoria": "UNIVERSO",
            "parametro": "total_vin",
            "valor": total_vin,
        },
        {
            "categoria": "UNIVERSO",
            "parametro": "pana",
            "valor": pana,
        },
        {
            "categoria": "UNIVERSO",
            "parametro": "nopana",
            "valor": nopana,
        },
        {
            "categoria": "UNIVERSO",
            "parametro": "con_historial_preventivo",
            "valor": con_historial,
        },
        {
            "categoria": "UNIVERSO",
            "parametro": "sin_historial_preventivo",
            "valor": sin_historial,
        },
        {
            "categoria": "COBERTURA",
            "parametro": "sin_fecha_historica",
            "valor": sin_fecha_historica,
        },
        {
            "categoria": "COBERTURA",
            "parametro": "sin_fecha_politica",
            "valor": sin_fecha_politica,
        },
        {
            "categoria": "REGLA",
            "parametro": "ventana_visita_analitica",
            "valor": "7 días",
        },
        {
            "categoria": "REGLA",
            "parametro": "min_intervalos_vin",
            "valor": 3,
        },
        {
            "categoria": "REGLA",
            "parametro": "min_referencias_segmento",
            "valor": 20,
        },
        {
            "categoria": "REGLA",
            "parametro": "politica_1k",
            "valor": (
                "PANA sin preventivo: "
                "1 mes desde entrega"
            ),
        },
        {
            "categoria": "REGLA",
            "parametro": "politica_5k_pana",
            "valor": (
                "PANA con último 1K: "
                "5K a 6 meses desde entrega"
            ),
        },
        {
            "categoria": "REGLA",
            "parametro": "politica_ciclo",
            "valor": (
                "Desde 5K: 6 meses desde "
                "último preventivo"
            ),
        },
        {
            "categoria": "ALCANCE",
            "parametro": "nopana_sin_preventivo",
            "valor": (
                "Excluido por no contar con "
                "ancla preventiva"
            ),
        },
    ]

    metadata = pd.DataFrame(
        filas
    )

    # --------------------------------------------------------
    # Agregar auditoría final como metadata
    # --------------------------------------------------------

    if not auditoria_base_demanda.empty:

        auditoria = (
            auditoria_base_demanda[
                [
                    "indicador",
                    "casos",
                ]
            ]
            .copy()
        )

        auditoria[
            "categoria"
        ] = "AUDITORIA_BASE"

        auditoria = auditoria.rename(
            columns={
                "indicador":
                    "parametro",

                "casos":
                    "valor",
            }
        )

        auditoria = auditoria[
            [
                "categoria",
                "parametro",
                "valor",
            ]
        ]

        metadata = pd.concat(
            [
                metadata,
                auditoria,
            ],
            ignore_index=True,
        )

    return metadata


# ============================================================
# DEFINICIONES FUNCIONALES
# ============================================================

def construir_definiciones_reporte() -> pd.DataFrame:
    """
    Documenta las reglas funcionales, premisas y criterios
    utilizados por el Motor CGO de Demanda Proyectada.

    Esta hoja está orientada a usuarios nuevos y sirve como
    referencia funcional del reporte.
    """

    definiciones = [
        # ====================================================
        # PROPÓSITO
        # ====================================================
        {
            "categoria": "PROPÓSITO",
            "concepto": "BASE_DEMANDA",
            "definicion": (
                "Base operacional de demanda proyectada de "
                "mantenimientos preventivos."
            ),
            "implicancia": (
                "Cada fila representa un VIN único y reúne "
                "vehículo, cliente actual, historial, "
                "proyección histórica y política."
            ),
        },
        {
            "categoria": "PROPÓSITO",
            "concepto": "Unidad de análisis",
            "definicion": (
                "La unidad principal de análisis es el VIN."
            ),
            "implicancia": (
                "BASE_DEMANDA debe contener una sola fila "
                "por VIN."
            ),
        },

        # ====================================================
        # UNIVERSO
        # ====================================================
        {
            "categoria": "UNIVERSO",
            "concepto": "PANA",
            "definicion": (
                "Vehículo cuyo VIN aparece en la base Retail "
                "de PanaAutos."
            ),
            "implicancia": (
                "La fecha de entrega puede utilizarse como "
                "ancla cuando corresponda."
            ),
        },
        {
            "categoria": "UNIVERSO",
            "concepto": "NOPANA",
            "definicion": (
                "Vehículo observado en Taller cuyo VIN no "
                "aparece en la base Retail."
            ),
            "implicancia": (
                "No se conoce una fecha de entrega confiable "
                "dentro de las fuentes utilizadas."
            ),
        },
        {
            "categoria": "UNIVERSO",
            "concepto": "PANA con historial preventivo",
            "definicion": (
                "VIN PANA con al menos una visita preventiva "
                "analítica registrada."
            ),
            "implicancia": (
                "Forma parte de BASE_DEMANDA."
            ),
        },
        {
            "categoria": "UNIVERSO",
            "concepto": "PANA sin historial preventivo",
            "definicion": (
                "VIN presente en Retail pero sin visita "
                "preventiva analítica registrada."
            ),
            "implicancia": (
                "Forma parte de BASE_DEMANDA y su primera "
                "proyección corresponde al mantenimiento 1K."
            ),
        },
        {
            "categoria": "UNIVERSO",
            "concepto": "NOPANA sin historial preventivo",
            "definicion": (
                "Vehículo NOPANA sin una visita preventiva "
                "que permita establecer un punto de partida."
            ),
            "implicancia": (
                "No se incorpora a la demanda proyectada "
                "por no contar con ancla preventiva válida."
            ),
        },

        # ====================================================
        # MANTENIMIENTOS
        # ====================================================
        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "Secuencia preventiva esperada",
            "definicion": (
                "ENTREGA → 1K → 5K → 10K → 15K → 20K → "
                "25K, continuando cada 5K."
            ),
            "implicancia": (
                "Se utiliza para determinar el próximo nivel "
                "preventivo esperado."
            ),
        },
        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "Kilometraje de mantenimiento",
            "definicion": (
                "El nivel 1K, 5K, 10K, etc. se interpreta "
                "desde servicio2."
            ),
            "implicancia": (
                "No representa una lectura real del "
                "odómetro del vehículo."
            ),
        },
        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "Preventivo sin KM interpretable",
            "definicion": (
                "Registro preventivo donde servicio2 no "
                "permite identificar el nivel de "
                "mantenimiento."
            ),
            "implicancia": (
                "Permanece en auditoría, pero no participa "
                "en secuencias ni referencias históricas."
            ),
        },

        # ====================================================
        # VISITA ANALÍTICA
        # ====================================================
        {
            "categoria": "VISITA_ANALITICA",
            "concepto": "Ventana de consolidación",
            "definicion": (
                "Registros preventivos del mismo VIN dentro "
                "de una ventana máxima de 7 días desde el "
                "inicio de la visita se consideran una sola "
                "visita analítica."
            ),
            "implicancia": (
                "Evita tratar órdenes cercanas del mismo "
                "evento como mantenimientos independientes."
            ),
        },
        {
            "categoria": "VISITA_ANALITICA",
            "concepto": "Ventana no encadenada",
            "definicion": (
                "Los 7 días se calculan desde la primera "
                "fecha de la visita, no desde el registro "
                "inmediatamente anterior."
            ),
            "implicancia": (
                "Evita que una cadena de órdenes cercanas "
                "extienda artificialmente una visita durante "
                "más de 7 días."
            ),
        },
        {
            "categoria": "VISITA_ANALITICA",
            "concepto": "Fecha de visita",
            "definicion": (
                "La fecha analítica corresponde a la primera "
                "fecha de orden de la visita consolidada."
            ),
            "implicancia": (
                "Se utiliza para calcular intervalos entre "
                "visitas."
            ),
        },
        {
            "categoria": "VISITA_ANALITICA",
            "concepto": "Registro representativo",
            "definicion": (
                "Cuando existen varias órdenes dentro de una "
                "visita, la última orden es utilizada como "
                "registro representativo."
            ),
            "implicancia": (
                "De esa orden se toman cliente, placa, "
                "modelo, sede, asesor y mantenimiento KM."
            ),
        },
        {
            "categoria": "VISITA_ANALITICA",
            "concepto": "Visita con múltiples KM",
            "definicion": (
                "Visita analítica donde aparecen dos o más "
                "niveles de mantenimiento distintos."
            ),
            "implicancia": (
                "Se conserva en la historia y se identifica "
                "con un flag, pero no alimenta las medianas "
                "históricas de transición."
            ),
        },

        # ====================================================
        # COMPORTAMIENTO
        # ====================================================
        {
            "categoria": "COMPORTAMIENTO",
            "concepto": "PRIMERA_VISITA",
            "definicion": (
                "Primera visita preventiva observada para "
                "un VIN."
            ),
            "implicancia": (
                "No existe una transición preventiva previa "
                "contra la cual comparar."
            ),
        },
        {
            "categoria": "COMPORTAMIENTO",
            "concepto": "SIGUE_CICLO",
            "definicion": (
                "El mantenimiento actual corresponde "
                "exactamente al siguiente mantenimiento "
                "esperado."
            ),
            "implicancia": (
                "La transición puede utilizarse como "
                "referencia histórica si cumple los demás "
                "controles de calidad."
            ),
        },
        {
            "categoria": "COMPORTAMIENTO",
            "concepto": "SALTA_MANTENIMIENTOS",
            "definicion": (
                "El mantenimiento observado supera el "
                "siguiente nivel preventivo esperado."
            ),
            "implicancia": (
                "Permanece en la trayectoria del VIN, pero "
                "no se utiliza como transición normal para "
                "calcular medianas."
            ),
        },
        {
            "categoria": "COMPORTAMIENTO",
            "concepto": "REPITE_MANTENIMIENTO",
            "definicion": (
                "El mantenimiento observado es igual al "
                "mantenimiento preventivo anterior."
            ),
            "implicancia": (
                "Se considera una inconsistencia de "
                "secuencia para el cálculo del ciclo normal."
            ),
        },
        {
            "categoria": "COMPORTAMIENTO",
            "concepto": "RETROCESO",
            "definicion": (
                "El mantenimiento observado tiene un nivel "
                "inferior al mantenimiento anterior."
            ),
            "implicancia": (
                "Se conserva para trazabilidad, pero no se "
                "utiliza como intervalo normal."
            ),
        },

        # ====================================================
        # CLIENTE
        # ====================================================
        {
            "categoria": "CLIENTE",
            "concepto": "Clave de cliente",
            "definicion": (
                "El cliente se identifica mediante "
                "nro_documento."
            ),
            "implicancia": (
                "Nombre, teléfono y correo se enriquecen "
                "desde clientes.xlsx."
            ),
        },
        {
            "categoria": "CLIENTE",
            "concepto": "Cliente actual — con historial",
            "definicion": (
                "Para un VIN con historial preventivo, el "
                "cliente actual es el nro_documento de su "
                "última visita preventiva."
            ),
            "implicancia": (
                "La propiedad registrada originalmente en "
                "Retail no reemplaza al cliente observado "
                "más recientemente en preventivo."
            ),
        },
        {
            "categoria": "CLIENTE",
            "concepto": "Cliente actual — sin historial",
            "definicion": (
                "Para un PANA sin historial preventivo, se "
                "utiliza el nro_documento registrado en "
                "Retail."
            ),
            "implicancia": (
                "fuente_cliente se identifica como RETAIL."
            ),
        },
        {
            "categoria": "CLIENTE",
            "concepto": "Datos de contacto",
            "definicion": (
                "Nombre, teléfono y correo corresponden a "
                "los valores vigentes disponibles en "
                "clientes.xlsx."
            ),
            "implicancia": (
                "El motor no mantiene historia temporal de "
                "teléfono o correo."
            ),
        },

        # ====================================================
        # PROYECCIÓN HISTÓRICA
        # ====================================================
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "Estadístico utilizado",
            "definicion": (
                "La duración histórica de los ciclos se "
                "estima utilizando la mediana de días."
            ),
            "implicancia": (
                "Reduce el efecto de retornos atípicamente "
                "tardíos frente al uso de un promedio."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "VIN_PROPIO",
            "definicion": (
                "Primera prioridad de referencia histórica. "
                "Utiliza la mediana de intervalos normales "
                "del mismo VIN."
            ),
            "implicancia": (
                "Requiere al menos 3 intervalos normales "
                "válidos."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "PARQUE_MODELO_TRANSICION_SEDE",
            "definicion": (
                "Segunda prioridad de referencia: parque + "
                "modelo + transición KM + sede."
            ),
            "implicancia": (
                "Requiere al menos 20 observaciones."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "PARQUE_MODELO_TRANSICION",
            "definicion": (
                "Tercera prioridad: parque + modelo + "
                "transición KM."
            ),
            "implicancia": (
                "Se utiliza si el nivel anterior no tiene "
                "muestra suficiente. Requiere mínimo 20."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "PARQUE_TRANSICION",
            "definicion": (
                "Cuarta prioridad: parque + transición KM."
            ),
            "implicancia": (
                "Requiere al menos 20 observaciones."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "TRANSICION_GENERAL",
            "definicion": (
                "Última referencia histórica utilizable: "
                "transición KM sin segmentar por parque, "
                "modelo o sede."
            ),
            "implicancia": (
                "Requiere al menos 20 observaciones."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "SIN_REFERENCIA_HISTORICA",
            "definicion": (
                "No existe una referencia histórica con "
                "muestra suficiente para el VIN."
            ),
            "implicancia": (
                "fecha_historica queda vacía, pero "
                "fecha_politica puede seguir disponible."
            ),
        },
        {
            "categoria": "PROYECCION_HISTORICA",
            "concepto": "PANA sin historial — ENTREGA → 1K",
            "definicion": (
                "La primera fecha histórica se estima con "
                "el comportamiento real de PANA cuya primera "
                "visita preventiva observada fue 1K."
            ),
            "implicancia": (
                "La jerarquía utilizada es Modelo + Sede, "
                "luego Modelo y finalmente PANA general."
            ),
        },

        # ====================================================
        # POLÍTICA
        # ====================================================
        {
            "categoria": "POLITICA",
            "concepto": "Regla general",
            "definicion": (
                "El mantenimiento preventivo se considera "
                "por kilometraje o por tiempo, lo que ocurra "
                "primero. En este motor no existe odómetro "
                "real, por lo que se modela la dimensión "
                "temporal."
            ),
            "implicancia": (
                "La fecha política representa el criterio "
                "temporal definido para el mantenimiento."
            ),
        },
        {
            "categoria": "POLITICA",
            "concepto": "PANA sin preventivo — 1K",
            "definicion": (
                "El primer mantenimiento 1K tiene fecha "
                "política de 1 mes calendario después de la "
                "entrega."
            ),
            "implicancia": (
                "fecha_politica = fecha_entrega + 1 mes."
            ),
        },
        {
            "categoria": "POLITICA",
            "concepto": "PANA último mantenimiento 1K",
            "definicion": (
                "El 1K no reinicia el reloj hacia el 5K."
            ),
            "implicancia": (
                "La fecha política del 5K corresponde a "
                "6 meses calendario desde la fecha de "
                "entrega."
            ),
        },
        {
            "categoria": "POLITICA",
            "concepto": "PANA desde 5K",
            "definicion": (
                "Cada preventivo válido desde 5K reinicia "
                "el ciclo temporal."
            ),
            "implicancia": (
                "La próxima fecha política es 6 meses "
                "calendario después de la última visita."
            ),
        },
        {
            "categoria": "POLITICA",
            "concepto": "NOPANA",
            "definicion": (
                "Al desconocerse la fecha de entrega, la "
                "política se calcula desde el último "
                "preventivo observado."
            ),
            "implicancia": (
                "fecha_politica = fecha_ultima_visita "
                "+ 6 meses calendario."
            ),
        },

        # ====================================================
        # PERSPECTIVAS DE FECHA
        # ====================================================
        {
            "categoria": "PERSPECTIVAS",
            "concepto": "fecha_historica",
            "definicion": (
                "Fecha calculada según el comportamiento "
                "real histórico observado."
            ),
            "implicancia": (
                "Puede ser anterior o posterior a la fecha "
                "definida por política."
            ),
        },
        {
            "categoria": "PERSPECTIVAS",
            "concepto": "fecha_politica",
            "definicion": (
                "Fecha calculada según las reglas temporales "
                "de mantenimiento."
            ),
            "implicancia": (
                "Se conserva independientemente de la "
                "proyección histórica."
            ),
        },
        {
            "categoria": "PERSPECTIVAS",
            "concepto": "fecha_mas_inmediata",
            "definicion": (
                "La fecha más temprana entre fecha_historica "
                "y fecha_politica."
            ),
            "implicancia": (
                "Permite una visión comercial más "
                "conservadora de la demanda."
            ),
        },

        # ====================================================
        # ESTADOS
        # ====================================================
        {
            "categoria": "ESTADOS",
            "concepto": "VENCIDO_LEJANO",
            "definicion": (
                "La fecha objetivo venció hace 180 días "
                "o más."
            ),
            "implicancia": (
                "Demanda vencida de larga antigüedad."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "VENCIDO_CERCANO",
            "definicion": (
                "La fecha objetivo venció entre 31 y "
                "179 días atrás."
            ),
            "implicancia": (
                "Demanda vencida todavía relativamente "
                "cercana al ciclo esperado."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "VENCIDO_RECIENTE",
            "definicion": (
                "La fecha objetivo venció entre 8 y "
                "30 días atrás."
            ),
            "implicancia": (
                "Demanda vencida recientemente."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "EN_FECHA",
            "definicion": (
                "La fecha objetivo se encuentra entre "
                "7 días antes y 7 días después de la fecha "
                "de generación."
            ),
            "implicancia": (
                "Vehículo dentro de la ventana inmediata "
                "del mantenimiento."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "FUTURO_RECIENTE",
            "definicion": (
                "La fecha objetivo se encuentra entre "
                "8 y 30 días en el futuro."
            ),
            "implicancia": (
                "Demanda próxima de corto plazo."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "FUTURO_PROXIMO",
            "definicion": (
                "La fecha objetivo se encuentra entre "
                "31 y 150 días en el futuro."
            ),
            "implicancia": (
                "Demanda futura dentro del horizonte "
                "operacional."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "FUTURO_LEJANO",
            "definicion": (
                "La fecha objetivo se encuentra a más de "
                "150 días en el futuro."
            ),
            "implicancia": (
                "Demanda existente pero fuera del horizonte "
                "próximo."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "SERVICIO_MUY_RECIENTE",
            "definicion": (
                "El último preventivo ocurrió entre 0 y "
                "30 días antes de la generación y la próxima "
                "fecha objetivo aún está fuera de la ventana "
                "EN_FECHA."
            ),
            "implicancia": (
                "Tiene precedencia sobre estados futuros "
                "para evitar tratar inmediatamente al cliente "
                "como nueva oportunidad."
            ),
        },
        {
            "categoria": "ESTADOS",
            "concepto": "SIN_FECHA_ESTIMABLE",
            "definicion": (
                "No se dispone de una fecha válida para la "
                "perspectiva evaluada."
            ),
            "implicancia": (
                "El VIN puede seguir teniendo otra "
                "perspectiva disponible, por ejemplo "
                "fecha_politica."
            ),
        },

        # ====================================================
        # TRAYECTORIAS
        # ====================================================
        {
            "categoria": "TRAYECTORIAS",
            "concepto": "trayectoria_observada",
            "definicion": (
                "Secuencia de mantenimientos preventivos "
                "efectivamente observados para el VIN."
            ),
            "implicancia": (
                "Ejemplo: 1K → 5K → 15K → 20K."
            ),
        },
        {
            "categoria": "TRAYECTORIAS",
            "concepto": "trayectoria_esperada",
            "definicion": (
                "Secuencia preventiva teórica que debería "
                "seguir el vehículo."
            ),
            "implicancia": (
                "Permite contrastar comportamiento real "
                "contra el ciclo esperado."
            ),
        },
        {
            "categoria": "TRAYECTORIAS",
            "concepto": "trayectoria_completa",
            "definicion": (
                "Secuencia observada incorporando los días "
                "transcurridos entre visitas."
            ),
            "implicancia": (
                "Las transiciones inconsistentes se marcan "
                "con (e); los saltos mantienen sus días "
                "reales."
            ),
        },

        # ====================================================
        # CALIDAD Y TRAZABILIDAD
        # ====================================================
        {
            "categoria": "CALIDAD_DATOS",
            "concepto": "Principio de auditoría",
            "definicion": (
                "Las inconsistencias detectadas se reportan "
                "en lugar de ser corregidas o eliminadas "
                "silenciosamente."
            ),
            "implicancia": (
                "El archivo mantiene trazabilidad sobre la "
                "calidad de las fuentes."
            ),
        },
        {
            "categoria": "CALIDAD_DATOS",
            "concepto": "CALIDAD_DATOS",
            "definicion": (
                "Hoja con controles descriptivos aplicados "
                "sobre Retail, Taller y Clientes."
            ),
            "implicancia": (
                "Permite identificar problemas de fuente "
                "sin alterar automáticamente los registros."
            ),
        },
        {
            "categoria": "CALIDAD_DATOS",
            "concepto": "METADATA",
            "definicion": (
                "Hoja que documenta parámetros, fuentes y "
                "resultados de la ejecución específica."
            ),
            "implicancia": (
                "Permite reproducir y auditar el contexto "
                "del archivo generado."
            ),
        },


        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "kilometraje_atendido",
            "definicion": (
                "Último nivel de mantenimiento preventivo "
                "efectivamente observado para el VIN."
            ),
            "implicancia": (
                "Representa historia real, no una estimación."
            ),
        },
        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "kilometraje_siguiente_ciclo",
            "definicion": (
                "Mantenimiento inmediatamente posterior al último "
                "nivel observado según la secuencia preventiva."
            ),
            "implicancia": (
                "Se utiliza como transición técnica para construir "
                "la siguiente proyección histórica."
            ),
        },
        {
            "categoria": "MANTENIMIENTOS",
            "concepto": "kilometraje_esperado_actual",
            "definicion": (
                "Nivel de mantenimiento aproximado que correspondería "
                "al vehículo a la fecha de generación considerando "
                "los ciclos temporales transcurridos."
            ),
            "implicancia": (
                "Es el kilometraje de referencia más útil "
                "comercialmente para vehículos con largos periodos "
                "sin retornar."
            ),
        },
    ]

    return pd.DataFrame(
        definiciones
    )


# ============================================================
# FORMATO EXCEL
# ============================================================

def _formatear_hoja(
    worksheet,
) -> None:
    """
    Aplica formato ligero y legible a una hoja Excel.

    Se evita sobrecargar el archivo con estilos complejos.
    """

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = (
        worksheet.dimensions
    )

    # --------------------------------------------------------
    # Encabezados
    # --------------------------------------------------------

    for celda in worksheet[1]:

        celda.font = Font(
            bold=True
        )

        celda.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    # --------------------------------------------------------
    # Ancho de columnas
    # --------------------------------------------------------

    for indice, columna in enumerate(
        worksheet.columns,
        start=1,
    ):

        max_longitud = 0

        for celda in columna[:200]:

            if celda.value is None:
                continue

            longitud = len(
                str(
                    celda.value
                )
            )

            max_longitud = max(
                max_longitud,
                longitud,
            )

        ancho = min(
            max(
                max_longitud + 2,
                10,
            ),
            35,
        )

        worksheet.column_dimensions[
            get_column_letter(
                indice
            )
        ].width = ancho


def _formatear_fechas(
    worksheet,
    dataframe: pd.DataFrame,
) -> None:
    """
    Aplica formato de fecha a columnas datetime.
    """

    for indice, columna in enumerate(
        dataframe.columns,
        start=1,
    ):

        if not pd.api.types.is_datetime64_any_dtype(
            dataframe[
                columna
            ]
        ):
            continue

        for fila in range(
            2,
            worksheet.max_row + 1,
        ):

            worksheet.cell(
                row=fila,
                column=indice,
            ).number_format = "dd/mm/yyyy"


# ============================================================
# GENERACIÓN DEL ARCHIVO
# ============================================================

def generar_excel_demanda(
    base_demanda: pd.DataFrame,
    calidad_datos: pd.DataFrame,
    auditoria_base_demanda: pd.DataFrame,
    fecha_generacion: datetime | None = None,
) -> BytesIO:
    """
    Genera el Excel completo del motor en memoria.

    Hojas:
    - BASE_DEMANDA
    - CALIDAD_DATOS
    - METADATA
    """

    if fecha_generacion is None:
        fecha_generacion = datetime.now()

    metadata = (
        construir_metadata_reporte(
            base_demanda=
                base_demanda,
            auditoria_base_demanda=
                auditoria_base_demanda,
            fecha_generacion=
                fecha_generacion,
        )
    )

    definiciones = (
        construir_definiciones_reporte()
    )

    archivo = BytesIO()

    with pd.ExcelWriter(
        archivo,
        engine="openpyxl",
    ) as writer:

        base_demanda.to_excel(
            writer,
            sheet_name=
                NOMBRE_HOJA_BASE,
            index=False,
        )

        calidad_datos.to_excel(
            writer,
            sheet_name=
                NOMBRE_HOJA_CALIDAD,
            index=False,
        )

        metadata.to_excel(
            writer,
            sheet_name=
                NOMBRE_HOJA_METADATA,
            index=False,
        )

        definiciones.to_excel(
            writer,
            sheet_name=NOMBRE_HOJA_DEFINICIONES,
            index=False,
        )

        workbook = writer.book

        for (
            nombre_hoja,
            dataframe,
        ) in [
            (
                NOMBRE_HOJA_BASE,
                base_demanda,
            ),
            (
                NOMBRE_HOJA_CALIDAD,
                calidad_datos,
            ),
            (
                NOMBRE_HOJA_METADATA,
                metadata,
            ),
            (
                NOMBRE_HOJA_DEFINICIONES,
                definiciones,
            ),
        ]:

            worksheet = workbook[
                nombre_hoja
            ]

            _formatear_hoja(
                worksheet
            )

            _formatear_fechas(
                worksheet,
                dataframe,
            )

    archivo.seek(0)

    return archivo


# ============================================================
# NOMBRE DEL REPORTE
# ============================================================

def generar_nombre_reporte(
    fecha_generacion: datetime | None = None,
) -> str:
    """
    Genera un nombre único para cada ejecución.
    """

    if fecha_generacion is None:
        fecha_generacion = datetime.now()

    timestamp = (
        fecha_generacion
        .strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
    )

    return (
        f"BASE_DEMANDA_{timestamp}.xlsx"
    )