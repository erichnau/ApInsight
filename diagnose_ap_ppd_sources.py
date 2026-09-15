from pathlib import Path
import csv
import json

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from GPR_func.ap_ppd.ApPPDReader import ApPPDReader


FOLDER = Path(r"D:\05_sites\Keldur\processing\PreProcData\nomig")
FILENAME = "B_10072022_nomig_0003.ap_ppd"

# Centre trace number for each contributing channel.
GROUPS = {
    "T2943": {
        "centre": 2943,
        "channels": [9, 12, 13, 14, 15],
    },
    "T7491": {
        "centre": 7491,
        "channels": [0, 1, 2, 3, 4],
    },
}


def diagnose_source_sequences(
    folder=FOLDER,
    filename=FILENAME,
    groups=None,
    half_count=100,
):
    """
    Read acquisition-order trace windows directly from one ApPPD file.

    No spatial interpolation, smoothing, gain normalization or additional
    time-zero adjustment is applied. Existing source processing remains.
    """
    if groups is None:
        groups = GROUPS

    if not isinstance(half_count, int) or half_count < 1:
        raise ValueError("half_count must be a positive integer.")

    folder = Path(folder)
    source_path = folder / filename
    output_dir = folder / f"{source_path.stem}_source_diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = ApPPDReader(str(source_path))
    header, metadata = reader.read()
    sample_count = int(header["points_per_trace"])

    sequences = []

    for group_name, settings in groups.items():
        centre = int(settings["centre"])
        first_trace = centre - half_count
        last_trace = centre + half_count

        for channel in settings["channels"]:
            selected = sorted(
                (
                    trace for trace in metadata
                    if int(trace["channel"]) == channel
                    and first_trace <= int(trace["trace"]) <= last_trace
                ),
                key=lambda trace: int(trace["trace"]),
            )

            if not selected:
                print(f"No records: {group_name}, channel {channel}")
                continue

            numbers = np.array(
                [int(trace["trace"]) for trace in selected],
                dtype=np.int64,
            )

            if len(np.unique(numbers)) != len(numbers):
                raise ValueError(
                    f"Duplicate trace numbers in channel {channel}."
                )

            amplitudes = np.stack([
                reader.read_trace_samples(trace, header)
                for trace in selected
            ]).astype(np.float32)

            if amplitudes.shape != (len(selected), sample_count):
                raise ValueError("Unexpected amplitude-array dimensions.")

            if not np.isfinite(amplitudes).all():
                raise ValueError(
                    f"Non-finite amplitudes in channel {channel}."
                )

            # Keep missing records as gaps on the acquisition-number axis.
            expected = np.arange(first_trace, last_trace + 1)
            display = np.full(
                (sample_count, len(expected)),
                np.nan,
                dtype=np.float32,
            )
            display[:, numbers - first_trace] = amplitudes.T

            sequences.append({
                "group": group_name,
                "channel": channel,
                "centre": centre,
                "numbers": numbers,
                "metadata": selected,
                "amplitudes": amplitudes,
                "display": display,
                "first_trace": first_trace,
                "last_trace": last_trace,
            })

            # Save exact decoded samples for subsequent numerical analysis.
            prefix = output_dir / f"{group_name}_CH{channel:02d}"

            np.savez_compressed(
                str(prefix) + ".npz",
                amplitudes=amplitudes,  # traces × samples
                trace_numbers=numbers,
                x=np.array([trace["x"] for trace in selected]),
                y=np.array([trace["y"] for trace in selected]),
                z=np.array([trace["z"] for trace in selected]),
                time_zero=np.array([
                    trace["time_zero"] for trace in selected
                ]),
            )

            # Preserve all reader metadata, including the quality flags.
            with open(
                str(prefix) + "_metadata.csv",
                "w",
                newline="",
                encoding="utf-8",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=list(selected[0]),
                )
                writer.writeheader()
                writer.writerows(selected)

            print(
                f"{group_name}, CH{channel}: "
                f"{len(selected)}/{len(expected)} records; "
                f"T{numbers[0]}–T{numbers[-1]}"
            )

    if not sequences:
        raise ValueError("No requested traces were found.")

    with open(
        output_dir / "source_header.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            {"source_file": str(source_path), "header": header},
            handle,
            indent=2,
        )

    # One shared amplitude scale across every channel and group.
    all_values = np.concatenate([
        sequence["amplitudes"].ravel()
        for sequence in sequences
    ])
    limit = max(
        float(np.percentile(np.abs(all_values), 99)),
        1e-12,
    )

    # One figure per source group; identical colour limits.
    for group_name in groups:
        group_sequences = [
            sequence for sequence in sequences
            if sequence["group"] == group_name
        ]
        if not group_sequences:
            continue

        fig = Figure(
            figsize=(14, 2.8 * len(group_sequences)),
            constrained_layout=True,
        )
        FigureCanvasAgg(fig)

        axes = fig.subplots(
            len(group_sequences),
            1,
            squeeze=False,
        ).ravel()

        from matplotlib import colormaps
        cmap = colormaps["gray"].copy()
        cmap.set_bad("lightblue")

        for ax, sequence in zip(axes, group_sequences):
            image = ax.imshow(
                np.ma.masked_invalid(sequence["display"]),
                origin="upper",
                aspect="auto",
                interpolation="nearest",
                cmap=cmap,
                vmin=-limit,
                vmax=limit,
                extent=(
                    sequence["first_trace"] - 0.5,
                    sequence["last_trace"] + 0.5,
                    sample_count - 0.5,
                    -0.5,
                ),
            )
            ax.axvline(
                sequence["centre"],
                color="dodgerblue",
                linestyle="--",
                linewidth=1,
            )
            ax.set_title(f"Channel {sequence['channel']}")
            ax.set_ylabel("Stored sample index")
            ax.set_xlabel("Acquisition trace number")

        fig.colorbar(
            image,
            ax=list(axes),
            label="Decoded amplitude — shared scale",
            shrink=0.8,
        )
        fig.suptitle(
            f"{filename}: {group_name}\n"
            "Acquisition order; no additional timing or amplitude correction"
        )
        fig.savefig(
            output_dir / f"{group_name}_channels.png",
            dpi=180,
        )

    # Plot the actual trajectories to assess spatial overlap.
    fig = Figure(figsize=(10, 9), constrained_layout=True)
    FigureCanvasAgg(fig)
    ax = fig.subplots()

    x_origin = float(sequences[0]["metadata"][0]["x"])
    y_origin = float(sequences[0]["metadata"][0]["y"])

    for sequence in sequences:
        xy = np.array([
            (trace["x"], trace["y"])
            for trace in sequence["metadata"]
        ])
        xy -= [x_origin, y_origin]

        line, = ax.plot(
            xy[:, 0],
            xy[:, 1],
            ".-",
            markersize=2,
            linewidth=0.8,
            label=f"{sequence['group']} / CH{sequence['channel']}",
        )

        centre_rows = np.flatnonzero(
            sequence["numbers"] == sequence["centre"]
        )
        if len(centre_rows):
            point = xy[centre_rows[0]]
            ax.scatter(
                *point,
                marker="x",
                s=65,
                color=line.get_color(),
            )

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel(f"East offset from {x_origin:.3f} m")
    ax.set_ylabel(f"North offset from {y_origin:.3f} m")
    ax.set_title("Source trajectories; crosses = centre traces")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    fig.savefig(output_dir / "source_trajectories.png", dpi=180)

    print(f"\nSaved diagnostics to:\n{output_dir}")
    return sequences


if __name__ == "__main__":
    diagnose_source_sequences()