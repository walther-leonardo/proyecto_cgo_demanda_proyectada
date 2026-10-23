
import os

from databricks import sql
from dotenv import load_dotenv


def main():
    load_dotenv()

    hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")

    if not hostname or not http_path:
        raise ValueError(
            "Faltan las variables de conexión de Databricks."
        )

    print("🐔 Conectando a Databricks...")

    with sql.connect(
        server_hostname=hostname,
        http_path=http_path,
        auth_type="databricks-oauth",
    ) as connection:
        print("✅ Conexión establecida.")

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    ID_OPERACION,
                    FECHA_CONTABILIZACION,
                    VIN,
                    PLACA,
                    MODELO
                FROM hive_metastore.db_gold.ordenes_unegocio_s4
                LIMIT 5
            """)

            for fila in cursor.fetchall():
                print(fila)

        if resultado is None or resultado[0] != 1:
            raise RuntimeError("La consulta no devolvió el valor esperado.")

        print(f"✅ Consulta SQL exitosa: {resultado[0]}")


if __name__ == "__main__":
    main()
