from __future__ import annotations

import pandas as pd


# ============================================================
# METODOLOGÍA Y DEFINICIONES DEL MOTOR 05
# ============================================================

DEFINICIONES_RETENCION = [
    {
        "categoria": "Arquitectura",
        "concepto": "Historia preventiva canónica",
        "definicion": (
            "El Motor 05 reutiliza las mismas reglas de visitas "
            "analíticas y secuencia preventiva del Motor 04."
        ),
    },
    {
        "categoria": "Visitas",
        "concepto": "Visita analítica",
        "definicion": (
            "Conjunto de órdenes preventivas del mismo VIN que "
            "ocurren dentro de una ventana anclada de 7 días."
        ),
    },
    {
        "categoria": "Visitas",
        "concepto": "Fecha de visita",
        "definicion": (
            "Primera fecha de orden observada dentro de la visita "
            "analítica consolidada."
        ),
    },
    {
        "categoria": "Visitas",
        "concepto": "Registro representativo",
        "definicion": (
            "La última orden dentro de la visita representa "
            "mantenimiento, cliente, placa, modelo, sede y asesor."
        ),
    },
    {
        "categoria": "Secuencia",
        "concepto": "Secuencia preventiva",
        "definicion": (
            "1K → 5K → 10K → 15K y sucesivamente en pasos de 5K."
        ),
    },
    {
        "categoria": "Secuencia",
        "concepto": "SIGUE_CICLO",
        "definicion": (
            "El mantenimiento observado coincide exactamente con "
            "el siguiente mantenimiento esperado."
        ),
    },
    {
        "categoria": "Secuencia",
        "concepto": "SALTA_MANTENIMIENTOS",
        "definicion": (
            "El mantenimiento observado es superior al siguiente "
            "mantenimiento esperado."
        ),
    },
    {
        "categoria": "Secuencia",
        "concepto": "REPITE_MANTENIMIENTO",
        "definicion": (
            "El mantenimiento observado tiene el mismo nivel que "
            "el mantenimiento preventivo anterior."
        ),
    },
    {
        "categoria": "Secuencia",
        "concepto": "RETROCESO",
        "definicion": (
            "El mantenimiento observado tiene un nivel inferior "
            "al mantenimiento preventivo anterior."
        ),
    },
    {
        "categoria": "Parque",
        "concepto": "PANA",
        "definicion": (
            "VIN presente en Retail y, por tanto, identificado "
            "como vehículo vendido por PanaAutos."
        ),
    },
    {
        "categoria": "Parque",
        "concepto": "NOPANA",
        "definicion": (
            "VIN observado en Taller que no se encuentra en Retail."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "Retorno",
        "definicion": (
            "El vehículo registra una visita preventiva posterior "
            "a la oportunidad analizada."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "NO_RETORNO",
        "definicion": (
            "La oportunidad ya maduró y no existe una visita "
            "preventiva posterior observable."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "NO_EVALUABLE",
        "definicion": (
            "La oportunidad todavía no ha alcanzado su fecha "
            "esperada al corte disponible de información."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "Tasa de retorno",
        "definicion": (
            "Retornos dividido entre oportunidades evaluables. "
            "Las oportunidades NO_EVALUABLE no forman parte "
            "del denominador."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "Adherencia",
        "definicion": (
            "Entre los vehículos que retornaron, identifica si el "
            "mantenimiento observado fue exactamente el esperado."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "Retención flexible",
        "definicion": (
            "Un vehículo puede considerarse retenido aunque haya "
            "saltado un mantenimiento. Ejemplo: 5K → 15K implica "
            "retorno, pero no adherencia."
        ),
    },
    {
        "categoria": "Retención",
        "concepto": "Puntualidad",
        "definicion": (
            "Se evalúa únicamente sobre retornos adherentes. "
            "EN_FECHA corresponde a una tolerancia de ±30 días "
            "respecto de la fecha esperada."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Cohorte gerencial",
        "definicion": (
            "Mes calendario en el que correspondía el mantenimiento, "
            "es decir, el mes de la fecha esperada."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Mes de retorno",
        "definicion": (
            "Mes calendario real en el que el vehículo regresó "
            "posteriormente al taller."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Oportunidad 1K PANA",
        "definicion": (
            "Su fecha esperada corresponde a fecha de entrega "
            "+ 1 mes."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Oportunidad 5K PANA",
        "definicion": (
            "Su fecha esperada corresponde a fecha de entrega "
            "+ 6 meses. El 1K no reinicia el reloj."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Oportunidad 10K+",
        "definicion": (
            "Se construye desde la transición preventiva anterior "
            "y utiliza una expectativa de 6 meses."
        ),
    },
    {
        "categoria": "Cohortes",
        "concepto": "Unicidad de oportunidad",
        "definicion": (
            "La lectura gerencial utiliza una sola oportunidad por "
            "VIN + parque + hito."
        ),
    },
    {
        "categoria": "Comparación",
        "concepto": "PANA vs NOPANA",
        "definicion": (
            "La comparación directa debe utilizar ciclos "
            "comparables 10K+, porque NOPANA no dispone de fecha "
            "de entrega conocida."
        ),
    },
    {
        "categoria": "Snowball",
        "concepto": "Parque comercial acumulado",
        "definicion": (
            "PANA entra desde fecha de entrega. NOPANA entra desde "
            "su primera visita preventiva analítica observada."
        ),
    },
    {
        "categoria": "Snowball",
        "concepto": "Parque vigente",
        "definicion": (
            "VIN cuya última ancla preventiva mantiene vigencia "
            "de 6 meses al snapshot analizado."
        ),
    },
    {
        "categoria": "Snowball",
        "concepto": "Reactivación",
        "definicion": (
            "Nueva visita preventiva de un VIN cuya vigencia "
            "anterior ya había expirado."
        ),
    },
    {
        "categoria": "Snowball",
        "concepto": "Efecto Snowball",
        "definicion": (
            "Parque vigente actual = parque vigente anterior "
            "+ altas + reactivaciones - nuevos vencidos."
        ),
    },
    {
        "categoria": "Snowball",
        "concepto": "Índice Snowball",
        "definicion": (
            "Índice base 100 que compara el parque vigente de cada "
            "snapshot contra el parque vigente del primer snapshot. "
            "No es una tasa de retención."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Cliente asociado a visita",
        "definicion": (
            "Documento registrado en la visita preventiva. No se "
            "interpreta automáticamente como propietario legal "
            "del vehículo."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Vehículo fiel con cambio de cliente",
        "definicion": (
            "VIN con buen comportamiento de retorno aunque haya "
            "tenido distintos clientes asociados históricamente."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Cliente fiel a su vehículo",
        "definicion": (
            "Cliente con recurrencia y continuidad elevada con "
            "un mismo VIN."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Cliente multivehículo recurrente",
        "definicion": (
            "Cliente que aparece recurrentemente en Postventa "
            "asociado a más de un VIN."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Cliente multivehículo de alta fidelidad",
        "definicion": (
            "Cliente con múltiples VIN, alta recurrencia, mínimo "
            "de oportunidades y buen nivel de retorno."
        ),
    },
    {
        "categoria": "Clientes",
        "concepto": "Mínimo de oportunidades para ranking",
        "definicion": (
            "Las tasas utilizadas para rankings requieren al menos "
            "3 oportunidades evaluables para reducir resultados "
            "engañosos por muestras muy pequeñas."
        ),
    },
    {
        "categoria": "Calidad de datos",
        "concepto": "Datos actuales de clientes",
        "definicion": (
            "La información de clientes utilizada actualmente es "
            "dummy. Los resultados permiten validar la lógica del "
            "modelo, pero no deben interpretarse como hallazgos "
            "comerciales reales de clientes."
        ),
    },
    {
        "categoria": "Calidad de datos",
        "concepto": "Proyecto de calidad de clientes",
        "definicion": (
            "La evaluación y mejora de la calidad real de los datos "
            "de clientes se gestiona como un proyecto independiente "
            "del Motor 05."
        ),
    },
]


def obtener_definiciones_retencion() -> pd.DataFrame:
    """
    Devuelve la metodología del Motor 05 en formato tabular.

    Esta función será consumida tanto por:
    - exportación Excel;
    - Streamlit.
    """

    return pd.DataFrame(
        DEFINICIONES_RETENCION
    )