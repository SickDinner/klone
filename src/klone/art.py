from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any, Mapping

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
except ImportError as error:  # pragma: no cover - exercised through dependency guard
    Image = None
    ImageChops = None
    ImageFilter = None
    ImageOps = None
    ImageStat = None
    PIL_IMPORT_ERROR = error
else:  # pragma: no cover - import branch only
    PIL_IMPORT_ERROR = None

from .guards import output_guard
from .repository import KloneRepository
from .schemas import ArtAssetMetricsRecord, PublicCapabilityRecord, ServiceSeamRecord


ART_ANALYSIS_VERSION = "v1.1.formal_image_metrics"
MAX_ANALYSIS_SIZE = 128
SYMMETRY_SAMPLE_SIZE = 64
EDGE_THRESHOLD = 32
DARK_PIXEL_THRESHOLD = 64
LIGHT_PIXEL_THRESHOLD = 192
INK_PIXEL_THRESHOLD = 224


class ArtLabError(RuntimeError):
    pass


class ArtDependencyError(ArtLabError):
    pass


class UnsupportedArtAssetError(ArtLabError):
    pass


class ArtAssetSourceMissingError(ArtLabError):
    pass


def _require_pillow() -> None:
    if PIL_IMPORT_ERROR is not None:
        raise ArtDependencyError(
            "Pillow is required for art metrics analysis but is not installed."
        ) from PIL_IMPORT_ERROR


def _resampling_lanczos():
    _require_pillow()
    resampling = getattr(Image, "Resampling", None)
    return resampling.LANCZOS if resampling is not None else Image.LANCZOS


def _round_metric(value: float) -> float:
    return round(float(value), 4)


def _orientation_for_dimensions(width: int, height: int) -> str:
    if width == height:
        return "square"
    ratio = width / max(height, 1)
    if 0.95 <= ratio <= 1.05:
        return "square"
    return "landscape" if width > height else "portrait"


def _downscale_for_analysis(image) -> Any:
    sampled = image.copy()
    sampled.thumbnail((MAX_ANALYSIS_SIZE, MAX_ANALYSIS_SIZE), _resampling_lanczos())
    return sampled


def _symmetry_score(image, *, axis: str) -> float:
    if axis == "vertical":
        mirrored = ImageOps.mirror(image)
    else:
        mirrored = ImageOps.flip(image)
    difference = ImageChops.difference(image, mirrored)
    mean_difference = ImageStat.Stat(difference).mean[0]
    return max(0.0, 1.0 - (mean_difference / 255.0))


def _colorfulness(rgb_pixels: list[tuple[int, int, int]]) -> float:
    if not rgb_pixels:
        return 0.0

    rg_values: list[float] = []
    yb_values: list[float] = []
    for red, green, blue in rgb_pixels:
        rg_values.append(abs(red - green))
        yb_values.append(abs((red + green) / 2.0 - blue))

    mean_rg = sum(rg_values) / len(rg_values)
    mean_yb = sum(yb_values) / len(yb_values)
    std_rg = sqrt(sum((value - mean_rg) ** 2 for value in rg_values) / len(rg_values))
    std_yb = sqrt(sum((value - mean_yb) ** 2 for value in yb_values) / len(yb_values))
    return (sqrt(std_rg**2 + std_yb**2) + (0.3 * sqrt(mean_rg**2 + mean_yb**2))) / 255.0


def _darkness_center_of_mass(gray_pixels: list[int], *, width: int, height: int) -> tuple[float, float]:
    weighted_x = 0.0
    weighted_y = 0.0
    total_weight = 0.0

    for index, grayscale_value in enumerate(gray_pixels):
        x = index % width
        y = index // width
        weight = 255 - grayscale_value
        if weight <= 0:
            continue
        weighted_x += x * weight
        weighted_y += y * weight
        total_weight += weight

    if total_weight == 0:
        return 0.5, 0.5

    normalized_x = weighted_x / total_weight / max(width - 1, 1)
    normalized_y = weighted_y / total_weight / max(height - 1, 1)
    return normalized_x, normalized_y


