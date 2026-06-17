"""Iceberg table utilities."""

from pyspark.sql import SparkSession, DataFrame
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def get_iceberg_session(app_name: str = "traffic-analytics") -> SparkSession:
    """Return a SparkSession configured for Iceberg."""
    from pipelines.processing.utils.spark_session import get_spark_session

    return get_spark_session(app_name, enable_iceberg=True)


def write_iceberg_table(
    df: DataFrame,
    table_name: str,
    s3_path: str = "s3a://lakehouse",
    mode: str = "overwrite",
    partition_cols: Optional[List[str]] = None,
) -> None:
    """Write a DataFrame to an Iceberg table using the local catalog convention."""
    writer = df.write.format("iceberg").mode(mode)
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.saveAsTable(f"{s3_path}.db.{table_name}")
    logger.info("Wrote Iceberg table: %s", table_name)


def create_iceberg_table(
    spark: SparkSession,
    table_name: str,
    df: DataFrame,
    location: str,
    partition_by: Optional[List[str]] = None,
) -> None:
    """Create Iceberg table with schema from DataFrame."""
    try:
        write = df.write.format("iceberg").mode("overwrite")

        if partition_by:
            write = write.partitionedBy(*partition_by)

        write.option("path", location).saveAsTable(table_name)
        logger.info(f"Created Iceberg table: {table_name} at {location}")
    except Exception as e:
        logger.error(f"Error creating table {table_name}: {e}")
        raise


def read_iceberg_table(spark: SparkSession, table_name: str) -> DataFrame:
    """Read Iceberg table."""
    return spark.table(table_name)


def merge_into_table(
    spark: SparkSession,
    target_table: str,
    source_df: DataFrame,
    join_condition: str,
) -> None:
    """Merge source into target Iceberg table (upsert)."""
    try:
        source_df.createOrReplaceTempView("source")
        spark.sql(f"""
            MERGE INTO iceberg.{target_table} t
            USING source s
            ON {join_condition}
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
        logger.info(f"Merged into {target_table}")
    except Exception as e:
        logger.error(f"Error merging into {target_table}: {e}")
        raise


def get_table_schema(spark: SparkSession, table_name: str) -> str:
    """Get schema of Iceberg table."""
    return spark.table(table_name).schema.json()
