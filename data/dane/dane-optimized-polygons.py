import ee

PROJECT_ID = "dengue-506002"

ee.Initialize(project=PROJECT_ID)

# ============================================================
# DANE DIVIPOLA
# ============================================================

RAW_ASSET = "projects/dengue-506002/assets/municipios-dane"

OPTIMIZED_ASSET = (
    "projects/dengue-506002/assets/municipios-dane-optimized"
)

CAMPO_DPTO = "dpto_ccdgo"
CAMPO_NOM_DPTO = "dpto_cnmbr"
CAMPO_MPIO = "mpio_ccdgo"
CAMPO_MPIO_COMPLETO = "mpio_cdpmp"
CAMPO_NOM_MPIO = "mpio_cnmbr"

FIELDS = [
    CAMPO_DPTO,
    CAMPO_NOM_DPTO,
    CAMPO_MPIO,
    CAMPO_MPIO_COMPLETO,
    CAMPO_NOM_MPIO,
]


municipios_raw = (
    ee.FeatureCollection(RAW_ASSET)
    .select(FIELDS)
)


# ============================================================
# DIAGNOSTIC
# ============================================================

raw_count = municipios_raw.size().getInfo()

unique_codes = (
    ee.List(
        municipios_raw.aggregate_array(
            CAMPO_MPIO_COMPLETO
        )
    )
    .distinct()
)

municipality_count = unique_codes.size().getInfo()

print(f"Raw features: {raw_count:,}")
print(f"Unique municipality codes: {municipality_count:,}")

print("\nExample:")
print(
    municipios_raw
    .first()
    .toDictionary(FIELDS)
    .getInfo()
)


# ============================================================
# OPTIMIZATION
# ============================================================

# 500 meters is small relative to CHIRPS (~5.5 km)
# and ERA5-Land (~11 km).
SIMPLIFY_METERS = 500

# Larger error margin makes geometric operations cheaper.
GEOMETRY_ERROR = 1000


if raw_count == municipality_count:

    print(
        "\nThere is already one feature per municipality."
        "\nOnly simplifying geometry..."
    )

    def simplify_municipality(feature):

        feature = ee.Feature(feature)

        geometry = (
            feature.geometry()
            .simplify(SIMPLIFY_METERS)
        )

        return ee.Feature(
            geometry,
            feature.toDictionary(FIELDS)
        )

    municipios_optimized = (
        municipios_raw
        .map(simplify_municipality)
    )


else:

    print(
        "\nMultiple polygons/fragments found per municipality."
        "\nDissolving by DIVIPOLA code..."
    )

    def dissolve_municipality(code):

        subset = municipios_raw.filter(
            ee.Filter.eq(
                CAMPO_MPIO_COMPLETO,
                code
            )
        )

        first = ee.Feature(
            subset.first()
        )

        # Merge fragments belonging to the municipality.
        merged_feature = ee.Feature(
            subset
            .union(maxError=GEOMETRY_ERROR)
            .first()
        )

        geometry = (
            merged_feature
            .geometry()
            .simplify(SIMPLIFY_METERS)
        )

        return ee.Feature(
            geometry,
            {
                CAMPO_DPTO:
                    first.get(CAMPO_DPTO),

                CAMPO_NOM_DPTO:
                    first.get(CAMPO_NOM_DPTO),

                CAMPO_MPIO:
                    first.get(CAMPO_MPIO),

                CAMPO_MPIO_COMPLETO:
                    first.get(CAMPO_MPIO_COMPLETO),

                CAMPO_NOM_MPIO:
                    first.get(CAMPO_NOM_MPIO),
            }
        )

    municipios_optimized = ee.FeatureCollection(
        unique_codes.map(
            dissolve_municipality
        )
    )


# ============================================================
# EXPORT OPTIMIZED VERSION AS A NEW GEE ASSET
# ============================================================

task = ee.batch.Export.table.toAsset(
    collection=municipios_optimized,

    description="municipio_dane_optimized",

    assetId=OPTIMIZED_ASSET,
)

task.start()

print("\nOptimization task started.")
print(f"Task ID: {task.id}")
print(f"Destination: {OPTIMIZED_ASSET}")