def _analyze_image_file(path: Path) -> dict[str, Any]:
    _require_pillow()
    warnings: list[str] = []

    with Image.open(path) as opened:
        width_px, height_px = opened.size
        rgb = opened.convert("RGB")

    if width_px < 32 or height_px < 32:
        warnings.append("small_source_image")

    sampled = _downscale_for_analysis(rgb)
    sample_width_px, sample_height_px = sampled.size
    if sample_width_px != width_px or sample_height_px != height_px:
        warnings.append("downscaled_for_analysis")

    grayscale = sampled.convert("L")
    edge_map = grayscale.filter(ImageFilter.FIND_EDGES)
    symmetry_source = grayscale.resize(
        (SYMMETRY_SAMPLE_SIZE, SYMMETRY_SAMPLE_SIZE),
        _resampling_lanczos(),
    )

    gray_pixels = list(grayscale.getdata())
    edge_pixels = list(edge_map.getdata())
    rgb_pixels = list(sampled.getdata())
    total_pixels = max(len(gray_pixels), 1)

    brightness_stat = ImageStat.Stat(grayscale)
    dark_pixel_ratio = sum(1 for value in gray_pixels if value < DARK_PIXEL_THRESHOLD) / total_pixels
    light_pixel_ratio = sum(1 for value in gray_pixels if value > LIGHT_PIXEL_THRESHOLD) / total_pixels
    ink_coverage_ratio = sum(1 for value in gray_pixels if value < INK_PIXEL_THRESHOLD) / total_pixels
    edge_density = sum(1 for value in edge_pixels if value > EDGE_THRESHOLD) / total_pixels
    center_of_mass_x, center_of_mass_y = _darkness_center_of_mass(
        gray_pixels,
        width=sample_width_px,
        height=sample_height_px,
    )

    quantized = sampled.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    color_bins = quantized.getcolors(maxcolors=16) or []

    return {
        "width_px": width_px,
        "height_px": height_px,
        "sample_width_px": sample_width_px,
        "sample_height_px": sample_height_px,
        "orientation": _orientation_for_dimensions(width_px, height_px),
        "aspect_ratio": _round_metric(width_px / max(height_px, 1)),
        "brightness_mean": _round_metric(brightness_stat.mean[0] / 255.0),
        "contrast_stddev": _round_metric(brightness_stat.stddev[0] / 255.0),
        "dark_pixel_ratio": _round_metric(dark_pixel_ratio),
        "light_pixel_ratio": _round_metric(light_pixel_ratio),
        "ink_coverage_ratio": _round_metric(ink_coverage_ratio),
        "edge_density": _round_metric(edge_density),
        "colorfulness": _round_metric(_colorfulness(rgb_pixels)),
        "entropy": _round_metric(grayscale.entropy() / 8.0),
        "symmetry_vertical": _round_metric(_symmetry_score(symmetry_source, axis="vertical")),
        "symmetry_horizontal": _round_metric(_symmetry_score(symmetry_source, axis="horizontal")),
        "center_of_mass_x": _round_metric(center_of_mass_x),
        "center_of_mass_y": _round_metric(center_of_mass_y),
        "quantized_color_count": len(color_bins),
        "warnings": warnings,
    }


class ArtLabService:
    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository

    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="art-lab-service",
            name="ArtLabService",
            implementation="in_process_read_only_shell",
            status="formal_metrics_shell",
            notes=[
                "Computes deterministic formal image metrics over existing governed image assets.",
                "Blocks psychological or clinical inference and does not mutate ingest or asset rows.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="art.asset.metrics.read",
                name="Asset Formal Metrics",
                category="art",
                path="/api/art/assets/{asset_id}/metrics",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read deterministic formal image metrics for one governed image asset.",
                backed_by=["ArtLabService", "PolicyService"],
            ),
        ]

    def get_asset_metrics(
        self,
        *,
        asset_id: int,
        room_id: str,
    ) -> ArtAssetMetricsRecord | None:
        row = self.repository.get_asset(asset_id, room_id=room_id)
        if row is None:
            return None
        return self.metrics_from_asset_row(row)

    def metrics_from_asset_row(self, row: Mapping[str, Any]) -> ArtAssetMetricsRecord:
        if str(row["asset_kind"]) != "image":
            raise UnsupportedArtAssetError("Formal art metrics currently support image assets only.")

        file_path = Path(str(row["path"]))
        if not file_path.exists():
            raise ArtAssetSourceMissingError(
                f"Source file for art metrics no longer exists: {file_path}"
            )

        analysis = _analyze_image_file(file_path)
        decision = output_guard.evaluate(classification_level=str(row["classification_level"]))
        relative_path = str(row["relative_path"])
        file_name = str(row["file_name"])
        if decision.decision == "summary_only":
            relative_path = "[summary-only]"
            file_name = "[summary-only]"

        return ArtAssetMetricsRecord(
            analysis_version=ART_ANALYSIS_VERSION,
            asset_id=int(row["id"]),
            room_id=str(row["room_id"]),
            classification_level=str(row["classification_level"]),
            asset_kind=str(row["asset_kind"]),
            file_name=file_name,
            relative_path=relative_path,
            width_px=int(analysis["width_px"]),
            height_px=int(analysis["height_px"]),
            sample_width_px=int(analysis["sample_width_px"]),
            sample_height_px=int(analysis["sample_height_px"]),
            orientation=str(analysis["orientation"]),
            aspect_ratio=float(analysis["aspect_ratio"]),
            brightness_mean=float(analysis["brightness_mean"]),
            contrast_stddev=float(analysis["contrast_stddev"]),
            dark_pixel_ratio=float(analysis["dark_pixel_ratio"]),
            light_pixel_ratio=float(analysis["light_pixel_ratio"]),
            ink_coverage_ratio=float(analysis["ink_coverage_ratio"]),
            edge_density=float(analysis["edge_density"]),
            colorfulness=float(analysis["colorfulness"]),
            entropy=float(analysis["entropy"]),
            symmetry_vertical=float(analysis["symmetry_vertical"]),
            symmetry_horizontal=float(analysis["symmetry_horizontal"]),
            center_of_mass_x=float(analysis["center_of_mass_x"]),
            center_of_mass_y=float(analysis["center_of_mass_y"]),
            quantized_color_count=int(analysis["quantized_color_count"]),
            notes=[
                "Formal image metrics only; no personality or clinical inference is performed.",
                "Metrics are computed deterministically from the current asset file.",
            ],
            warnings=list(analysis["warnings"]),
        )
