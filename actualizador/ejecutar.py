
from __future__ import annotations

import argparse
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd
from openpyxl import load_workbook

from actualizador.databricks import obtener_ordenes, obtener_facturacion
from actualizador.fuentes import preparar_fuentes
from m365.config import (
    SITE_NAME,
    DRIVE_NAME,
    INPUT_FOLDER,
    PROJECT_FOLDER,
    TALLER_FILE,
    CLIENTES_FILE,
)
from m365.sharepoint import SharePoint
from m365.excel import read_excel


SERVICIOS_FILE = "nivel de servicio.xlsx"
MODELOS_FILE = "modelos vehiculos.xlsx"
BACKUP_FOLDER = f"{PROJECT_FOLDER}/backup"

COLUMNAS_CLIENTES = [
    "nro documento", "nombre", "telefono", "correo"
]

COLUMNAS_TEXTO = {
    TALLER_FILE: {"Id doc", "doc ref", "placa", "vin",
                  "modelo", "año", "sede", "asesor",
                  "nro documento", "servicio1", "servicio2"},
    CLIENTES_FILE: set(COLUMNAS_CLIENTES),
    MODELOS_FILE: {"Material", "Modelo", "Año"},
}


def texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def conectar_sharepoint():
    sp = SharePoint()
    site = sp.get_site(SITE_NAME)

    if site is None:
        raise RuntimeError("No se encontró el sitio SharePoint.")

    drive = sp.get_drive(site["id"], DRIVE_NAME)

    if drive is None:
        raise RuntimeError("No se encontró la biblioteca.")

    return sp, drive["id"]


def descargar(sp, drive_id, nombre):
    ruta = f"{INPUT_FOLDER}/{nombre}"
    archivo = sp.download_file_by_path(drive_id, ruta)

    contenido = archivo.getvalue()
    datos = read_excel(
        BytesIO(contenido),
        dtype="string",
    )

    return contenido, datos


def filtrar_clientes_nuevos(
    historico: pd.DataFrame,
    propuestas: pd.DataFrame,
) -> pd.DataFrame:
    """
    No elimina registros históricos.

    Descarta propuestas idénticas al histórico y evita
    repetir filas idénticas dentro del lote nuevo.
    """
    if propuestas.empty:
        return propuestas.copy()

    def normalizar(df):
        resultado = df[COLUMNAS_CLIENTES].copy()

        for columna in COLUMNAS_CLIENTES:
            resultado[columna] = (
                resultado[columna]
                .astype("string")
                .fillna("")
                .str.strip()
            )

        return resultado

    antiguos = normalizar(historico)
    nuevos = normalizar(propuestas)

    existentes = set(
        antiguos.itertuples(index=False, name=None)
    )

    conservar = []
    vistos = set()

    for fila in nuevos.itertuples(index=False, name=None):
        if not fila[0]:
            continue

        if fila in existentes or fila in vistos:
            continue

        conservar.append(fila)
        vistos.add(fila)

    return pd.DataFrame(
        conservar,
        columns=COLUMNAS_CLIENTES,
    )


def agregar_filas_excel(
    contenido_original: bytes,
    nuevas: pd.DataFrame,
    nombre_archivo: str,
) -> BytesIO:
    """
    Agrega filas al libro original conservando las hojas
    existentes y su formato general.
    """
    wb = load_workbook(BytesIO(contenido_original))
    ws = wb.worksheets[0]

    encabezados = {
        str(celda.value).strip(): celda.column
        for celda in ws[1]
        if celda.value is not None
    }

    faltantes = set(nuevas.columns) - set(encabezados)

    if faltantes:
        raise ValueError(
            f"{nombre_archivo}: columnas ausentes: "
            f"{sorted(faltantes)}"
        )

    # Localizar la última fila con datos reales.
    ultima_fila_datos = 1

    for fila in ws.iter_rows(min_row=2):
        if any(
            celda.value is not None
            and str(celda.value).strip() != ""
            for celda in fila
        ):
            ultima_fila_datos = fila[0].row

    for valores in nuevas.to_dict("records"):
        ultima_fila_datos += 1
        fila_destino = ultima_fila_datos

        for columna, valor in valores.items():
            celda = ws.cell(
                row=fila_destino,
                column=encabezados[columna],
            )

            if pd.isna(valor):
                continue

            if isinstance(valor, pd.Timestamp):
                celda.value = valor.to_pydatetime()
                celda.number_format = "dd/mm/yyyy"
            elif columna in COLUMNAS_TEXTO.get(
                nombre_archivo, set()
            ):
                celda.value = str(valor)
                celda.number_format = "@"
            else:
                celda.value = valor

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)

    return salida


def validar_incremento(
    original: pd.DataFrame,
    resultado: pd.DataFrame,
    nuevas: pd.DataFrame,
    nombre: str,
) -> None:
    if len(resultado) != len(original) + len(nuevas):
        raise RuntimeError(
            f"Inconsistencia de filas en {nombre}."
        )

    if list(original.columns) != list(resultado.columns):
        raise RuntimeError(
            f"Se modificó la estructura de {nombre}."
        )

    pd.testing.assert_frame_equal(
        resultado.iloc[:len(original)].reset_index(drop=True),
        original.reset_index(drop=True),
        check_dtype=False,
    )


