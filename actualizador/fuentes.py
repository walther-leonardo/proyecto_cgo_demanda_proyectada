
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

import pandas as pd

from motor.datos import COLUMNAS_CLIENTES, COLUMNAS_TALLER


# ============================================================
# CONTRATOS Y RESULTADOS
# ============================================================

@dataclass
class ResultadoFuentes:
    taller: pd.DataFrame
    clientes: pd.DataFrame
    diccionario_servicios: pd.DataFrame
    diccionario_modelos: pd.DataFrame
    nuevas_ordenes: pd.DataFrame
    pendientes: pd.DataFrame
    nuevas_categorias: int
    nuevos_modelos: int


def texto(valor) -> str:
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    if valor.endswith(".0") and valor[:-2].isdigit():
        valor = valor[:-2]

    return valor


def clave(valor) -> str:
    return texto(valor).upper()


def fecha(valor):
    if pd.isna(valor) or texto(valor) == "":
        return pd.NaT

    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(valor).normalize()

    if isinstance(valor, (int, float)):
        return pd.to_datetime(
            valor, unit="D", origin="1899-12-30",
            errors="coerce",
        )

    return pd.to_datetime(valor, errors="coerce")


def solicitar_opcion(
    mensaje: str,
    opciones: list[str],
    preguntar: Callable[[str], str],
) -> str:
    print(f"\n{mensaje}")

    for indice, opcion in enumerate(opciones, start=1):
        print(f"  {indice}. {opcion}")

    print("  0. Dejar pendiente")

    while True:
        respuesta = preguntar("Seleccione una opción: ").strip()

        if respuesta == "0":
            return ""

        if respuesta.isdigit():
            posicion = int(respuesta) - 1
            if 0 <= posicion < len(opciones):
                return opciones[posicion]

        print("⚠️ Seleccione una opción válida.")


def validar_columnas(
    df: pd.DataFrame,
    columnas: list[str],
    nombre: str,
) -> None:
    faltantes = sorted(set(columnas) - set(df.columns))

    if faltantes:
        raise ValueError(
            f"{nombre}: faltan columnas {faltantes}"
        )


# ============================================================
# PREPARACIÓN DE DICCIONARIOS
# ============================================================

