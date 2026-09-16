# ApPPD tools — selected workflow revision 17 (2026-09-16).
# Full replacement module; existing extraction and reader interfaces retained.
# Joint source statics/window trends, final rollback checks, always-on numeric snapshot.
import numpy as np
import os
import shapefile
import json
from scipy.spatial import cKDTree, Delaunay

from .ApPPDReader import ApPPDReader

# ------------------------------------------------------------
# TRACE UTILITIES
# ------------------------------------------------------------

def get_channel_traces(traces, channel):
    """
    Return list of trace dictionaries belonging to a channel.
    """
    return [t for t in traces if t["channel"] == channel]


def get_trace_count(traces, channel):
    """
    Number of traces in a channel.
    """
    return len(get_channel_traces(traces, channel))


def get_trace_offsets(traces, channel):
    """
    Return byte offsets for trace data in file.
    """
    ch = get_channel_traces(traces, channel)
    return np.array([t["data_offset"] for t in ch])


def get_trace_ids(traces, channel):
    """
    Return global trace IDs.
    """
    ch = get_channel_traces(traces, channel)
    return np.array([t["gid"] for t in ch])


# ------------------------------------------------------------
# COORDINATE UTILITIES
# ------------------------------------------------------------

def get_trace_coordinates(traces, channel):
    """
    Return x,y,z arrays for a channel.
    """
    ch = get_channel_traces(traces, channel)

    x = np.array([t["x"] for t in ch])
    y = np.array([t["y"] for t in ch])
    z = np.array([t["z"] for t in ch])

    return x, y, z


def compute_trace_spacing(traces, channel):
    """
    Compute spacing between consecutive traces.
    """
    x, y, _ = get_trace_coordinates(traces, channel)

    dx = np.diff(x)
    dy = np.diff(y)

    spacing = np.sqrt(dx**2 + dy**2)

    return spacing


def compute_cumulative_distance(traces, channel):
    """
    Cumulative survey distance along the profile.
    """
    spacing = compute_trace_spacing(traces, channel)

    cumulative = np.zeros(len(spacing) + 1)
    cumulative[1:] = np.cumsum(spacing)

    return cumulative


def trace_spacing_statistics(traces, channel):
    """
    Useful diagnostic for checking resampling.
    """
    spacing = compute_trace_spacing(traces, channel)

    stats = {
        "mean": np.mean(spacing),
        "std": np.std(spacing),
        "min": np.min(spacing),
        "max": np.max(spacing)
    }

    return stats


# ------------------------------------------------------------
# TRACE → WORLD COORDINATE LOOKUP
# ------------------------------------------------------------

def trace_index_to_world(traces, channel, trace_index):
    """
    Convert radargram trace index to world coordinates.
    """
    ch = get_channel_traces(traces, channel)

    tr = ch[trace_index]

    return tr["x"], tr["y"], tr["z"]

def export_trace_coordinates(traces, ap_ppd_filepath):
    output_path = (
        os.path.splitext(ap_ppd_filepath)[0]
        + "_trace_coordinates.shp"
    )

    with shapefile.Writer(
        output_path,
        shapeType=shapefile.POINT
    ) as writer:

        writer.field("GID", "N", decimal=0)
        writer.field("CHANNEL", "N", decimal=0)
        writer.field("TRACE", "N", decimal=0)
        writer.field("Z", "F", size=18, decimal=4)

        for trace in traces:
            writer.point(trace["x"], trace["y"])
            writer.record(
                trace["gid"],
                trace["channel"],
                trace["trace"],
                trace["z"]
            )

    print(
        f"Exported {len(traces)} trace coordinates to: "
        f"{output_path}"
    )

    return output_path

def export_folder_trace_coordinates(folder_path):
    """
    Read all ApPPD files in a folder and export their trace positions
    into one combined point shapefile.
    """
    valid_extensions = (".ap_ppd", ".apppd")

    ap_ppd_files = sorted(
        os.path.join(folder_path, filename)
        for filename in os.listdir(folder_path)
        if filename.lower().endswith(valid_extensions)
    )

    if not ap_ppd_files:
        raise ValueError(
            "No ApPPD files were found in the selected folder."
        )

    folder_name = os.path.basename(os.path.normpath(folder_path))

    output_path = os.path.join(
        folder_path,
        f"{folder_name}_trace_coordinates.shp"
    )

    total_traces = 0
    successful_files = 0
    failed_files = []
    epsg_values = set()

    with shapefile.Writer(
        output_path,
        shapeType=shapefile.POINT
    ) as writer:

        # Shapefile field names must not exceed ten characters.
        writer.field("GLOBAL_ID", "N", decimal=0)
        writer.field("FILE_ID", "N", decimal=0)
        writer.field("SOURCE", "C", size=254)
        writer.field("LOCAL_GID", "N", decimal=0)
        writer.field("CHANNEL", "N", decimal=0)
        writer.field("TRACE", "N", decimal=0)
        writer.field("Z", "F", size=18, decimal=4)

        file_results = []

        for file_id, filepath in enumerate(ap_ppd_files):
            filename = os.path.basename(filepath)

            print(
                f"Reading ApPPD file "
                f"{file_id + 1}/{len(ap_ppd_files)}: {filename}"
            )

            try:
                reader = ApPPDReader(filepath)
                header, traces = reader.read()

                file_results.append(
                    (filepath, header, traces)
                )

                epsg = header.get("epsg")

                if epsg:
                    epsg_values.add(epsg)

                for trace in traces:
                    writer.point(
                        trace["x"],
                        trace["y"]
                    )

                    writer.record(
                        total_traces,
                        file_id,
                        filename,
                        trace["gid"],
                        trace["channel"],
                        trace["trace"],
                        trace["z"]
                    )

                    total_traces += 1

                successful_files += 1

            except Exception as exc:
                failed_files.append((filename, str(exc)))
                print(f"Failed to process {filename}: {exc}")

    create_ap_ppd_trace_cache(
        folder_path,
        file_results
    )

    print("\n--- Combined coordinate export complete ---")
    print(f"Files found: {len(ap_ppd_files)}")
    print(f"Files processed successfully: {successful_files}")
    print(f"Files failed: {len(failed_files)}")
    print(f"Total trace points: {total_traces}")
    print(f"Output: {output_path}")

    if len(epsg_values) == 1:
        print(f"EPSG: {next(iter(epsg_values))}")
    elif len(epsg_values) > 1:
        print(
            "Warning: the ApPPD files contain different EPSG codes: "
            f"{sorted(epsg_values)}"
        )

    for filename, error in failed_files:
        print(f"  Failed: {filename}: {error}")

    return output_path

def create_ap_ppd_trace_cache(
    folder_path,
    file_results
):
    """
    Create a permanent spatial trace index for an ApPPD folder.

    file_results must contain tuples:
        (filepath, header, traces)
    """
    total_traces = sum(
        len(traces)
        for filepath, header, traces in file_results
    )

    index_dtype = np.dtype([
        ("x", "<f8"),
        ("y", "<f8"),
        ("z", "<f8"),
        ("file_id", "<i4"),
        ("data_offset", "<i8"),
        ("channel", "<i2"),
        ("trace", "<i4"),
        ("local_gid", "<i8"),
        ("time_zero", "<i2"),
        ("first_zero", "<i2"),
        ("second_zero", "<i2"),
        ("section_incorrect", "<i2"),
        ("time_zero_adjusted", "<i2"),
        ("gps_flags", "<u2"),
    ])

    trace_index = np.empty(
        total_traces,
        dtype=index_dtype
    )

    manifest = {
        "format": "ApInsight ApPPD trace index",
        "version": 1,
        "files": []
    }

    position = 0

    for file_id, (filepath, header, traces) in enumerate(
        file_results
    ):
        filename = os.path.basename(filepath)

        manifest["files"].append({
            "file_id": file_id,
            "filename": filename,
            "size": os.path.getsize(filepath),
            "modified": os.path.getmtime(filepath),
            "header": header
        })

        end_position = position + len(traces)
        file_slice = trace_index[position:end_position]

        file_slice["x"] = [
            trace["x"] for trace in traces
        ]
        file_slice["y"] = [
            trace["y"] for trace in traces
        ]
        file_slice["z"] = [
            trace["z"] for trace in traces
        ]
        file_slice["file_id"] = file_id
        file_slice["data_offset"] = [
            trace["data_offset"] for trace in traces
        ]
        file_slice["channel"] = [
            trace["channel"] for trace in traces
        ]
        file_slice["trace"] = [
            trace["trace"] for trace in traces
        ]
        file_slice["local_gid"] = [
            trace["gid"] for trace in traces
        ]

        for field in (
                "time_zero",
                "first_zero",
                "second_zero",
                "section_incorrect",
                "time_zero_adjusted",
                "gps_flags",
        ):
            file_slice[field] = [trace[field] for trace in traces]

        position = end_position

    index_path = os.path.join(
        folder_path,
        "ap_ppd_trace_index.npy"
    )

    manifest_path = os.path.join(
        folder_path,
        "ap_ppd_manifest.json"
    )

    np.save(index_path, trace_index)

    with open(
        manifest_path,
        "w",
        encoding="utf-8"
    ) as manifest_file:
        json.dump(
            manifest,
            manifest_file,
            indent=2
        )

    print(f"Created trace index: {index_path}")
    print(f"Created trace manifest: {manifest_path}")
    print(f"Indexed traces: {total_traces}")

    return index_path, manifest_path

def extract_ap_ppd_trace_coordinates_from_section(
    trace_index,
    vertices,
    output_folder,
    section_name,
    max_distance=0.50,
    export_diagnostics=False,
):
    """
    Export the section line and trace points within max_distance.

    Coordinates must share the same projected CRS, with metre units.
    Returns the selected trace records and their distances to the line.
    """
    vertices = np.asarray(vertices, dtype=np.float64)

    if (
        vertices.ndim != 2
        or vertices.shape[1] != 2
        or len(vertices) < 2
        or not np.isfinite(vertices).all()
    ):
        raise ValueError("Expected at least two valid x/y vertices.")

    if not np.isfinite(max_distance) or max_distance < 0:
        raise ValueError("Search distance must be finite and non-negative.")

    segments = np.diff(vertices, axis=0)
    lengths_squared = np.sum(segments ** 2, axis=1)

    if not np.any(lengths_squared > 0):
        raise ValueError("The section line has zero length.")

    # First narrow the search to the expanded bounding box.
    minimum = vertices.min(axis=0) - max_distance
    maximum = vertices.max(axis=0) + max_distance

    x = trace_index["x"]
    y = trace_index["y"]

    candidate_rows = np.flatnonzero(
        (x >= minimum[0])
        & (x <= maximum[0])
        & (y >= minimum[1])
        & (y <= maximum[1])
    )

    points = np.column_stack((
        x[candidate_rows],
        y[candidate_rows],
    ))

    if export_diagnostics:
        print(f"Bounding-box candidates: {len(points)}")

    # Calculate each candidate's shortest distance to any segment.
    min_distance_squared = np.full(len(points), np.inf)

    for start, direction, length_squared in zip(
        vertices[:-1], segments, lengths_squared
    ):
        if length_squared == 0:
            continue  # Repeated consecutive vertex.

        relative = points - start

        # Position along the segment: 0 = start, 1 = end.
        fraction = np.clip(
            (relative @ direction) / length_squared,
            0.0,
            1.0,
        )

        offset = relative - fraction[:, None] * direction
        distance_squared = np.sum(offset ** 2, axis=1)

        np.minimum(
            min_distance_squared,
            distance_squared,
            out=min_distance_squared,
        )

    keep = min_distance_squared <= max_distance ** 2
    selected_rows = candidate_rows[keep]
    selected_traces = trace_index[selected_rows]
    distances = np.sqrt(min_distance_squared[keep])

    # Produce filenames from the section name.
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in section_name
    ) or "polysection"

    line_path = os.path.join(
        output_folder, f"{safe_name}_line.shp"
    )
    points_path = os.path.join(
        output_folder, f"{safe_name}_trace_coordinates.shp"
    )

    if export_diagnostics:
        # Export the original polyline.
        with shapefile.Writer(
            line_path, shapeType=shapefile.POLYLINE
        ) as writer:
            writer.field("NAME", "C", size=254)
            writer.field("RADIUS_M", "F", size=18, decimal=3)

            writer.line([vertices.tolist()])
            writer.record(section_name, max_distance)

        # Export each matching trace once, retaining its cache references.
        with shapefile.Writer(
            points_path, shapeType=shapefile.POINT
        ) as writer:
            writer.field("INDEX_ROW", "N", size=18, decimal=0)
            writer.field("FILE_ID", "N", size=10, decimal=0)
            writer.field("LOCAL_GID", "N", size=18, decimal=0)
            writer.field("CHANNEL", "N", size=10, decimal=0)
            writer.field("TRACE", "N", size=18, decimal=0)
            writer.field("OFFSET", "N", size=20, decimal=0)
            writer.field("Z", "F", size=18, decimal=4)
            writer.field("DIST_M", "F", size=18, decimal=6)

            for row, trace, distance in zip(
                selected_rows, selected_traces, distances
            ):
                writer.point(float(trace["x"]), float(trace["y"]))
                writer.record(
                    int(row),
                    int(trace["file_id"]),
                    int(trace["local_gid"]),
                    int(trace["channel"]),
                    int(trace["trace"]),
                    int(trace["data_offset"]),
                    float(trace["z"]),
                    float(distance),
                )

    if export_diagnostics:
        print(f"Traces within {max_distance:.2f} m: {len(selected_traces)}")
    if export_diagnostics:
        print(f"Section line: {line_path}")
    if export_diagnostics:
        print(f"Trace coordinates: {points_path}")

    return selected_traces, distances

def test_section_extraction_methods(
    traces,
    vertices,
    output_folder,
    section_name,
    spacing=0.05,
    max_nearest_distance=0.20,
    max_triangle_edge=0.35,
    diagnostics=False,
    export_diagnostics=False,
):
    """
    Compare nearest-trace and triangular linear interpolation geometry.

    All coordinates must use the same projected CRS in metres.
    Returned trace indices refer to the supplied `traces` array.
    No amplitudes are read.
    """
    vertices = np.asarray(vertices, dtype=np.float64)

    if (
        vertices.ndim != 2
        or vertices.shape[1] != 2
        or len(vertices) < 2
        or not np.isfinite(vertices).all()
    ):
        raise ValueError("Expected at least two finite x/y vertices.")

    for value in (spacing, max_nearest_distance, max_triangle_edge):
        if not np.isfinite(value) or value <= 0:
            raise ValueError("Spacing and distance limits must be positive.")

    # Remove consecutive duplicate vertices.
    lengths = np.linalg.norm(np.diff(vertices, axis=0), axis=1)
    vertices = vertices[np.r_[True, lengths > 0]]

    if len(vertices) < 2:
        raise ValueError("The section has zero length.")

    # 1. Sample by cumulative distance along the original polyline.
    lengths = np.linalg.norm(np.diff(vertices, axis=0), axis=1)
    vertex_distances = np.r_[0.0, np.cumsum(lengths)]
    total_length = vertex_distances[-1]

    distances = np.arange(0.0, total_length, spacing)

    # Avoid an almost-duplicate endpoint from floating-point rounding.
    distances = distances[distances < total_length - 1e-9]
    distances = np.r_[distances, total_length]

    sample_xy = np.column_stack([
        np.interp(distances, vertex_distances, vertices[:, axis])
        for axis in range(2)
    ])

    trace_xy = np.column_stack((traces["x"], traces["y"]))

    usable_rows, excluded_rows, excluded_chainage = (
        filter_ap_ppd_trace_quality(
            traces,
            vertices,
            output_folder,
            section_name,
            export_diagnostics=export_diagnostics,
        )
    )

    if len(usable_rows) < 3:
        raise ValueError("Too few usable traces for triangulation.")

    unique_xy, representative_rows, coordinate_counts = np.unique(
        trace_xy[usable_rows],
        axis=0,
        return_index=True,
        return_counts=True,
    )

    # Map filtered-array indices back to the ORIGINAL corridor rows.
    representative_rows = usable_rows[representative_rows]

    if export_diagnostics:
        print(f"Unique usable positions: {len(unique_xy)}")
    if export_diagnostics:
        print(
            "Additional usable traces at repeated positions:",
            len(usable_rows) - len(unique_xy),
        )

    if len(unique_xy) < 3:
        raise ValueError("Need at least three unique trace positions.")

    # Keep both the original coordinates and the unique geometry.
    origin = vertices[0]
    local_traces = trace_xy - origin
    local_unique = unique_xy - origin
    local_samples = sample_xy - origin

    # Nearest-trace selection on unique positions.
    tree = cKDTree(local_unique)
    nearest_distance, nearest_unique_index = tree.query(local_samples)

    # Map back to rows in the ORIGINAL supplied traces array.
    nearest_index = representative_rows[nearest_unique_index]
    nearest_valid = nearest_distance <= max_nearest_distance

    # Triangulate only unique positions.
    triangulation = Delaunay(local_unique)
    simplex = triangulation.find_simplex(local_samples)
    inside = simplex >= 0
    inside_rows = np.flatnonzero(inside)

    triangle_indices = np.full((len(sample_xy), 3), -1, dtype=np.int64)
    triangle_weights = np.full((len(sample_xy), 3), np.nan)
    triangle_edge = np.full(len(sample_xy), np.nan)

    if len(inside_rows):
        selected_simplex = simplex[inside]

        # Triangle vertices initially refer to the unique-coordinate array.
        unique_neighbours = triangulation.simplices[selected_simplex]

        # Convert them to rows in the original traces array.
        neighbours = representative_rows[unique_neighbours]

        # Convert x/y positions to barycentric weights.
        transform = triangulation.transform[selected_simplex]
        relative = local_samples[inside] - transform[:, 2, :]

        first_two = np.einsum(
            "nij,nj->ni",
            transform[:, :2, :],
            relative,
        )

        weights = np.column_stack((
            first_two,
            1.0 - first_two.sum(axis=1),
        ))

        triangle_indices[inside] = neighbours
        triangle_weights[inside] = weights

        triangle_xy = local_traces[neighbours]
        edge_lengths = np.column_stack([
            np.linalg.norm(
                triangle_xy[:, a] - triangle_xy[:, b], axis=1
            )
            for a, b in ((0, 1), (1, 2), (2, 0))
        ])

        triangle_edge[inside] = edge_lengths.max(axis=1)

    weights_valid = (
        np.isfinite(triangle_weights).all(axis=1)
        & (triangle_weights >= -1e-10).all(axis=1)
        & (triangle_weights <= 1.0 + 1e-10).all(axis=1)
    )

    triangle_valid = (
        inside
        & weights_valid
        & (triangle_edge <= max_triangle_edge)
    )

    # Remove negligible numerical negatives from accepted weights.
    triangle_weights[triangle_valid] = np.clip(
        triangle_weights[triangle_valid], 0.0, 1.0
    )
    triangle_weights[triangle_valid] /= (
        triangle_weights[triangle_valid].sum(axis=1, keepdims=True)
    )

    # 4. Export diagnostics.
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in section_name
    ) or "polysection"

    points_path = os.path.join(
        output_folder, f"{safe_name}_sampling_points.shp"
    )
    links_path = os.path.join(
        output_folder, f"{safe_name}_sampling_links.shp"
    )

    def optional_float(value):
        return float(value) if np.isfinite(value) else None

    if export_diagnostics:
        with shapefile.Writer(
            points_path, shapeType=shapefile.POINT
        ) as writer:
            writer.field("SAMPLE_ID", "N", size=12)
            writer.field("CHAIN_M", "F", size=18, decimal=4)
            writer.field("NN_DIST", "F", size=18, decimal=6)
            writer.field("NN_OK", "N", size=1)
            writer.field("TRI_EDGE", "F", size=18, decimal=6)
            writer.field("TRI_OK", "N", size=1)

            for i, point in enumerate(sample_xy):
                writer.point(float(point[0]), float(point[1]))
                writer.record(
                    i,
                    float(distances[i]),
                    float(nearest_distance[i]),
                    int(nearest_valid[i]),
                    optional_float(triangle_edge[i]),
                    int(triangle_valid[i]),
                )

        with shapefile.Writer(
            links_path, shapeType=shapefile.POLYLINE
        ) as writer:
            writer.field("SAMPLE_ID", "N", size=12)
            writer.field("METHOD", "C", size=10)
            writer.field("SUBSET_ROW", "N", size=18)
            writer.field("FILE_ID", "N", size=10)
            writer.field("LOCAL_GID", "N", size=18)
            writer.field("CHANNEL", "N", size=10)
            writer.field("TRACE", "N", size=18)
            writer.field("WEIGHT", "F", size=18, decimal=10)
            writer.field("DIST_M", "F", size=18, decimal=6)
            writer.field("VALID", "N", size=1)

            for i, point in enumerate(sample_xy):
                connections = [
                    (
                        "nearest",
                        int(nearest_index[i]),
                        1.0,
                        nearest_valid[i],
                    )
                ]

                if inside[i]:
                    connections.extend(
                        (
                            "linear",
                            int(row),
                            float(weight),
                            triangle_valid[i],
                        )
                        for row, weight in zip(
                            triangle_indices[i], triangle_weights[i]
                        )
                    )

                for method, row, weight, valid in connections:
                    trace = traces[row]
                    target = trace_xy[row]

                    writer.line([[point.tolist(), target.tolist()]])
                    writer.record(
                        i,
                        method,
                        row,
                        int(trace["file_id"]),
                        int(trace["local_gid"]),
                        int(trace["channel"]),
                        int(trace["trace"]),
                        optional_float(weight),
                        float(np.linalg.norm(target - point)),
                        int(valid),
                    )

    if export_diagnostics:
        print("\n--- Section sampling comparison ---")
    if export_diagnostics:
        print(f"Length: {total_length:.3f} m")
    if export_diagnostics:
        print(f"Output positions: {len(sample_xy)}")
    if export_diagnostics:
        print(f"Spacing: {spacing:.3f} m (last interval may be shorter)")
    if export_diagnostics:
        print(f"Valid nearest positions: {nearest_valid.sum()}/{len(sample_xy)}")
    if export_diagnostics:
        print(f"Valid linear positions: {triangle_valid.sum()}/{len(sample_xy)}")
    if export_diagnostics:
        print(f"Outside triangulation: {(~inside).sum()}")
    if export_diagnostics:
        print(f"Sampling points: {points_path}")
    if export_diagnostics:
        print(f"Sampling links: {links_path}")

    if diagnostics:
        plot_section_sampling_diagnostics(
            trace_xy=trace_xy,
            vertices=vertices,
            sample_xy=sample_xy,
            distances=distances,
            nearest_index=nearest_index,
            nearest_distance=nearest_distance,
            triangle_indices=triangle_indices,
            triangle_weights=triangle_weights,
            triangle_edge=triangle_edge,
            triangle_valid=triangle_valid,
            output_path=os.path.join(
                output_folder,
                f"{safe_name}_sampling_diagnostics.png",
            ),
            max_nearest_distance=max_nearest_distance,
            max_triangle_edge=max_triangle_edge,
            inspect_distance=10.0,
        )

        inspect_row = int(np.argmin(np.abs(distances - 10.0)))

        if triangle_valid[inspect_row]:
            diagnostic_rows = triangle_indices[inspect_row]
        else:
            diagnostic_rows = [nearest_index[inspect_row]]

        test_ap_ppd_trace_reading(
            traces=traces,
            selected_rows=diagnostic_rows,
            folder_path=output_folder,
            output_path=os.path.join(
                output_folder,
                f"{safe_name}_trace_reading_test.png",
            ),
        )

    return {
        "sample_xy": sample_xy,
        "quality_filtered": True,
        "excluded_rows": excluded_rows,
        "excluded_chainage": excluded_chainage,
        "distance": distances,
        "nearest_index": nearest_index,
        "nearest_distance": nearest_distance,
        "nearest_valid": nearest_valid,
        "triangle_indices": triangle_indices,
        "triangle_weights": triangle_weights,
        "triangle_edge": triangle_edge,
        "triangle_valid": triangle_valid,
    }



