from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List
from pandas import DataFrame, read_csv, to_numeric
from folium import CircleMarker, FeatureGroup, LayerControl, TileLayer, plugins, Map
from folium.features import LatLngPopup
from branca.colormap import LinearColormap
from numpy import nanmedian, nanmin, nanmax, ndarray


@dataclass
class ColumnConfig:
    lat: str = "lat"
    lon: str = "lon"
    value: str = "value"


class MagnetometerVisualizer:
    """
    Visualize magnetometer intensity as a heatmap over satellite imagery or animated plot.

    - Automatically decides bounding box from data and fits map to it.
    - Threshold value_threshold: points below this are ignored
    - Skips rows where GPS isn't ready (Has a startup time with no gps data).
    - Customizable column names via ColumnConfig object (If we decide to change in future)
    - Esri World Imagery (For satellite) and OSM as base layers, switchable via LayerControl.
    - Optional click popup that shows the clicked latitude/longitude
    """

    def __init__(
        self,
        csv_path: Path | str,
        columns: ColumnConfig | None = None,
        value_threshold: Optional[float] = None,
        skip_zero_coords: bool = True,
        drop_out_of_range: bool = True,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.columns = columns or ColumnConfig()
        self.value_threshold = value_threshold
        self.skip_zero_coords = skip_zero_coords
        self.drop_out_of_range = drop_out_of_range
        self.df: Optional[DataFrame] = None
        self._load_and_clean()

    def to_heatmap_html(
        self,
        output_path: Path | str,
        radius: int = 14,
        blur: int = 18,
        min_opacity: float = 0.2,
        add_points_layer: bool = False,
        use_osm_fallback: bool = True,
        click_popup: bool = True,
    ) -> Path:
        """
        Render the heatmap to an interactive HTML file with Esri satellite imagery + OSM base layers.
        If satellite tiles can't load then switch to OSM via the layer control.
        If click_popup is True, clicking anywhere shows a popup with Lat/Lon.
        """
        if self.df is None or self.df.empty:
            raise ValueError(
                "No valid GPS rows found to visualize. Try lowering the threshold value if you have data."
            )

        lats = self.df[self.columns.lat].to_numpy()
        lons = self.df[self.columns.lon].to_numpy()
        values = self.df[self.columns.value].to_numpy(dtype=float)

        center_lat = float(nanmedian(lats))
        center_lon = float(nanmedian(lons))
        m = Map(
            location=[center_lat, center_lon],
            zoom_start=16,
            control_scale=True,
            tiles=None,
        )

        # Creating Layers for Satelitte Images
        esri_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        esri_attr = (
            "Tiles &copy; Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, "
            "Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
        )
        TileLayer(
            tiles=esri_url,
            name="Satellite (Esri)",
            attr=esri_attr,
            overlay=False,
            control=True,
            max_zoom=19,
            show=True,
        ).add_to(m)

        if use_osm_fallback:
            TileLayer(
                tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                name="OSM",
                attr="&copy; OpenStreetMap contributors",
                overlay=False,
                control=True,
                max_zoom=19,
                show=False,
            ).add_to(m)

        # Normalize to [0,1] for heat scale
        vmin, vmax = float(nanmin(values)), float(nanmax(values))
        denom = (vmax - vmin) if vmax > vmin else 1.0
        weights01 = (values - vmin) / denom
        heat_data = [
            [float(lat), float(lon), float(w)]
            for lat, lon, w in zip(lats, lons, weights01)
        ]
        plugins.HeatMap(
            heat_data,
            name="Heatmap",
            radius=radius,
            blur=blur,
            min_opacity=min_opacity,
            max_zoom=19,
        ).add_to(m)

        cm = LinearColormap(
            colors=["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
            vmin=vmin,
            vmax=vmax,
        )

        cm.caption = f"Magnetometer intensity ({self.columns.value})"
        cm.add_to(m)

        if add_points_layer:
            fg = FeatureGroup(name="Sample points", overlay=True)
            for lat, lon, val in zip(lats, lons, values):
                CircleMarker(
                    location=[float(lat), float(lon)],
                    radius=3,
                    weight=1,
                    fill=True,
                    fill_opacity=0.8,
                    popup=f"{self.columns.value}={val:.3f}",
                ).add_to(fg)
            fg.add_to(m)

        sw, ne = self._bounds_with_pad(lats, lons, pad_ratio=0.02)
        m.fit_bounds([sw, ne])

        # Layer Control between Sat and OSM
        LayerControl(collapsed=False).add_to(m)

        if click_popup:
            m.add_child(LatLngPopup())

        output_path = Path(output_path)
        m.save(str(output_path))
        return output_path

    #### Helper Functions
    def _load_and_clean(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {self.csv_path}")

        raw = read_csv(self.csv_path)
        self._maybe_infer_columns(raw)
        df = raw.copy()

        for c in [self.columns.lat, self.columns.lon, self.columns.value]:
            df[c] = to_numeric(df[c], errors="coerce")

        df = df.dropna(subset=[self.columns.lat, self.columns.lon])

        if self.skip_zero_coords:
            df = df[~((df[self.columns.lat] == 0) & (df[self.columns.lon] == 0))]

        if self.drop_out_of_range:
            df = df[
                (df[self.columns.lat].between(-90, 90))
                & (df[self.columns.lon].between(-180, 180))
            ]

        if self.value_threshold is not None:
            df = df[df[self.columns.value] >= float(self.value_threshold)]

        df = df.dropna(subset=[self.columns.value])

        self.df = df.reset_index(drop=True)

    # TODO: Find out final structure
    def _maybe_infer_columns(self, raw: DataFrame) -> None:
        cols_lower = {c.lower(): c for c in raw.columns}
        lat_candidates = ["lat", "latitude", "gps_lat", "y", "lat_deg"]
        lon_candidates = ["lon", "lng", "longitude", "gps_lon", "x", "lon_deg"]
        val_candidates = [
            "fmag_ut",
            "mag",
            "magnetic",
            "field",
            "value",
            "strength",
            "reading",
            "mag_ut",
        ]

        def find(col_list: List[str], default: str) -> str:
            for key in col_list:
                if key in cols_lower:
                    return cols_lower[key]
            return default

        if self.columns.lat not in raw.columns:
            self.columns.lat = find(lat_candidates, self.columns.lat)
        if self.columns.lon not in raw.columns:
            self.columns.lon = find(lon_candidates, self.columns.lon)
        if self.columns.value not in raw.columns:
            self.columns.value = find(val_candidates, self.columns.value)

        missing = [
            c
            for c in [self.columns.lat, self.columns.lon, self.columns.value]
            if c not in raw.columns
        ]
        if missing:
            raise KeyError(
                "Could not infer required columns. "
                f"Looked for latitude='{self.columns.lat}', longitude='{self.columns.lon}', value='{self.columns.value}'. "
                f"Available columns: {list(raw.columns)}"
            )

    @staticmethod
    def _bounds_with_pad(
        lats: ndarray, lons: ndarray, pad_ratio: float = 0.02
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        lat_min, lat_max = float(nanmin(lats)), float(nanmax(lats))
        lon_min, lon_max = float(nanmin(lons)), float(nanmax(lons))
        dlat = max(1e-6, (lat_max - lat_min) * (1 + pad_ratio))
        dlon = max(1e-6, (lon_max - lon_min) * (1 + pad_ratio))
        lat_pad = (dlat - (lat_max - lat_min)) / 2
        lon_pad = (dlon - (lon_max - lon_min)) / 2
        sw = (lat_min - lat_pad, lon_min - lon_pad)
        ne = (lat_max + lat_pad, lon_max + lon_pad)
        return sw, ne


if __name__ == "__main__":
    simulations_dir = (
        Path.home()
        / "Desktop"
        / "Senior Year"
        / "Super_Senior"
        / "ECE 455"
        / "autonomous-boat"
        / "simulations"
    )

    data_file_dir = simulations_dir / "Data" / "Magnetometer_Data"
    data_file_path0 = data_file_dir / "init_magnetometer_data.csv"
    data_file_path1 = data_file_dir / "vietnam_mock_data.csv"

    test_cases = [(data_file_path0, 9), (data_file_path1, 0.02)]
    test_case = 0

    columns = ColumnConfig(lat="lat_deg", lon="lon_deg", value="fmag_uT")
    vis = MagnetometerVisualizer(
        test_cases[test_case][0],
        columns=columns,
        value_threshold=test_cases[test_case][1],
    )

    vis.to_heatmap_html(
        simulations_dir / "heat_map_files" / "magnetometer_heatmap_init_test.html",
        radius=14,
        blur=18,
        min_opacity=0.2,
        add_points_layer=False,
        use_osm_fallback=True,
        click_popup=True,
    )