def preparar_diccionarios(
    servicios: pd.DataFrame,
    modelos: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validar_columnas(
        servicios,
        ["Nivel_4", "servicio1", "servicio2"],
        "nivel de servicio.xlsx",
    )

    validar_columnas(
        modelos,
        ["Material", "Modelo", "Año"],
        "modelos vehiculos.xlsx",
    )

    servicios = servicios.copy()
    modelos = modelos.copy()

    for columna in ("Nivel_4", "servicio1", "servicio2"):
        servicios[columna] = servicios[columna].map(clave)

    for columna in ("Material", "Modelo", "Año"):
        modelos[columna] = modelos[columna].map(clave)

    return servicios, modelos


def opciones_servicio(
    diccionario: pd.DataFrame,
) -> list[tuple[str, str]]:
    opciones = {
        (fila.servicio1, fila.servicio2)
        for fila in diccionario.itertuples(index=False)
        if fila.servicio1
    }

    return sorted(opciones)


def clasificar_servicio(
    orden: pd.Series,
    diccionario: pd.DataFrame,
    preguntar: Callable[[str], str],
) -> tuple[str, str, pd.DataFrame, bool]:
    categoria = clave(orden["CATEGORIA_ORDEN"])
    id_orden = texto(orden["ID_OPERACION"])

    if categoria:
        coincidencias = diccionario[
            diccionario["Nivel_4"] == categoria
        ]

        if not coincidencias.empty:
            valores = {
                (fila.servicio1, fila.servicio2)
                for fila in coincidencias.itertuples(index=False)
            }

            if len(valores) == 1:
                servicio1, servicio2 = next(iter(valores))
                return servicio1, servicio2, diccionario, False

    print("\n" + "=" * 60)
    print("🐔 SERVICIO PENDIENTE DE CLASIFICACIÓN")
    print("=" * 60)
    print(f"ID_OPERACION         : {id_orden}")
    print(f"CLASE_OPERACION      : {texto(orden['CLASE_OPERACION'])}")
    print(
        "DESCRIPCION_OPERACION: "
        f"{texto(orden['DESCRIPCION_OPERACION'])}"
    )
    print(f"CATEGORIA_ORDEN      : {categoria or 'VACÍA'}")

    pares = opciones_servicio(diccionario)

    # Si el código tiene correspondencias contradictorias,
    # siempre requerimos una decisión explícita.
    etiquetas = [
        f"{servicio1} / {servicio2 or '(vacío)'}"
        for servicio1, servicio2 in pares
    ]

    seleccion = solicitar_opcion(
        "Indique la clasificación de la orden:",
        etiquetas,
        preguntar,
    )

    if not seleccion:
        return "", "", diccionario, False

    indice = etiquetas.index(seleccion)
    servicio1, servicio2 = pares[indice]

    # Las categorías vacías nunca se guardan como códigos.
    if not categoria:
        return servicio1, servicio2, diccionario, False

    # Para categorías con código nuevo se prepara una fila
    # respetando las columnas existentes del diccionario.
    fila_nueva = {
        columna: ""
        for columna in diccionario.columns
    }

    if "Nivel_1" in fila_nueva:
        fila_nueva["Nivel_1"] = categoria[:3]
    if "Nivel_2" in fila_nueva:
        fila_nueva["Nivel_2"] = categoria[:5]
    if "Nivel_3" in fila_nueva:
        fila_nueva["Nivel_3"] = categoria[:7]

    fila_nueva.update({
        "Nivel_4": categoria,
        "servicio1": servicio1,
        "servicio2": servicio2,
    })

    # Si el código ya existe con una traducción contradictoria,
    # no modificamos silenciosamente el diccionario.
    if (diccionario["Nivel_4"] == categoria).any():
        print("⚠️ Código ya existente con clasificación ambigua.")
        print("   La decisión se usará solo para esta orden.")
        return servicio1, servicio2, diccionario, False

    diccionario = pd.concat(
        [diccionario, pd.DataFrame([fila_nueva])],
        ignore_index=True,
    )

    print(f"✅ Nueva categoría preparada: {categoria}")

    return servicio1, servicio2, diccionario, True


def traducir_modelo(
    orden: pd.Series,
    diccionario: pd.DataFrame,
    preguntar: Callable[[str], str],
) -> tuple[str, str, pd.DataFrame, bool]:
    codigos = [
        clave(orden["MODELO"]),
        clave(orden["MODELO_VERSION"]),
    ]

    for codigo in dict.fromkeys(codigos):
        if not codigo:
            continue

        filas = diccionario[diccionario["Material"] == codigo]

        equivalencias = {
            (fila.Modelo, fila.Año)
            for fila in filas.itertuples(index=False)
            if fila.Modelo and fila.Año
        }

        if len(equivalencias) == 1:
            modelo, año = next(iter(equivalencias))
            return modelo, año, diccionario, False

        if len(equivalencias) > 1:
            print(f"⚠️ Traducciones contradictorias: {codigo}")
            return "", "", diccionario, False

    codigo = next(
        (valor for valor in codigos if valor),
        "",
    )

    print("\n" + "=" * 60)
    print("🐔 MODELO SIN TRADUCCIÓN")
    print("=" * 60)
    print(f"Orden          : {texto(orden['ID_OPERACION'])}")
    print(f"VIN            : {texto(orden['VIN'])}")
    print(f"MODELO         : {codigos[0]}")
    print(f"MODELO_VERSION : {codigos[1]}")

    if not codigo:
        return "", "", diccionario, False

    existentes = sorted({
        clave(valor)
        for valor in diccionario["Modelo"]
        if clave(valor)
    })

    seleccion = solicitar_opcion(
        "Seleccione el modelo comercial:",
        existentes,
        preguntar,
    )

    if not seleccion:
        return "", "", diccionario, False

    while True:
        año = preguntar(
            "Año de modelo (AAAA o AA/AA; Enter para pendiente): "
        ).strip()

        if not año:
            return "", "", diccionario, False

        if (
            (len(año) == 4 and año.isdigit())
            or (
                len(año) == 5
                and año[2] == "/"
                and año[:2].isdigit()
                and año[3:].isdigit()
            )
        ):
            break

        print("⚠️ Formato no reconocido.")

    fila_nueva = {
        columna: ""
        for columna in diccionario.columns
    }
    fila_nueva.update({
        "Material": codigo,
        "Modelo": seleccion,
        "Año": año,
    })

    diccionario = pd.concat(
        [diccionario, pd.DataFrame([fila_nueva])],
        ignore_index=True,
    )

    print(f"✅ Nuevo modelo preparado: {codigo}")

    return seleccion, año, diccionario, True


# ============================================================
# CONSOLIDACIÓN DE ÓRDENES
# ============================================================

def consolidar_orden(
    grupo: pd.DataFrame,
    diccionario_servicios: pd.DataFrame,
) -> pd.Series:
    grupo = grupo.copy()

    categorias_preventivas = set(
        diccionario_servicios.loc[
            diccionario_servicios["servicio1"]
            .eq("PREVENTIVO"),
            "Nivel_4",
        ]
    )

    grupo["_preventivo"] = (
        grupo["CATEGORIA_ORDEN"]
        .map(clave)
        .isin(categorias_preventivas)
    )

    sedes = grupo["SEDE_COSTO_FINAL"].map(clave)

    grupo["_sede"] = sedes.map(
        lambda valor: (
            0 if "SAN ISIDRO" in valor
            else 1 if "SAN MIGUEL" in valor
            else 2
        )
    )

    grupo = grupo.sort_values(
        ["_preventivo", "_sede"],
        ascending=[False, True],
        kind="stable",
    )

    seleccionada = grupo.iloc[0].copy()

    # Recuperar información no vacía sin mezclar
    # categorías de filas distintas.
    campos_completables = [
        "VIN",
        "PLACA",
        "MODELO",
        "MODELO_VERSION",
        "NUMERO_DOC_SOLICITANTE",
        "NOMBRE_SOLICITANTE",
        "CELULAR_SOLICITANTE",
        "CORREO_SOLICITANTE",
        "FECHA_CONTABILIZACION",
    ]

    for campo in campos_completables:
        if campo not in grupo:
            continue

        if texto(seleccionada[campo]):
            continue

        candidatos = grupo[campo].dropna()
        candidatos = candidatos[
            candidatos.map(texto) != ""
        ]

        if not candidatos.empty:
            seleccionada[campo] = candidatos.iloc[0]

    return seleccionada.drop(
        labels=["_preventivo", "_sede"]
    )


# ============================================================
# FACTURACIÓN
# ============================================================

def consolidar_facturacion(
    facturacion: pd.DataFrame,
) -> dict[str, tuple]:
    if facturacion.empty:
        return {}

    validar_columnas(
        facturacion,
        [
            "ORDEN_SERVICIO_ORIGINAL",
            "FECHA_FACTURA_RP",
            "DOCUMENTO_SUNAT",
        ],
        "Facturación Databricks",
    )

    trabajo = facturacion.copy()
    trabajo["id"] = trabajo[
        "ORDEN_SERVICIO_ORIGINAL"
    ].map(texto)

    trabajo["fecha"] = trabajo[
        "FECHA_FACTURA_RP"
    ].map(fecha)

    trabajo["documento"] = trabajo[
        "DOCUMENTO_SUNAT"
    ].map(texto)

    trabajo = trabajo.sort_values(
        ["id", "fecha", "documento"],
        na_position="last",
        kind="stable",
    )

    # Se conserva el primer comprobante informado.
    # Si existen varios, habrá que auditar esa casuística.
    resultado = {}

    for identificador, grupo in trabajo.groupby("id"):
        validas = grupo[
            grupo["documento"].ne("")
            | grupo["fecha"].notna()
        ]

        if validas.empty:
            continue

        fila = validas.iloc[0]
        resultado[identificador] = (
            fila["fecha"],
            fila["documento"],
        )

    return resultado


# ============================================================
# PREPARACIÓN DE FUENTES
# ============================================================

def preparar_fuentes(
    ordenes: pd.DataFrame,
    facturacion: pd.DataFrame,
    taller_actual: pd.DataFrame,
    clientes_actual: pd.DataFrame,
    servicios_actual: pd.DataFrame,
    modelos_actual: pd.DataFrame,
    preguntar: Callable[[str], str] = input,
) -> ResultadoFuentes:
    """
    Prepara las actualizaciones sin escribir en SharePoint.

    Las órdenes no resueltas quedan pendientes.
    Los registros existentes de taller no se modifican.
    """

    validar_columnas(
        taller_actual, COLUMNAS_TALLER, "taller.xlsx"
    )
    validar_columnas(
        clientes_actual, COLUMNAS_CLIENTES, "clientes.xlsx"
    )

    validar_columnas(
        ordenes,
        [
            "ID_OPERACION", "FECHA_CONTABILIZACION",
            "CATEGORIA_ORDEN", "CLASE_OPERACION",
            "DESCRIPCION_OPERACION", "SEDE_COSTO_FINAL",
            "VIN", "PLACA", "MODELO", "MODELO_VERSION",
            "NUMERO_DOC_SOLICITANTE",
            "NOMBRE_SOLICITANTE",
            "CELULAR_SOLICITANTE",
            "CORREO_SOLICITANTE",
        ],
        "Órdenes Databricks",
    )

    servicios, modelos = preparar_diccionarios(
        servicios_actual, modelos_actual
    )

    ids_existentes = set(
        taller_actual["Id doc"].map(texto)
    )

    trabajo = ordenes.copy()
    trabajo["ID_OPERACION"] = trabajo[
        "ID_OPERACION"
    ].map(texto)

    trabajo = trabajo[
        ~trabajo["ID_OPERACION"].isin(ids_existentes)
        & trabajo["ID_OPERACION"].ne("")
    ].copy()

    print(
        f"\n🐔 Órdenes nuevas detectadas: "
        f"{trabajo['ID_OPERACION'].nunique():,}"
    )

    facturas = consolidar_facturacion(facturacion)

    nuevas = []
    clientes_nuevos = []
    pendientes = []
    categorias_agregadas = 0
    modelos_agregados = 0

    for id_orden, grupo in trabajo.groupby(
        "ID_OPERACION", sort=True
    ):
        orden = consolidar_orden(grupo, servicios)

        servicio1, servicio2, servicios, nueva_categoria = (
            clasificar_servicio(
                orden, servicios, preguntar
            )
        )

        if not servicio1:
            pendientes.append({
                "ID_OPERACION": id_orden,
                "motivo": "SERVICIO_SIN_CLASIFICAR",
            })
            continue

        modelo, año, modelos, nuevo_modelo = (
            traducir_modelo(
                orden, modelos, preguntar
            )
        )

        if not modelo or not año:
            pendientes.append({
                "ID_OPERACION": id_orden,
                "motivo": "MODELO_SIN_CLASIFICAR",
            })
            continue

        # Las nuevas equivalencias permanecen en memoria
        # hasta que el controlador autorice su publicación.
        categorias_agregadas += int(nueva_categoria)
        modelos_agregados += int(nuevo_modelo)

        factura_fecha, documento_sunat = facturas.get(
            id_orden,
            (pd.NaT, ""),
        )

        sede_original = clave(orden["SEDE_COSTO_FINAL"])

        sede = (
            "SAN MIGUEL"
            if "SAN MIGUEL" in sede_original
            else "SAN ISIDRO"
        )

        nueva_fila = {
            "Id doc": id_orden,
            "f factura servicio": factura_fecha,
            "f orden": fecha(
                orden["FECHA_CONTABILIZACION"]
            ),
            "doc ref": documento_sunat,
            "servicio1": servicio1.lower(),
            "servicio2": servicio2,
            "placa": clave(orden["PLACA"]),
            "vin": clave(orden["VIN"]),
            "modelo": modelo,
            "año": año,
            "sede": sede,
            "asesor": "asesor",
            "nro documento": texto(
                orden["NUMERO_DOC_SOLICITANTE"]
            ),
        }

        nuevas.append(nueva_fila)

        if servicio1 == "PREVENTIVO":
            clientes_nuevos.append({
                "nro documento": texto(
                    orden["NUMERO_DOC_SOLICITANTE"]
                ),
                "nombre": texto(
                    orden["NOMBRE_SOLICITANTE"]
                ),
                "telefono": texto(
                    orden["CELULAR_SOLICITANTE"]
                ),
                "correo": texto(
                    orden["CORREO_SOLICITANTE"]
                ),
            })

    df_nuevas = pd.DataFrame(
        nuevas, columns=COLUMNAS_TALLER
    )

    df_clientes_nuevos = pd.DataFrame(
        clientes_nuevos, columns=COLUMNAS_CLIENTES
    )

    # Conservar exactamente las filas anteriores.
    taller_final = pd.concat(
        [taller_actual, df_nuevas],
        ignore_index=True,
    )

    clientes_final = pd.concat(
        [clientes_actual, df_clientes_nuevos],
        ignore_index=True,
    )

    df_pendientes = pd.DataFrame(
        pendientes,
        columns=["ID_OPERACION", "motivo"],
    )

    print("\n" + "=" * 60)
    print("🐔 RESUMEN DE ACTUALIZACIÓN — SIMULACIÓN")
    print("=" * 60)
    print(f"Órdenes incorporables : {len(df_nuevas):,}")
    print(f"Órdenes pendientes    : {len(df_pendientes):,}")
    print(f"Clientes por agregar  : {len(df_clientes_nuevos):,}")
    print(f"Nuevas categorías     : {categorias_agregadas:,}")
    print(f"Nuevos modelos        : {modelos_agregados:,}")
    print("✅ Sin modificaciones en SharePoint.")

    return ResultadoFuentes(
        taller=taller_final,
        clientes=clientes_final,
        diccionario_servicios=servicios,
        diccionario_modelos=modelos,
        nuevas_ordenes=df_nuevas,
        pendientes=df_pendientes,
        nuevas_categorias=categorias_agregadas,
        nuevos_modelos=modelos_agregados,
    )
