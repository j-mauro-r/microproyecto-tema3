import ee


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ID = "dengue-506002"

MUNICIPALITIES_ASSET = (
    "projects/dengue-506002/assets/municipios-dane-optimized"
)

START_YEAR = 2018
END_YEAR = 2024

DRIVE_FOLDER = "Dengue_Colombia_Raw_Environment"

ANALYSIS_SCALE = 5566
TILE_SCALE = 4
MAX_PIXELS_PER_REGION = 1_000_000


# ============================================================
# DIVIPOLA FIELD NAMES
# ============================================================

CAMPO_DPTO = "dpto_ccdgo"
CAMPO_NOM_DPTO = "dpto_cnmbr"

CAMPO_MPIO = "mpio_ccdgo"
CAMPO_MPIO_COMPLETO = "mpio_cdpmp"
CAMPO_NOM_MPIO = "mpio_cnmbr"


# ============================================================
# INITIALIZE EARTH ENGINE
#
# IMPORTANT:
# This must happen BEFORE creating ee.ImageCollection,
# ee.FeatureCollection, ee.Image, etc.
# ============================================================

def initialize_earth_engine():
    try:
        ee.Initialize(project=PROJECT_ID)
        print(
            f"Earth Engine initialized with project: "
            f"{PROJECT_ID}"
        )

    except ee.EEException:
        print("Earth Engine authentication required...")

        ee.Authenticate()

        ee.Initialize(project=PROJECT_ID)

        print(
            f"Earth Engine authenticated and initialized "
            f"with project: {PROJECT_ID}"
        )


# INITIALIZE NOW, not inside main()
initialize_earth_engine()


# ============================================================
# DATASETS
#
# Now it is safe to create Earth Engine objects.
# ============================================================

ERA5 = ee.ImageCollection(
    "ECMWF/ERA5_LAND/DAILY_AGGR"
)

CHIRPS = ee.ImageCollection(
    "UCSB-CHG/CHIRPS/DAILY"
)


# ============================================================
# MUNICIPALITIES
# ============================================================

def get_municipalities():

    municipios = (
        ee.FeatureCollection(MUNICIPALITIES_ASSET)
        .select([
            CAMPO_DPTO,
            CAMPO_NOM_DPTO,
            CAMPO_MPIO,
            CAMPO_MPIO_COMPLETO,
            CAMPO_NOM_MPIO,
        ])
    )

    return municipios


# ============================================================
# CLIMATE DATASETS
# ============================================================

ERA5 = ee.ImageCollection(
    "ECMWF/ERA5_LAND/DAILY_AGGR"
)

CHIRPS = ee.ImageCollection(
    "UCSB-CHG/CHIRPS/DAILY"
)


# ============================================================
# BUILD ONE DAILY ENVIRONMENTAL IMAGE
# ============================================================