def cargar_excel_desde_bytes(contenido: bytes) -> pd.DataFrame:
    return read_excel(BytesIO(contenido), dtype="string")


def verificar_archivo(
    contenido: bytes,
    filas_esperadas: int,
    nombre: str,
) -> None:
    df = cargar_excel_desde_bytes(contenido)

    if len(df) != filas_esperadas:
        raise RuntimeError(
            f"{nombre}: se esperaban {filas_esperadas} "
            f"filas, pero se encontraron {len(df)}."
        )



def respaldar(sp, drive_id, originales, archivos):
    """
    Crea o sobrescribe un backup rotativo por cada archivo
    que será modificado.

    Verifica que el contenido respaldado sea idéntico
    al original antes de autorizar la publicación.
    """
    for nombre in archivos:
        nombre_backup = (
            f"{nombre.removesuffix('.xlsx')}_backup.xlsx"
        )

        ruta = f"{BACKUP_FOLDER}/{nombre_backup}"

        print(f"💾 Respaldando {nombre}...")

        sp.upload_file_by_path(
            drive_id=drive_id,
            file_path=ruta,
            file_content=BytesIO(originales[nombre]),
        )

        copia = sp.download_file_by_path(
            drive_id=drive_id,
            file_path=ruta,
        ).getvalue()

        if copia != originales[nombre]:
            raise RuntimeError(
                f"Backup de {nombre} no coincide "
                "con el archivo original."
            )

        print(f"   ✅ Backup verificado: {nombre_backup}")





def publicar(sp, drive_id, preparados, originales):
    """
    Publica y verifica cada archivo.

    Si ocurre un error, intenta restaurar todos los
    archivos involucrados, incluido aquel cuya carga falló.

    La restauración también se verifica mediante descarga.
    """
    archivos = list(preparados)
    archivo_en_proceso = None

    try:
        for nombre in archivos:
            archivo_en_proceso = nombre

            print(f"📤 Publicando {nombre}...")

            ruta = f"{INPUT_FOLDER}/{nombre}"

            sp.upload_file_by_path(
                drive_id=drive_id,
                file_path=ruta,
                file_content=BytesIO(preparados[nombre]),
            )

            verificacion = sp.download_file_by_path(
                drive_id=drive_id,
                file_path=ruta,
            ).getvalue()

            if verificacion != preparados[nombre]:
                raise RuntimeError(
                    f"Verificación fallida: {nombre}"
                )

            print(f"   ✅ Publicación verificada: {nombre}")

    except Exception as error:
        print("\n⚠️ Error durante la publicación.")
        print(f"Archivo en proceso: {archivo_en_proceso}")
        print(f"Detalle: {error}")
        print("🔄 Intentando restaurar los originales...")

        errores_restauracion = []

        # Se restauran todos los archivos preparados.
        # No asumimos que una carga fallida dejó
        # el archivo de destino intacto.
        for nombre in reversed(archivos):
            ruta = f"{INPUT_FOLDER}/{nombre}"

            try:
                sp.upload_file_by_path(
                    drive_id=drive_id,
                    file_path=ruta,
                    file_content=BytesIO(originales[nombre]),
                )

                restaurado = sp.download_file_by_path(
                    drive_id=drive_id,
                    file_path=ruta,
                ).getvalue()

                if restaurado != originales[nombre]:
                    raise RuntimeError(
                        "El contenido restaurado no coincide "
                        "con el original."
                    )

                print(f"   ✅ Restaurado: {nombre}")

            except Exception as exc:
                errores_restauracion.append(
                    f"{nombre}: {exc}"
                )
                print(
                    f"   ❌ No se confirmó restauración: "
                    f"{nombre}"
                )

        if errores_restauracion:
            raise RuntimeError(
                "PUBLICACIÓN FALLIDA Y RESTAURACIÓN INCOMPLETA. "
                "Revisar los archivos originales y los backups "
                "en SharePoint antes de continuar. Detalles: "
                + "; ".join(errores_restauracion)
            ) from error

        raise RuntimeError(
            "Publicación fallida. Todos los archivos "
            "fueron restaurados y verificados."
        ) from error






