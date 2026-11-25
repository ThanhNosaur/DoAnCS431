"""Compare reference selection policies through the public DA3 inference API."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from cs431.geometry import (
    cloud_metrics,
    predicted_poses,
    relative_pose_metrics,
    to_metric_poses,
    voxel_sample,
)
from cs431.reference import reference_scores

DA3_BASE = "depth-anything/DA3-BASE"
DA3_BASE_REVISION = "f4a6c9b3c95e41c82048423d3493a81ec3fa810e"


def load_views(transforms, image_root, count, image_paths=None):
    frames = json.loads(transforms.read_text(encoding="utf-8"))["frames"]
    root = image_root.resolve()
    if image_paths is None:
        if not 3 <= count <= len(frames):
            raise ValueError(f"Choose 3 to {len(frames)} views from {transforms}.")
        selected = [
            ((root / frames[i]["file_path"]).resolve(), frames[i])
            for i in np.linspace(0, len(frames) - 1, count, dtype=int)
        ]
    else:
        by_name = {}
        for frame in frames:
            name = Path(frame["file_path"]).name.casefold()
            if name in by_name:
                raise ValueError(f"Ambiguous camera metadata for image name {name}.")
            by_name[name] = frame
        names = [path.name.casefold() for path in image_paths]
        if len(names) < 3 or len(names) != len(set(names)):
            raise ValueError("Explicit images must contain at least three distinct view names.")
        if missing := set(names) - by_name.keys():
            raise ValueError(f"No camera metadata for: {', '.join(sorted(missing))}")
        selected = [(path.resolve(), by_name[name]) for path, name in zip(image_paths, names)]

    paths, matrices = [], []
    for path, frame in selected:
        if not path.is_file() or (image_paths is None and not path.is_relative_to(root)):
            raise ValueError(f"Image path is missing or outside the image root: {path}")
        matrix = np.asarray(frame["transform_matrix"], dtype=float)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            raise ValueError(f"Expected a finite camera-to-world matrix for {path}.")
        if not np.allclose(matrix[3], [0, 0, 0, 1]):
            raise ValueError(f"Invalid homogeneous camera-to-world matrix for {path}.")
        paths.append(path)
        matrices.append(matrix @ np.diag([1, -1, -1, 1]))
    if len(set(paths)) != len(paths):
        raise ValueError("The sampled frames include duplicate image paths.")
    return paths, np.stack(matrices)


def _qvec_to_rotmat(qvec):
    qw, qx, qy, qz = qvec
    return np.array(
        [
            [1 - 2 * qy * qy - 2 * qz * qz, 2 * qx * qy - 2 * qz * qw, 2 * qx * qz + 2 * qy * qw],
            [2 * qx * qy + 2 * qz * qw, 1 - 2 * qx * qx - 2 * qz * qz, 2 * qy * qz - 2 * qx * qw],
            [2 * qx * qz - 2 * qy * qw, 2 * qy * qz + 2 * qx * qw, 1 - 2 * qx * qx - 2 * qy * qy],
        ],
        dtype=float,
    )


def _read_colmap_images(sparse_dir: Path) -> dict[str, np.ndarray]:
    """Read OpenCV camera-to-world poses directly from COLMAP images.bin or images.txt."""
    import struct

    by_name = {}
    bin_path = sparse_dir / "images.bin"
    txt_path = sparse_dir / "images.txt"
    if bin_path.is_file():
        with bin_path.open("rb") as f:
            (num_images,) = struct.unpack("<Q", f.read(8))
            for _ in range(num_images):
                _, qw, qx, qy, qz, tx, ty, tz, _ = struct.unpack("<idddddddi", f.read(64))
                chars = []
                while (ch := f.read(1)) and ch != b"\x00":
                    chars.append(ch)
                img_name = b"".join(chars).decode("utf-8")
                (num_pts2d,) = struct.unpack("<Q", f.read(8))
                f.seek(num_pts2d * 24, 1)
                w2c = np.eye(4, dtype=float)
                w2c[:3, :3] = _qvec_to_rotmat((qw, qx, qy, qz))
                w2c[:3, 3] = (tx, ty, tz)
                name = Path(img_name).name.casefold()
                if name in by_name:
                    raise ValueError(f"Ambiguous COLMAP pose for image name {name}.")
                by_name[name] = np.linalg.inv(w2c)
    elif txt_path.is_file():
        lines = iter(
            line.strip()
            for line in txt_path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        for line in lines:
            if not line:
                continue
            parts = line.split()
            qw, qx, qy, qz, tx, ty, tz = map(float, parts[1:8])
            img_name = " ".join(parts[9:])
            next(lines, None)  # The POINTS2D line can be empty.
            w2c = np.eye(4, dtype=float)
            w2c[:3, :3] = _qvec_to_rotmat((qw, qx, qy, qz))
            w2c[:3, 3] = (tx, ty, tz)
            name = Path(img_name).name.casefold()
            if name in by_name:
                raise ValueError(f"Ambiguous COLMAP pose for image name {name}.")
            by_name[name] = np.linalg.inv(w2c)
    else:
        raise FileNotFoundError(f"Neither images.bin nor images.txt found in {sparse_dir}")
    return by_name


def load_colmap_views(sparse_dir: Path, image_paths: list[Path]):
    """Load exact OpenCV camera-to-world poses from a COLMAP sparse reconstruction."""
    by_name = _read_colmap_images(sparse_dir)

    names = [path.name.casefold() for path in image_paths]
    if len(names) < 3 or len(names) != len(set(names)):
        raise ValueError("Explicit images must contain at least three distinct view names.")
    if missing := set(names) - by_name.keys():
        raise ValueError(f"No COLMAP pose for: {', '.join(sorted(missing))}")
    paths = [path.resolve(strict=True) for path in image_paths]
    return paths, np.stack([by_name[name] for name in names])


def evaluate_views(images, infer, sweep=False):
    started = perf_counter()
    scores = reference_scores(images)
    selection_seconds = perf_counter() - started
    indices = list(range(len(images)))
    runs = {
        "saddle_balanced": {
            "reference_index": None,
            **infer(images, "saddle_balanced", indices),
        }
    }
    by_index = {}

    def run(index):
        if index not in by_index:
            order = [index] + [i for i in indices if i != index]
            ordered = [images[i] for i in order]
            by_index[index] = {"reference_index": index, **infer(ordered, "first", order)}
        return by_index[index]

    runs.update({name: run(int(np.argmax(values))) for name, values in scores.items()})
    report = {
        "scores": {name: values.tolist() for name, values in scores.items()},
        "selection_seconds": selection_seconds,
        "runs": runs,
    }
    if sweep:
        report["sweep"] = [run(index) for index in indices]
        valid = [result for result in report["sweep"] if result.get("f1") is not None]
        if valid:
            report["oracle_f1"] = max(valid, key=lambda result: result["f1"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images", nargs="+", type=Path, help="RGB images in order, matched by name if using JSON."
    )
    parser.add_argument("--transforms", type=Path, help="RealX3D transforms_<split>.json.")
    parser.add_argument(
        "--colmap-sparse",
        type=Path,
        help="Optional COLMAP sparse/0 directory to load exact COLMAP poses for colmap2world.",
    )
    parser.add_argument("--image-root", type=Path, help="Override the image root for the JSON.")
    parser.add_argument("--views", type=int, default=4, help="Views sampled from the JSON.")
    parser.add_argument("--gt-cloud", type=Path, help="Metric RealX3D cull_pointcloud.ply.")
    parser.add_argument("--colmap-to-world", type=Path, help="Override the pose-to-scan transform.")
    parser.add_argument("--sweep", action="store_true", help="Try every image as the reference.")
    parser.add_argument("--model", default=DA3_BASE, help="Hub ID or checkpoint path.")
    parser.add_argument(
        "--lora-weights", type=Path, help="Evaluate the saved DA3-Base adapter with Combined selection."
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--resolution", type=int, default=504)
    parser.add_argument("--output", type=Path, help="Write the JSON report to a new file.")
    args = parser.parse_args()
    if not (args.images or args.transforms):
        parser.error("Supply --images, --transforms, or both.")
    if args.colmap_sparse and not args.images:
        parser.error("--colmap-sparse requires explicit --images.")
    if not (args.transforms or args.colmap_sparse) and (
        args.image_root or args.gt_cloud or args.colmap_to_world
    ):
        parser.error(
            "--image-root, --gt-cloud and --colmap-to-world require --transforms or --colmap-sparse."
        )
    if args.images and args.image_root:
        parser.error("Use either explicit --images or --image-root.")
    if args.colmap_to_world and not args.gt_cloud:
        parser.error("--colmap-to-world requires --gt-cloud.")
    if args.resolution < 14:
        parser.error("--resolution must be at least 14 pixels.")
    if args.lora_weights and args.model != DA3_BASE:
        parser.error("--lora-weights requires the pinned DA3-Base model.")
    if args.lora_weights and not args.lora_weights.is_file():
        parser.error(f"LoRA checkpoint does not exist: {args.lora_weights}")
    if args.output and args.output.exists():
        parser.error(f"Output already exists: {args.output}")

    gt_poses = gt_points = gt_metric_poses = None
    transform_path = None
    if args.colmap_sparse:
        paths, gt_poses = load_colmap_views(args.colmap_sparse, args.images)
    elif args.transforms:
        paths, gt_poses = load_views(
            args.transforms, args.image_root or args.transforms.parent, args.views, args.images
        )
    else:
        paths = [path.resolve(strict=True) for path in args.images]
        if len(paths) < 3 or len(set(paths)) != len(paths):
            parser.error("--images requires at least three distinct paths.")

    if args.gt_cloud:
        from plyfile import PlyData

        if args.colmap_to_world:
            transform_path = args.colmap_to_world
        elif args.transforms:
            transform_path = args.transforms.parent / "colmap2world.txt"
        else:
            transform_path = args.colmap_sparse.parent.parent / "colmap2world.txt"
        transform = (
            np.load(transform_path, allow_pickle=False)
            if transform_path.suffix.lower() == ".npy"
            else np.loadtxt(transform_path)
        )
        gt_metric_poses = to_metric_poses(gt_poses, transform)
        vertices = PlyData.read(str(args.gt_cloud))["vertex"].data
        xyz = np.column_stack([vertices[axis] for axis in "xyz"]).astype(float)
        if not len(xyz) or not np.isfinite(xyz).all():
            raise ValueError("The GT cloud must contain finite XYZ vertices.")
        gt_points = voxel_sample(xyz)

    images = []
    for path in paths:
        with Image.open(path) as image:
            images.append(image.convert("RGB"))

    import torch
    from depth_anything_3.api import DepthAnything3

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable. Enable a GPU runtime or try --device cpu.")
    revision = DA3_BASE_REVISION if args.model == DA3_BASE else None
    model = DepthAnything3.from_pretrained(args.model, revision=revision).to(device).eval()

    def infer(ordered, strategy, order):
        if device.type == "cuda":
            torch.cuda.synchronize(device)
            torch.cuda.reset_peak_memory_stats(device)
        started = perf_counter()
        prediction = model.inference(
            ordered, ref_view_strategy=strategy, process_res=args.resolution
        )
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        result = {"inference_seconds": perf_counter() - started}
        if device.type == "cuda":
            result["peak_cuda_mib"] = torch.cuda.max_memory_allocated(device) / 1024**2
        started = perf_counter()
        if gt_poses is not None:
            result.update(relative_pose_metrics(predicted_poses(prediction.extrinsics), gt_poses[order]))
        if gt_points is not None:
            result.update(cloud_metrics(prediction, gt_metric_poses[order], gt_points))
        result["metric_seconds"] = perf_counter() - started
        return result

    report = {
        "model": args.model,
        "model_revision": revision or getattr(model, "_commit_hash", None),
        "device": str(device),
        "resolution": args.resolution,
        "images": [str(path) for path in paths],
        "transforms": str(args.transforms) if args.transforms else None,
        "gt_cloud": str(args.gt_cloud) if args.gt_cloud else None,
        "colmap_to_world": str(transform_path) if transform_path else None,
        **evaluate_views(images, infer, args.sweep),
    }
    if args.lora_weights:
        from cs431.lora_adapt import attach_lora_to_da3, load_lora_weights

        attach_lora_to_da3(model)
        load_lora_weights(model, args.lora_weights)
        ref_idx = report["runs"]["combined"]["reference_index"]
        order = [ref_idx] + [i for i in range(len(images)) if i != ref_idx]
        report["lora_weights"] = str(args.lora_weights)
        report["runs"]["lora_combined"] = {
            "reference_index": ref_idx,
            **infer([images[i] for i in order], "first", order),
        }

    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as file:
            file.write(payload)
        print(f"Saved {args.output}")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