def build_daily_environment_image(date):
    """
    Creates one multi-band image for a single calendar day.

    Variables:

        rain_mm_day
        temp_mean_c
        dewpoint_mean_c
        soil_water_l1_mean
        surface_runoff_mm_day
        total_evaporation_mm_day_ecmwf
        wind_u_mean_ms
        wind_v_mean_ms
        solar_radiation_mj_m2_day

    Important:
    - Temperature/dewpoint/soil water/wind are daily means.
    - Rain/runoff/evaporation/solar radiation are daily
      accumulated quantities.
    """

    date = ee.Date(date)
    next_date = date.advance(1, "day")

    # --------------------------------------------------------
    # ERA5-LAND
    # --------------------------------------------------------

    era = ee.Image(
        ERA5
        .filterDate(date, next_date)
        .first()
    )

    # --------------------------------------------------------
    # CHIRPS PRECIPITATION
    #
    # mm/day
    # --------------------------------------------------------

    rain = (
        ee.Image(
            CHIRPS
            .filterDate(date, next_date)
            .first()
        )
        .select("precipitation")
        .rename("rain_mm_day")
    )

    # --------------------------------------------------------
    # AIR TEMPERATURE
    #
    # Kelvin -> Celsius
    # Daily mean
    # --------------------------------------------------------

    temp_mean = (
        era
        .select("temperature_2m")
        .subtract(273.15)
        .rename("temp_mean_c")
    )

    # --------------------------------------------------------
    # DEW POINT
    #
    # Kelvin -> Celsius
    # Daily mean
    #
    # Keep this raw instead of calculating relative humidity
    # from daily averages. RH can be engineered later.
    # --------------------------------------------------------

    dewpoint_mean = (
        era
        .select("dewpoint_temperature_2m")
        .subtract(273.15)
        .rename("dewpoint_mean_c")
    )

    # --------------------------------------------------------
    # SURFACE SOIL WATER
    #
    # ERA5-Land layer 1:
    # approximately 0-7 cm depth.
    #
    # Units: volumetric fraction m3/m3
    # Daily mean.
    # --------------------------------------------------------

    soil_water = (
        era
        .select("volumetric_soil_water_layer_1")
        .rename("soil_water_l1_mean")
    )

    # --------------------------------------------------------
    # SURFACE RUNOFF
    #
    # ERA5 unit = meters water depth/day
    # Convert m -> mm.
    # --------------------------------------------------------

    surface_runoff = (
        era
        .select("surface_runoff_sum")
        .multiply(1000)
        .rename("surface_runoff_mm_day")
    )

    # --------------------------------------------------------
    # TOTAL EVAPORATION
    #
    # ERA5 unit = meters water equivalent.
    #
    # Convert m -> mm.
    #
    # IMPORTANT:
    # ECMWF convention generally gives evaporation as
    # NEGATIVE values.
    #
    # We intentionally preserve that sign convention here.
    # --------------------------------------------------------

    evaporation = (
        era
        .select("total_evaporation_sum")
        .multiply(1000)
        .rename("total_evaporation_mm_day_ecmwf")
    )

    # --------------------------------------------------------
    # WIND COMPONENTS
    #
    # Daily means in m/s.
    #
    # We intentionally keep U and V independently.
    #
    # sqrt(mean(U)^2 + mean(V)^2)
    # is NOT mathematically equivalent to daily mean
    # wind speed.
    # --------------------------------------------------------

    wind_u = (
        era
        .select("u_component_of_wind_10m")
        .rename("wind_u_mean_ms")
    )

    wind_v = (
        era
        .select("v_component_of_wind_10m")
        .rename("wind_v_mean_ms")
    )

    # --------------------------------------------------------
    # SOLAR RADIATION
    #
    # ERA5 = J/m² accumulated during the day.
    #
    # Convert:
    # J/m² -> MJ/m²/day
    # --------------------------------------------------------

    solar = (
        era
        .select(
            "surface_solar_radiation_downwards_sum"
        )
        .divide(1_000_000)
        .rename("solar_radiation_mj_m2_day")
    )

    # --------------------------------------------------------
    # COMBINE
    #
    # Put CHIRPS first intentionally.
    #
    # reduceRegions() uses the first band's projection
    # unless another CRS is specified.
    # --------------------------------------------------------

    image = (
        rain
        .addBands(temp_mean)
        .addBands(dewpoint_mean)
        .addBands(soil_water)
        .addBands(surface_runoff)
        .addBands(evaporation)
        .addBands(wind_u)
        .addBands(wind_v)
        .addBands(solar)
    )

    return image.set({
        "system:time_start": date.millis(),
        "date": date.format("YYYY-MM-dd"),
    })


# ============================================================
# REDUCE ONE DAY TO MUNICIPALITIES
# ============================================================