def ejecutar(publicacion: bool = False):
    inicio = datetime.now(ZoneInfo("America/Lima"))

    print("\n" + "=" * 65)
    print("🐔 CGO — ACTUALIZADOR DE FUENTES")
    print("MODO:", "PUBLICACIÓN" if publicacion else "SIMULACIÓN")
    print("=" * 65)

    sp, drive_id = conectar_sharepoint()

    nombres = [
        TALLER_FILE,
        CLIENTES_FILE,
        SERVICIOS_FILE,
        MODELOS_FILE,
    ]

    originales = {}
    fuentes = {}

    for nombre in nombres:
        print(f"📥 Leyendo {nombre}...")
        originales[nombre], fuentes[nombre] = descargar(
            sp, drive_id, nombre
        )
        print(f"   ✅ {len(fuentes[nombre]):,} filas")

    ordenes = obtener_ordenes(sector="13")

    ids_existentes = set(
        fuentes[TALLER_FILE]["Id doc"].map(texto)
    )

    ids_nuevos = sorted(
        set(ordenes["ID_OPERACION"].map(texto))
        - ids_existentes - {""}
    )

    print(f"\n🐔 Órdenes nuevas: {len(ids_nuevos):,}")

    facturacion = obtener_facturacion(
        ids_ordenes=ids_nuevos,
        sector="13",
    )

    resultado = preparar_fuentes(
        ordenes=ordenes,
        facturacion=facturacion,
        taller_actual=fuentes[TALLER_FILE],
        clientes_actual=fuentes[CLIENTES_FILE],
        servicios_actual=fuentes[SERVICIOS_FILE],
        modelos_actual=fuentes[MODELOS_FILE],
    )

    # El historial de clientes permanece intacto.
    nuevos_clientes = resultado.clientes.iloc[
        len(fuentes[CLIENTES_FILE]):
    ].copy()

    clientes_filtrados = filtrar_clientes_nuevos(
        fuentes[CLIENTES_FILE],
        nuevos_clientes,
    )

    taller_final = resultado.taller

    clientes_final = pd.concat(
        [fuentes[CLIENTES_FILE], clientes_filtrados],
        ignore_index=True,
    )

    validar_incremento(
        fuentes[TALLER_FILE],
        taller_final,
        resultado.nuevas_ordenes,
        TALLER_FILE,
    )

    validar_incremento(
        fuentes[CLIENTES_FILE],
        clientes_final,
        clientes_filtrados,
        CLIENTES_FILE,
    )

    # Los diccionarios con nuevas equivalencias se preparan
    # sin modificar sus filas existentes.
    nuevos_modelos = resultado.diccionario_modelos.iloc[
        len(fuentes[MODELOS_FILE]):
    ].copy()

    nuevas_categorias = resultado.diccionario_servicios.iloc[
        len(fuentes[SERVICIOS_FILE]):
    ].copy()

    if not nuevas_categorias.empty:
        raise RuntimeError(
            "Existen categorías nuevas con jerarquía pendiente "
            "de validar. No se publicarán automáticamente."
        )

    incrementos = {
        TALLER_FILE: resultado.nuevas_ordenes,
        CLIENTES_FILE: clientes_filtrados,
        MODELOS_FILE: nuevos_modelos,
    }

    preparados = {}

    for nombre, nuevas in incrementos.items():
        if nuevas.empty:
            continue

        salida = agregar_filas_excel(
            originales[nombre],
            nuevas,
            nombre,
        )

        contenido = salida.getvalue()

        verificar_archivo(
            contenido,
            len(fuentes[nombre]) + len(nuevas),
            nombre,
        )

        preparados[nombre] = contenido

    print("\n" + "=" * 65)
    print("🐔 RESULTADO DE PREPARACIÓN")
    print("=" * 65)

    print(f"Órdenes incorporables : {len(resultado.nuevas_ordenes):,}")
    print(f"Órdenes pendientes    : {len(resultado.pendientes):,}")
    print(f"Clientes propuestos   : {len(nuevos_clientes):,}")
    print(f"Clientes a incorporar : {len(clientes_filtrados):,}")
    print(f"Modelos nuevos        : {len(nuevos_modelos):,}")

    print("\nArchivos que cambiarían:")
    for nombre in preparados:
        print(f"  - {nombre}")

    if not publicacion:
        print("\n✅ Simulación finalizada. Sin escrituras.")
        return

    if not preparados:
        print("\n✅ No hay archivos que actualizar.")
        return

    respuesta = input(
        "\n¿Confirmas la publicación en SharePoint? "
        "Escribe PUBLICAR: "
    ).strip()

    if respuesta != "PUBLICAR":
        print("Publicación cancelada.")
        return

    # Verificamos que las fuentes de producción no hayan
    # cambiado desde que fueron descargadas.
    for nombre in preparados:
        actual = sp.download_file_by_path(
            drive_id=drive_id,
            file_path=f"{INPUT_FOLDER}/{nombre}",
        ).getvalue()

        if actual != originales[nombre]:
            raise RuntimeError(
                f"{nombre} cambió durante la ejecución. "
                "Se cancela para evitar sobrescribir cambios."
            )

    # Backups obligatorios de los archivos raíz.
    respaldar(
        sp,
        drive_id,
        originales,
        archivos=list(preparados),
    )

    publicar(
        sp,
        drive_id,
        preparados,
        originales,
    )

    fin = datetime.now(ZoneInfo("America/Lima"))

    print("\n✅ FUENTES PUBLICADAS CORRECTAMENTE")
    print(f"Duración: {(fin - inicio).total_seconds():.1f} s")
    print("🐔 Ya puedes ejecutar el motor de demanda.")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--publicar",
        action="store_true",
        help="Autoriza solicitar publicación en SharePoint.",
    )

    args = parser.parse_args()

    ejecutar(publicacion=args.publicar)


if __name__ == "__main__":
    main()