def plot_section_sampling_diagnostics(
    trace_xy,
    vertices,
    sample_xy,
    distances,
    nearest_index,
    nearest_distance,
    triangle_indices,
    triangle_weights,
    triangle_edge,
    triangle_valid,
    output_path,
    max_nearest_distance,
    max_triangle_edge,
    inspect_distance=10.0,
):
    """Save a geometry comparison without reading radar amplitudes."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    # Select the output position closest to the requested chainage.
    i = int(np.argmin(np.abs(distances - inspect_distance)))
    centre = sample_xy[i]

    # Local coordinates keep the close-up axes easy to read.
    local_traces = trace_xy - centre
    local_samples = sample_xy - centre
    local_vertices = vertices - centre

    fig = Figure(figsize=(13, 6), constrained_layout=True)
    FigureCanvasAgg(fig)

    ax_map, ax_graph = fig.subplots(1, 2)

    # ---------------------------------------------------------
    # 1. Close-up of one output position
    # ---------------------------------------------------------
    half_width = 2.00  # Show 60 cm around the selected position.

    nearby = (
        (np.abs(local_traces[:, 0]) <= half_width)
        & (np.abs(local_traces[:, 1]) <= half_width)
    )

    ax_map.scatter(
        local_traces[nearby, 0],
        local_traces[nearby, 1],
        s=16,
        color="0.65",
        label="Measured trace positions",
        zorder=2,
    )

    ax_map.plot(
        local_vertices[:, 0],
        local_vertices[:, 1],
        color="black",
        linewidth=1,
        label="Original section line",
        zorder=1,
    )

    nearby_samples = (
        (np.abs(local_samples[:, 0]) <= half_width)
        & (np.abs(local_samples[:, 1]) <= half_width)
    )

    ax_map.scatter(
        local_samples[nearby_samples, 0],
        local_samples[nearby_samples, 1],
        s=22,
        color="royalblue",
        label="Output positions",
        zorder=3,
    )

    neighbours = triangle_indices[i]

    if np.all(neighbours >= 0):
        corners = local_traces[neighbours]
        closed_triangle = np.vstack((corners, corners[0]))

        ax_map.fill(
            corners[:, 0],
            corners[:, 1],
            color="darkorange",
            alpha=0.15,
        )

        ax_map.plot(
            closed_triangle[:, 0],
            closed_triangle[:, 1],
            color="darkorange",
            linewidth=1.5,
            label="Interpolation triangle",
        )

        for corner, weight in zip(corners, triangle_weights[i]):
            ax_map.plot(
                [0, corner[0]],
                [0, corner[1]],
                color="darkorange",
                linestyle=":",
                linewidth=1,
            )

            ax_map.scatter(
                corner[0], corner[1],
                s=45, color="darkorange", zorder=4,
            )

            ax_map.annotate(
                f"{weight:.1%}",
                xy=corner,
                xytext=(7, 7),
                textcoords="offset points",
                fontsize=10,
                bbox=dict(
                    facecolor="white",
                    edgecolor="none",
                    alpha=0.85,
                ),
                zorder=6,
            )

        status = "accepted" if triangle_valid[i] else "rejected"
    else:
        status = "no enclosing triangle"

    nearest = local_traces[nearest_index[i]]

    ax_map.plot(
        [0, nearest[0]],
        [0, nearest[1]],
        color="green",
        linestyle="--",
        linewidth=2,
        label="Nearest-trace connection",
        zorder=4,
    )

    ax_map.scatter(
        [0], [0],
        marker="*",
        s=180,
        color="royalblue",
        edgecolor="white",
        label="Selected output position",
        zorder=7,
    )

    ax_map.set(
        xlim=(-half_width, half_width),
        ylim=(-half_width, half_width),
        xlabel="East offset from output position (m)",
        ylabel="North offset from output position (m)",
        title=(
            f"Sample {i}: {distances[i]:.2f} m along section\n"
            f"Triangle: {status}"
        ),
    )
    ax_map.set_aspect("equal")
    ax_map.grid(alpha=0.2)
    ax_map.legend(fontsize=8, loc="upper left")

    # ---------------------------------------------------------
    # 2. Geometric support along the complete section
    # ---------------------------------------------------------
    ax_graph.plot(
        distances,
        nearest_distance * 100,
        color="green",
        linewidth=1,
        label="Distance to nearest trace",
    )

    ax_graph.plot(
        distances,
        triangle_edge * 100,
        color="darkorange",
        linewidth=1,
        label="Longest triangle edge",
    )

    ax_graph.axhline(
        max_nearest_distance * 100,
        color="green",
        linestyle="--",
        alpha=0.7,
        label="Nearest-distance limit",
    )

    ax_graph.axhline(
        max_triangle_edge * 100,
        color="darkorange",
        linestyle="--",
        alpha=0.7,
        label="Triangle-edge limit",
    )

    ax_graph.axvline(
        distances[i],
        color="royalblue",
        linestyle=":",
        label="Position shown at left",
    )

    ax_graph.set(
        xlabel="Distance along section (m)",
        ylabel="Distance / edge length (cm)",
        title="Geometric support along the section",
        xlim=(0, distances[-1]),
    )
    ax_graph.set_ylim(bottom=0)
    ax_graph.grid(alpha=0.2)
    ax_graph.legend(fontsize=8)

    fig.savefig(output_path, dpi=180)
    print(f"Sampling diagnostic image: {output_path}")

def test_ap_ppd_trace_reading(
    traces,
    selected_rows,
    folder_path,
    output_path,
):
    """
    Inspect selected trace records without applying processing.

    For int16 records, compare the cached offset with offset + 4.
    These are diagnostic candidates, not confirmed decoding rules.
    """
    import json
    import struct
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    selected_rows = np.unique(
        np.asarray(selected_rows, dtype=np.int64)
    )

    if (
        len(selected_rows) == 0
        or np.any(selected_rows < 0)
        or np.any(selected_rows >= len(traces))
    ):
        raise ValueError("Invalid diagnostic trace indices.")

    manifest_path = os.path.join(
        folder_path, "ap_ppd_manifest.json"
    )

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    files = {
        int(entry["file_id"]): entry
        for entry in manifest["files"]
    }

    fig = Figure(
        figsize=(13, 3 * len(selected_rows)),
        constrained_layout=True,
    )
    FigureCanvasAgg(fig)

    axes = fig.subplots(len(selected_rows), 2, squeeze=False)
    results = []

    for plot_row, subset_row in enumerate(selected_rows):
        trace = traces[subset_row]
        entry = files[int(trace["file_id"])]
        header = entry["header"]

        filepath = os.path.join(folder_path, entry["filename"])
        stat = os.stat(filepath)

        # A changed source file can invalidate cached byte offsets.
        if (
            stat.st_size != entry["size"]
            or abs(stat.st_mtime - entry["modified"]) > 1e-6
        ):
            raise ValueError(
                f"Source file changed; rebuild the cache:\n{filepath}"
            )

        count = int(header["points_per_trace"])
        offset = int(trace["data_offset"])
        short_format = int(header["data_format_short"])

        if count <= 0 or short_format not in (0, 1):
            raise ValueError("Unsupported sample count or storage flag.")

        dtype = np.dtype("<i2" if short_format == 1 else "<f4")
        shifts = (0, 4) if short_format == 1 else (0,)
        candidates = {}

        print(
            f"\nFile: {entry['filename']}\n"
            f"Channel: {int(trace['channel'])}, "
            f"trace: {int(trace['trace'])}, "
            f"subset row: {subset_row}\n"
            f"Cached offset: {offset}, dtype: {dtype}, "
            f"samples: {count}"
        )

        with open(filepath, "rb") as handle:
            if offset < 12:
                raise ValueError("Invalid cached byte offset.")

            # In the original reader, x/y/z immediately precede
            # data_offset. Check that this record matches the index.
            handle.seek(offset - 12)
            coordinate_bytes = handle.read(12)

            if len(coordinate_bytes) != 12:
                raise ValueError("Incomplete trace coordinate record.")

            relative_xyz = np.array(
                struct.unpack("<fff", coordinate_bytes)
            )
            decoded_xyz = relative_xyz + np.array([
                header["x_min"],
                header["y_min"],
                0.0,  # Z is already absolute altitude.
            ])
            cached_xyz = np.array([
                trace["x"], trace["y"], trace["z"]
            ])

            if not np.allclose(
                decoded_xyz, cached_xyz, rtol=0, atol=1e-6
            ):
                raise ValueError(
                    "Coordinates at the cached offset do not "
                    "match the trace index."
                )

            print("Cached coordinate/record alignment: OK")

            handle.seek(offset)
            first_four = handle.read(4)

            if len(first_four) != 4:
                raise ValueError("Incomplete sample record.")

            print(f"First four bytes: {first_four.hex(' ')}")

            if short_format == 1:
                print(
                    "Interpreted as two int16 values:",
                    struct.unpack("<hh", first_four),
                )
                print(
                    "Interpreted as one float32 value:",
                    struct.unpack("<f", first_four)[0],
                    "(diagnostic only)",
                )

            for shift in shifts:
                sample_offset = offset + shift
                byte_count = count * dtype.itemsize

                if sample_offset + byte_count > stat.st_size:
                    raise ValueError("Sample read would exceed file size.")

                handle.seek(sample_offset)
                raw = handle.read(byte_count)

                if len(raw) != byte_count:
                    raise ValueError("Incomplete sample read.")

                samples = np.frombuffer(raw, dtype=dtype).copy()
                candidates[shift] = samples

                values = samples.astype(np.float64)
                finite = np.isfinite(values)

                print(
                    f"Offset +{shift}: "
                    f"{finite.sum()}/{count} finite samples"
                )
                print("  First 12 samples:", samples[:12].tolist())

                if finite.all():
                    print(
                        f"  Min: {values.min():.6g}, "
                        f"max: {values.max():.6g}, "
                        f"RMS: {np.sqrt(np.mean(values ** 2)):.6g}"
                    )

        reader = ApPPDReader(filepath)
        decoded_samples = reader.read_trace_samples(trace, header)

        # Compare the reader with the independently decoded raw samples.
        if short_format == 1:
            factor = struct.unpack("<f", first_four)[0]
            expected = candidates[4].astype(np.float32) * factor
            print(f"Conversion factor: {factor:.9g}")
        else:
            expected = candidates[0]

        np.testing.assert_allclose(
            decoded_samples,
            expected,
            rtol=1e-6,
            atol=0,
        )

        if not np.isfinite(decoded_samples).all():
            raise ValueError("Decoded waveform contains non-finite values.")

        print("Corrected reader matches the specified decoding.")
        print(
            f"Decoded amplitude range: "
            f"{decoded_samples.min():.6g} to "
            f"{decoded_samples.max():.6g}"
        )

        # Plot only the correctly decoded waveform.
        candidates = {"Decoded and scaled": decoded_samples}

        title = (
            f"{entry['filename']} | "
            f"channel {int(trace['channel'])}, "
            f"trace {int(trace['trace'])}"
        )

        for label, samples in candidates.items():
            # Left panel: complete waveform.
            axes[plot_row, 0].plot(
                np.arange(len(samples)),
                samples,
                linewidth=0.9,
                label=label,
            )

            # Right panel: first 40 samples.
            zoom_count = min(40, len(samples))
            axes[plot_row, 1].plot(
                np.arange(zoom_count),
                samples[:zoom_count],
                marker=".",
                linewidth=0.9,
                label=label,
            )

        axes[plot_row, 0].set_title(title, fontsize=9)
        axes[plot_row, 1].set_title("First 40 samples")

        for ax in axes[plot_row]:
            ax.set_xlabel("Sample index")
            ax.set_ylabel("Decoded amplitude")
            ax.grid(alpha=0.2)
            ax.legend(fontsize=8)

        results.append({
            "subset_row": int(subset_row),
            "file_id": int(trace["file_id"]),
            "data_offset": offset,
            "candidates": candidates,
        })

    fig.savefig(output_path, dpi=180)
    print(f"\nTrace-reading diagnostic: {output_path}")

    return results

def align_ap_ppd_source_time_zero(source_data, trace_metadata):
    """Align source traces to a common recorded time-zero point."""
    source_data = np.asarray(source_data, dtype=np.float32)

    if source_data.ndim != 2:
        raise ValueError("Expected source traces × samples.")

    if len(trace_metadata) != len(source_data):
        raise ValueError("Source data and metadata lengths differ.")

    required = {"time_zero", "time_zero_adjusted"}
    if not required.issubset(trace_metadata.dtype.names or ()):
        raise ValueError("Rebuild the index: timing metadata is missing.")

    # This diagnostic currently supports the unadjusted data we inspected.
    if np.any(trace_metadata["time_zero_adjusted"] != 0):
        raise ValueError(
            "Some source files are already time-zero adjusted. "
            "Check their timing convention before applying another shift."
        )

    time_zero = trace_metadata["time_zero"].astype(np.int64)
    sample_count = source_data.shape[1]

    if np.any((time_zero <= 0) | (time_zero >= sample_count)):
        raise ValueError("Missing or out-of-range time-zero points.")

    # Provisional convention: TZ_POINT is a zero-based sample index.
    # Move each trace's recorded time-zero point to output sample 0.
    reference_point = 0
    shifts = reference_point - time_zero
    aligned = np.full_like(source_data, np.nan)

    for row, shift in enumerate(shifts):
        shift = int(shift)
        if shift > 0:
            aligned[row, shift:] = source_data[row, :-shift]
        elif shift < 0:
            aligned[row, :shift] = source_data[row, -shift:]
        else:
            aligned[row] = source_data[row]

    print(
        f"Time-zero reference: {reference_point}; "
        f"sample shifts: {np.unique(shifts).tolist()}"
    )

    return aligned, reference_point, shifts

def create_ap_ppd_section_comparison(
    traces,
    sampling,
    folder_path,
    section_name,
    clip_percentile=99.0,
    balance_sources=False,
    calibration_pairs=None,
    inspection_points=None,
    compare_same_pass=False,
    compare_section_timing=True,
    diagnostics=False,
    compare_gain=False,
    gain_options=None,
    timing_options=None,
    source_timing=True,
    source_timing_options=None,
    compare_coupling=False,
    coupling_options=None,
    selected_workflow=False,
    selected_gain_tracks=((85,125,95),(130,175,140)),
    selected_second_pass=True,
    selected_source_gain=True,
):
    """
    V14: source timing and local peak gain before interpolation, optional
    residual section timing and tracked peak gain, then lateral mean.
    Selected mode exports one PNG and one NPZ; diagnostics are opt-in.
    selected_gain_tracks are (low, high, seed) sample gates AFTER time zero.
    Defaults match the tested section and must be reviewed for other profiles.

    Legacy source timing plus optional pre-interpolation coupling diagnostics.

    source_timing=True jointly fits local offsets and smooth window trends, validates
    final source pairs and reconstructed mixtures, and exports
    source/contributor CSVs. Set False to restore post-interpolation timing.
    Full-cache context is loaded when available; the summary reports its origin.

    Panels use the same linear sampling and amplitude scale: original timing,
    recorded time-zero alignment, earlier shallow-window benchmark, and new
    source timing before mixing. source_timing=False retains three legacy panels.
    Gain is unchanged; missing samples are NaN. The baseline for final section
    checks is recorded time zero, NOT the shallow benchmark; compare both visually.
    A _timing_sources.npz snapshot is always exported for source timing. Use
    replay_ap_ppd_timing_snapshot to repeat its analysis without .ap_ppd binaries.
    The first panel uses stored sample indices; the others use aligned indices.

    diagnostics=True enables interval and detailed section-timing exports.
    inspection_points optionally names marked distances; none are marked by
    default. balance_sources=True enables the separate source-calibration
    outputs; compare_same_pass additionally enables its within-pass experiment.
    compare_section_timing=False hides the earlier benchmark when source_timing=True;
    with source_timing=False it disables per-column experimental shifts.
    timing_options configures timing fitting (fit_mode="shallow" restores prior result).
    compare_gain=True adds a separate timing-only versus gain experiment PNG.
    gain_options supplies keyword arguments to experiment_ap_ppd_section_gain.
    Existing raw/nearest return arrays are retained for compatibility.
    compare_coupling=True exports a separate source-pair diagnostic (CSV/JSON/PNG).
    It compares delay, gain and affine time scaling on held-out windows; it does
    not apply these new models to the section. coupling_options configures
    analyse_ap_ppd_coupling. Source timing and gain behaviour are unchanged.
    Raw decoded sources are included in new timing snapshots when this is enabled.
    traces must be the same corridor array used to create sampling.
    """
    import json
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    if not 0 < clip_percentile <= 100:
        raise ValueError("Clipping percentile must be between 0 and 100.")

    distances = np.asarray(sampling["distance"])
    nearest_index = sampling["nearest_index"]
    nearest_valid = sampling["nearest_valid"]
    triangle_indices = sampling["triangle_indices"]
    triangle_weights = sampling["triangle_weights"]
    triangle_valid = sampling["triangle_valid"]

    # Identify only the traces needed by accepted output positions.
    required_rows = np.unique(np.concatenate((
        nearest_index[nearest_valid],
        triangle_indices[triangle_valid].ravel(),
    ))).astype(np.int64)

    if len(required_rows) == 0:
        raise ValueError("No valid sampling positions to extract.")

    if np.any(required_rows < 0) or np.any(required_rows >= len(traces)):
        raise ValueError("Sampling indices do not match the trace subset.")

    display_source_rows = required_rows.copy()
    context_origin = "corridor_only"
    if source_timing or compare_coupling:
        context_radius = max((source_timing_options or {}).get("trend_radius_m", .8) if source_timing else 0.,
                             (coupling_options or {}).get("radius_m", .25) if compare_coupling else 0.)
        if selected_workflow:
            context_radius = .2
        traces, context_origin = _ap_expand_source_context(
            traces, required_rows, folder_path, context_radius)
        # Retain enough acquisition context for trend estimation.
        from scipy.spatial import cKDTree
        usable = np.flatnonzero(_ap_usable(traces))
        xy = np.column_stack((traces["x"], traces["y"]))
        radius = context_radius
        tree = cKDTree(xy[usable])
        nearby = tree.query_ball_point(xy[required_rows], radius)
        expanded = [usable[j] for group in nearby for j in group]
        required_rows = np.unique(np.r_[required_rows, expanded]).astype(np.int64)

    quality_report = ({"usable": _ap_usable(traces[required_rows])}
                      if selected_workflow and not diagnostics else
                      report_ap_ppd_timing_and_quality(traces[required_rows]))

    if not np.all(quality_report["usable"]):
        raise ValueError(
            "Sampling still includes flagged traces. "
            "Re-run the quality-filtered sampling step."
        )

    manifest_path = os.path.join(
        folder_path, "ap_ppd_manifest.json"
    )

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    file_entries = {
        int(entry["file_id"]): entry
        for entry in manifest["files"]
    }

    used_file_ids = np.unique(traces["file_id"][required_rows])

    # Validate referenced files and basic sampling compatibility.
    readers = {}
    reference_header = None

    for file_id in used_file_ids:
        file_id = int(file_id)
        entry = file_entries[file_id]
        filepath = os.path.join(folder_path, entry["filename"])
        stat = os.stat(filepath)

        if (
            stat.st_size != entry["size"]
            or abs(stat.st_mtime - entry["modified"]) > 1e-6
        ):
            raise ValueError(
                f"Source file changed; rebuild the index:\n{filepath}"
            )

        header = entry["header"]

        if reference_header is None:
            reference_header = header
        else:
            if (
                header["points_per_trace"]
                != reference_header["points_per_trace"]
                or header["epsg"] != reference_header["epsg"]
                or not np.isclose(
                    header["time_window"],
                    reference_header["time_window"],
                    rtol=1e-6,
                    atol=0,
                )
            ):
                raise ValueError(
                    "Source files have incompatible sample counts, "
                    "time windows or coordinate systems."
                )

        readers[file_id] = ApPPDReader(filepath)

    sample_count = int(reference_header["points_per_trace"])
    output_count = len(distances)

    print(
        f"\nReading {len(required_rows)} unique traces "
        f"from {len(used_file_ids)} files..."
    )

    # Compact matrix of source waveforms, indexed by required_rows.
    source_data = np.empty(
        (len(required_rows), sample_count),
        dtype=np.float32,
    )

    # Group reads by file and byte offset.
    selected = traces[required_rows]
    read_order = np.lexsort((
        selected["data_offset"],
        selected["file_id"],
    ))

    for progress, source_row in enumerate(read_order, start=1):
        subset_row = required_rows[source_row]
        trace = traces[subset_row]
        file_id = int(trace["file_id"])

        values = readers[file_id].read_trace_samples(
            trace,
            file_entries[file_id]["header"],
        )

        if not np.isfinite(values).all():
            raise ValueError(
                f"Non-finite amplitudes in subset row {subset_row}."
            )

        source_data[source_row] = values

        if progress % 500 == 0 or progress == len(required_rows):
            print(f"  Read {progress}/{len(required_rows)}")

    if selected_workflow:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in section_name) or "polysection"
        result = run_ap_ppd_selected_workflow(source_data, traces[required_rows], required_rows,
            sampling, os.path.join(folder_path,safe_name), gain_tracks=selected_gain_tracks,
            second_pass=selected_second_pass, source_gain_enabled=selected_source_gain, diagnostics=diagnostics,
            clip_percentile=clip_percentile)
        # ApPPD acquisition window is treated as N sample intervals, in ns.
        result['sample_interval_ns'] = float(reference_header['time_window']) / int(reference_header['points_per_trace'])
        heights = np.full(len(distances), np.nan)
        spread = np.full(len(distances), np.nan)
        for col in np.flatnonzero(triangle_valid):
            weights = triangle_weights[col]
            contributing = weights > 0
            zz = traces['z'][triangle_indices[col][contributing]]
            if np.isfinite(zz).all():
                heights[col] = weights[contributing] @ zz
                spread[col] = np.ptp(zz)
        result['surface_elevation'] = heights
        result['surface_elevation_spread'] = spread
        result['height_source'] = 'Triangle-weighted source z; vertical datum/antenna offset must be checked'
        return result

    aligned_source_data, time_zero_reference, time_zero_shifts = (
        align_ap_ppd_source_time_zero(
            source_data,
            traces[required_rows],
        )
    )

    # Build matrices as samples × output positions.
    nearest_section = np.full(
        (sample_count, output_count), np.nan, dtype=np.float32
    )
    linear_section = np.full_like(nearest_section, np.nan)

    aligned_linear_section = np.full_like(nearest_section, np.nan)

    nearest_source_rows = np.searchsorted(
        required_rows, nearest_index[nearest_valid]
    )
    nearest_section[:, nearest_valid] = (
        source_data[nearest_source_rows].T
    )

    # Process one output column at a time to avoid a large
    # positions × neighbours × samples temporary array.
    for column in np.flatnonzero(triangle_valid):
        source_rows = np.searchsorted(
            required_rows, triangle_indices[column]
        )
        weights = triangle_weights[column]

        linear_section[:, column] = (
            weights @ source_data[source_rows]
        )

        # Ignore vertices with exactly zero contribution.
        contributing = weights > 0
        aligned_values = aligned_source_data[
            source_rows[contributing]
        ]
        aligned_weights = weights[contributing]

        # Preserve missing samples introduced by shifting.
        supported = np.isfinite(aligned_values).all(axis=0)

        aligned_linear_section[supported, column] = (
            aligned_weights @ aligned_values[:, supported]
        )


    if inspection_points is None:
        inspection_points = {}
    # Skip out-of-range default inspections for shorter sections.
    inspection_points = {name: float(value) for name, value in inspection_points.items()
                         if distances[0] <= value <= distances[-1]}

    half_width_m = 0.5

    # These are sample indices, not nanoseconds.
    windows = {
        "full_trace": (0, source_data.shape[1]),
    }

    section_distances = np.asarray(sampling["distance"], dtype=float)

    if diagnostics:
        for inspection_name, requested_m in inspection_points.items():
            if not section_distances[0] <= requested_m <= section_distances[-1]:
                raise ValueError(
                    f"Inspection position {requested_m} m lies outside the section."
                )

            centre_column = int(
                np.argmin(np.abs(section_distances - requested_m))
            )

            start_m = max(
                float(section_distances[0]),
                requested_m - half_width_m,
            )
            end_m = min(
                float(section_distances[-1]),
                requested_m + half_width_m,
            )

            # Compare positions 15 cm either side of the estimated feature.
            # Select by distance so this also works with different output spacing.
            centre_m = float(section_distances[centre_column])
            inspected_columns = set()

            for offset_m, position_label in (
                    (-0.15, "before"),
                    (0.0, "centre"),
                    (0.15, "after"),
            ):
                target_m = centre_m + offset_m

                if not section_distances[0] <= target_m <= section_distances[-1]:
                    continue

                column = int(
                    np.argmin(np.abs(section_distances - target_m))
                )

                if column in inspected_columns:
                    continue
                inspected_columns.add(column)

                actual_m = float(section_distances[column])

                # Ensure the selected output is included in its interval.
                interval_start = min(start_m, actual_m)
                interval_end = max(end_m, actual_m)

                print(
                    f"\n{inspection_name}: {position_label}, "
                    f"column {column}, distance {actual_m:.3f} m"
                )

                for window_name, sample_window in windows.items():
                    diagnose_ap_ppd_section_interval(
                        traces=traces,
                        sampling=sampling,
                        required_rows=required_rows,
                        source_data=source_data,
                        aligned_source_data=aligned_source_data,
                        aligned_linear_section=aligned_linear_section,
                        time_zero_shifts=time_zero_shifts,
                        folder_path=folder_path,
                        section_name=section_name,
                        start_m=interval_start,
                        end_m=interval_end,
                        inspect_m=actual_m,
                        sample_range=sample_window,
                        file_entries=file_entries,
                        diagnostic_tag=(
                            f"{inspection_name}_{position_label}_{window_name}"
                        ),
                    )

    # Shared display scale based on the measured source amplitudes.
    # Clipping affects the PNG only; the returned arrays stay unchanged.
    amplitude_limit = float(np.percentile(
        np.abs(source_data[np.searchsorted(required_rows, display_source_rows)]), clip_percentile
    ))

    if amplitude_limit <= 0:
        amplitude_limit = float(np.max(np.abs(source_data)))

    if amplitude_limit <= 0:
        amplitude_limit = 1.0

    balancing_result = None
    if balance_sources:
        import csv
        proposals, corrections, audit = calibrate_ap_ppd_section_sources(
            traces, sampling, folder_path, inspection_points, calibration_pairs)
        corrected_sources, residual_advances, corrected_mask = apply_ap_ppd_source_corrections(
            source_data, traces[required_rows], corrections)
        corrected_section = interpolate_ap_ppd_source_matrix(
            corrected_sources, required_rows, sampling)
        coverage = np.full(output_count, np.nan)
        for column in np.flatnonzero(triangle_valid):
            compact = np.searchsorted(required_rows, triangle_indices[column])
            coverage[column] = float(np.sum(triangle_weights[column] * corrected_mask[compact]))
        source_status, status_fractions = ap_ppd_balance_status(
            selected, proposals, corrected_mask, required_rows, sampling)
        safe_balance_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in section_name) or 'polysection'
        prefix = os.path.join(folder_path, safe_balance_name)
        closeup_paths = plot_ap_ppd_balance_closeups(aligned_linear_section, corrected_section,
            sampling, coverage, traces, required_rows, corrected_mask, amplitude_limit,
            prefix, inspection_points, half_width_m)
        group_report = []
        for fid,channel in sorted(set(zip(selected['file_id'].tolist(),selected['channel'].tolist()))):
            group=(selected['file_id']==fid)&(selected['channel']==channel)
            group_report.append({'file_id':int(fid),'channel':int(channel),
                'reconstruction_sources':int(group.sum()),'corrected_sources':int((group&corrected_mask).sum()),
                'unchanged_sources':int((group&~corrected_mask).sum()),
                'status_counts':{k:int((group&(source_status==k)).sum()) for k in status_fractions}})
        with open(prefix + '_source_corrections.json', 'w', encoding='utf-8') as handle:
            json.dump({'version': 2, 'discovery_scope': 'full_section' if calibration_pairs is None else 'explicit_pairs', 'sample_origin': 'after recorded time zero',
                       'gain_enabled': False, 'proposals': proposals, 'applied': corrections,
                       'source_coverage': group_report,
                       'note': 'Full-section local neighbourhoods; 5 cm primary, 10 cm sensitivity. Unchanged includes fixed references and rejected estimates. See coverage CSV.'}, handle, indent=2)
        with open(prefix + '_balance_validation.csv', 'w', newline='', encoding='utf-8') as handle:
            fields = list(audit[0]) if audit else ['reference_file','reference_channel','target_file','target_channel','accepted']
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(audit)
        balance_path = prefix + '_balancing_comparison.png'
        plot_ap_ppd_balancing_comparison(aligned_linear_section, corrected_section,
            sampling, coverage, amplitude_limit, balance_path, inspection_points, half_width_m,
            status_fractions=status_fractions)
        coverage_path=prefix+'_balance_coverage.csv'
        with open(coverage_path,'w',newline='',encoding='utf-8') as handle:
            writer=csv.writer(handle);writer.writerow(['distance_m',*status_fractions])
            for col,d in enumerate(distances):
                writer.writerow([float(d),*[float(v[col]) if np.isfinite(v[col]) else '' for v in status_fractions.values()]])
        balancing_result = {'linear_time_zero_balanced': corrected_section,
                            'source_residual_advances': residual_advances,
                            'corrected_weight_fraction': coverage,
                            'source_status': source_status, 'status_weight_fractions': status_fractions,
                            'coverage_path': coverage_path,
                            'corrections': corrections, 'proposals': proposals,
                            'closeup_paths': closeup_paths, 'source_coverage':group_report,
                            'output_path': balance_path}
        print(f'Accepted local correction rules: {len(corrections)}; balancing plot: {balance_path}')
        if compare_same_pass:
            experiment = compare_ap_ppd_same_pass_timing(
                traces, sampling, folder_path, source_data, required_rows,
                aligned_linear_section, amplitude_limit, prefix, inspection_points)
            balancing_result['same_pass_experiment'] = experiment


    section_timing_result = None
    experimental_section = aligned_linear_section.copy()
    if compare_section_timing and not source_timing:
        if diagnostics:
            timing_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in section_name) or 'polysection'
            section_timing_result = create_ap_ppd_section_timing_comparison(
                aligned_linear_section, distances,
                os.path.join(folder_path, timing_name + '_section_timing'), **(timing_options or {}))
        else:
            preview, checked, proposed, applied, rows = analyse_ap_ppd_section_timing(
                aligned_linear_section, distances, **(timing_options or {}))
            section_timing_result = dict(
                proposed=preview, checked=checked,
                proposed_advances=proposed, checked_advances=applied,
                diagnostics=rows,
                summary=dict(positions=len(distances),
                             nonzero_proposals=int(np.count_nonzero(proposed)),
                             checked_shifts=int(np.count_nonzero(applied))))
        experimental_section = section_timing_result["proposed"]

    source_timing_result = None
    if source_timing:
        source_timing_result = analyse_ap_ppd_source_jitter(
            aligned_source_data, traces[required_rows],
            **(source_timing_options or {}))
        experimental_section = validate_ap_ppd_reconstructed_timing(
            source_timing_result, required_rows, sampling, aligned_linear_section)
        safe_prefix = "".join(c if c.isalnum() or c in "-_" else "_" for c in section_name)
        source_timing_result["report_paths"] = export_ap_ppd_source_jitter(
            source_timing_result, traces[required_rows], required_rows, sampling,
            os.path.join(folder_path, safe_prefix))
        # Always export a reproducible numeric snapshot for this experimental method.
        snapshot_options = dict(source_timing_options or {})
        snapshot_pass_ids = snapshot_options.pop("pass_ids", None)
        np.savez_compressed(os.path.join(folder_path,safe_prefix+"_timing_sources.npz"),
            time_zero_aligned_sources=aligned_source_data,
            **({"raw_sources": source_data} if compare_coupling else {}),
            metadata=traces[required_rows], required_rows=required_rows,
            source_advances=source_timing_result["advances"],
            options_json=np.array(json.dumps(snapshot_options, default=lambda v: np.asarray(v).tolist())),
            pass_ids=np.asarray(snapshot_pass_ids).astype(str) if snapshot_pass_ids is not None else np.array([], dtype=str),
            distance=distances, triangle_indices=sampling["triangle_indices"],
            triangle_weights=sampling["triangle_weights"], triangle_valid=sampling["triangle_valid"])
        source_timing_result["context"] = context_origin
        export_ap_ppd_joint_diagnostics(
            source_timing_result, traces[required_rows], required_rows, sampling,
            aligned_linear_section, experimental_section,
            os.path.join(folder_path, safe_prefix))
        print("Source timing applied:", np.count_nonzero(source_timing_result["advances"]),
              "/", len(required_rows))

    # Cell boundaries preserve the actual output positions, including
    # a potentially shorter final sampling interval.
    if len(distances) < 2 or np.any(np.diff(distances) <= 0):
        raise ValueError("Output distances must be strictly increasing.")

    distance_edges = np.r_[
        distances[0] - (distances[1] - distances[0]) / 2,
        (distances[:-1] + distances[1:]) / 2,
        distances[-1] + (distances[-1] - distances[-2]) / 2,
    ]
    sample_edges = np.arange(sample_count + 1) - 0.5

    benchmark_section = None
    if source_timing and compare_section_timing and len(distances) >= 9:
        benchmark_section = analyse_ap_ppd_section_timing(
            aligned_linear_section, distances, fit_mode="shallow")[0]
    panel_data = [linear_section, aligned_linear_section]
    panel_titles = ["Original timing — linear interpolation", "Recorded time-zero aligned"]
    if benchmark_section is not None:
        panel_data.append(benchmark_section)
        panel_titles.append("Earlier section timing — shallow-window benchmark")
    panel_data.append(experimental_section)
    panel_titles.append("Joint source timing — final source and section checks" if source_timing else
                        "Experimental timing — all proposed shifts" if compare_section_timing else
                        "Experimental timing disabled")
    if source_timing:
        affected = source_timing_result["summary"]["positions_with_corrected_contributor"]
        panel_titles[-1] += f"\n{affected}/{len(distances)} positions have shifted contributors"
    fig = Figure(figsize=(15, 4*len(panel_data)), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(len(panel_data), 1, sharex=True, sharey=True)

    from matplotlib import colormaps
    colourmap = colormaps["gray"].copy()
    colourmap.set_bad("lightblue")

    for ax, section, title in zip(
        axes,
        panel_data, panel_titles,
    ):
        image = ax.pcolormesh(
            distance_edges,
            sample_edges,
            np.ma.masked_invalid(section),
            cmap=colourmap,
            vmin=-amplitude_limit,
            vmax=amplitude_limit,
            shading="flat",
            rasterized=True,
        )

        ax.set_title(title)
        ax.set_ylabel("Stored sample index")
        ax.set_ylim(sample_count - 0.5, -0.5)
        ax.set_xlim(distances[0], distances[-1])

    # Mark the same horizontal intervals used by the diagnostics.
    from matplotlib.patches import Rectangle

    for inspection_name, requested_m in inspection_points.items():
        centre_column = int(
            np.argmin(np.abs(distances - requested_m))
        )
        centre_m = float(distances[centre_column])

        left_m = max(
            float(distances[0]),
            requested_m - half_width_m,
        )
        right_m = min(
            float(distances[-1]),
            requested_m + half_width_m,
        )

        for ax in axes:
            # X uses metres; Y uses a fraction of the axes height.
            ax.add_patch(Rectangle(
                (left_m, 0.0),
                right_m - left_m,
                1.0,
                transform=ax.get_xaxis_transform(),
                facecolor="none",
                edgecolor="dodgerblue",
                linewidth=1.5,
                zorder=8,
            ))

            ax.axvline(
                centre_m,
                color="dodgerblue",
                linestyle="--",
                linewidth=1.0,
                zorder=8,
            )

            ax.text(
                (left_m + right_m) / 2,
                0.96,
                f"{inspection_name}\n"
                f"{left_m:.2f}–{right_m:.2f} m",
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
                color="dodgerblue",
                bbox=dict(
                    facecolor="white",
                    edgecolor="none",
                    alpha=0.85,
                    pad=2,
                ),
                zorder=11,
            )

    for ax in axes[1:]:
        ax.set_ylabel("Samples after recorded time zero")
    axes[-1].set_xlabel("Distance along polysection (m)")
    excluded_chainage = np.asarray(
        sampling.get("excluded_chainage", []),
        dtype=np.float64,
    )
    excluded_chainage = excluded_chainage[
        np.isfinite(excluded_chainage)
    ]

    for ax in axes:
        if len(excluded_chainage):
            ax.plot(
                excluded_chainage,
                np.full(len(excluded_chainage), 0.985),
                linestyle="none",
                marker="|",
                color="crimson",
                markersize=7,
                transform=ax.get_xaxis_transform(),
                zorder=10,
            )
    fig.colorbar(
        image,
        ax=list(axes),
        label="Decoded amplitude — shared display scale",
        shrink=0.85,
    )
    fig.suptitle(
        f"{section_name}: timing comparison\n"
        "Same linear sampling and amplitude scale; gain unchanged"
    )
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in section_name
    ) or "polysection"

    output_path = os.path.join(
        folder_path, f"{safe_name}_section_comparison.png"
    )
    fig.savefig(output_path, dpi=200)

    print(f"Section shape: {nearest_section.shape}")
    print(f"Shared display limits: ±{amplitude_limit:.6g}")
    print(f"Section comparison: {output_path}")

    gain_result = None
    if compare_gain:
        gain_result = experiment_ap_ppd_section_gain(
            experimental_section, distances, **(gain_options or {}))
        gain_result["output_path"] = plot_ap_ppd_gain_comparison(
            experimental_section, distances, gain_result,
            os.path.join(folder_path, f"{safe_name}_gain_comparison.png"),
            clip_percentile=clip_percentile)

    coupling_result = None
    if compare_coupling:
        options = dict(coupling_options or {})
        if "pass_ids" not in options and (source_timing_options or {}).get("pass_ids") is not None:
            options["pass_ids"] = source_timing_options["pass_ids"]
        coupling_result = analyse_ap_ppd_coupling(
            aligned_source_data, traces[required_rows], required_rows, sampling,
            raw_sources=source_data, **options)
        coupling_result["paths"] = export_ap_ppd_coupling(
            coupling_result, aligned_source_data,
            os.path.join(folder_path, safe_name))

    return {
        "coupling": coupling_result,
        "source_timing": source_timing_result,
        "shallow_timing_benchmark": benchmark_section,
        "gain": gain_result,
        "balancing": balancing_result,
        "section_timing": section_timing_result,
        "nearest": nearest_section,
        "linear": linear_section,
        "distance": distances.copy(),
        "sample_index": np.arange(sample_count),
        "time_zero_aligned": False,
        "linear_time_zero_aligned_applied": True,
        "output_path": output_path,
        "linear_time_zero_aligned": aligned_linear_section,
        "linear_time_zero_experimental": experimental_section,
        "time_zero_reference_point": time_zero_reference,
        "time_zero_shifts": time_zero_shifts,
    }

def report_ap_ppd_timing_and_quality(traces):
    """
    Report timing and quality metadata for a trace subset.

    Returns masks for explicit quality problems.
    Does not modify, filter or align the supplied traces.
    """
    required = {
        "file_id",
        "channel",
        "time_zero",
        "first_zero",
        "second_zero",
        "section_incorrect",
        "time_zero_adjusted",
        "gps_flags",
    }

    missing = required - set(traces.dtype.names or ())

    if missing:
        raise ValueError(
            "Rebuild the ApPPD cache: missing metadata fields "
            + ", ".join(sorted(missing))
        )

    # Specification uses one-based bit numbering:
    # bits 1–4 = GPS quality, bit 5 = bad position,
    # bit 6 = incorrect trace.
    flags = traces["gps_flags"].astype(np.uint16)

    gps_quality = flags & 0x0F
    bad_position = (flags & 0x10) != 0
    trace_incorrect = (flags & 0x20) != 0
    channel_incorrect = traces["section_incorrect"] != 0

    usable = ~(
        bad_position | trace_incorrect | channel_incorrect
    )

    print("\n--- ApPPD timing and quality ---")
    print(f"Traces inspected: {len(traces)}")
    print(f"Flagged bad position: {bad_position.sum()}")
    print(f"Flagged incorrect trace: {trace_incorrect.sum()}")
    print(f"In incorrect channels: {channel_incorrect.sum()}")
    print(f"Without these quality flags: {usable.sum()}")

    qualities, counts = np.unique(
        gps_quality, return_counts=True
    )
    print(
        "GPS quality counts:",
        dict(zip(qualities.tolist(), counts.tolist())),
    )

    adjusted_values, adjusted_counts = np.unique(
        traces["time_zero_adjusted"], return_counts=True
    )
    print(
        "Time-zero-adjusted flag counts:",
        dict(zip(
            adjusted_values.tolist(),
            adjusted_counts.tolist(),
        )),
    )

    unknown_bits = flags & 0xFFC0
    if np.any(unknown_bits):
        print(
            "Additional quality bits present:",
            np.unique(unknown_bits[unknown_bits != 0]).tolist(),
        )

    # One report row per source file and channel.
    groups = np.unique(traces[["file_id", "channel"]])

    print(
        "\nFILE  CH  COUNT  TZ_POINT  "
        "FIRST_ZERO_NS  SECOND_ZERO_NS  FLAGGED"
    )

    for group in groups:
        mask = (
            (traces["file_id"] == group["file_id"])
            & (traces["channel"] == group["channel"])
        )

        time_zero = np.unique(traces["time_zero"][mask])
        first_zero = np.unique(traces["first_zero"][mask])
        second_zero = np.unique(traces["second_zero"][mask])

        # Zero crossings are stored in units of 10 ps = 0.01 ns.
        first_ns = np.round(first_zero * 0.01, 4).tolist()
        second_ns = np.round(second_zero * 0.01, 4).tolist()

        print(
            f"{int(group['file_id']):4d} "
            f"{int(group['channel']):3d} "
            f"{int(mask.sum()):6d}  "
            f"{time_zero.tolist()}  "
            f"{first_ns}  "
            f"{second_ns}  "
            f"{int((mask & ~usable).sum())}"
        )

    return {
        "usable": usable,
        "gps_quality": gps_quality,
        "bad_position": bad_position,
        "trace_incorrect": trace_incorrect,
        "channel_incorrect": channel_incorrect,
    }

def filter_ap_ppd_trace_quality(
    traces,
    vertices,
    output_folder,
    section_name,
    export_diagnostics=False,
):
    """Filter quality flags without modifying the original trace array."""
    import csv

    required = {"gps_flags", "section_incorrect"}

    if not required.issubset(traces.dtype.names or ()):
        raise ValueError("Rebuild the ApPPD cache with quality metadata.")

    flags = traces["gps_flags"].astype(np.uint16)

    bad_position = (flags & 0x10) != 0
    incorrect_trace = (flags & 0x20) != 0
    incorrect_channel = traces["section_incorrect"] != 0
    finite_xy = np.isfinite(traces["x"]) & np.isfinite(traces["y"])

    usable = (
        ~(bad_position | incorrect_trace | incorrect_channel)
        & finite_xy
    )

    usable_rows = np.flatnonzero(usable)
    excluded_rows = np.flatnonzero(~usable)

    # Find each excluded trace's closest position along the polyline.
    points = np.column_stack((
        traces["x"][excluded_rows],
        traces["y"][excluded_rows],
    ))

    vertices = np.asarray(vertices, dtype=np.float64)
    chainage = np.full(len(points), np.nan)
    minimum_distance = np.full(len(points), np.inf)
    cumulative_distance = 0.0

    for start, stop in zip(vertices[:-1], vertices[1:]):
        direction = stop - start
        length = np.linalg.norm(direction)

        if length == 0:
            continue

        fraction = np.clip(
            ((points - start) @ direction) / length**2,
            0.0,
            1.0,
        )

        distance = np.linalg.norm(
            points - start - fraction[:, None] * direction,
            axis=1,
        )

        closer = distance < minimum_distance

        minimum_distance[closer] = distance[closer]
        chainage[closer] = (
            cumulative_distance + fraction[closer] * length
        )

        cumulative_distance += length

    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in section_name
    ) or "polysection"

    csv_path = os.path.join(
        output_folder,
        f"{safe_name}_excluded_traces.csv",
    )

    if export_diagnostics:
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)

            writer.writerow([
                "subset_row", "file_id", "channel", "trace", "local_gid",
                "x", "y", "chain_m", "distance_m",
                "bad_position", "incorrect_trace", "incorrect_channel",
                "nonfinite_xy",
            ])

            for i, row in enumerate(excluded_rows):
                trace = traces[row]

                writer.writerow([
                    int(row),
                    int(trace["file_id"]),
                    int(trace["channel"]),
                    int(trace["trace"]),
                    int(trace["local_gid"]),
                    float(trace["x"]),
                    float(trace["y"]),
                    float(chainage[i]) if np.isfinite(chainage[i]) else "",
                    (
                        float(minimum_distance[i])
                        if np.isfinite(minimum_distance[i])
                        else ""
                    ),
                    int(bad_position[row]),
                    int(incorrect_trace[row]),
                    int(incorrect_channel[row]),
                    int(not finite_xy[row]),
                ])

    if export_diagnostics:
        print(f"Corridor traces: {len(traces)}")
    if export_diagnostics:
        print(f"Excluded: {len(excluded_rows)}")
    if export_diagnostics:
        print(f"Usable: {len(usable_rows)}")
    if export_diagnostics:
        print(f"Excluded-trace report: {csv_path}")

    return usable_rows, excluded_rows, chainage

def diagnose_ap_ppd_section_interval(
    traces,
    sampling,
    required_rows,
    source_data,
    aligned_source_data,
    aligned_linear_section,
    time_zero_shifts,
    folder_path,
    section_name,
    start_m,
    end_m,
    inspect_m=None,
    sample_range=(0, 180),
    file_entries=None,
    diagnostic_tag="",
):
    import csv
    from pathlib import Path
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import colormaps

    distance = np.asarray(sampling["distance"])
    columns = np.flatnonzero(
        (distance >= start_m) & (distance <= end_m)
    )
    if len(columns) < 2:
        raise ValueError("Select an interval containing at least two positions.")

    first, last = map(int, sample_range)
    sample_count = source_data.shape[1]
    if not 0 <= first < last <= sample_count:
        raise ValueError("Invalid sample_range.")

    if inspect_m is None:
        inspect_m = (start_m + end_m) / 2

    selected_column = columns[
        np.argmin(np.abs(distance[columns] - inspect_m))
    ]

    # Convert original corridor indices to compact source-matrix indices.
    row_lookup = {
        int(row): i for i, row in enumerate(required_rows)
    }

    def contributors(column):
        result = []
        if sampling["nearest_valid"][column]:
            result.append((
                "nearest",
                int(sampling["nearest_index"][column]),
                1.0,
            ))
        if sampling["triangle_valid"][column]:
            for row, weight in zip(
                sampling["triangle_indices"][column],
                sampling["triangle_weights"][column],
            ):
                if weight > 0:
                    result.append(("linear", int(row), float(weight)))
        return result

    # Read metadata once per unique source in this interval.
    # Keys remain original corridor-array indices.
    import struct
    from contextlib import ExitStack

    if file_entries is None:
        import json

        manifest_path = Path(folder_path) / "ap_ppd_manifest.json"
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)

        file_entries = {
            int(entry["file_id"]): entry
            for entry in manifest["files"]
        }

    interval_rows = sorted({
        row
        for column in columns
        for _, row, _ in contributors(column)
    })

    source_metadata = {}

    with ExitStack() as stack:
        handles = {}

        for row in interval_rows:
            trace = traces[row]
            file_id = int(trace["file_id"])
            entry = file_entries[file_id]
            storage_format = int(entry["header"]["data_format_short"])

            # Float-format samples have no stored conversion factor.
            conversion_factor = None

            if storage_format == 1:
                if file_id not in handles:
                    handles[file_id] = stack.enter_context(
                        open(Path(folder_path) / entry["filename"], "rb")
                    )

                handle = handles[file_id]
                handle.seek(int(trace["data_offset"]))
                factor_bytes = handle.read(4)

                if len(factor_bytes) != 4:
                    raise ValueError(
                        f"Incomplete conversion factor in corridor row {row}."
                    )

                conversion_factor = struct.unpack("<f", factor_bytes)[0]

                if not np.isfinite(conversion_factor):
                    raise ValueError(
                        f"Non-finite conversion factor in corridor row {row}."
                    )

            elif storage_format != 0:
                raise ValueError(
                    f"Unknown sample format {storage_format} in file {file_id}."
                )

            source_metadata[row] = {
                "filename": entry["filename"],
                "data_offset": int(trace["data_offset"]),
                "z": float(trace["z"]),
                "recorded_time_zero": int(trace["time_zero"]),
                "time_zero_adjusted": int(trace["time_zero_adjusted"]),
                "conversion_factor": conversion_factor,
                "data_format_short": storage_format,
            }

    # Aligned nearest section: same timing treatment as aligned linear.
    nearest = np.full(
        (sample_count, len(columns)), np.nan, dtype=np.float32
    )
    records = []

    for local_column, column in enumerate(columns):
        output_xy = sampling["sample_xy"][column]

        for method, row, weight in contributors(column):
            compact = row_lookup[row]
            trace = traces[row]

            if method == "nearest":
                nearest[:, local_column] = aligned_source_data[compact]

            records.append({
                "output_column": int(column),
                "distance_m": float(distance[column]),
                "method": method,
                "subset_row": row,
                "file_id": int(trace["file_id"]),
                "channel": int(trace["channel"]),
                "trace": int(trace["trace"]),
                "weight": weight,
                "x": float(trace["x"]),
                "y": float(trace["y"]),
                "offset_m": float(np.hypot(
                    trace["x"] - output_xy[0],
                    trace["y"] - output_xy[1],
                )),
                "shift_samples": int(time_zero_shifts[compact]),
                "source_rms": float(np.sqrt(np.mean(
                    source_data[compact].astype(np.float64) ** 2
                ))),
                **source_metadata[row],
                "output_x": float(output_xy[0]),
                "output_y": float(output_xy[1]),
            })

    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in section_name
    ) or "polysection"
    safe_tag = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in diagnostic_tag
    )

    suffix = f"_{safe_tag}" if safe_tag else ""

    prefix = Path(folder_path) / (
        f"{safe_name}_diagnostic_{start_m:g}_{end_m:g}m"
        f"_at_{distance[selected_column]:.3f}m"
        f"_samples_{first}_{last}{suffix}"
    )
    csv_path = str(prefix) + ".csv"

    fields = [
        "output_column", "distance_m", "output_x", "output_y",
        "method", "subset_row",
        "file_id", "filename", "channel", "trace", "data_offset",
        "weight", "x", "y", "z", "offset_m",
        "recorded_time_zero", "time_zero_adjusted",
        "shift_samples", "data_format_short", "conversion_factor",
        "source_rms",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    # First figure: section comparison and source identities.
    x = distance[columns]
    x_edges = np.r_[
        x[0] - (x[1] - x[0]) / 2,
        (x[:-1] + x[1:]) / 2,
        x[-1] + (x[-1] - x[-2]) / 2,
    ]
    y_edges = np.arange(first, last + 1) - 0.5
    linear = aligned_linear_section[:, columns]

    finite_values = np.concatenate([
        nearest[first:last].ravel(),
        linear[first:last].ravel(),
    ])
    finite_values = finite_values[np.isfinite(finite_values)]
    if not len(finite_values):
        raise ValueError("No supported amplitudes in this interval.")
    limit = max(float(np.percentile(np.abs(finite_values), 99)), 1e-12)

    cmap = colormaps["gray"].copy()
    cmap.set_bad("lightblue")

    fig = Figure(figsize=(13, 11), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(4, 1, sharex=True)

    for ax, values, title in zip(
        axes[:2],
        (nearest, linear),
        ("Aligned nearest trace", "Aligned linear interpolation"),
    ):
        ax.pcolormesh(
            x_edges, y_edges,
            np.ma.masked_invalid(values[first:last]),
            cmap=cmap, vmin=-limit, vmax=limit, shading="flat",
        )
        ax.set_ylim(last - 0.5, first - 0.5)
        ax.set_ylabel("Samples after recorded time zero")
        ax.set_title(title)

    # Show all linear contributors; marker size represents their weight.
    for ax, field, label in (
        (axes[2], "file_id", "Source file ID"),
        (axes[3], "channel", "Source channel"),
    ):
        for method, marker, colour in (
            ("linear", "o", "tab:orange"),
            ("nearest", "x", "tab:blue"),
        ):
            group = [r for r in records if r["method"] == method]
            ax.scatter(
                [r["distance_m"] for r in group],
                [r[field] for r in group],
                s=[15 + 65 * r["weight"] for r in group],
                marker=marker, color=colour, alpha=0.65,
                label=method,
            )
        ax.set_ylabel(label)
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right")

    for ax in axes:
        ax.axvline(
            distance[selected_column], color="crimson",
            linestyle=":", linewidth=1,
        )
        ax.set_xlim(x[0], x[-1])

    axes[-1].set_xlabel("Distance along section (m)")
    fig.suptitle(
        f"{section_name}: BASELINE source diagnostics (before balancing)\n"
        "Orange circle size = interpolation weight; "
        "red line = inspected position"
    )
    interval_path = str(prefix) + "_interval.png"
    fig.savefig(interval_path, dpi=180)

    # Second figure: individual measured waveforms at the selected position.
    selected = contributors(selected_column)
    if not selected:
        print("Selected position is unsupported; choose another inspect_m.")
        return {"interval": interval_path, "csv": csv_path}

    rows = sorted({row for _, row, _ in selected})
    origin = np.asarray(sampling["sample_xy"][selected_column])
    sample_axis = np.arange(first, last)

    fig2 = Figure(figsize=(14, 9), constrained_layout=True)
    FigureCanvasAgg(fig2)
    raw_ax, aligned_ax, normalized_ax, map_ax = fig2.subplots(2, 2).ravel()

    for number, row in enumerate(rows):
        compact = row_lookup[row]
        trace = traces[row]
        colour = f"C{number % 10}"
        roles = ", ".join(
            f"{method}: {weight:.2f}"
            for method, source_row, weight in selected
            if source_row == row
        )
        label = (
            f"F{int(trace['file_id'])} / CH{int(trace['channel'])} / "
            f"T{int(trace['trace'])} [{roles}]"
        )

        # Raw and aligned panels intentionally use different timing origins.
        raw = source_data[compact, first:last]
        aligned = aligned_source_data[compact, first:last]
        raw_ax.plot(sample_axis, raw, color=colour, label=label)
        aligned_ax.plot(sample_axis, aligned, color=colour, label=label)

        finite = aligned[np.isfinite(aligned)]
        scale = np.max(np.abs(finite)) if len(finite) else 0
        if scale > 0:
            normalized_ax.plot(
                sample_axis, aligned / scale, color=colour, label=label
            )

        dx = float(trace["x"] - origin[0])
        dy = float(trace["y"] - origin[1])
        map_ax.plot([0, dx], [0, dy], color=colour, alpha=0.5)
        map_ax.scatter(dx, dy, color=colour, s=60)
        map_ax.annotate(
            f"F{int(trace['file_id'])}/CH{int(trace['channel'])}",
            (dx, dy), xytext=(4, 4), textcoords="offset points",
        )

    # Compare output waveforms directly against the aligned inputs.
    local_selected = int(np.flatnonzero(columns == selected_column)[0])
    aligned_ax.plot(
        sample_axis, nearest[first:last, local_selected],
        "k--", linewidth=1.5, label="Nearest output",
    )
    aligned_ax.plot(
        sample_axis, linear[first:last, local_selected],
        color="magenta", linewidth=1.5, label="Linear output",
    )

    raw_ax.set_title("Source waveforms — original timing")
    raw_ax.set_xlabel("Stored sample index")
    aligned_ax.set_title("Aligned sources and section outputs")
    normalized_ax.set_title("Aligned sources — normalized for shape only")

    for ax in (raw_ax, aligned_ax, normalized_ax):
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
        ax.set_ylabel("Amplitude")
    for ax in (aligned_ax, normalized_ax):
        ax.set_xlabel("Samples after recorded time zero")
    normalized_ax.set_ylabel("Normalized amplitude")

    # Common amplitude scale for the two unnormalized waveform panels.
    low = min(raw_ax.get_ylim()[0], aligned_ax.get_ylim()[0])
    high = max(raw_ax.get_ylim()[1], aligned_ax.get_ylim()[1])
    raw_ax.set_ylim(low, high)
    aligned_ax.set_ylim(low, high)

    local_xy = np.asarray(sampling["sample_xy"])[columns] - origin
    map_ax.plot(
        local_xy[:, 0], local_xy[:, 1], "k.-",
        markersize=3, label="Section output positions",
    )
    map_ax.scatter(0, 0, marker="*", s=160, color="magenta",
                   label="Inspected position", zorder=5)
    map_ax.set_aspect("equal", adjustable="datalim")
    map_ax.set_xlabel("East offset (m)")
    map_ax.set_ylabel("North offset (m)")
    map_ax.set_title("Source positions relative to output")
    map_ax.grid(alpha=0.2)
    map_ax.legend(fontsize=8)

    fig2.suptitle(
        f"{section_name}: BASELINE {diagnostic_tag or 'source comparison'}\n"
        f"Output position {distance[selected_column]:.3f} m; "
        f"sample window [{first}, {last})"
    )
    waveform_path = str(prefix) + "_waveforms.png"
    fig2.savefig(waveform_path, dpi=180)

    print(f"Interval diagnostic: {interval_path}")
    print(f"Waveform diagnostic: {waveform_path}")
    print(f"Contributor table: {csv_path}")

    return {
        "interval": interval_path,
        "waveforms": waveform_path,
        "csv": csv_path,
    }
# ------------------------------------------------------------
# LOCAL OVERLAP CALIBRATION (experimental, timing only)
# ------------------------------------------------------------
def _ap_usable(records):
    flags = records['gps_flags'].astype(np.uint16)
    return ((flags & 0x30) == 0) & (records['section_incorrect'] == 0) & np.isfinite(records['x']) & np.isfinite(records['y'])


def collect_ap_ppd_calibration_neighbourhoods(folder_path, seeds, half_count=100):
    """Seeds: dictionaries with file_id, channel, trace. Rows remain full-index rows.

    Reads acquisition neighbours from the full cache, not the section corridor.
    The requested trace-number range is also the maximum correction scope.
    """
    if not isinstance(half_count, int) or half_count < 1:
        raise ValueError('half_count must be a positive integer')
    index = np.load(os.path.join(folder_path, 'ap_ppd_trace_index.npy'), mmap_mode='r', allow_pickle=False)
    with open(os.path.join(folder_path, 'ap_ppd_manifest.json'), encoding='utf-8') as f:
        entries = {int(e['file_id']): e for e in json.load(f)['files']}
    result = []
    reference = None
    for seed in seeds:
        fid, channel, centre = (int(seed[k]) for k in ('file_id','channel','trace'))
        entry = entries[fid]; header = entry['header']
        path = os.path.join(folder_path, entry['filename']); stat = os.stat(path)
        if stat.st_size != entry['size'] or abs(stat.st_mtime-entry['modified']) > 1e-6:
            raise ValueError('Source changed; rebuild cache: ' + path)
        signature = (int(header['points_per_trace']), int(header['epsg']), float(header['time_window']))
        if reference is not None and (signature[:2] != reference[:2] or not np.isclose(signature[2],reference[2],rtol=1e-6,atol=0)):
            raise ValueError('Calibration sources have incompatible sampling or CRS')
        reference = signature
        rows = np.flatnonzero((index['file_id']==fid)&(index['channel']==channel)&(index['trace']>=centre-half_count)&(index['trace']<=centre+half_count))
        records = index[rows].copy(); good = _ap_usable(records)
        rows, records = rows[good], records[good]
        order = np.argsort(records['trace']); rows, records = rows[order], records[order]
        if len(records) == 0:
            continue
        reader = ApPPDReader(path)
        raw = np.stack([reader.read_trace_samples(t,header) for t in records]).astype(np.float32)
        if not np.isfinite(raw).all():
            raise ValueError('Nonfinite calibration amplitudes')
        aligned, _, _ = align_ap_ppd_source_time_zero(raw, records)
        result.append(dict(seed=dict(file_id=fid,channel=channel,trace=centre),
            trace_start=centre-half_count,trace_end=centre+half_count,
            full_index_rows=rows,records=records,aligned=aligned,filename=entry['filename'],
            source_size=entry['size'],source_modified=entry['modified']))
    return result


def match_ap_ppd_overlap_traces(reference, target, max_distance=0.05):
    """Reciprocal nearest XY matches, unique on both sides. No amplitude interpolation."""
    if not np.isfinite(max_distance) or max_distance <= 0:
        raise ValueError('Invalid matching distance')
    a,b = reference['records'],target['records']
    xa=np.c_[a['x'],a['y']]; xb=np.c_[b['x'],b['y']]
    distance, j=cKDTree(xb).query(xa); _, back=cKDTree(xa).query(xb)
    i=np.flatnonzero((distance<=max_distance)&(back[j]==np.arange(len(a))))
    return i,j[i],distance[i]


def _ap_corr(a,b):
    valid=np.isfinite(a)&np.isfinite(b)
    if valid.sum()<24: return np.nan
    a=a[valid].astype(float); b=b[valid].astype(float)
    a-=a.mean(); b-=b.mean(); denominator=np.linalg.norm(a)*np.linalg.norm(b)
    return float(a@b/denominator) if denominator>0 else np.nan


def estimate_ap_ppd_overlap_correction(reference, target, max_distance=0.05,
        windows=((80,150),(150,300)), max_lag=8, min_pairs=24,
        matched_indices=None, allow_zero=False):
    """Estimate one residual integer advance of target, on time-zero-relative samples.

    Four contiguous spatial blocks alternate calibration/validation, with one
    pair removed at each internal boundary. Nearby pairs remain correlated;
    these are conservative engineering gates, not statistical confidence limits.
    Gain stays 1.0. No per-trace or per-window correction is fitted.
    """
    if max_lag < 1 or min_pairs < 8:
        raise ValueError('Invalid lag or pair limits')
    a,b,d=(match_ap_ppd_overlap_traces(reference,target,max_distance)
           if matched_indices is None else matched_indices)
    proposal=dict(**target['seed'],trace_start=target['trace_start'],trace_end=target['trace_end'],
        filename=target['filename'],source_size=target['source_size'],source_modified=target['source_modified'],
        reference=reference['seed'],advance_samples=0,gain=1.0,timing_accepted=False,gain_accepted=False,
        max_distance=max_distance,matched_pairs=len(a),reason='insufficient matched pairs',validation=[])
    if len(a)<min_pairs: return proposal,[]
    aa=reference['aligned'][a]; bb=target['aligned'][b]
    n=aa.shape[1]
    for lo,hi in windows:
        if not 0<=lo<hi<=n or hi-lo<=2*max_lag+24:
            raise ValueError('Calibration window incompatible with sample count')
    candidates=np.arange(-max_lag,max_lag+1)
    scores=np.full((len(a),len(windows),len(candidates)),np.nan)
    # All candidate scores for a pair/window use the SAME finite support.
    for row in range(len(a)):
        for w,(lo,hi) in enumerate(windows):
            ix=np.arange(lo+max_lag,hi-max_lag)
            valid=np.isfinite(aa[row,ix])
            for k in candidates: valid &= np.isfinite(bb[row,ix+k])
            ix=ix[valid]
            if len(ix)<24: continue
            for c,k in enumerate(candidates): scores[row,w,c]=_ap_corr(aa[row,ix],bb[row,ix+k])
    finite=np.isfinite(scores).all(axis=(1,2))
    blocks=np.array_split(np.arange(len(a)),4)
    train=np.concatenate([blocks[0][:-1],blocks[2][1:-1]])
    test_blocks=[blocks[1][1:-1],blocks[3][1:]]
    train=train[finite[train]]; test_blocks=[v[finite[v]] for v in test_blocks]
    if len(train)<8 or any(len(v)<4 for v in test_blocks):
        proposal['reason']='insufficient finite calibration/validation support';return proposal,[]
    objective=np.median(scores[train],axis=(0,1))
    ties=np.flatnonzero(np.isclose(objective,objective.max(),rtol=0,atol=1e-10))
    best=ties[np.argmin(abs(candidates[ties]))]; lag=int(candidates[best]); zero=max_lag
    proposal['advance_samples']=lag
    block_lags=[]; acceptable=True
    for block_id,rows in enumerate(test_blocks):
        block_obj=np.median(scores[rows],axis=(0,1)); local=int(candidates[np.argmax(block_obj)]);block_lags.append(local)
        for w,window in enumerate(windows):
            before=scores[rows,w,zero];after=scores[rows,w,best]
            stats=dict(block=block_id,window=list(window),count=len(rows),
                median_before=float(np.median(before)),median_after=float(np.median(after)),
                median_gain=float(np.median(after-before)),fraction_not_worse=float(np.mean(after>=before-.01)))
            proposal['validation'].append(stats)
            minimum_gain=-.01 if allow_zero and lag==0 else .02
            acceptable &= stats['median_after']>=.85 and stats['median_gain']>=minimum_gain and stats['fraction_not_worse']>=.7
    acceptable &= (lag!=0 or allow_zero) and abs(lag)<max_lag and all(abs(v-lag)<=1 for v in block_lags)
    proposal['timing_accepted']=bool(acceptable)
    proposal['reason']='accepted on both validation blocks/windows' if acceptable else 'no shift or validation gates not met'
    proposal['validation_block_best_lags']=block_lags
    records=[]
    split={int(v):'calibration' for v in train}
    for bi,rows in enumerate(test_blocks): split.update({int(v):f'validation_{bi}' for v in rows})
    for r in sorted(split):
        for w,window in enumerate(windows):
            records.append(dict(reference_file=reference['seed']['file_id'],reference_channel=reference['seed']['channel'],
                target_file=target['seed']['file_id'],target_channel=target['seed']['channel'],
                reference_trace=int(reference['records']['trace'][a[r]]),target_trace=int(target['records']['trace'][b[r]]),
                max_distance=max_distance,separation_m=float(d[r]),split=split[r],window=str(window),
                candidate_advance=lag,correlation_before=float(scores[r,w,zero]),correlation_after=float(scores[r,w,best]),
                individual_best_lag=int(candidates[np.argmax(scores[r,w])]),
                individual_best_correlation=float(np.max(scores[r,w])),
                individual_at_search_limit=bool(abs(candidates[np.argmax(scores[r,w])])==max_lag),
                accepted=bool(acceptable)))
    return proposal,records


def apply_ap_ppd_source_corrections(source_data, metadata, corrections):
    """Combine recorded time zero and accepted residual advance in ONE shift.

    Reference groups must remain unchanged; reject contradictory overlapping rules.
    Positive advance moves target samples earlier. No cyclic wrapping or gain fit.
    """
    # Reuse existing timing validation; shift originals below to avoid lost edges.
    _,reference,base_shifts=align_ap_ppd_source_time_zero(source_data,metadata)
    advances=np.zeros(len(metadata),dtype=int);used=np.zeros(len(metadata),dtype=bool)
    for rule in corrections:
        if not rule.get('timing_accepted',False): continue
        lag=rule['advance_samples']
        if not np.isfinite(lag) or int(lag)!=lag or abs(lag)>8:
            raise ValueError('Correction must be an integer advance within ±8 samples')
        if rule.get('gain',1.0)!=1.0: raise ValueError('Gain calibration is not enabled')
        mask=(metadata['file_id']==rule['file_id'])&(metadata['channel']==rule['channel'])&(metadata['trace']>=rule['trace_start'])&(metadata['trace']<=rule['trace_end'])
        if np.any(used&mask): raise ValueError('Overlapping accepted correction scopes')
        advances[mask]=int(lag);used[mask]=True
    output=np.full_like(source_data,np.nan)
    for row,shift in enumerate(base_shifts-advances):
        shift=int(shift);n=source_data.shape[1]
        if abs(shift)>=n: continue
        if shift<0: output[row,:shift]=source_data[row,-shift:]
        elif shift>0: output[row,shift:]=source_data[row,:-shift]
        else: output[row]=source_data[row]
    return output,advances,used


def interpolate_ap_ppd_source_matrix(source_data, required_rows, sampling):
    """Original corridor rows → compact source rows; preserve missing support."""
    lookup={int(row):i for i,row in enumerate(required_rows)}
    out=np.full((source_data.shape[1],len(sampling['distance'])),np.nan,dtype=np.float32)
    for col in np.flatnonzero(sampling['triangle_valid']):
        weights=np.asarray(sampling['triangle_weights'][col]); positive=weights>0
        rows=[lookup[int(r)] for r in sampling['triangle_indices'][col][positive]]
        values=source_data[rows];valid=np.isfinite(values).all(axis=0)
        out[valid,col]=weights[positive]@values[:,valid]
    return out


def plot_ap_ppd_balancing_comparison(baseline, corrected, sampling, coverage,
        amplitude_limit, output_path, inspection_points=None, half_width=.5, source_contributions=None, status_fractions=None,
        corrected_title="Accepted residual timing corrections", figure_title=None):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import colormaps
    distance=np.asarray(sampling['distance']);n=baseline.shape[0]
    edges=np.r_[distance[0]-(distance[1]-distance[0])/2,(distance[:-1]+distance[1:])/2,distance[-1]+(distance[-1]-distance[-2])/2]
    ys=np.arange(n+1)-.5;difference=corrected-baseline
    finite=abs(difference[np.isfinite(difference)])
    nonzero=finite[finite>0]
    diff_limit=float(np.percentile(nonzero,99)) if len(nonzero) else max(float(amplitude_limit),1.0)
    fig=Figure(figsize=(15,13),constrained_layout=True);FigureCanvasAgg(fig)
    axes=fig.subplots(5 if source_contributions else 4,1,sharex=True,
        gridspec_kw={'height_ratios':[3,3,3,1,1] if source_contributions else [3,3,3,1]})
    for ax,values,title,cmap,limit in zip(axes[:3],(baseline,corrected,difference),
            ('Recorded time zero only',corrected_title,'Corrected minus baseline (common valid samples)'),
            ('gray','gray','RdBu_r'),(amplitude_limit,amplitude_limit,diff_limit)):
        cm=colormaps[cmap].copy();cm.set_bad('lightblue')
        im=ax.pcolormesh(edges,ys,np.ma.masked_invalid(values),cmap=cm,vmin=-limit,vmax=limit,shading='flat',rasterized=True)
        ax.set_ylim(n-.5,-.5);ax.set_ylabel('Samples after recorded time zero');ax.set_title(title)
        fig.colorbar(im,ax=ax,label='Amplitude' if cmap=='gray' else 'Amplitude difference')
        for centre in (inspection_points or {}).values():
            ax.axvspan(centre-half_width,centre+half_width,facecolor='none',edgecolor='dodgerblue');ax.axvline(centre,color='dodgerblue',ls='--',lw=.8)
        excluded=np.asarray(sampling.get('excluded_chainage',[]));excluded=excluded[np.isfinite(excluded)]
        ax.plot(excluded,np.full(len(excluded),.985),'|',color='crimson',transform=ax.get_xaxis_transform())
    if status_fractions is None:
        axes[3].plot(distance,coverage*100,color='purple')
    else:
        labels={'corrected':'Corrected','evaluated_unchanged':'Evaluated, unchanged (includes references)',
                'insufficient_support':'Insufficient overlap/support','not_evaluated':'Not evaluated'}
        for key,values in status_fractions.items():
            axes[3].plot(distance,values*100,label=labels[key])
        axes[3].legend(fontsize=7,ncol=2)
    axes[3].set_ylim(-2,102)
    axes[3].set_ylabel('Source weight (%)');axes[3].set_xlabel('Distance along polysection (m)')
    axes[3].set_xlim(distance[0],distance[-1]);axes[3].grid(alpha=.2)
    if not len(nonzero): axes[2].text(.02,.9,'No amplitude change on common valid samples',transform=axes[2].transAxes)
    if source_contributions:
        for label,weights in source_contributions.items(): axes[4].plot(distance,weights*100,label=label)
        axes[4].set_ylabel('Source weight (%)');axes[4].set_ylim(-2,102)
        axes[4].legend(fontsize=7,ncol=2);axes[4].set_xlabel('Distance along polysection (m)')
    fig.suptitle(figure_title or 'Full-section timing balance — local validated corrections; same sampling and weights; gain unchanged')
    fig.savefig(output_path,dpi=180)


def discover_ap_ppd_section_seeds(traces, sampling, half_count=100):
    """Cover every positive-weight linear source and valid nearest source.

    File/channel/acquisition ranges identify local neighbourhoods, not loop IDs.
    A long contribution receives several neighbourhoods. Inspection markers do
    not restrict discovery. Trace numbers must follow acquisition order.
    """
    if not isinstance(half_count, int) or half_count < 1:
        raise ValueError('half_count must be a positive integer')
    rows = set(int(r) for r in np.asarray(sampling['nearest_index'])[sampling['nearest_valid']])
    for col in np.flatnonzero(sampling['triangle_valid']):
        rows.update(int(r) for r,w in zip(sampling['triangle_indices'][col],
                                         sampling['triangle_weights'][col]) if w > 0)
    groups = {}
    for row in sorted(rows):
        if row < 0 or row >= len(traces):
            raise ValueError('Sampling source row outside corridor')
        t = traces[row]
        groups.setdefault((int(t['file_id']),int(t['channel'])),set()).add(int(t['trace']))
    seeds = []
    for (fid,ch),numbers in sorted(groups.items()):
        covered_until = -np.inf
        for number in sorted(numbers):
            if number > covered_until:
                seeds.append(dict(file_id=fid,channel=ch,trace=number))
                covered_until = number + half_count
    return seeds


def calibrate_ap_ppd_section_sources(traces,sampling,folder_path,inspection_points=None,calibration_pairs=None):
    """Full-section discovery by default; explicit pairs restrict calibration.

    Read +/-100 acquisition trace numbers per seed from the full cache. Compare
    spatial overlaps between separated acquisition ranges, including the same
    channel on successive passes. Markers control close-ups only. Preserve the
    strict 5/10 cm validation gates; do not infer universal channel offsets.
    """
    if calibration_pairs is None:
        seeds=discover_ap_ppd_section_seeds(traces,sampling)
        print(f'Full-section calibration: {len(seeds)} source neighbourhoods')
        neighbourhoods=collect_ap_ppd_calibration_neighbourhoods(folder_path,seeds)
        candidates=[]
        bounds=[]
        for g in neighbourhoods:
            xy=np.c_[g['records']['x'],g['records']['y']]
            bounds.append((xy.min(axis=0),xy.max(axis=0)))
        for i,a in enumerate(neighbourhoods):
            for j in range(i+1,len(neighbourhoods)):
                b=neighbourhoods[j]
                # Avoid comparing simultaneous channels or overlapping pieces of
                # one acquisition range. This is a range heuristic, not a pass ID.
                if a['seed']['file_id']==b['seed']['file_id'] and abs(a['seed']['trace']-b['seed']['trace'])<=200:
                    continue
                if np.any(bounds[i][0] > bounds[j][1]+.10) or np.any(bounds[j][0] > bounds[i][1]+.10):
                    continue
                count=len(match_ap_ppd_overlap_traces(a,b,.10)[0])
                if count>=24:candidates.append((count,a,b))
        candidates.sort(key=lambda v:-v[0]);pairs=[]
        for _,a,b in candidates:
            if (a['seed']['file_id'],a['seed']['trace'])>(b['seed']['file_id'],b['seed']['trace']):a,b=b,a
            pairs.append((a,b))
    else:
        pairs=[];neighbourhoods=[]
        for specification in calibration_pairs:
            groups=collect_ap_ppd_calibration_neighbourhoods(folder_path,[specification['reference'],specification['target']])
            if len(groups)!=2:raise ValueError('Empty requested calibration neighbourhood')
            pairs.append(tuple(groups));neighbourhoods.extend(groups)
    proposals=[];eligible=[];audit=[];participating=set()
    key=lambda g:tuple(g['seed'][k] for k in ('file_id','channel','trace'))
    for pair_id,(a,b) in enumerate(pairs):
        participating.update((key(a),key(b)))
        if pair_id % 10 == 0:print(f'Calibrating overlap pair {pair_id+1}/{len(pairs)}')
        local=[]
        for tolerance in (.05,.10):
            rule,rows=estimate_ap_ppd_overlap_correction(a,b,tolerance)
            rule.update(pair_id=pair_id,applied=False,
                        reference_trace_start=a['trace_start'],reference_trace_end=a['trace_end'])
            for row in rows:row['pair_id']=pair_id
            proposals.append(rule);local.append(rule);audit.extend(rows)
        strict,wide=local
        if strict['timing_accepted'] and wide['timing_accepted'] and strict['advance_samples']==wide['advance_samples']:
            eligible.append(strict.copy())
        else:
            strict['reason'] += '; not applied: requires same accepted lag at both limits'
    # Retain unsupported neighbourhoods in the report, including sources with no
    # candidate pair. These must not disappear into an apparently successful run.
    for g in neighbourhoods:
        if key(g) not in participating:
            proposals.append(dict(**g['seed'],trace_start=g['trace_start'],trace_end=g['trace_end'],
                pair_id=-(len(proposals)+1),max_distance=.05,applied=False,timing_accepted=False,
                advance_samples=0,gain=1.,matched_pairs=0,validation=[],
                reason='no eligible separated acquisition overlap with 24 reciprocal pairs within 10 cm'))
    accepted,decisions=_resolve_ap_ppd_corrections(eligible)
    chosen={r['pair_id'] for r in accepted}
    for proposal in proposals:
        proposal['applied']=proposal['pair_id'] in chosen and proposal['max_distance']==.05
        if proposal['pair_id'] in decisions:proposal['selection_reason']=decisions[proposal['pair_id']]
    for row in audit:
        # A pair may contribute only a subset of its original scope. Match the
        # actual applied intervals rather than marking the whole pair applied.
        row['applied']=row['max_distance']==.05 and any(
            r['pair_id']==row['pair_id'] and r['trace_start']<=row['target_trace']<=r['trace_end']
            for r in accepted)
    return proposals,accepted,audit


def _resolve_ap_ppd_corrections(eligible):
    """Partition target ranges; retain agreeing coverage, reject local conflicts.

    Freeze complete reference neighbourhoods, not just their centre trace.
    No chained correction or extension outside a validated target scope.
    """
    anchors={};groups={};accepted=[];decisions={}
    for r in eligible:
        a=r['reference'];k=(a['file_id'],a['channel'])
        anchors.setdefault(k,[]).append((r.get('reference_trace_start',a['trace']-100),
                                         r.get('reference_trace_end',a['trace']+100)))
        groups.setdefault((r['file_id'],r['channel']),[]).append(r)
        decisions[r['pair_id']]='not applied: reference protection, conflict, or redundant scope'
    for key,rules in sorted(groups.items()):
        fixed=anchors.get(key,[])
        edges=sorted({v for r in rules for v in (r['trace_start'],r['trace_end']+1)} |
                     {v for lo,hi in fixed for v in (lo,hi+1)})
        for lo,stop in zip(edges[:-1],edges[1:]):
            active=[r for r in rules if r['trace_start']<=lo and r['trace_end']>=stop-1]
            if not active or any(a<=lo<=b for a,b in fixed):continue
            if len({r['advance_samples'] for r in active})!=1:continue
            best=max(active,key=lambda r:(r['matched_pairs'],-r['pair_id']))
            rule=best.copy();rule.update(trace_start=lo,trace_end=stop-1,applied=True)
            if accepted and accepted[-1]['pair_id']==rule['pair_id'] and accepted[-1]['trace_end']+1==lo:
                accepted[-1]['trace_end']=stop-1
            else:accepted.append(rule)
            decisions[best['pair_id']]='applied on reported nonconflicting intervals; reference neighbourhoods protected'
    return accepted,decisions


def ap_ppd_balance_status(metadata,proposals,corrected_mask,required_rows,sampling):
    """Report status by actual reconstruction source and weighted section column.

    Evaluated unchanged includes fixed references, failed validation, and
    conflicting proposals. It does not imply that every unchanged trace is bad.
    """
    status=np.full(len(metadata),'not_evaluated',dtype='U32')
    def mask(seed,lo,hi):
        return ((metadata['file_id']==seed['file_id'])&(metadata['channel']==seed['channel']) &
                (metadata['trace']>=lo)&(metadata['trace']<=hi))
    for r in proposals:
        m=mask(r,r['trace_start'],r['trace_end'])
        if 'reference' in r:
            m |= mask(r['reference'],r['reference_trace_start'],r['reference_trace_end'])
        status[m & (status=='not_evaluated')]='insufficient_support'
    for r in proposals:
        if not r.get('validation'):continue
        status[mask(r,r['trace_start'],r['trace_end'])]='evaluated_unchanged'
        if 'reference' in r:
            status[mask(r['reference'],r['reference_trace_start'],r['reference_trace_end'])]='evaluated_unchanged'
    status[corrected_mask]='corrected'
    categories=('corrected','evaluated_unchanged','insufficient_support','not_evaluated')
    fractions={k:np.full(len(sampling['distance']),np.nan) for k in categories}
    for col in np.flatnonzero(sampling['triangle_valid']):
        weights=np.asarray(sampling['triangle_weights'][col]);positive=weights>0
        compact=np.searchsorted(required_rows,sampling['triangle_indices'][col][positive])
        for k in categories:fractions[k][col]=float(np.sum(weights[positive]*(status[compact]==k)))
    return status,fractions


def plot_ap_ppd_balance_closeups(baseline,corrected,sampling,coverage,traces,
        required_rows,corrected_mask,amplitude_limit,prefix,inspection_points,half_width=.5):
    """Same baseline/corrected reconstruction, with actual per-channel weights."""
    paths=[];distance=np.asarray(sampling['distance'])
    for name,centre in inspection_points.items():
        cols=np.flatnonzero(abs(distance-centre)<=half_width+1e-8)
        if len(cols)<2: continue
        local={'distance':distance[cols], 'excluded_chainage':sampling.get('excluded_chainage',[])}
        contributions={}
        for j,col in enumerate(cols):
            if not sampling['triangle_valid'][col]:continue
            for row,weight in zip(sampling['triangle_indices'][col],sampling['triangle_weights'][col]):
                if weight<=0:continue
                compact=np.searchsorted(required_rows,row);t=traces[row]
                label=f"F{int(t['file_id'])}/CH{int(t['channel'])} " + ('corrected' if corrected_mask[compact] else 'unchanged')
                if label not in contributions:
                    contributions[label]=np.where(sampling['triangle_valid'][cols],0.,np.nan)
                contributions[label][j]+=weight
        safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in name)
        path=prefix+'_'+safe+'_balancing_closeup.png'
        plot_ap_ppd_balancing_comparison(baseline[:,cols],corrected[:,cols],local,coverage[cols],amplitude_limit,path,{name:centre},half_width,contributions)
        paths.append(path)
    return paths


# Within-pass comparisons deliberately remain separate from overlap corrections:
# channels sample different ground, so apparent delay is not uniquely instrumental.
def solve_ap_ppd_channel_graph(channel_count, edges, residual_limit=.5):
    """Solve advance[B]-advance[A]=lag with a zero-mean gauge per component.

    Edges are (A, B, lag, weight). Reject an inconsistent component as a whole.
    Zero-lag edges matter: they keep channels already in agreement together.
    No absolute timing or relationship between disconnected components is known.
    """
    shifts=np.zeros(channel_count); supported=np.zeros(channel_count,dtype=bool)
    components=[];remaining=set(range(channel_count))
    while remaining:
        root=min(remaining);nodes={root};changed=True
        while changed:
            changed=False
            for a,b,lag,w in edges:
                if (a in nodes or b in nodes) and not (a in nodes and b in nodes):
                    nodes.update((a,b));changed=True
        remaining-=nodes
        local=[e for e in edges if e[0] in nodes and e[1] in nodes]
        if not local:continue
        nodes=sorted(nodes);lookup={v:i for i,v in enumerate(nodes)}
        matrix=np.zeros((len(local)+1,len(nodes)));rhs=np.zeros(len(local)+1)
        for row,(a,b,lag,w) in enumerate(local):
            weight=np.sqrt(max(float(w),1.))
            matrix[row,lookup[a]]=-weight;matrix[row,lookup[b]]=weight;rhs[row]=lag*weight
        matrix[-1]=1.
        solution=np.linalg.lstsq(matrix,rhs,rcond=None)[0]
        residual=[float(solution[lookup[b]]-solution[lookup[a]]-lag) for a,b,lag,w in local]
        ok=max(abs(np.asarray(residual)))<=residual_limit and max(abs(solution))<=8
        if ok:shifts[nodes]=solution;supported[nodes]=True
        components.append(dict(nodes=nodes,accepted=bool(ok),residuals_samples=residual,
                               advances_samples=solution.tolist()))
    return shifts,supported,components


def apply_ap_ppd_fractional_advances(source_data,metadata,advances):
    """One resampling from originals: recorded TZ plus fractional residual advance.

    Positive advance samples later input positions, moving events earlier.
    Linear interpolation; no wrapping, no gain fit, no interpolation across NaNs.
    """
    _,_,base=align_ap_ppd_source_time_zero(source_data,metadata)
    advances=np.asarray(advances,dtype=float)
    if advances.shape!=(len(source_data),) or not np.isfinite(advances).all() or np.any(abs(advances)>8):
        raise ValueError('Expected one finite residual advance within +/-8 per source')
    out=np.full_like(source_data,np.nan);sample=np.arange(source_data.shape[1],dtype=float)
    for row in range(len(out)):
        out[row]=np.interp(sample-base[row]+advances[row],sample,source_data[row],left=np.nan,right=np.nan)
    return out


def compare_ap_ppd_same_pass_timing(traces,sampling,folder_path,source_data,
        required_rows,baseline,amplitude_limit,prefix,inspection_points=None):
    """Experimental same-acquisition channel calibration, separately reconstructed.

    200-trace-number blocks, +/-100 around their centres. Compare matching
    acquisition numbers at <=35 cm XY separation. Require held-out agreement in
    both windows and stable lags using 25 cm and 35 cm subsets. This cannot
    distinguish a spatially constant cross-channel geological dip from timing.
    Never combine these relative offsets blindly with the overlap correction.
    """
    import csv
    seeds=discover_ap_ppd_section_seeds(traces,sampling)
    # All actually used source rows, including long contributions covered by seeds.
    selected=traces[required_rows]
    keys=sorted({(int(t['file_id']),int(t['trace'])//200,int(t['channel'])) for t in selected})
    block_seeds=[dict(file_id=fid,channel=ch,trace=block*200+100) for fid,block,ch in keys]
    groups=collect_ap_ppd_calibration_neighbourhoods(folder_path,block_seeds)
    blocks={}
    for g in groups:
        blocks.setdefault((g['seed']['file_id'],g['seed']['trace']//200),[]).append(g)
    advances=np.zeros(len(selected));status=np.full(len(selected),'no_supported_channel_pair',dtype='U40')
    reports=[];audit=[]
    for (fid,block),channels in sorted(blocks.items()):
        channels.sort(key=lambda g:g['seed']['channel']);edges=[];pair_reports=[]
        print(f'Within-pass timing: file {fid}, trace block {block*200}-{block*200+199}, {len(channels)} channels')
        for i,a in enumerate(channels):
            for j in range(i+1,len(channels)):
                b=channels[j]
                common,ia,ib=np.intersect1d(a['records']['trace'],b['records']['trace'],return_indices=True)
                d=np.hypot(a['records']['x'][ia]-b['records']['x'][ib],a['records']['y'][ia]-b['records']['y'][ib])
                if np.count_nonzero(d<=.35)<24:continue
                rules=[]
                for limit in (.25,.35):
                    keep=d<=limit
                    rule,rows=estimate_ap_ppd_overlap_correction(a,b,limit,
                        matched_indices=(ia[keep],ib[keep],d[keep]),allow_zero=True)
                    rules.append(rule)
                    for row in rows:
                        row.update(block_start=block*200,method='same_acquisition_experimental')
                        audit.append(row)
                accepted=all(r['timing_accepted'] for r in rules) and rules[0]['advance_samples']==rules[1]['advance_samples']
                pair_reports.append(dict(reference_channel=a['seed']['channel'],target_channel=b['seed']['channel'],
                    accepted=bool(accepted),tests=rules))
                if accepted:edges.append((i,j,rules[0]['advance_samples'],rules[0]['matched_pairs']))
        shifts,support,components=solve_ap_ppd_channel_graph(len(channels),edges)
        for i,g in enumerate(channels):
            mask=(selected['file_id']==fid)&(selected['channel']==g['seed']['channel']) & (selected['trace']//200==block)
            if support[i]:
                advances[mask]=shifts[i]
                status[mask]='relative_channel_solution'
        reports.append(dict(file_id=fid,block_start=block*200,block_end=block*200+199,
            channels=[g['seed']['channel'] for g in channels],pairs=pair_reports,components=components))
    # Explicit block boundaries are exported. Do not smooth offsets across an
    # unsupported interval or hide a correction step with amplitude blending.
    corrected=apply_ap_ppd_fractional_advances(source_data,selected,advances)
    section=interpolate_ap_ppd_source_matrix(corrected,required_rows,sampling)
    coverage=np.full(len(sampling['distance']),np.nan)
    solved=np.full_like(coverage,np.nan)
    for col in np.flatnonzero(sampling['triangle_valid']):
        w=np.asarray(sampling['triangle_weights'][col]);positive=w>0
        rows=np.searchsorted(required_rows,sampling['triangle_indices'][col][positive])
        coverage[col]=float(w[positive]@(abs(advances[rows])>1e-8))
        solved[col]=float(w[positive]@(status[rows]=='relative_channel_solution'))
    path=prefix+'_same_pass_timing_comparison.png'
    plot_ap_ppd_balancing_comparison(baseline,section,sampling,coverage,amplitude_limit,path,
        inspection_points,corrected_title='Experimental within-pass relative channel timing',
        figure_title='Within-pass timing experiment — separate from overlap corrections; geology/timing ambiguity remains')
    with open(prefix+'_same_pass_timing.json','w',encoding='utf-8') as f:
        json.dump(dict(version=1,blocks=reports,note='Relative zero-mean offsets per connected component; not absolute timing calibration. Different ground positions; experimental only.'),f,indent=2)
    with open(prefix+'_same_pass_source_shifts.csv','w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['subset_row','file_id','channel','trace','block_start','advance_samples','status'])
        for row,t,advance,state in zip(required_rows,selected,advances,status):
            writer.writerow([int(row),int(t['file_id']),int(t['channel']),int(t['trace']),int(t['trace'])//200*200,float(advance),state])
    with open(prefix+'_same_pass_validation.csv','w',newline='',encoding='utf-8') as f:
        fields=list(audit[0]) if audit else ['method','block_start','accepted']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(audit)
    np.savez_compressed(prefix+'_same_pass_sections.npz',baseline=baseline,experimental=section,
        distance=sampling['distance'],source_advances=advances,required_rows=required_rows,
        corrected_weight=coverage,solved_weight=solved)
    print(f'Within-pass experiment: {np.count_nonzero(abs(advances)>1e-8)}/{len(advances)} sources shifted; {path}')
    return dict(output_path=path,section=section,source_advances=advances,source_status=status,
                corrected_weight=coverage,solved_weight=solved)


# PER-OUTPUT-TRACE TIMING EXPERIMENT (same algorithm as test_section_timing.py)
def _ap_section_correlation(a, b):
    if len(a) < 24 or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return np.nan
    a = a - a.mean()
    b = b - b.mean()
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / den) if den > 0 else np.nan

def _ap_section_advance(values, lag):
    ix = np.arange(len(values), dtype=float)
    return np.interp(ix + lag, ix, values, left=np.nan, right=np.nan)

def _ap_section_reference(section, x, column, radius, max_gap):
    left, right = (column - radius, column + radius)
    if left < 0 or right >= len(x):
        return None
    if x[column] - x[left] > max_gap or x[right] - x[column] > max_gap:
        return None
    weight = (x[column] - x[left]) / (x[right] - x[left])
    return (1 - weight) * section[:, left] + weight * section[:, right]

def _ap_section_measure(trace, template, window, lags):
    lo, hi = window
    margin = int(np.ceil(max(abs(lags)))) + 1
    ix = np.arange(lo + margin, hi - margin)
    candidates = np.array([_ap_section_advance(trace, k)[ix] for k in lags])
    valid = np.isfinite(template[ix]) & np.isfinite(candidates).all(axis=0)
    if valid.sum() < 24:
        return None
    scores = np.array([_ap_section_correlation(template[ix][valid], a[valid]) for a in candidates])
    if not np.isfinite(scores).all():
        return None
    ties = np.flatnonzero(np.isclose(scores, scores.max(), atol=1e-10, rtol=0))
    best = ties[np.argmin(abs(lags[ties]))]
    return (scores, int(best))

def analyse_ap_ppd_section_timing(section, x, windows=((80, 150), (150, 230), (230, 320)), max_lag=3.0, max_gap=0.3, fit_mode="multiwindow"):
    """Fit the median correlation across available coherent windows.

    fit_mode="shallow" reproduces the earlier window-0 experiment.
    Multiwindow checks are consistency checks, not independent validation.

    All references and scores come from the ORIGINAL baseline in one pass.
    No sequential re-estimation and no amplitude normalization of outputs.
    """
    section = np.asarray(section, dtype=float)
    x = np.asarray(x, dtype=float)
    if section.ndim != 2 or section.shape[1] != len(x) or len(x) < 9 or (not np.isfinite(x).all()) or np.any(np.diff(x) <= 0):
        raise ValueError('Need samples x positions, at least 9 increasing positions')
    if not np.isfinite(max_lag) or not 0 < max_lag <= 8 or (not np.isfinite(max_gap)) or (max_gap <= 0):
        raise ValueError('max-lag must be in (0,8]; max-gap must be positive')
    for lo, hi in windows:
        if not 0 <= lo < hi <= section.shape[0] or hi - lo < 24 + 2 * (int(np.ceil(max_lag)) + 1):
            raise ValueError('Sample windows too short or outside section')
    if fit_mode not in ("shallow", "multiwindow") or len(windows) != 3:
        raise ValueError("Require three windows and shallow or multiwindow fit_mode.")
    limit = np.floor(max_lag * 4) / 4
    if limit < 0.25:
        raise ValueError('max-lag must be at least 0.25')
    lags = np.arange(-limit, limit + 0.125, 0.25)
    zero = int(np.argmin(abs(lags)))
    proposed = np.zeros(len(x))
    applied = np.zeros(len(x))
    rows = []
    for col in range(len(x)):
        row = dict(column=col, distance_m=float(x[col]), proposed_advance=0.0, applied_advance=0.0, accepted=False, reason='insufficient support')
        measurements = {}
        for radius in (1, 2, 4):
            template = _ap_section_reference(section, x, col, radius, max_gap)
            if template is None:
                continue
            for w, window in enumerate(windows):
                result = _ap_section_measure(section[:, col], template, window, lags)
                if result is not None:
                    measurements[radius, w] = result
        if (1, 0) not in measurements:
            rows.append(row)
            continue
        scores, best = measurements[1, 0]
        row["fit_mode"] = fit_mode
        if fit_mode == "multiwindow":
            coherent = [measurements[1, w][0] for w in range(3)
                        if (1, w) in measurements and
                        measurements[1, w][0].max() >= 0.7]
            if len(coherent) >= 2:
                scores = np.median(coherent, axis=0)
                best = int(np.argmax(scores))
            row["fitting_windows"] = len(coherent)
        lag = float(lags[best])
        row["at_search_limit"] = bool(best in (0, len(lags)-1))

        proposed[col] = lag
        row['proposed_advance'] = lag
        failures = []
        if best in (0, len(lags) - 1):
            failures.append('search limit')
        if scores[best] < 0.85 or scores[best] - scores[zero] < 0.015:
            failures.append('weak fitting-window improvement')
        for radius in (2, 4):
            if (radius, 0) not in measurements:
                failures.append('missing radius check')
                continue
            sc, bi = measurements[radius, 0]
            if abs(lags[bi] - lag) > 0.75:
                failures.append('neighbour-radius disagreement')
        validation_gains = []
        for w in range(3):
            if (1, w) not in measurements:
                failures.append('missing validation window')
                continue
            sc, bi = measurements[1, w]
            gain = float(sc[best] - sc[zero])
            row.update({f'w{w}_best_lag': float(lags[bi]), f'w{w}_before': float(sc[zero]), f'w{w}_after': float(sc[best]), f'w{w}_gain': gain})
            if w > 0:
                validation_gains.append(gain)
                if gain < -0.01 or sc[best] < 0.7:
                    failures.append('validation degradation or low correlation')
                if abs(lags[bi] - lag) > 1.0:
                    failures.append('sample-window lag disagreement')
        if not validation_gains or max(validation_gains) < 0.01:
            failures.append('no independent-window improvement')
        for radius in (2, 4):
            if (radius, 0) in measurements:
                row[f'radius{radius}_lag'] = float(lags[measurements[radius, 0][1]])
        if not failures:
            applied[col] = lag
            row['accepted'] = True
            row['applied_advance'] = lag
        row['reason'] = 'checks passed (experimental)' if not failures else '; '.join(sorted(set(failures)))
        rows.append(row)
    preview = np.column_stack([_ap_section_advance(section[:, i], k) for i, k in enumerate(proposed)])
    checked = np.column_stack([_ap_section_advance(section[:, i], k) for i, k in enumerate(applied)])
    return (preview, checked, proposed, applied, rows)

def create_ap_ppd_section_timing_comparison(baseline, distance, output, max_lag=3., max_gap=.3, windows=((80,150),(150,230),(230,320)), fit_mode="multiwindow"):
    """Reproduce the standalone timing experiment from the TZ-aligned section.

    Separate output product; original sections and source calibrations are not
    replaced. Proposals and checked shifts are both available for comparison.
    No gain fitting. Do not stack this blindly with other timing corrections.
    """
    import csv
    from pathlib import Path
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    section=np.asarray(baseline,dtype=float)
    x=np.asarray(distance,dtype=float)
    preview, checked, proposed, applied, rows = analyse_ap_ppd_section_timing(section, x, windows, max_lag, max_gap, fit_mode)
    fields = list(dict.fromkeys((k for r in rows for k in r)))
    with open(output / 'trace_timing.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(input='in-memory time-zero-aligned linear section', windows=[list(v) for v in windows], max_lag=max_lag, max_gap_m=max_gap, positions=len(x), nonzero_proposals=int(np.count_nonzero(proposed)), checked_shifts=int(np.count_nonzero(applied)), interpretation='Continuity experiment on interpolated section traces, not calibrated source timing. A smoother picture does not prove correctness.')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    np.savez_compressed(output / 'timing_experiment.npz', baseline=section, unfiltered_proposal=preview, checked_proposal=checked, distance=x, proposed_advances=proposed, applied_advances=applied)
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    edges = np.r_[x[0] - (x[1] - x[0]) / 2, (x[:-1] + x[1:]) / 2, x[-1] + (x[-1] - x[-2]) / 2]
    finite = abs(section[np.isfinite(section)])
    limit = max(float(np.percentile(finite, 99)), 1e-12) if len(finite) else 1.0
    fig = Figure(figsize=(15, 12), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(4, 1, sharex=True)
    for ax, array, title in zip(axes[:3], (section, preview, checked), ('Baseline', 'Unfiltered proposed shifts — exploratory only', 'Shifts passing window and radius checks — still experimental')):
        im = ax.pcolormesh(edges, np.arange(section.shape[0] + 1) - 0.5, np.ma.masked_invalid(array), cmap='gray', vmin=-limit, vmax=limit, shading='flat')
        ax.set_ylim(section.shape[0] - 0.5, -0.5)
        ax.set_title(title)
        ax.set_ylabel('Samples after recorded time zero')
    axes[3].plot(x, proposed, label='Proposed advance', alpha=0.6)
    axes[3].plot(x, applied, label='Checked advance')
    axes[3].set_ylabel('Advance (samples)')
    axes[3].set_xlabel('Section distance (m)')
    axes[3].legend()
    axes[3].grid(alpha=0.2)
    fig.colorbar(im, ax=list(axes[:3]), label='Amplitude — common scale')
    fig.savefig(output / 'section_experiment.png', dpi=160)
    fig = Figure(figsize=(14, 7), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(2, 1, sharex=True)
    for w in range(3):
        axes[0].plot(x, [r.get(f'w{w}_best_lag', np.nan) for r in rows], label=f'Window {windows[w]}')
        axes[1].plot(x, [r.get(f'w{w}_gain', np.nan) for r in rows], label=f'Window {windows[w]}')
    axes[0].set_ylabel('Independently preferred lag')
    axes[1].set_ylabel('Correlation change at fitted lag')
    axes[1].set_xlabel('Section distance (m)')
    for ax in axes:
        ax.legend()
        ax.grid(alpha=0.2)
    fig.savefig(output / 'window_agreement.png', dpi=160)
    print(json.dumps(summary, indent=2))
    return dict(summary=summary, proposed=preview, checked=checked,
                proposed_advances=proposed, checked_advances=applied,
                output_path=str(output/'section_experiment.png'),
                diagnostics_path=str(output/'window_agreement.png'),
                csv_path=str(output/'trace_timing.csv'))


def experiment_ap_ppd_section_gain(
    section, distance, windows=((80, 150), (150, 230), (230, 320)),
    radius_m=0.30, bounds=(0.8, 1.25), max_ratio_spread=1.15,
):
    """Mild local scalar gain experiment on a timing-corrected section.

    Input shape is samples x positions. Estimate robust RMS in each window
    against the median RMS of neighbours on both sides, excluding this column.
    Require three neighbours, bilateral support, and agreement between all
    window ratios. No gain interpolation over unsupported columns, no AGC,
    no timing changes. Broad amplitude trends are approximately retained.
    Returns corrected data, applied/proposed gains, acceptance mask and ratios.
    """
    section = np.asarray(section, dtype=float)
    distance = np.asarray(distance, dtype=float)
    if (section.ndim != 2 or distance.ndim != 1 or
            section.shape[1] != len(distance) or len(distance) < 2 or
            not np.isfinite(distance).all() or np.any(np.diff(distance) <= 0)):
        raise ValueError("Require samples x positions and increasing finite distance.")
    if (not np.isfinite(radius_m) or radius_m <= 0 or
            len(bounds) != 2 or not 0 < bounds[0] <= 1 <= bounds[1] or
            not np.isfinite(bounds).all() or
            not np.isfinite(max_ratio_spread) or max_ratio_spread < 1):
        raise ValueError("Invalid gain radius, bounds or ratio spread.")
    windows = tuple(windows)
    if len(windows) < 2:
        raise ValueError("At least two independent sample windows are required.")
    energy = np.full((len(windows), len(distance)), np.nan)
    for k, (first, last) in enumerate(windows):
        if int(first) != first or int(last) != last or not 0 <= first < last <= section.shape[0]:
            raise ValueError("Gain windows must lie within the sample axis.")
        for j in range(len(distance)):
            values = section[int(first):int(last), j]
            finite = values[np.isfinite(values)]
            if len(finite) < max(8, int(np.ceil(0.8 * (last-first)))):
                continue
            # Winsorize isolated spikes without normalizing the source waveform.
            absolute = np.abs(finite)
            cap = np.percentile(absolute, 95)
            rms = np.sqrt(np.mean(np.minimum(absolute, cap)**2))
            if rms > 0:
                energy[k, j] = rms
    ratios = np.full_like(energy, np.nan)
    proposed = np.full(len(distance), np.nan)
    gains = np.ones(len(distance))
    accepted = np.zeros(len(distance), dtype=bool)
    for j, position in enumerate(distance):
        lo = np.searchsorted(distance, position-radius_m)
        hi = np.searchsorted(distance, position+radius_m, side="right")
        neighbours = np.arange(lo, hi)
        neighbours = neighbours[neighbours != j]
        for k in range(len(windows)):
            valid = neighbours[np.isfinite(energy[k, neighbours])]
            if (len(valid) < 3 or not np.any(valid < j) or
                    not np.any(valid > j) or not np.isfinite(energy[k, j])):
                continue
            ratios[k, j] = np.median(energy[k, valid]) / energy[k, j]
        column = ratios[:, j]
        if not np.isfinite(column).all():
            continue
        proposed[j] = np.exp(np.median(np.log(column)))
        if column.max()/column.min() <= max_ratio_spread:
            gains[j] = np.clip(proposed[j], *bounds)
            accepted[j] = True
    status = np.full(len(distance), "insufficient_support", dtype=object)
    status[np.isfinite(proposed)] = "window_disagreement"
    status[accepted] = "accepted"
    clipped = accepted & ((proposed < bounds[0]) | (proposed > bounds[1]))
    status[clipped] = "clipped"
    summary = {name: int(np.count_nonzero(status == name)) for name in
               ("insufficient_support", "window_disagreement", "accepted", "clipped")}
    summary["changed"] = int(np.count_nonzero(np.abs(gains-1) > 1e-6))
    print("Gain experiment:", summary)
    return dict(status=status, summary=summary,
                corrected=section*gains[None, :], gains=gains,
                proposed_gains=proposed, accepted=accepted, window_ratios=ratios)


def plot_ap_ppd_gain_comparison(section, distance, result, output_path,
                                clip_percentile=99.0):
    """Save timing-only versus timing+gain with shared scale and multipliers."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import colormaps
    x = np.asarray(distance)
    edges = np.r_[x[0]-(x[1]-x[0])/2, (x[:-1]+x[1:])/2,
                  x[-1]+(x[-1]-x[-2])/2]
    finite = np.abs(np.asarray(section)[np.isfinite(section)])
    limit = max(float(np.percentile(finite, clip_percentile)), 1e-12) if len(finite) else 1.
    fig = Figure(figsize=(15, 10), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(3, 1, sharex=True, gridspec_kw={"height_ratios": [3, 3, 1]})
    cmap = colormaps["gray"].copy()
    cmap.set_bad("lightblue")
    for ax, data, title in zip(axes[:2], (section, result["corrected"]),
                              ("Experimental timing — gain unchanged",
                               "Experimental timing + local scalar gain")):
        im = ax.pcolormesh(edges, np.arange(data.shape[0]+1)-.5,
                          np.ma.masked_invalid(data), cmap=cmap,
                          vmin=-limit, vmax=limit, shading="flat")
        ax.set_ylim(data.shape[0]-.5, -.5)
        ax.set_ylabel("Samples after recorded time zero")
        ax.set_title(title)
    axes[2].plot(x, result["proposed_gains"], color="gray", alpha=.4,
                 label="Proposed (including rejected)")
    axes[2].plot(x, result["gains"], label="Applied multiplier")
    axes[2].axhline(1, color="gray", linestyle="--", linewidth=.8)
    axes[2].set_ylabel("Gain")
    axes[2].set_xlabel("Distance along polysection (m)")
    axes[2].grid(alpha=.2)
    axes[2].legend()
    fig.colorbar(im, ax=list(axes[:2]), label="Amplitude — shared scale")
    fig.suptitle("Gain experiment: " + ", ".join(
        f"{k}={v}" for k, v in result["summary"].items()))
    fig.savefig(output_path, dpi=180)
    import csv
    csv_path = os.path.splitext(str(output_path))[0] + ".csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["distance_m", "proposed_gain", "applied_gain", "status"])
        writer.writerows(zip(x, result["proposed_gains"], result["gains"], result["status"]))
    result["csv_path"] = csv_path
    return str(output_path)



def _ap_joint_pair(trace, reference, windows, max_lag):
    """Positive lag means advance trace relative to reference; fixed support."""
    records = []
    shifts = np.arange(-max_lag, max_lag+1)
    for first, last in windows:
        ix = np.arange(first+max_lag, last-max_lag)
        target = trace[ix[None, :]+shifts[:, None]]
        ref = reference[ix]
        valid = np.isfinite(ref) & np.isfinite(target).all(axis=0)
        if valid.sum() < 24:
            records.append(dict(lag=np.nan, correlation=np.nan, before=np.nan,
                                boundary=False, reason="missing_samples"))
            continue
        a = target[:, valid]
        a = a-a.mean(axis=1, keepdims=True)
        b = ref[valid]-ref[valid].mean()
        den = np.linalg.norm(a, axis=1)*np.linalg.norm(b)
        scores = np.divide(a@b, den, out=np.full(len(shifts), np.nan), where=den>0)
        if not np.isfinite(scores).all():
            records.append(dict(lag=np.nan, correlation=np.nan, before=np.nan,
                                boundary=False, reason="no_signal"))
            continue
        best = int(np.argmax(scores))
        boundary = best in (0, len(shifts)-1)
        lag = float(shifts[best])
        if not boundary:
            curvature = scores[best-1]-2*scores[best]+scores[best+1]
            if curvature < -1e-10:
                lag += float(np.clip(.5*(scores[best-1]-scores[best+1])/curvature, -.5, .5))
        records.append(dict(lag=lag, correlation=float(scores[best]),
                            before=float(scores[max_lag]), boundary=boundary,
                            reason="search_limit" if boundary else "measured"))
    return records


def _ap_timing_trend_basis(metadata, knot_spacing, pass_ids=None):
    """Cubic along-track nuisance trends per channel/pass; split acquisition gaps.

    Knot spacing limits the geological model's spatial frequency. Curvature is
    weakly penalized; linear and quadratic reflectors are represented directly.
    This separation remains ambiguous for genuinely abrupt geological features.
    """
    from scipy.sparse import coo_matrix
    from scipy.interpolate import BSpline
    n=len(metadata); groups={}
    for i,t in enumerate(metadata):
        key=(int(t['file_id']),int(t['channel']),str(pass_ids[i]) if pass_ids is not None else '')
        groups.setdefault(key,[]).append(i)
    rows=[];cols=[];values=[];cr=[];cc=[];cv=[]
    curve_ids=np.full(n,-1,int); along=np.zeros(n); nk=0; nr=0; curve=0
    spacing=knot_spacing/2
    for key in sorted(groups):
        order=np.array(sorted(groups[key],key=lambda i:(int(metadata['trace'][i]),float(metadata['x'][i]),float(metadata['y'][i]))))
        xy=np.column_stack((metadata['x'][order],metadata['y'][order]))
        ds=np.linalg.norm(np.diff(xy,axis=0),axis=1);dt=np.diff(metadata['trace'][order].astype(float))
        breaks=np.flatnonzero((ds>knot_spacing)|(dt>16)|(dt<=0))+1
        for part in np.split(order,breaks):
            if not len(part): continue
            xy=np.column_stack((metadata['x'][part],metadata['y'][part]))
            x=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
            length=max(float(x[-1]),spacing)
            # Distribute the intervals evenly: a tiny remainder at the right edge
            # otherwise creates enormous second derivatives and false LSMR convergence.
            grid=np.linspace(0.,length,max(1,int(np.ceil(length/spacing)))+1)
            knots=np.r_[np.zeros(4),grid[1:-1],np.full(4,length)]
            count=len(knots)-4
            # Building locally avoids a global dense source x spline matrix.
            b=BSpline.design_matrix(x,knots,3).tocoo()
            rows.extend(part[b.row]);cols.extend(b.col+nk);values.extend(b.data)
            locations=np.linspace(0,length,max(3,int(np.ceil(length/spacing))*2+1))
            # Evaluate compact second derivatives without a dense identity matrix.
            for k in range(count):
                unit=np.zeros(count);unit[k]=1.
                derivative=BSpline(knots,unit,3)(locations,nu=2)*spacing**2
                keep=np.flatnonzero(abs(derivative)>1e-12)
                cr.extend(nr+keep);cc.extend([nk+k]*len(keep));cv.extend(derivative[keep])
            nr+=len(locations);nk+=count;curve_ids[part]=curve;along[part]=x;curve+=1
    return (coo_matrix((values,(rows,cols)),shape=(n,nk)).tocsr(),
            coo_matrix((cv,(cr,cc)),shape=(nr,nk)).tocsr(),curve_ids,along)


def _ap_timing_solve(matrix, target, weights, penalty, penalty_weights,
                     iterations=5, huber=.25):
    """Robust sparse fit. All penalties belong to the joint fit, not a later detrend."""
    from scipy.sparse import vstack
    from scipy.sparse.linalg import lsmr
    robust = np.ones(len(target))
    answer = np.zeros(matrix.shape[1])
    for _ in range(iterations):
        root = np.sqrt(weights * robust)
        system = vstack((matrix.multiply(root[:, None]),
                         penalty.multiply(np.sqrt(penalty_weights)[:, None])), format='csr')
        rhs = np.r_[target * root, np.zeros(penalty.shape[0])]
        fit = lsmr(system, rhs, damp=1e-6, atol=2e-6, btol=2e-6,
                   maxiter=2500, x0=answer)
        if fit[1] not in (0, 1, 2, 4, 5):
            raise RuntimeError('Timing fit did not converge; no result was applied.')
        answer = fit[0]
        residual = matrix @ answer - target
        robust = np.minimum(1., huber / np.maximum(np.abs(residual), 1e-9))
    return answer


def analyse_ap_ppd_source_jitter(data, metadata, radius_m=.35, max_lag=4,
                                min_neighbours=6, trend_radius_m=.8,
                                min_correlation=.80, lag_agreement=.75,
                                same_pass_trace_gap=12, overlap_radius_m=.06,
                                max_correction=3., pass_ids=None,
                                windows=((80,150),(150,230),(230,320)),
                                validation_window=(330,410),
                                static_penalty=.04, trend_penalty=.001,
                                validation_tolerance=.01,
                                minimum_improvement=.002):
    """V10: shared source statics + window-specific smooth trends fitted jointly.

    Sources x samples must already have recorded time zero applied. Windows 0/1
    fit statics; window 2 fits ONLY a smooth nuisance trend for validation. The
    optional fourth window checks deeper data when coherent. No cross-window
    lag agreement veto: differing geological dips are modeled per window.

    Same-channel neighbours and up to four physically neighbouring channel
    groups are included. Without explicit pass IDs, acquisition identity remains
    a trace-number heuristic. Stable IDs sort pair orientation independent of
    incoming row order. Broad channel/pass offsets remain uncalibrated.

    Final waveform correlations compensate only the smooth spatial lag and use
    the exact fractionally shifted waveforms. Failed pairs roll back BOTH sources;
    all pairs are rechecked after rollback. If no stable set is reached, rollback
    is complete. No sequential shifting, gain fitting, or extrapolated samples.
    These are model-dependent quality checks, not independent archaeological truth.
    lag_agreement is retained for API compatibility and used as a residual limit.
    """
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix, hstack, vstack, block_diag, eye, csr_matrix
    data = np.asarray(data, dtype=float)
    required = {'x','y','file_id','channel','trace'}
    if (data.ndim != 2 or not len(data) or len(data) != len(metadata)
            or not required.issubset(metadata.dtype.names or ())):
        raise ValueError('Need source x samples and matching structured metadata.')
    n = len(data)
    xy = np.column_stack((metadata['x'], metadata['y'])).astype(float)
    if (not np.isfinite(xy).all() or
        not np.isfinite([radius_m, trend_radius_m, min_correlation, lag_agreement,
                        max_correction, overlap_radius_m, static_penalty, trend_penalty,
                        validation_tolerance, minimum_improvement]).all() or
        not 0 < radius_m <= trend_radius_m or not 0 < min_correlation <= 1 or
        min_neighbours < 4 or int(min_neighbours) != min_neighbours or
        int(max_lag) != max_lag or not 1 <= max_lag <= 8 or
        max_correction <= 0 or overlap_radius_m <= 0 or same_pass_trace_gap < 0 or
        lag_agreement <= 0 or static_penalty <= 0 or trend_penalty <= 0 or
        validation_tolerance < 0 or minimum_improvement < 0):
        raise ValueError('Invalid source timing parameters.')
    max_lag = int(max_lag)
    if pass_ids is not None:
        pass_ids = np.asarray(pass_ids)
        if pass_ids.shape != (n,):
            raise ValueError('pass_ids must match the expanded source rows.')
    windows = tuple(tuple(w) for w in windows)
    if len(windows) != 3:
        raise ValueError('Require two fitting windows and one validation window.')
    measured_windows = list(windows)
    if validation_window is not None:
        measured_windows.append(tuple(validation_window))
    previous = -1
    for lo, hi in measured_windows:
        if int(lo) != lo or int(hi) != hi or lo < previous or not 0 <= lo < hi <= data.shape[1] or hi-lo < 24+2*max_lag:
            raise ValueError('Need ordered nonoverlapping sample windows within the data.')
        previous = hi
    fid, ch, tr = (metadata[k] for k in ('file_id','channel','trace'))
    ids = [(int(fid[i]), int(ch[i]), int(tr[i]), float(xy[i,0]), float(xy[i,1])) for i in range(n)]
    if len(set(ids)) != n:
        raise ValueError('Duplicate source identities: deduplicate sources before timing analysis.')
    tree = cKDTree(xy)
    selected_pairs = set()
    for i in range(n):
        groups = {}
        for j in tree.query_ball_point(xy[i], radius_m):
            if i == j: continue
            separation = float(np.linalg.norm(xy[i]-xy[j]))
            same = fid[i] == fid[j] and (pass_ids[i] == pass_ids[j] if pass_ids is not None
                                        else abs(int(tr[i])-int(tr[j])) <= same_pass_trace_gap)
            if not same and separation > overlap_radius_m: continue
            groups.setdefault((int(fid[j]), int(ch[j])), []).append((separation, ids[j], j))
        own = (int(fid[i]), int(ch[i]))
        chosen = sorted(groups.get(own, []))[:8]
        others = sorted((min(v)[0], key) for key,v in groups.items() if key != own)
        for _, key in others[:4]: chosen.extend(sorted(groups[key])[:2])
        for _, _, j in chosen:
            selected_pairs.add((i,j) if ids[i] < ids[j] else (j,i))
    pair_list = sorted(selected_pairs, key=lambda ij: (ids[ij[0]], ids[ij[1]]))
    measurements, pair_rows = [], []
    for p, (i,j) in enumerate(pair_list):
        if p and p % 10000 == 0: print(f'Joint timing pairs: {p}/{len(pair_list)}', flush=True)
        m = _ap_joint_pair(data[i], data[j], measured_windows, max_lag)
        measurements.append(m)
        row = dict(pair_id=p, source_i=i, source_j=j, file_i=int(fid[i]), channel_i=int(ch[i]),
                   trace_i=int(tr[i]), file_j=int(fid[j]), channel_j=int(ch[j]), trace_j=int(tr[j]),
                   separation_m=float(np.linalg.norm(xy[i]-xy[j])), status='not_fitted')
        for k, one in enumerate(m):
            for name,value in one.items(): row[f'w{k}_{name}'] = value
            row[f'w{k}_smooth_lag'] = np.nan
            row[f'w{k}_final_before'] = np.nan
            row[f'w{k}_final_after'] = np.nan
        pair_rows.append(row)
    basis, curvature, curves, along = _ap_timing_trend_basis(metadata, trend_radius_m, pass_ids)
    nk = basis.shape[1]
    ii = np.array([p[0] for p in pair_list], int); jj = np.array([p[1] for p in pair_list], int)
    incidence = coo_matrix((np.r_[np.ones(len(ii)), -np.ones(len(ii))],
        (np.tile(np.arange(len(ii)), 2), np.r_[ii,jj])), shape=(len(ii), n)).tocsr()
    smooth = incidence @ basis
    coherent = np.array([[m['reason']=='measured' and m['correlation'] >= min_correlation
                          for m in ms] for ms in measurements], bool).reshape(len(ii), len(measured_windows))
    obs, target, weight, fitting_pairs = [], [], [], []
    for w in range(2):
        selected = np.flatnonzero(coherent[:,w])
        blocks = [incidence[selected], smooth[selected] if w == 0 else csr_matrix((len(selected),nk)),
                  smooth[selected] if w == 1 else csr_matrix((len(selected),nk))]
        obs.append(hstack(blocks, format='csr'))
        target.extend(measurements[p][w]['lag'] for p in selected)
        weight.extend(measurements[p][w]['correlation']**2 for p in selected)
        fitting_pairs.extend(selected)
    matrix = vstack(obs, format='csr'); target = np.asarray(target); weight = np.asarray(weight)
    degrees = np.asarray(abs(incidence[np.flatnonzero(coherent[:,:2].any(axis=1))]).sum(axis=0)).ravel()
    eligible = np.zeros(n, bool)
    for i in np.flatnonzero(degrees >= 2):
        nearby = tree.query_ball_point(xy[i], trend_radius_m)
        neighbours = np.array([j for j in nearby if j != i and curves[j] == curves[i] and degrees[j] >= 2], int)
        eligible[i] = len(neighbours) >= min_neighbours and np.any(along[neighbours] < along[i]) and np.any(along[neighbours] > along[i])
    penalty = block_diag((eye(n), curvature, curvature), format='csr')
    proposal = np.zeros(n); advances = np.zeros(n)
    trend_lags = np.full((len(pair_list), len(measured_windows)), np.nan)
    model_residual = np.full(n, np.nan)
    status = np.where(eligible, 'no_supported_solution', 'insufficient_context').astype(object)
    if len(target) and eligible.any():
        # Unsupported nodes are fixed to zero IN the solve, via column removal.
        free = np.r_[np.flatnonzero(eligible), np.arange(n,n+2*nk)]
        static_weights = static_penalty * np.maximum(degrees,1.)
        pw = np.r_[static_weights, np.full(2*curvature.shape[0], trend_penalty)]
        solution = np.zeros(n+2*nk)
        for outer in range(4):
            if n > 1000: print(f'Joint timing: simultaneous fit {outer+1}/4', flush=True)
            fit = _ap_timing_solve(matrix[:,free], target, weight, penalty[:,free], pw, iterations=3)
            solution[:] = 0.; solution[free] = fit
            # Sparse departure prior; do not independently detrend the solution.
            pw[:n] = static_weights / np.maximum(np.abs(solution[:n]), .10)
        proposal = solution[:n].copy()
        advances = np.where(eligible & (abs(proposal) <= max_correction) & (abs(proposal) >= .05), proposal, 0.)
        status[eligible] = 'negligible'
        status[eligible & (abs(proposal) > max_correction)] = 'correction_limit'
        status[advances != 0] = 'proposed'
        for w in range(2): trend_lags[:,w] = smooth @ solution[n+w*nk:n+(w+1)*nk]
        # Validation window trends cannot fit a separate per-trace timing term.
        # Freeze these smooth references before any rollback/rechecking.
        for w in range(2, len(measured_windows)):
            selected = np.flatnonzero(coherent[:,w])
            if len(selected):
                y = np.array([measurements[p][w]['lag'] for p in selected]) - incidence[selected] @ proposal
                weights = np.array([measurements[p][w]['correlation']**2 for p in selected])
                fit = _ap_timing_solve(smooth[selected], y, weights, curvature,
                                       np.full(curvature.shape[0],trend_penalty))
                trend_lags[:,w] = smooth @ fit
        final_residual = matrix @ solution - target
        residuals_by_source = [[] for _ in range(n)]
        for p, value in zip(fitting_pairs, abs(final_residual)):
            residuals_by_source[ii[p]].append(value)
            residuals_by_source[jj[p]].append(value)
        for i in np.flatnonzero(eligible):
            if residuals_by_source[i]: model_residual[i] = np.median(residuals_by_source[i])
        bad = np.isfinite(model_residual) & (model_residual > lag_agreement)
        advances[bad] = 0.; status[bad] = 'fit_residual'
    result = dict(advances=advances, proposed_advances=proposal, pairs=pair_rows,
                  settings=dict(method='joint_statics_and_window_trends_v11', radius_m=radius_m,
                      trend_radius_m=trend_radius_m, max_lag=max_lag, max_correction=max_correction,
                      min_neighbours=min_neighbours, lag_agreement=lag_agreement,
                      same_pass_trace_gap=same_pass_trace_gap, overlap_radius_m=overlap_radius_m,
                      min_correlation=min_correlation, windows=[list(w) for w in windows],
                      validation_window=list(validation_window) if validation_window is not None else None,
                      static_penalty=static_penalty, trend_penalty=trend_penalty,
                      validation_tolerance=validation_tolerance, minimum_improvement=minimum_improvement,
                      pass_identity='explicit' if pass_ids is not None else 'trace_number_heuristic'),
                  _validation=dict(ii=ii, jj=jj, coherent=coherent, trends=trend_lags,
                                   windows=measured_windows, original=data, tolerance=validation_tolerance,
                                   improvement=minimum_improvement, min_correlation=min_correlation),
                  audit=[dict(source_row=i, file_id=int(fid[i]),channel=int(ch[i]),trace=int(tr[i]),
                              neighbours=int(degrees[i]),component=int(curves[i]),
                              proposed_advance=float(proposal[i]),applied_advance=float(advances[i]),
                              residual=float(model_residual[i]),status=str(status[i]),
                              validation_neighbours=0,improving_validation_neighbours=0,
                              worst_checked_correlation_change=np.nan) for i in range(n)])
    _ap_validate_final_source_timing(result)
    return result


def _ap_timing_pair_scores(original, shifted, i, j, smooth_lag, window):
    """Compare exact final shifts on identical finite samples, removing spatial lag."""
    if not np.isfinite(smooth_lag) or abs(smooth_lag) > 8: return None
    lo, hi = window
    before_i = _ap_section_advance(original[i], smooth_lag)[lo:hi]
    after_i = _ap_section_advance(shifted[i], smooth_lag)[lo:hi]
    b, a = original[j,lo:hi], shifted[j,lo:hi]
    valid = np.isfinite(before_i) & np.isfinite(after_i) & np.isfinite(b) & np.isfinite(a)
    if valid.sum() < max(24, int(.8*(hi-lo))): return None
    before = _ap_section_correlation(before_i[valid], b[valid])
    after = _ap_section_correlation(after_i[valid], a[valid])
    return (before,after) if np.isfinite([before,after]).all() else None


def _ap_validate_final_source_timing(result, max_rounds=12):
    """Monotone rollback, rechecking all affected pairs including unchanged sources."""
    v = result['_validation']; data = v['original']; shifts = result['advances']
    n = len(shifts)
    for round_number in range(max_rounds+1):
        shifted = np.array([_ap_section_advance(t,s) if s else t.copy() for t,s in zip(data,shifts)])
        bad = np.zeros(n,bool); supported = np.zeros(n,int); improving = np.zeros(n,int)
        worst_change=np.full(n,np.nan)
        for p,(i,j) in enumerate(zip(v['ii'],v['jj'])):
            row = result['pairs'][p]
            row['status'] = 'unchanged' if not (shifts[i] or shifts[j]) else 'final_checked'
            if not (shifts[i] or shifts[j]): continue
            for w,window in enumerate(v['windows']):
                if not v['coherent'][p,w]: continue
                scores = _ap_timing_pair_scores(data, shifted, i,j,v['trends'][p,w],window)
                if scores is None: continue
                before,after = scores
                for node in (i,j):
                    worst_change[node]=min(worst_change[node],after-before) if np.isfinite(worst_change[node]) else after-before
                row[f'w{w}_smooth_lag'] = float(v['trends'][p,w])
                row[f'w{w}_final_before'] = before; row[f'w{w}_final_after'] = after
                # Any coherent window can veto; window 2 is required for support.
                if after < before-v['tolerance']:
                    bad[[i,j]] = True; row['status'] = 'final_degradation'
                if w == 2 and max(before,after) >= v['min_correlation']:
                    supported[[i,j]] += 1
                    if after-before >= v['improvement']: improving[[i,j]] += 1
        for i in np.flatnonzero(shifts):
            result['audit'][i].update(validation_neighbours=int(supported[i]),
                improving_validation_neighbours=int(improving[i]),
                worst_checked_correlation_change=float(worst_change[i]))
        bad |= (supported < 2) | (improving < 1)
        bad &= shifts != 0
        if not bad.any(): break
        if round_number == max_rounds:
            bad = shifts != 0
            for i in np.flatnonzero(bad): result['audit'][i]['status'] = 'validation_no_stable_set'
        else:
            for i in np.flatnonzero(bad):
                result['audit'][i]['status'] = ('validation_degradation' if np.isfinite(worst_change[i]) and worst_change[i] < -v['tolerance'] else
                    'insufficient_validation_support' if supported[i] < 2 else 'no_validation_improvement')
        shifts[bad] = 0.
    # Clear stale scores for pairs restored by the last rollback round.
    for p,(i,j) in enumerate(zip(v['ii'],v['jj'])):
        row=result['pairs'][p]
        row['applied_relative_advance']=float(shifts[i]-shifts[j])
        if not (shifts[i] or shifts[j]):
            row['status']='unchanged'
            for w in range(len(v['windows'])):
                row[f'w{w}_final_before']=np.nan
                row[f'w{w}_final_after']=np.nan
    # Recreate once from ORIGINAL data; never accumulate interpolation passes.
    result['corrected'] = np.array([_ap_section_advance(t,s) if s else t.copy() for t,s in zip(data,shifts)])
    for i,row in enumerate(result['audit']):
        row['applied_advance'] = float(shifts[i])
        if shifts[i]: row['status'] = 'applied'
    result['source_validation_rounds'] = round_number+1


def _ap_section_continuity_change(baseline, candidate, x, windows, tolerance=.01):
    """Evidence for local seams, with fixed common masks; never a geology classifier."""
    bad = np.zeros(baseline.shape[1],bool); rows = []
    for j in range(1,baseline.shape[1]-1):
        if max(x[j]-x[j-1],x[j+1]-x[j]) > .3: continue
        fraction = (x[j]-x[j-1])/(x[j+1]-x[j-1])
        for w,(lo,hi) in enumerate(windows):
            a=baseline[lo:hi,j]; b=(1-fraction)*baseline[lo:hi,j-1]+fraction*baseline[lo:hi,j+1]
            c=candidate[lo:hi,j]; d=(1-fraction)*candidate[lo:hi,j-1]+fraction*candidate[lo:hi,j+1]
            valid=np.isfinite(a)&np.isfinite(b)&np.isfinite(c)&np.isfinite(d)
            if valid.sum() < max(24,int(.8*(hi-lo))): continue
            before=_ap_section_correlation(a[valid],b[valid]); after=_ap_section_correlation(c[valid],d[valid])
            if not np.isfinite([before,after]).all(): continue
            veto = before >= .7 and after < before-tolerance
            bad[j] |= veto
            rows.append(dict(column=j,distance_m=float(x[j]),window=w,before=before,after=after,
                             change=after-before,degradation=bool(veto)))
    return bad,rows


def validate_ap_ppd_reconstructed_timing(result, required_rows, sampling, baseline,
                                         tolerance=.01, max_rounds=12):
    """Check FINAL mixtures, roll back contributors of degraded columns and neighbours.

    Source-pair checks are rerun after every section rollback. All corrections
    fall back to zero if a stable final set cannot be verified within max_rounds.
    Returning the baseline is an explicit valid outcome, never reported as a fix.
    """
    x=np.asarray(sampling['distance']); windows=result['_validation']['windows']
    rolled_back=set()
    for iteration in range(max_rounds+1):
        section=interpolate_ap_ppd_source_matrix(result['corrected'],required_rows,sampling)
        bad,rows=_ap_section_continuity_change(baseline,section,x,windows,tolerance)
        if not bad.any(): break
        if iteration == max_rounds:
            remove=np.flatnonzero(result['advances'])
        else:
            columns=np.unique(np.clip(np.r_[np.flatnonzero(bad)-1,np.flatnonzero(bad),np.flatnonzero(bad)+1],0,len(x)-1))
            used=[]
            for col in columns:
                if not sampling['triangle_valid'][col]: continue
                indices=np.asarray(sampling['triangle_indices'][col])
                weights=np.asarray(sampling['triangle_weights'][col])
                used.extend(np.searchsorted(required_rows,indices[weights>0]))
            remove=np.array(sorted(set(used)),int)
        remove=remove[result['advances'][remove]!=0]
        if not len(remove):
            # Unexpected reconstruction discrepancy: fail closed, don't loop forever.
            remove=np.flatnonzero(result['advances'])
        rolled_back.update(remove.tolist()); result['advances'][remove]=0.
        for i in remove: result['audit'][i]['status']='reconstructed_section_degradation'
        _ap_validate_final_source_timing(result)
    section=interpolate_ap_ppd_source_matrix(result['corrected'],required_rows,sampling)
    bad,rows=_ap_section_continuity_change(baseline,section,x,windows,tolerance)
    if bad.any():
        for i in np.flatnonzero(result['advances']): result['audit'][i]['status']='section_validation_no_stable_set'
        result['advances'][:]=0.; _ap_validate_final_source_timing(result)
        section=interpolate_ap_ppd_source_matrix(result['corrected'],required_rows,sampling)
        bad,rows=_ap_section_continuity_change(baseline,section,x,windows,tolerance)
        if bad.any(): raise RuntimeError('Baseline reconstruction differs; timing was not exported.')
    result['section_validation']=dict(rounds=iteration+1,rolled_back_sources=len(rolled_back),
        remaining_degraded_columns=int(bad.sum()),tolerance=tolerance,
        checked_windows=[list(w) for w in windows])
    result['section_validation_rows']=rows
    return section


def export_ap_ppd_source_jitter(result, metadata, required_rows, sampling, prefix):
    """Export source estimates and every positive-weight section contributor."""
    import csv
    path = str(prefix)+"_source_timing.csv"
    with open(path,"w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(result["audit"][0]))
        writer.writeheader()
        writer.writerows(result["audit"])
    contribution_path = str(prefix)+"_timing_contributors.csv"
    with open(contribution_path,"w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f)
        writer.writerow(["column","distance_m","subset_row","file_id","channel",
                         "trace","weight","advance_samples"])
        for col in np.flatnonzero(sampling["triangle_valid"]):
            for row,weight in zip(sampling["triangle_indices"][col],
                                  sampling["triangle_weights"][col]):
                if weight <= 0: continue
                compact=np.searchsorted(required_rows,row)
                t=metadata[compact]
                writer.writerow([col,sampling["distance"][col],row,t["file_id"],
                                 t["channel"],t["trace"],weight,
                                 result["advances"][compact]])
    return path,contribution_path


def _ap_expand_source_context(traces, required_rows, folder_path, radius):
    """Append full-cache neighbours while preserving every existing subset row."""
    from scipy.spatial import cKDTree
    centres=np.column_stack((traces["x"][required_rows],traces["y"][required_rows]))
    path=os.path.join(folder_path,"ap_ppd_trace_index.npy")
    if not os.path.exists(path):
        return traces, "corridor_only"
    index=np.load(path,mmap_mode="r",allow_pickle=False)
    if index.dtype != traces.dtype:
        raise ValueError("Source index schema differs from corridor; rebuild sampling.")
    lower=centres.min(axis=0)-radius; upper=centres.max(axis=0)+radius
    selected=((index["x"]>=lower[0])&(index["x"]<=upper[0])&
              (index["y"]>=lower[1])&(index["y"]<=upper[1])&
              np.isin(index["file_id"],np.unique(traces["file_id"][required_rows])))
    candidates=np.array(index[selected])
    candidates=candidates[_ap_usable(candidates)]
    if not len(candidates): return traces,"full_cache"
    tree=cKDTree(centres)
    distance,_=tree.query(np.column_stack((candidates["x"],candidates["y"])),
                          distance_upper_bound=radius)
    candidates=candidates[np.isfinite(distance)]
    present={(int(t["file_id"]),int(t["data_offset"])) for t in traces}
    extra=[i for i,t in enumerate(candidates)
           if (int(t["file_id"]),int(t["data_offset"])) not in present]
    return np.concatenate((traces,candidates[extra])),"full_cache"


def export_ap_ppd_joint_diagnostics(result, metadata, required_rows, sampling,
                                     baseline, corrected, prefix):
    """Machine-readable evidence plus one source coverage/identity figure."""
    import csv
    import json
    from collections import Counter
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    path=str(prefix)+"_timing_pairs.csv"
    fields=list(result["pairs"][0]) if result["pairs"] else ["pair_id","status"]
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(result["pairs"])
    x=np.asarray(sampling["distance"])
    coverage=np.zeros(len(x)); magnitude=np.zeros(len(x))
    dominant=np.full(len(x),np.nan)
    sources=[]
    for col in np.flatnonzero(sampling["triangle_valid"]):
        w=np.asarray(sampling["triangle_weights"][col])
        rows=np.searchsorted(required_rows,sampling["triangle_indices"][col])
        positive=w>0;rows=rows[positive];w=w[positive]
        shifts=result["advances"][rows]
        coverage[col]=w@(abs(shifts)>.000001)
        magnitude[col]=w@abs(shifts)
        dominant[col]=metadata["channel"][rows[np.argmax(w)]]
        for j,weight in zip(rows,w): sources.append((x[col],metadata["channel"][j],weight,result["advances"][j]))
    summary=dict(method=result["settings"].get("method", "source_timing"),
                 final_section_validation=result.get("section_validation", {}),
                 settings=result["settings"],context=result.get("context","provided_sources"),
                 source_status=dict(Counter(r["status"] for r in result["audit"])),
                 pair_status=dict(Counter(r["status"] for r in result["pairs"])),
                 output_positions=len(x),positions_with_corrected_contributor=int(sum(coverage>0)),
                 mean_corrected_weight=float(np.mean(coverage[sampling["triangle_valid"]]))
                     if np.any(sampling["triangle_valid"]) else 0.,
                 mean_weighted_absolute_advance=float(np.mean(magnitude)),
                 note="Joint statics/trends experiment; broad channel/pass offsets remain uncalibrated. Final checks are model-dependent, not ground truth.")
    with open(str(prefix)+"_timing_summary.json","w",encoding="utf-8") as f:
        json.dump(summary,f,indent=2,allow_nan=False)
    if result.get("section_validation_rows"):
        with open(str(prefix)+"_timing_section_validation.csv","w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(result["section_validation_rows"][0]))
            writer.writeheader(); writer.writerows(result["section_validation_rows"])
    np.savez_compressed(str(prefix)+"_timing_sections.npz",baseline=baseline,
                        corrected=corrected,distance=x,corrected_weight=coverage,
                        weighted_absolute_advance=magnitude)
    fig=Figure(figsize=(15,7),constrained_layout=True);FigureCanvasAgg(fig)
    axes=fig.subplots(3,1,sharex=True)
    axes[0].plot(x,coverage*100);axes[0].set_ylabel("Corrected source weight (%)");axes[0].set_ylim(0,100)
    axes[1].plot(x,magnitude);axes[1].set_ylabel("Weighted |advance|\n(samples)")
    if sources:
        p=np.array(sources)
        dots=axes[2].scatter(p[:,0],p[:,1],s=3+20*p[:,2],c=p[:,3],cmap="coolwarm",
                            vmin=-3,vmax=3)
        fig.colorbar(dots,ax=axes[2],label="Source advance (samples)")
    from matplotlib.ticker import MaxNLocator
    axes[2].yaxis.set_major_locator(MaxNLocator(integer=True))
    axes[1].set_ylim(0,max(.1,float(magnitude.max())*1.1))
    axes[2].set_ylabel("Contributing channel");axes[2].set_xlabel("Section distance (m)")
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle("Joint source timing — applied coverage and contributors")
    fig.savefig(str(prefix)+"_timing_diagnostics.png",dpi=160)
    result["summary"]=summary
    print(json.dumps(summary,indent=2))
    return path


def replay_ap_ppd_timing_snapshot(snapshot_path, output_prefix=None, source_timing_options=None):
    """Rerun a V10 numeric snapshot without the original .ap_ppd files.

    Example: replay_ap_ppd_timing_snapshot('Polysection_1_timing_sources.npz')
    Outputs an aligned baseline / earlier shallow benchmark / new timing image,
    source and pair audits, and final-section check CSVs. Gain remains unchanged.
    Saved input options are reused; supplied options override them explicitly.
    """
    from pathlib import Path
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    with np.load(snapshot_path, allow_pickle=False) as stored:
        required={'time_zero_aligned_sources','metadata','required_rows','distance',
                  'triangle_indices','triangle_weights','triangle_valid'}
        if not required.issubset(stored.files):
            raise ValueError('Need a V10 snapshot including sampling geometry; rerun extraction with V10.')
        data=stored['time_zero_aligned_sources']; metadata=stored['metadata']; rows=stored['required_rows']
        sampling={k:stored[k] for k in ('distance','triangle_indices','triangle_weights','triangle_valid')}
        options=json.loads(str(stored['options_json'])) if 'options_json' in stored else {}
        if 'pass_ids' in stored and len(stored['pass_ids']): options['pass_ids']=stored['pass_ids']
    options.update(source_timing_options or {})
    if len(sampling['distance']) < 2 or np.any(np.diff(sampling['distance']) <= 0):
        raise ValueError('Snapshot needs at least two increasing output distances.')
    result=analyse_ap_ppd_source_jitter(data,metadata,**options)
    baseline=interpolate_ap_ppd_source_matrix(data,rows,sampling)
    corrected=validate_ap_ppd_reconstructed_timing(result,rows,sampling,baseline)
    prefix=str(output_prefix) if output_prefix is not None else str(Path(snapshot_path).with_suffix(''))+'_replay'
    Path(prefix).parent.mkdir(parents=True,exist_ok=True)
    export_ap_ppd_source_jitter(result,metadata,rows,sampling,prefix)
    export_ap_ppd_joint_diagnostics(result,metadata,rows,sampling,baseline,corrected,prefix)
    x=np.asarray(sampling['distance']); arrays=[baseline];titles=['Recorded time-zero aligned']
    benchmark=None
    if len(x)>=9:
        benchmark=analyse_ap_ppd_section_timing(baseline,x,fit_mode='shallow')[0]
        arrays.append(benchmark);titles.append('Earlier shallow-window benchmark')
    arrays.append(corrected);titles.append('Joint source timing — final checks')
    edges=np.r_[x[0]-(x[1]-x[0])/2,(x[:-1]+x[1:])/2,x[-1]+(x[-1]-x[-2])/2]
    finite=abs(baseline[np.isfinite(baseline)]);limit=max(float(np.percentile(finite,99)),1e-12) if len(finite) else 1.
    fig=Figure(figsize=(15,4*len(arrays)),constrained_layout=True);FigureCanvasAgg(fig)
    axes=fig.subplots(len(arrays),1,sharex=True,sharey=True)
    from matplotlib import colormaps
    cmap=colormaps['gray'].copy();cmap.set_bad('lightblue')
    for ax,section,title in zip(axes,arrays,titles):
        im=ax.pcolormesh(edges,np.arange(section.shape[0]+1)-.5,np.ma.masked_invalid(section),
                         cmap=cmap,vmin=-limit,vmax=limit,shading='flat')
        ax.set_ylim(section.shape[0]-.5,-.5);ax.set_title(title)
        ax.set_ylabel('Samples after recorded time zero')
    axes[-1].set_xlabel('Section distance (m)');fig.colorbar(im,ax=list(axes),label='Amplitude — shared scale')
    fig.savefig(prefix+'_comparison.png',dpi=160)
    result.update(baseline=baseline,section=corrected,shallow_timing_benchmark=benchmark,
                  output_path=prefix+'_comparison.png')
    return result


# ---------------------------------------------------------------------------
# V12: exploratory coupling diagnostics. No new corrections are applied.
# ---------------------------------------------------------------------------
def _ap_coupling_pair_models(reference, target, windows, fit_indices, max_lag,
                             max_stretch, min_correlation, min_improvement):
    """Fit on designated windows; evaluate all models on identical finite support.

    Convention: compare reference(t) with gain * target(t + a + b*(t-pivot)).
    Positive a advances target. b is a sampling-coordinate slope, not a ground
    velocity estimate. Output durations scale by 1/(1+b).
    """
    from scipy.optimize import minimize, minimize_scalar
    reference = np.asarray(reference, dtype=float)
    target = np.asarray(target, dtype=float)
    centres = np.array([(lo + hi - 1)/2 for lo, hi in windows])
    pivot = float(np.mean(centres[list(fit_indices)]))
    n = len(target)
    margin = int(np.ceil(max_lag + max_stretch*np.max(abs(np.ravel(windows)-pivot)))) + 2
    # Intersect validity over the entire allowed warp envelope BEFORE fitting.
    # Thus a model cannot win by moving difficult samples off the trace.
    bad = (~np.isfinite(target)).astype(int)
    cumulative = np.r_[0, np.cumsum(bad)]
    supports = []
    for lo, hi in windows:
        # Trim each window so even warped target samples never enter another window.
        ix = np.arange(lo+margin, hi-margin)
        valid = np.isfinite(reference[ix]) & ((cumulative[ix+margin+1]-cumulative[ix-margin]) == 0)
        supports.append(ix[valid])
    measured = _ap_joint_pair(target, reference, windows, max_lag)
    result = dict(status='insufficient_support', pivot_sample=pivot,
                  static_advance_samples=np.nan, affine_advance_samples=np.nan,
                  stretch_fraction=np.nan, affine_at_limit=False,
                  static_at_limit=False, gain_only=np.nan, gain_static=np.nan,
                  gain_affine=np.nan, validation_static_nrmse=np.nan,
                  validation_affine_nrmse=np.nan, validation_baseline_nrmse=np.nan,
                  validation_gain_nrmse=np.nan, validation_static_correlation=np.nan,
                  validation_affine_correlation=np.nan)
    records = []
    for k, ((lo,hi), m, ix) in enumerate(zip(windows, measured, supports)):
        records.append(dict(window_index=k, first_sample=lo, last_sample_exclusive=hi,
                            role='fit' if k in fit_indices else 'validation',
                            valid_samples=len(ix), measured_lag_samples=m['lag'],
                            peak_correlation=m['correlation'], lag_at_limit=m['boundary'],
                            lag_status=m['reason'], correlation_before=m['before']))
    if any(len(ix) < 24 for ix in supports):
        return result, records
    good_fit = [k for k in fit_indices if measured[k]['reason']=='measured'
                and measured[k]['correlation'] >= min_correlation]
    if len(good_fit) != len(fit_indices):
        result['status'] = ('fit_search_limit' if any(measured[k]['boundary'] for k in fit_indices)
                            else 'insufficient_coherent_fit')
        return result, records
    def vectors(k, a, b):
        ix = supports[k]
        r = reference[ix]; r = r-r.mean()
        t = np.interp(ix+a+b*(ix-pivot), np.arange(n), target)
        return r, t-t.mean()
    def corr(r,t):
        den = np.linalg.norm(r)*np.linalg.norm(t)
        return float(r@t/den) if den > 1e-12 else np.nan
    def objective(par):
        scores = [corr(*vectors(k,par[0],par[1])) for k in fit_indices]
        return 1-float(np.mean(scores)) if np.isfinite(scores).all() else 2.
    lags = np.array([measured[k]['lag'] for k in fit_indices])
    weights = np.array([measured[k]['correlation']**2 for k in fit_indices])
    static_seed = float(np.average(lags,weights=weights))
    # Refine near the measured peak, avoiding unconstrained cycle skipping.
    lower,upper = max(-max_lag,static_seed-1),min(max_lag,static_seed+1)
    opt = minimize_scalar(lambda a: objective((a,0)),bounds=(lower,upper),method='bounded',
                          options={'xatol':.005})
    static = float(opt.x)
    X = np.column_stack((np.ones(len(fit_indices)),centres[list(fit_indices)]-pivot))
    affine_seed = np.linalg.lstsq(X*np.sqrt(weights[:,None]),lags*np.sqrt(weights),rcond=None)[0]
    seed = np.clip(affine_seed,[-max_lag,-max_stretch],[max_lag,max_stretch])
    opt2 = minimize(objective,seed,method='L-BFGS-B',bounds=[(-max_lag,max_lag),(-max_stretch,max_stretch)],
                    options={'maxiter':50,'ftol':1e-10})
    a,b = map(float,opt2.x)
    def fit_gain(a,b):
        numerator=0.; denominator=0.
        for k in fit_indices:
            r,t=vectors(k,a,b)
            # Equal window weighting; shallow large amplitudes cannot dominate.
            scale = max(float(r@r),1e-12)
            numerator += float(r@t)/scale
            denominator += float(t@t)/scale
        return numerator/denominator if denominator>1e-12 else np.nan
    gains = {'gain':fit_gain(0,0),'static':fit_gain(static,0),'affine':fit_gain(a,b)}
    result.update(static_advance_samples=static,affine_advance_samples=a,stretch_fraction=b,
                  gain_only=gains['gain'],gain_static=gains['static'],gain_affine=gains['affine'],
                  static_at_limit=abs(static)>=max_lag-.05,
                  affine_at_limit=(abs(a)>=max_lag-.05 or abs(b)>=max_stretch*.98),
                  optimizer_success=bool(opt.success and opt2.success))
    for k,row in enumerate(records):
        for label,aa,bb,gg in [('baseline',0,0,1),('gain',0,0,gains['gain']),
                                ('static',static,0,gains['static']),('affine',a,b,gains['affine'])]:
            r,t=vectors(k,aa,bb)
            row[label+'_correlation']=corr(r,t)
            row[label+'_nrmse']=float(np.linalg.norm(r-gg*t)/max(np.linalg.norm(r),1e-12))
        r,t=vectors(k,static,0)
        row['window_gain_after_static']=float(r@t/(t@t)) if t@t>1e-12 else np.nan
        ix=supports[k]
        # Spectral ratio is only meaningful with contiguous support.
        ratio=np.nan
        if np.all(np.diff(ix)==1):
            taper=np.hanning(len(ix)); f=np.fft.rfftfreq(len(ix))
            er=abs(np.fft.rfft(r*taper))**2; et=abs(np.fft.rfft(t*taper))**2
            cr=float(f@er/max(er.sum(),1e-12)); ct=float(f@et/max(et.sum(),1e-12))
            if cr>1e-12: ratio=ct/cr
        row['spectral_centroid_target_over_reference']=ratio
    held=[k for k in range(len(windows)) if k not in fit_indices]
    for label in ('baseline','gain','static','affine'):
        for metric in ('nrmse','correlation'):
            result['validation_'+label+'_'+metric]=float(np.mean([records[k][label+'_'+metric] for k in held]))
    def improves(new,old):
        changes=np.array([records[k][old+'_nrmse']-records[k][new+'_nrmse'] for k in held])
        return (changes.mean()>=min_improvement and changes.min()>=-.02
                and all(records[k][new+'_correlation']>=.9 for k in held)
                and all(records[k][new+'_correlation']>=records[k][old+'_correlation']-.01 for k in held))
    if not result['optimizer_success'] or not all(np.isfinite(g) and g>0 for g in gains.values()):
        result['status']='unreliable_fit'
    elif result['affine_at_limit'] and improves('affine','static'):
        result['status']='stretch_search_limit'
    elif abs(b)>=.001 and improves('affine','static'):
        result['status']='stretch_candidate'
    elif result['static_at_limit'] and improves('static','gain'):
        result['status']='delay_search_limit'
    elif abs(static)>=.1 and improves('static','gain'):
        result['status']='delay_candidate'
    elif abs(gains['gain']-1)>=.03 and improves('gain','baseline'):
        result['status']='gain_candidate'
    elif all(records[k]['baseline_correlation']>=.95 and records[k]['baseline_nrmse']<=.2 for k in held):
        result['status']='already_similar'
    else:
        result['status']='waveform_or_spatial_mismatch'
    return result,records


def analyse_ap_ppd_coupling(data, metadata, required_rows, sampling, *,
                            radius_m=.25, cross_interval_radius_m=.15,
                            neighbour_channels=2, same_interval_trace_gap=12,
                            max_pairs=6000, windows=((80,150),(150,230),(230,320),(330,410)),
                            fit_indices=(0,2), max_lag=8, max_stretch=.02,
                            min_correlation=.8, min_improvement=.03,
                            pass_ids=None, sample_interval_ns=None, raw_sources=None):
    """Compare unmixed time-zero-aligned sources: delay, scalar gain, small stretch.

    Pair priorities: actual positive-weight co-contributors, then the nearest
    source in each same-channel / channel +/-1,+/-2 / other-interval category.
    Neighbours are drawn around section contributors only. Cross-interval matches
    have their own tighter radius. Channel numbers must reflect physical order.
    With no pass_ids, trace-number proximity is a labelled heuristic, NOT a pass ID.
    Co-contributor pairs outside radii are still audited as geometry confounds.
    max_pairs retains all co-contributors first and evenly subsamples context pairs
    by spatial order; both available and analysed counts are reported.

    fit_indices windows estimate models. All other windows validate them. Window
    samples are exclusive at the end, referenced to recorded time zero. No model
    is applied to source data or section. Candidate labels do not identify air gaps.
    Optional sample_interval_ns must come from verified acquisition metadata.
    raw_sources is optional decoded data before time zero, retained for inspection
    by the snapshot exporter; it is not silently substituted for aligned data.
    """
    from collections import Counter
    from scipy.spatial import cKDTree
    data=np.asarray(data); metadata=np.asarray(metadata); rows=np.asarray(required_rows)
    windows=tuple(tuple(int(v) for v in w) for w in windows); fit_indices=tuple(fit_indices)
    if data.ndim!=2 or len(metadata)!=len(data) or len(rows)!=len(data):
        raise ValueError('Expected data[sources,samples], matching metadata and required_rows.')
    if not {'file_id','channel','trace','x','y'}.issubset(metadata.dtype.names or ()):
        raise ValueError('Metadata needs file_id, channel, trace, x and y.')
    if len(np.unique(rows))!=len(rows): raise ValueError('required_rows must be unique.')
    if not (np.isfinite(radius_m) and np.isfinite(cross_interval_radius_m)
            and 0<cross_interval_radius_m<=radius_m): raise ValueError('Invalid matching radii.')
    if (not isinstance(max_lag,(int,np.integer)) or max_lag<1
            or not 0<max_stretch<.1 or not np.isfinite(max_stretch)):
        raise ValueError('max_lag must be a positive integer; max_stretch must be between 0 and .1.')
    if (len(windows)<4 or len(fit_indices)<2 or len(set(fit_indices))!=len(fit_indices)
            or any(k<0 or k>=len(windows) for k in fit_indices)
            or len(windows)-len(fit_indices)<2):
        raise ValueError('Need at least two fitting and two held-out windows.')
    if any(lo<0 or hi>data.shape[1] or hi-lo<2*max_lag+24 for lo,hi in windows):
        raise ValueError('Windows outside trace or too short for requested lag search.')
    if any(windows[k][1]>windows[k+1][0] for k in range(len(windows)-1)):
        raise ValueError('Windows must be ordered and non-overlapping.')
    if max_pairs is not None and (not isinstance(max_pairs,int) or max_pairs<1):
        raise ValueError('max_pairs must be positive or None.')
    if neighbour_channels<0 or same_interval_trace_gap<0: raise ValueError('Invalid neighbourhood.')
    if not 0<min_correlation<=1 or min_improvement<=0: raise ValueError('Invalid model thresholds.')
    if sample_interval_ns is not None and (not np.isfinite(sample_interval_ns) or sample_interval_ns<=0):
        raise ValueError('sample_interval_ns must be finite and positive.')
    if raw_sources is not None and np.shape(raw_sources)!=data.shape: raise ValueError('Raw source shape differs.')
    passes=None if pass_ids is None else np.asarray(pass_ids).astype(str)
    if passes is not None and (passes.ndim!=1 or len(passes)!=len(data) or np.any(passes=='')):
        raise ValueError('pass_ids must contain one nonempty ID per source.')
    xy=np.column_stack((metadata['x'],metadata['y']))
    if not np.isfinite(xy).all(): raise ValueError('Source coordinates must be finite.')
    mapping={int(v):k for k,v in enumerate(rows)}
    identity=[(int(m['file_id']),int(m['channel']),int(m['trace'])) for m in metadata]
    if len(set(identity))!=len(identity): raise ValueError('Source identities must be unique.')
    tri=np.asarray(sampling['triangle_indices']); weights=np.asarray(sampling['triangle_weights'])
    valid=np.asarray(sampling['triangle_valid'],dtype=bool); distances=np.asarray(sampling['distance'])
    if tri.shape!=weights.shape or tri.ndim!=2 or len(tri)!=len(distances) or valid.shape!=distances.shape:
        raise ValueError('Sampling geometry shapes differ.')
    if not np.isfinite(distances).all() or np.any(np.diff(distances)<=0): raise ValueError('Invalid section distances.')
    pairs={}; seed_positions={}
    def relation(i,j):
        same_file=metadata['file_id'][i]==metadata['file_id'][j]
        close_trace=abs(int(metadata['trace'][i])-int(metadata['trace'][j]))<=same_interval_trace_gap
        same=(same_file and passes[i]==passes[j]) if passes is not None else (same_file and close_trace)
        if same:
            delta=abs(int(metadata['channel'][i])-int(metadata['channel'][j]))
            if delta==0: return 'same_interval_same_channel'
            return 'same_interval_neighbour_channel' if delta<=neighbour_channels else 'same_interval_other_channel'
        return 'different_interval'
    def add(i,j,distance,weight=0.,co=False):
        if i==j: return
        if identity[j]<identity[i]: i,j=j,i
        key=(i,j)
        if key not in pairs: pairs[key]=dict(positions=[],weight=0.,co=False)
        item=pairs[key];item['positions'].append(float(distance));item['weight']+=float(weight);item['co']|=co
    for col in np.flatnonzero(valid):
        ww=weights[col]
        if not np.isfinite(ww).all() or np.any(ww<0) or not np.isclose(ww.sum(),1,atol=1e-5):
            raise ValueError('Valid interpolation weights must be finite, nonnegative and sum to one.')
        ids=[mapping[int(r)] for r,w in zip(tri[col],ww) if w>1e-8]
        pw=ww[ww>1e-8]
        for i in ids: seed_positions.setdefault(i,[]).append(float(distances[col]))
        for k,i in enumerate(ids):
            for q in range(k+1,len(ids)): add(i,ids[q],distances[col],pw[k]*pw[q],True)
    tree=cKDTree(xy)
    for i in sorted(seed_positions,key=lambda k: identity[k]):
        buckets={}
        nearby=tree.query_ball_point(xy[i],radius_m)
        for j in nearby:
            if i==j: continue
            kind=relation(i,j); sep=float(np.linalg.norm(xy[i]-xy[j]))
            delta=int(metadata['channel'][j])-int(metadata['channel'][i])
            if kind=='different_interval':
                if sep>cross_interval_radius_m: continue
                category=('other',)
            else:
                if abs(delta)>neighbour_channels: continue
                category=('same',delta)
            buckets.setdefault(category,[]).append((sep,identity[j],j))
        for group in buckets.values():
            # Two nearest samples in each channel category and across intervals.
            for _,_,j in sorted(group)[:2]: add(i,j,float(np.mean(seed_positions[i])))
    available=len(pairs)
    ordered=sorted(pairs,key=lambda key:(not pairs[key]['co'],np.mean(pairs[key]['positions']),identity[key[0]],identity[key[1]]))
    co_keys=[key for key in ordered if pairs[key]['co']]; context=[key for key in ordered if not pairs[key]['co']]
    if max_pairs is not None and len(ordered)>max_pairs:
        # Keep all pairs entering the actual interpolation even if they exceed the budget.
        budget=max(0,max_pairs-len(co_keys))
        selected=np.linspace(0,len(context)-1,budget,dtype=int) if budget else []
        ordered=co_keys+[context[k] for k in selected]
    audit=[]; window_rows=[]
    for pair_id,(i,j) in enumerate(ordered):
        info=pairs[(i,j)]; sep=float(np.linalg.norm(xy[i]-xy[j])); kind=relation(i,j)
        res,wr=_ap_coupling_pair_models(data[i],data[j],windows,fit_indices,max_lag,max_stretch,min_correlation,min_improvement)
        limit=cross_interval_radius_m if kind=='different_interval' else radius_m
        res['model_status']=res['status']
        if sep>limit: res['status']='outside_matching_radius'
        row=dict(pair_id=pair_id,reference_row=int(rows[i]),target_row=int(rows[j]),
                 reference_compact_row=i,target_compact_row=j,
                 reference_file=int(metadata['file_id'][i]),reference_channel=int(metadata['channel'][i]),
                 reference_trace=int(metadata['trace'][i]),target_file=int(metadata['file_id'][j]),
                 target_channel=int(metadata['channel'][j]),target_trace=int(metadata['trace'][j]),
                 reference_pass='' if passes is None else passes[i], target_pass='' if passes is None else passes[j],
                 relation=kind,interval_identity='explicit_pass_ids' if passes is not None else 'trace_number_heuristic',
                 separation_m=sep,section_distance_m=float(np.mean(info['positions'])),
                 co_contributor=info['co'],mixing_weight_sum=info['weight'],**res)
        if sample_interval_ns is not None:
            row['static_advance_ns']=res['static_advance_samples']*sample_interval_ns
        # Early waveform comparison is descriptive, never an automatic time-zero pick.
        early=np.arange(min(60,data.shape[1])); good=np.isfinite(data[i,early])&np.isfinite(data[j,early])
        row['early_0_60_correlation']=_ap_corr(data[i,early][good],data[j,early][good]) if good.sum()>=24 else np.nan
        audit.append(row)
        window_rows.extend(dict(pair_id=pair_id,**w) for w in wr)
    summary=dict(method='source_coupling_diagnostics_v12',diagnostic_only=True,applied_corrections=0,
                 source_count=len(data),section_contributor_sources=len(seed_positions),
                 pairs_available=available,pairs_analysed=len(audit),pairs_omitted=available-len(audit),
                 co_contributor_pairs=len(co_keys),status_counts=dict(Counter(r['status'] for r in audit)),
                 relation_counts=dict(Counter(r['relation'] for r in audit)),
                 interval_identity='explicit_pass_ids' if passes is not None else 'trace_number_heuristic',
                 raw_sources_available=raw_sources is not None,sample_interval_ns=sample_interval_ns,
                 settings=dict(windows=windows,fit_indices=fit_indices,max_lag=max_lag,max_stretch=max_stretch,
                               radius_m=radius_m,cross_interval_radius_m=cross_interval_radius_m,
                               neighbour_channels=neighbour_channels,same_interval_trace_gap=same_interval_trace_gap,
                               max_pairs=max_pairs,min_correlation=min_correlation,min_improvement=min_improvement),
                 interpretation='Pairwise candidates, not independent observations or proof of coupling. Spatial geology, antenna geometry, positioning and waveform interference remain confounds. No height or soil velocity is inferred.')
    return dict(pairs=audit,windows=window_rows,summary=summary)


def export_ap_ppd_coupling(result, data, prefix):
    """One compact diagnostic image plus complete pair/window/channel CSVs and JSON."""
    import csv
    from pathlib import Path
    from collections import defaultdict
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    prefix=str(prefix);Path(prefix).parent.mkdir(parents=True,exist_ok=True)
    paths={}
    def write_csv(label,rows):
        path=prefix+'_coupling_'+label+'.csv'
        fields=list(dict.fromkeys(key for row in rows for key in row)) or ['status']
        with open(path,'w',newline='',encoding='utf-8') as handle:
            w=csv.DictWriter(handle,fieldnames=fields);w.writeheader();w.writerows(rows)
        paths[label]=path
    write_csv('pairs',result['pairs']);write_csv('windows',result['windows'])
    groups=defaultdict(list)
    for row in result['pairs']:
        for side in ('reference','target'):
            groups[(row[side+'_file'],row[side+'_channel'],row['relation'])].append(row)
    grouped=[]
    for (f,ch,relation),rr in sorted(groups.items()):
        grouped.append(dict(file_id=f,channel=ch,relation=relation,pairs=len(rr),
                            stretch_candidates=sum(r['status']=='stretch_candidate' for r in rr),
                            delay_candidates=sum(r['status']=='delay_candidate' for r in rr),
                            waveform_or_spatial_mismatch=sum(r['status']=='waveform_or_spatial_mismatch' for r in rr),
                            insufficient_coherent_fit=sum(r['status']=='insufficient_coherent_fit' for r in rr)))
    write_csv('channels',grouped)
    path=prefix+'_coupling_summary.json'
    with open(path,'w',encoding='utf-8') as handle: json.dump(result['summary'],handle,indent=2,allow_nan=False)
    paths['summary']=path
    fig=Figure(figsize=(15,11),constrained_layout=True);FigureCanvasAgg(fig)
    axes=fig.subplots(3,2); pairs=result['pairs']; good=[r for r in pairs if np.isfinite(r['static_advance_samples'])]
    labels=list(result['summary']['status_counts']);counts=[result['summary']['status_counts'][k] for k in labels]
    axes[0,0].barh([s.replace('_',' ') for s in labels],counts,color='#537e9c')
    axes[0,0].set_title('Pair outcomes (diagnostic only)');axes[0,0].set_xlabel('Number of pairs')
    colours={'same_interval_same_channel':'#999999','same_interval_neighbour_channel':'#288db5','different_interval':'#d47a25','same_interval_other_channel':'#b873ad'}
    for relation,colour in colours.items():
        rr=[r for r in good if r['relation']==relation and r['status']!='outside_matching_radius']
        axes[0,1].scatter([r['section_distance_m'] for r in rr],[r['static_advance_samples'] for r in rr],s=5,alpha=.3,color=colour,label=relation.replace('_',' '))
    axes[0,1].set(xlabel='Section distance (m)',ylabel='Fitted advance (samples)',title='Constant-delay fits — all fitted candidates')
    axes[0,1].legend(fontsize=7)
    if good:
        axes[1,0].scatter([r['validation_static_nrmse'] for r in good],[r['validation_affine_nrmse'] for r in good],s=6,alpha=.3)
        lim=max(1.,min(3.,max(max(r['validation_static_nrmse'],r['validation_affine_nrmse']) for r in good)))
        axes[1,0].plot([0,lim],[0,lim],color='grey',lw=1)
        axes[1,0].set(xlim=(0,lim),ylim=(0,lim))
    axes[1,0].set(xlabel='Held-out NRMSE: delay + gain',ylabel='Held-out NRMSE: stretch + delay + gain',title='Below diagonal = stretch predicts better')
    candidates=[r for r in good if r['status']=='stretch_candidate']
    axes[1,1].scatter([r['section_distance_m'] for r in good],[100*r['stretch_fraction'] for r in good],s=5,color='lightgrey',label='All fits')
    axes[1,1].scatter([r['section_distance_m'] for r in candidates],[100*r['stretch_fraction'] for r in candidates],s=15,color='#a34a24',label='Held-out candidate')
    axes[1,1].set(xlabel='Section distance (m)',ylabel='Sampling-coordinate slope (%)',title='Exploratory time scaling — not ground velocity')
    axes[1,1].legend(fontsize=8)
    # Display a relevant mixed-source example near the previously inspected seam.
    example_pool=[r for r in good if r['co_contributor'] and r['relation']=='different_interval'] or good
    if example_pool:
        r=min(example_pool,key=lambda r:abs(r['section_distance_m']-28.35))
        i,j=r['reference_compact_row'],r['target_compact_row']; t=np.arange(data.shape[1])
        a=r['static_advance_samples'];b=r['stretch_fraction'];aa=r['affine_advance_samples'];pivot=r['pivot_sample']
        target=np.interp(t+a,t,data[j],left=np.nan,right=np.nan)*r['gain_static']
        affine=np.interp(t+aa+b*(t-pivot),t,data[j],left=np.nan,right=np.nan)*r['gain_affine']
        scale=max(float(np.nanmax(abs(data[i]))),1e-12)
        for values,label in [(data[i],'Reference'),(target,'Delay + gain'),(affine,'Stretch + delay + gain')]:
            axes[2,0].plot(t,values/scale,lw=.8,label=label)
        axes[2,0].set(xlim=(60,410),xlabel='Samples after recorded time zero',ylabel='Amplitude / reference peak',title=f"Example pair {r['pair_id']} near {r['section_distance_m']:.2f} m: {r['status']}")
        axes[2,0].legend(fontsize=7)
        ww=[w for w in result['windows'] if w['pair_id']==r['pair_id']]
        for role,marker in [('fit','o'),('validation','s')]:
            wr=[w for w in ww if w['role']==role]
            axes[2,1].scatter([(w['first_sample']+w['last_sample_exclusive']-1)/2 for w in wr],
                              [w['measured_lag_samples'] for w in wr],marker=marker,label=role+' window peak')
        axes[2,1].plot(t,np.full_like(t,a,dtype=float),label='Fitted delay')
        axes[2,1].plot(t,aa+b*(t-pivot),label='Fitted affine delay')
        axes[2,1].set(xlim=(60,410),xlabel='Window centre (samples)',ylabel='Advance (samples)',title='Window-dependent disagreement in the example')
        axes[2,1].legend(fontsize=7)
    else:
        for ax in axes[2]: ax.text(.5,.5,'No coherent pairs fitted',ha='center',transform=ax.transAxes)
    for ax in axes.ravel(): ax.grid(alpha=.15)
    fig.suptitle('Source coupling exploration — before interpolation; no new corrections applied\nPairs are spatially separated; acquisition intervals are heuristic unless pass IDs were supplied.',fontsize=13)
    path=prefix+'_coupling_diagnostics.png';fig.savefig(path,dpi=160);paths['image']=path
    return paths


def replay_ap_ppd_coupling_snapshot(snapshot_path, output_prefix=None, **options):
    """Fast coupling-only replay of a V10+ source snapshot; no statics rerun needed.

    Example:
        replay_ap_ppd_coupling_snapshot('Polysection_1_timing_sources.npz')
    Returned pair candidates are diagnostic and are never applied to the section.
    """
    from pathlib import Path
    with np.load(snapshot_path,allow_pickle=False) as saved:
        required={'time_zero_aligned_sources','metadata','required_rows','distance',
                  'triangle_indices','triangle_weights','triangle_valid'}
        if not required.issubset(saved.files): raise ValueError('Need a source snapshot including sampling geometry.')
        data=saved['time_zero_aligned_sources'];metadata=saved['metadata'];rows=saved['required_rows']
        sampling={k:saved[k] for k in ('distance','triangle_indices','triangle_weights','triangle_valid')}
        if 'pass_ids' not in options and 'pass_ids' in saved and saved['pass_ids'].size:
            options['pass_ids']=saved['pass_ids']
        raw=saved['raw_sources'] if 'raw_sources' in saved else None
    result=analyse_ap_ppd_coupling(data,metadata,rows,sampling,raw_sources=raw,**options)
    prefix=str(output_prefix) if output_prefix is not None else str(Path(snapshot_path).with_suffix(''))
    result['paths']=export_ap_ppd_coupling(result,data,prefix)
    print(json.dumps(result['summary'],indent=2))
    return result


def _ap_selected_corr(a,b):
 a=a-a.mean();b=b-b.mean();d=np.linalg.norm(a)*np.linalg.norm(b)
 return float(a@b/d) if d>0 else -1.
def _ap_selected_fit(r, y, x):
 grid = np.arange(-8, 8.001, .25)
 values = np.interp((x[None, :] + grid[:, None]).ravel(), np.arange(len(y)), y).reshape(len(grid), -1)
 ref = r[x] - np.mean(r[x]); values -= values.mean(axis=1, keepdims=True)
 denom = np.linalg.norm(values, axis=1) * np.linalg.norm(ref)
 scores = np.divide(np.sum(values * ref, axis=1), denom, out=np.full(len(grid), -1.), where=denom>0)
 scores[~np.isfinite(scores)] = -1
 k = int(np.argmax(scores))
 return grid[k], scores[k], _ap_selected_corr(r[x], y[x]), k in (0, len(grid)-1)

def _ap_selected_track(s,lo,hi,seed):
 from scipy.signal import find_peaks
 n=s.shape[1];cand=[];cost=[];back=[]
 for j in range(n):
  pp=find_peaks(-s[lo-1:hi+2,j])[0]+lo-1;pp=pp[(pp>=lo)&(pp<=hi)&(s[pp,j]<0)]
  if not len(pp):raise ValueError('No peak in tracking gate')
  unary=-abs(s[pp,j])/max(np.max(abs(s[lo:hi+1,j])),1)
  if j==0:cost.append(unary+.02*(pp-seed)**2);back.append(None)
  else:
   mat=cost[-1][None,:]+.08*(pp[:,None]-cand[-1][None,:])**2;back.append(mat.argmin(axis=1));cost.append(unary+mat.min(axis=1))
  cand.append(pp)
 k=cost[-1].argmin();out=np.zeros(n)
 for j in range(n-1,-1,-1):
  q=cand[j][k];den=s[q-1,j]-2*s[q,j]+s[q+1,j];out[j]=q+np.clip(.5*(s[q-1,j]-s[q+1,j])/den if den else 0,-.5,.5)
  if j:k=back[j][k]
 return out


def _ap_selected_references(metadata):
 """Spatial index; nearest adjacent-ID pair in another channel, same file."""
 from scipy.spatial import cKDTree
 xy=np.column_stack((metadata['x'],metadata['y'])); tree=cKDTree(xy)
 refs=np.full((len(metadata),2),-1,dtype=int)
 for i, point in enumerate(xy):
  local=sorted(tree.query_ball_point(point,.2)); candidates=[]
  lookup={}
  for j in local:
   if metadata['file_id'][j]==metadata['file_id'][i] and metadata['channel'][j]!=metadata['channel'][i]:
    lookup.setdefault((int(metadata['channel'][j]),int(metadata['trace'][j])),[]).append(j)
  for (ch,tr), aa in lookup.items():
   for a in aa:
    for b in lookup.get((ch,tr+1),[]):
     a0,b0=sorted((a,b));candidates.append((np.linalg.norm(xy[a]-point)+np.linalg.norm(xy[b]-point),a0,b0))
  if candidates:refs[i]=min(candidates)[1:]
 return refs


def _ap_selected_curves(base, refs, metadata, label):
 from types import SimpleNamespace
 from scipy.ndimage import gaussian_filter1d
 import time
 started=time.monotonic();n,nt=base.shape;m=metadata
 args=SimpleNamespace(window=30,min_shift=2.)
 curves=np.zeros_like(base);constant=np.zeros(n);rows=[];accepted=np.zeros(n,int)
 valid_ends=np.array([np.flatnonzero(np.isfinite(y))[-1]+1 if np.isfinite(y).any() else 0 for y in base])
 for i in range(n):
  if i % 100 == 0:
   print(f"{label}: {i}/{n} ({time.monotonic()-started:.1f}s)", flush=True)
  a,b=refs[i]
  if a<0 or b<0:continue
  row_start=len(rows)
  valid_end=min(valid_ends[i],valid_ends[a],valid_ends[b]);measure={}
  for width in [args.window,args.window+20]:
   for centre in range(50,valid_end-43,10):
    x=np.arange(centre-width//2,centre+width//2)
    d1,c1,b1,e1=_ap_selected_fit(base[a],base[i],x);d2,c2,b2,e2=_ap_selected_fit(base[b],base[i],x)
    agreement=_ap_selected_corr(base[a,x],base[b,x]);shift=(d1+d2)/2
    good=agreement>=.95 and min(c1,c2)>=.9 and abs(d1-d2)<=.5 and not(e1 or e2) and min(c1-b1,c2-b2)>=.02
    measure[width,centre]=(shift,good)
    rows.append(dict(source=i,channel=int(m['channel'][i]),trace=int(m['trace'][i]),reference_a=a,reference_b=b,width=width,centre=centre,shift_a=d1,shift_b=d2,reference_correlation=agreement,correlation_after=min(c1,c2),improvement=min(c1-b1,c2-b2),accepted_initial=good,accepted_stable=False))
  goodpoints=[]
  for row in rows[row_start:]:
   if row['source']!=i or row['width']!=args.window:continue
   c=row['centre'];s,g=measure[args.window,c];s2,g2=measure[args.window+20,c]
   row['accepted_stable']=bool(g and g2 and abs(s-s2)<=.5 and abs(s)>args.min_shift and abs(s2)>args.min_shift)
   if row['accepted_stable']:goodpoints.append((c,s))
  accepted[i]=len(goodpoints)
  if len(goodpoints)<3:continue
  cc,ss=np.array(goodpoints).T;constant[i]=np.median(ss)
  # Only uninterrupted, same-sign accepted runs. Never bridge small/rejected windows.
  groups=np.split(np.arange(len(cc)),np.flatnonzero((np.diff(cc)>10)|(ss[:-1]*ss[1:]<=0))+1)
  for g in groups:
   if len(g)<3:continue
   c,s=cc[g],ss[g];lo=int(c[0]);hi=int(c[-1]);xx=np.arange(lo,hi+1)
   curve=gaussian_filter1d(np.interp(xx,c,s),2)
   ramp=min(25.,(hi-lo)/2)
   taper=np.minimum(1,np.minimum(xx-lo,hi-xx)/ramp)
   curve*=.5-.5*np.cos(np.pi*taper)
   # Reject overly abrupt runs instead of leaking corrections into untouched regions.
   if np.max(abs(np.diff(np.r_[0,curve,0])))>.5:continue
   curves[i,xx]=curve
 print(f"{label}: {n}/{n}; {np.count_nonzero(np.any(curves != 0,axis=1))} adjusted",flush=True)
 return curves,rows


def _ap_selected_source_gain(data, refs):
 """30-sample peak windows, immutable pair shared target; log-gain blending."""
 n,nt=data.shape;acc=np.zeros_like(data);support=np.zeros_like(data)
 for i,(a,b) in enumerate(refs):
  if a<0:continue
  for start in range(0,nt-29,10):
   stop=start+30;v=data[[i,a,b],start:stop]
   if not np.isfinite(v).all():continue
   amps=np.max(abs(v),axis=1)
   if amps[0]<.05*np.nanpercentile(abs(data[i]),95) or np.min(amps)<=0 or min(amps[1:]) < .05*np.nanpercentile(abs(data[[a,b]]),95):continue
   if max(amps[1:])/min(amps[1:])>1.5:continue
   target=np.median(amps);g=np.clip(target/amps[0],.67,1.5)
   w=np.hanning(32)[1:-1];acc[i,start:stop]+=w*np.log(g);support[i,start:stop]+=w
 return np.exp(np.divide(acc,support,out=np.zeros_like(acc),where=support>0))


def _ap_selected_peak_gain(s, gain_tracks):
 """Keep supported local track segments; a remote failure cannot veto all gain."""
 from scipy.signal import savgol_filter, find_peaks
 nt,nc=s.shape;t=np.arange(nt);acc=np.zeros_like(s);sup=np.zeros_like(s);records=[]
 for lo,hi,seed in gain_tracks:
  if not (1<=lo<hi<nt-1):raise ValueError('Gain track outside sample range')
  valid=np.isfinite(s[lo-1:hi+2]).all(axis=0)
  for j in np.flatnonzero(valid):
   pp=find_peaks(-s[lo-1:hi+2,j])[0]+lo-1
   valid[j]=np.any((pp>=lo)&(pp<=hi)&(s[pp,j]<0))
  ids=np.flatnonzero(valid)
  for run in np.split(ids,np.flatnonzero(np.diff(ids)>1)+1):
   if len(run)<11:continue
   q=_ap_selected_track(s[:,run],lo,hi,seed)
   # Split at event switches instead of rejecting the full section.
   cuts=np.flatnonzero(abs(np.diff(q))>6)+1
   for local in np.split(np.arange(len(run)),cuts):
    if len(local)<11:continue
    cols=run[local];peaks=q[local]
    amp=np.array([-np.interp(v,t,s[:,j]) for v,j in zip(peaks,cols)])
    target=np.exp(savgol_filter(np.log(amp),11,2));g=np.clip(target/amp,.67,1.5)
    for k,j in enumerate(cols):
     if amp[k]<.05*np.nanpercentile(abs(s[:,j]),95):continue
     d=abs(t-peaks[k]);w=np.where(d<=8,1,np.where(d<22,.5*(1+np.cos(np.pi*(d-8)/14)),0))
     acc[:,j]+=w*np.log(g[k]);sup[:,j]+=w
     records.append(dict(column=int(j),peak=float(peaks[k]),gain=float(g[k]),gate=[lo,hi]))
 return np.exp(acc/np.maximum(1,sup)),records


def run_ap_ppd_selected_workflow(raw, metadata, required_rows, sampling, output_prefix=None,
 gain_tracks=((85,125,95),(130,175,140)), second_pass=True, diagnostics=False, clip_percentile=99., source_gain_enabled=True):
 """One source pass, one optional residual section pass, one final lateral mean.
 References are frozen at the start of each pass. Header time zero is applied once.
 Gain track gates refer to samples AFTER header time zero, and are site-specific.
 """
 import time
 started=time.monotonic()
 raw=np.asarray(raw,dtype=float);n,nt=raw.shape;t=np.arange(nt)
 print(f"Selected workflow: {n} sources; building local reference pairs",flush=True)
 base,_,shifts=align_ap_ppd_source_time_zero(raw,metadata);tz=-np.asarray(shifts)
 refs=_ap_selected_references(metadata)
 curves,rows=_ap_selected_curves(base,refs,metadata,'Source timing')
 mapping=t[None,:]+tz[:,None]+curves
 if not np.all(np.diff(mapping,axis=1)>0):raise ValueError('Non-monotonic source timing')
 corrected=np.array([np.interp(q,t,y,left=np.nan,right=np.nan) for q,y in zip(mapping,raw)])
 print('Source peak gain and interpolation',flush=True)
 source_gain=_ap_selected_source_gain(corrected,refs) if source_gain_enabled else np.ones_like(corrected)
 balanced=corrected*source_gain
 baseline=interpolate_ap_ppd_source_matrix(base,required_rows,sampling)
 source_timing_section=interpolate_ap_ppd_source_matrix(corrected,required_rows,sampling)
 combined=interpolate_ap_ppd_source_matrix(balanced,required_rows,sampling)
 x=np.asarray(sampling['distance']);nc=len(x)
 section_curves=np.zeros((nc,nt));section_rows=[];timing=combined.copy()
 section_refs=np.full((nc,2),-1,dtype=int)
 if second_pass:
  for j in range(1,nc-1):
   if 0<x[j]-x[j-1]<=.1 and 0<x[j+1]-x[j]<=.1:section_refs[j]=[j-1,j+1]
  sm=np.zeros(nc,dtype=[('channel',int),('trace',int)]);sm['trace']=np.arange(nc)
  section_curves,section_rows=_ap_selected_curves(combined.T,section_refs,sm,'Section residual timing')
  if not np.all(np.diff(t[None,:]+section_curves,axis=1)>0):
   raise ValueError("Non-monotonic section timing")
  timing=np.array([np.interp(t+d,t,y,left=np.nan,right=np.nan) for d,y in zip(section_curves,combined.T)]).T
  # Preserve unsupported samples; never manufacture coverage.
  timing[~np.isfinite(combined)]=np.nan
 print('Section peak gain and final lateral mean',flush=True)
 gain,track_records=_ap_selected_peak_gain(timing,gain_tracks)
 print(f"Section gain: {len(track_records)} supported picks; {np.count_nonzero(np.any(gain != 1,axis=0))}/{nc} columns changed",flush=True)
 gained=timing*gain;final=gained.copy()
 if nc>2:
  candidate=.2*gained[:,:-2]+.6*gained[:,1:-1]+.2*gained[:,2:]
  ok=np.isfinite(candidate)&((np.diff(x)[:-1]<=.1)&(np.diff(x)[1:]<=.1))[None,:]
  final[:,1:-1]=np.where(ok,candidate,gained[:,1:-1])
 result=dict(linear_time_zero_aligned=baseline,linear_time_zero_experimental=timing,
  source_timing_section=source_timing_section,source_reference_indices=refs,
  section_reference_indices=section_refs,
  combined_section=combined,peak_gain_section=gained,final_section=final,distance=x,
  source_residual_advance=curves,source_corrected=corrected,source_gain=source_gain,
  section_residual_advance=section_curves,section_gain=gain,gain_tracks=track_records,
  second_pass=bool(second_pass))
 if diagnostics:result.update(window_diagnostics=rows,section_window_diagnostics=section_rows)
 if output_prefix is not None:
  from matplotlib.figure import Figure
  from matplotlib.backends.backend_agg import FigureCanvasAgg
  prefix=str(output_prefix)
  print('Saving comparison and processed arrays',flush=True)
  np.savez_compressed(prefix+'_selected_workflow.npz',baseline=baseline,combined=combined,
   timing=timing,gained=gained,final=final,distance=x,source_rows=required_rows,
   workflow_revision=np.array(16),source_timing_section=source_timing_section,
   source_reference_indices=refs,section_reference_indices=section_refs,
   source_gain_enabled=np.array(source_gain_enabled),second_pass=np.array(second_pass),
   metadata=metadata,source_residual_advance=curves,source_gain=source_gain,
   section_residual_advance=section_curves,section_gain=gain,time_zero_advance=tz)
  if diagnostics:
   import csv
   for name,records in [('source_windows',rows),('section_windows',section_rows)]:
    if records:
     with open(prefix+'_'+name+'.csv','w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
  fig=Figure(figsize=(13,11),layout='constrained');FigureCanvasAgg(fig)
  axes=fig.subplots(4,1,sharex=True,sharey=True)
  finite=abs(baseline[np.isfinite(baseline)]);lim=max(float(np.percentile(finite,clip_percentile)) if finite.size else 1.,1e-12)
  for ax,data,title in zip(axes,[baseline,combined,gained,final],['Header time zero','Source timing + peak gain, then interpolation','Residual section timing + reflector peak gain','Final lateral mean: 0.2 / 0.6 / 0.2']):
   ax.imshow(data,aspect='auto',interpolation='nearest',cmap='gray',vmin=-lim,vmax=lim,extent=[x[0],x[-1],nt,0]);ax.set_title(title);ax.set_ylabel('Samples after time zero')
  axes[-1].set_xlabel('Distance (m)');result['output_path']=prefix+'_selected_workflow.png';fig.savefig(result['output_path'],dpi=160)
 print(f"Selected workflow complete in {time.monotonic()-started:.1f}s",flush=True)
 return result