def reduce_day_to_municipalities(
    date,
    municipios
):

    date = ee.Date(date)

    image = build_daily_environment_image(
        date
    )

    stats = image.reduceRegions(
        collection=municipios,
        reducer=ee.Reducer.mean(),
        scale=ANALYSIS_SCALE,
        tileScale=TILE_SCALE,
        maxPixelsPerRegion=MAX_PIXELS_PER_REGION,
    )

    # --------------------------------------------------------
    # REMOVE GEOMETRY
    #
    # Extremely important for reducing exported file size.
    # --------------------------------------------------------

    def clean_feature(feature):

        feature = ee.Feature(feature)

        return ee.Feature(
            None,
            {
                # --------------------------------------------
                # TIME
                # --------------------------------------------

                "date":
                    date.format("YYYY-MM-dd"),

                "year":
                    date.get("year"),

                "month":
                    date.get("month"),

                "day_of_year":
                    date.getRelative(
                        "day",
                        "year"
                    ).add(1),

                # --------------------------------------------
                # DANE / DIVIPOLA
                # --------------------------------------------

                "dpto_ccdgo":
                    feature.get(
                        CAMPO_DPTO
                    ),

                "dpto_cnmbr":
                    feature.get(
                        CAMPO_NOM_DPTO
                    ),

                "mpio_ccdgo":
                    feature.get(
                        CAMPO_MPIO
                    ),

                "mpio_cdpmp":
                    feature.get(
                        CAMPO_MPIO_COMPLETO
                    ),

                "mpio_cnmbr":
                    feature.get(
                        CAMPO_NOM_MPIO
                    ),

                # --------------------------------------------
                # ENVIRONMENT
                # --------------------------------------------

                "rain_mm_day":
                    feature.get(
                        "rain_mm_day"
                    ),

                "temp_mean_c":
                    feature.get(
                        "temp_mean_c"
                    ),

                "dewpoint_mean_c":
                    feature.get(
                        "dewpoint_mean_c"
                    ),

                "soil_water_l1_mean":
                    feature.get(
                        "soil_water_l1_mean"
                    ),

                "surface_runoff_mm_day":
                    feature.get(
                        "surface_runoff_mm_day"
                    ),

                "total_evaporation_mm_day_ecmwf":
                    feature.get(
                        "total_evaporation_mm_day_ecmwf"
                    ),

                "wind_u_mean_ms":
                    feature.get(
                        "wind_u_mean_ms"
                    ),

                "wind_v_mean_ms":
                    feature.get(
                        "wind_v_mean_ms"
                    ),

                "solar_radiation_mj_m2_day":
                    feature.get(
                        "solar_radiation_mj_m2_day"
                    ),
            }
        )

    return stats.map(clean_feature)


# ============================================================
# BUILD ONE MONTH
# ============================================================

def build_month(
    year,
    month,
    municipios
):

    start = ee.Date.fromYMD(
        year,
        month,
        1
    )

    end = start.advance(
        1,
        "month"
    )

    number_days = (
        end
        .difference(
            start,
            "day"
        )
        .toInt()
    )

    dates = ee.List.sequence(
        0,
        number_days.subtract(1)
    ).map(
        lambda offset:
        start.advance(
            ee.Number(offset),
            "day"
        )
    )

    daily_collections = dates.map(
        lambda date:
        reduce_day_to_municipalities(
            date,
            municipios
        )
    )

    monthly_data = (
        ee.FeatureCollection(
            daily_collections
        )
        .flatten()
    )

    return monthly_data


# ============================================================
# EXPORT ONE MONTH
# ============================================================

def export_month(
    year,
    month,
    municipios
):

    data = build_month(
        year,
        month,
        municipios
    )

    filename = (
        f"dengue_environment_"
        f"{year}_{month:02d}"
    )

    task = ee.batch.Export.table.toDrive(
        collection=data,

        description=filename,

        folder=DRIVE_FOLDER,

        fileNamePrefix=filename,

        fileFormat="CSV",

        selectors=[
            "date",
            "year",
            "month",
            "day_of_year",

            "dpto_ccdgo",
            "dpto_cnmbr",

            "mpio_ccdgo",
            "mpio_cdpmp",
            "mpio_cnmbr",

            "rain_mm_day",
            "temp_mean_c",
            "dewpoint_mean_c",

            "soil_water_l1_mean",

            "surface_runoff_mm_day",
            "total_evaporation_mm_day_ecmwf",

            "wind_u_mean_ms",
            "wind_v_mean_ms",

            "solar_radiation_mj_m2_day",
        ],
    )

    task.start()

    print(
        f"Submitted {year}-{month:02d} "
        f"| task={task.id}"
    )

    return task


# ============================================================
# MAIN
# ============================================================

def main():

    municipios = get_municipalities()

    # Small getInfo request only for validation.
    municipality_count = (
        municipios
        .size()
        .getInfo()
    )

    print()
    print(
        f"Municipalities loaded: "
        f"{municipality_count:,}"
    )

    print(
        f"Years: {START_YEAR}-{END_YEAR}"
    )

    print(
        f"Analysis scale: "
        f"{ANALYSIS_SCALE:,} m"
    )

    print()
    print(
        "Submitting monthly exports..."
    )
    print()

    tasks = []

    for year in range(
        START_YEAR,
        END_YEAR + 1
    ):

        for month in range(
            1,
            13
        ):

            task = export_month(
                year,
                month,
                municipios
            )

            tasks.append(task)

    print()
    print("=" * 70)
    print(
        f"Submitted {len(tasks)} "
        f"Earth Engine export tasks."
    )
    print("=" * 70)

    print(
        f"\nGoogle Drive folder:"
        f"\n{DRIVE_FOLDER}"
    )


if __name__ == "__main__":
    main()
