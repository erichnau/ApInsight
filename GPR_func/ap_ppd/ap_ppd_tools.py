import numpy as np
import os
import shapefile
import json
import numpy as np
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

    print(f"Traces within {max_distance:.2f} m: {len(selected_traces)}")
    print(f"Section line: {line_path}")
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

    print(f"Unique usable positions: {len(unique_xy)}")
    print(
        "Additional usable traces at repeated positions:",
        len(usable_rows) - len(unique_xy),
    )

    if len(usable_rows) < 3:
        raise ValueError("Too few usable traces for triangulation.")

    # Resolve duplicate coordinates only among usable traces.
    unique_xy, representative_rows, coordinate_counts = np.unique(
        trace_xy[usable_rows],
        axis=0,
        return_index=True,
        return_counts=True,
    )

    # Convert indices in the filtered array back to ORIGINAL corridor rows.
    representative_rows = usable_rows[representative_rows]

    print(f"Unique usable positions: {len(unique_xy)}")
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

    print("\n--- Section sampling comparison ---")
    print(f"Length: {total_length:.3f} m")
    print(f"Output positions: {len(sample_xy)}")
    print(f"Spacing: {spacing:.3f} m (last interval may be shorter)")
    print(f"Valid nearest positions: {nearest_valid.sum()}/{len(sample_xy)}")
    print(f"Valid linear positions: {triangle_valid.sum()}/{len(sample_xy)}")
    print(f"Outside triangulation: {(~inside).sum()}")
    print(f"Sampling points: {points_path}")
    print(f"Sampling links: {links_path}")

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
):
    """
    Create three section previews: nearest trace, linear interpolation,
    and linear interpolation after relative source time-zero alignment.

    `traces` must be the same corridor array used to create `sampling`.
    The first two panels retain stored sample indices; the third uses
    aligned sample indices. Unavailable samples remain NaN.
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

    quality_report = report_ap_ppd_timing_and_quality(
        traces[required_rows]
    )

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

    # Start with the existing 29 m position to verify the new outputs.
    # Then replace/add centres using distances from the fixed section.
    inspection_points = {
        "marked_left": 28.35,
        # Enable these after checking the first location:
        # "marked_middle": 36.25,
        # "marked_right": 41.75,
    }

    half_width_m = 0.5

    # These are sample indices, not nanoseconds.
    windows = {
        "full_trace": (0, source_data.shape[1]),
    }

    section_distances = np.asarray(sampling["distance"], dtype=float)

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
        np.abs(source_data), clip_percentile
    ))

    if amplitude_limit <= 0:
        amplitude_limit = float(np.max(np.abs(source_data)))

    if amplitude_limit <= 0:
        amplitude_limit = 1.0

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

    fig = Figure(figsize=(15, 13), constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(3, 1, sharex=True, sharey=True)

    from matplotlib import colormaps
    colourmap = colormaps["gray"].copy()
    colourmap.set_bad("lightblue")

    for ax, section, title in zip(
            axes,
            (
                    nearest_section,
                    linear_section,
                    aligned_linear_section,
            ),
            (
                    "Nearest trace — original timing",
                    "Linear interpolation — original timing",
                    (
                            "Linear interpolation — time-zero aligned "
                            f"to reference point {time_zero_reference}"
                    ),
            ),
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

    axes[2].set_ylabel("Samples after recorded time zero")
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
        f"{section_name}: quality-filtered section comparison\n"
        "Third panel: source timing aligned before interpolation\n"
        "Light blue = unavailable samples; "
        "red ticks = excluded corridor traces\n"
        "Blue outline = diagnostic interval; dashed line = centre"
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

    return {
        "nearest": nearest_section,
        "linear": linear_section,
        "distance": distances.copy(),
        "sample_index": np.arange(sample_count),
        "time_zero_aligned": False,
        "linear_time_zero_aligned_applied": True,
        "output_path": output_path,
        "linear_time_zero_aligned": aligned_linear_section,
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

    print(f"Corridor traces: {len(traces)}")
    print(f"Excluded: {len(excluded_rows)}")
    print(f"Usable: {len(usable_rows)}")
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
        f"{section_name}: source diagnostics\n"
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
        f"{section_name}: {diagnostic_tag or 'source comparison'}\n"
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