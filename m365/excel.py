from io import BytesIO

import pandas as pd


def read_excel(
    excel_file: BytesIO,
    **kwargs,
) -> pd.DataFrame:
    """
    Reads an Excel file stored in memory and returns a DataFrame.

    Parameters
    ----------
    excel_file : BytesIO
        Excel file stored in memory.

    kwargs :
        Additional arguments forwarded to pandas.read_excel().

    Returns
    -------
    pandas.DataFrame
    """

    excel_file.seek(0)

    return pd.read_excel(excel_file, **kwargs)


from io import BytesIO

import pandas as pd


def dataframe_to_excel(df: pd.DataFrame) -> BytesIO:
    """
    Convierte un DataFrame en un archivo Excel
    almacenado en memoria.
    """

    archivo = BytesIO()

    with pd.ExcelWriter(
        archivo,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            index=False,
        )

    archivo.seek(0)

    return archivo