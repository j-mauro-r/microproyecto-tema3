import polars as pl

df = pl.read_csv(
    "./*.csv",
    schema_overrides={
        "dpto_ccdgo": pl.String,
        "mpio_ccdgo": pl.String,
        "mpio_cdpmp": pl.String,
    }
)

df.write_parquet(
    "./dengue_environment.parquet"
)
