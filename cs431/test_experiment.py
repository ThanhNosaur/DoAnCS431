import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from cs431.geometry import cloud_metrics, relative_pose_metrics, to_metric_poses, voxel_sample
from cs431.reference import reference_scores
from cs431.run_experiment import evaluate_views, load_views


class ReferenceSelectionTests(unittest.TestCase):
    def test_exposure_penalizes_blacks_and_clipped_highlights(self):
        images = [Image.new("RGB", (48, 48), (level,) * 3) for level in (5, 100, 254)]
        scores = reference_scores(images)
        self.assertEqual(int(np.argmax(scores["exposure"])), 1)
        self.assertEqual(int(np.argmax(scores["combined"])), 1)
        np.testing.assert_array_equal(scores["overlap"], [0, 0, 0])

    def test_feature_overlap_prefers_a_view_with_shared_detail(self):
        rng = np.random.default_rng(5)
        texture = rng.integers(30, 220, (240, 240), dtype=np.uint8)
        images = [
            Image.fromarray(np.roll(texture, shift, axis=1)).convert("RGB")
            for shift in (0, 12, 24)
        ]
        images.append(Image.new("RGB", (240, 240), (100,) * 3))
        scores = reference_scores(images)
        self.assertTrue(np.all(scores["overlap"][:3] > 0.1))
        self.assertEqual(scores["overlap"][3], 0)


class GeometryTests(unittest.TestCase):
    def test_voxel_sample_does_not_depend_on_view_order(self):
        points = np.array([[0.003, 0, 0], [0.007, 0, 0], [0.02, 0, 0]])
        np.testing.assert_allclose(voxel_sample(points), voxel_sample(points[::-1]))
        np.testing.assert_allclose(voxel_sample(points)[0], [0.005, 0, 0])

    def test_relative_pose_ignores_world_similarity(self):
        poses = np.repeat(np.eye(4)[None], 3, axis=0)
        poses[:, :3, 3] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        transform = np.eye(4)
        transform[:3, :3] = 2 * rotation
        transform[:3, 3] = [4, 5, 6]
        changed = to_metric_poses(poses, transform)
        self.assertAlmostEqual(relative_pose_metrics(changed, poses)["auc10"], 1.0)
        np.testing.assert_allclose(changed[1, :3, 3], [4, 7, 6])

    def test_world_transform_rejects_nonuniform_scale(self):
        with self.assertRaises(ValueError):
            to_metric_poses(np.eye(4)[None], np.diag([2, 1, 1, 1]))

    def test_cloud_alignment_restores_units_and_frame(self):
        poses = np.repeat(np.eye(4)[None], 3, axis=0)
        poses[:, :3, 3] = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]  # collinear camera centers!
        prediction = SimpleNamespace(
            depth=np.ones((3, 2, 2)),
            intrinsics=np.repeat(np.eye(3)[None], 3, axis=0),
            extrinsics=np.linalg.inv(poses)[:, :3],
        )
        rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        transform = np.eye(4)
        transform[:3, :3] = 2.0 * rotation
        transform[:3, 3] = [3, 4, 5]
        gt_poses = to_metric_poses(poses, transform)
        base_pts = np.array(
            [[x, y, 1] for x, y in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1))],
            dtype=float,
        )
        points = 2.0 * (base_pts @ rotation.T) + [3, 4, 5]
        metrics = cloud_metrics(prediction, gt_poses, points, stride=1)
        self.assertAlmostEqual(metrics["f1"], 1.0)
        self.assertAlmostEqual(metrics["scale_to_metres"], 2.0)
        self.assertLess(metrics["median_pred_to_gt_m"], 1e-6)


class ExperimentTests(unittest.TestCase):
    def test_image_order_and_ablation_reuse(self):
        images = [Image.new("RGB", (2, 2), (i, i, i)) for i in range(4)]
        calls = []

        def infer(ordered, strategy, order):
            self.assertEqual(order, [im.getpixel((0, 0))[0] for im in ordered])
            calls.append((tuple(im.getpixel((0, 0))[0] for im in ordered), strategy))
            return {"f1": float(ordered[0].getpixel((0, 0))[0]) / 3}

        scores = {
            "exposure": np.array([0.1, 0.8, 0.3, 0.1]),
            "overlap": np.array([0.1, 0.3, 0.8, 0.1]),
            "combined": np.array([0.1, 0.55, 0.55, 0.1]),
        }
        with patch("cs431.run_experiment.reference_scores", return_value=scores):
            result = evaluate_views(images, infer, sweep=True)
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[0], ((0, 1, 2, 3), "saddle_balanced"))
        self.assertEqual(calls[2], ((2, 0, 1, 3), "first"))
        self.assertEqual(result["runs"]["combined"]["reference_index"], 1)
        self.assertEqual(result["oracle_f1"]["reference_index"], 3)

    def test_scene_loader_reads_blender_camera_centres_and_safe_paths(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame_matrix = np.eye(4)
            frame_matrix[0, 3] = 1
            rows = []
            for i in range(4):
                path = root / f"view_{i}.jpg"
                path.touch()
                frame_matrix[1, 3] = i
                rows.append({"file_path": path.name, "transform_matrix": frame_matrix.tolist()})
            metadata = root / "transforms_train.json"
            metadata.write_text(json.dumps({"frames": rows}), encoding="utf-8")
            views, poses = load_views(metadata, root, 4)
            self.assertEqual(views[0], root / "view_0.jpg")
            np.testing.assert_array_equal(poses[0, :3, :3], np.diag([1, -1, -1]))
            self.assertEqual(poses[0, 0, 3], 1)
            alternate = root / "train_400"
            alternate.mkdir()
            exposures = [alternate / f"view_{i}.jpg" for i in (3, 0, 1)]
            for path in exposures:
                path.touch()
            selected, matched = load_views(metadata, root, 4, image_paths=exposures)
            self.assertEqual(selected, exposures)
            np.testing.assert_array_equal(matched, poses[[3, 0, 1]])
            rows[0]["file_path"] = "../escape.jpg"
            metadata.write_text(json.dumps({"frames": rows}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_views(metadata, root, 4)


if __name__ == "__main__":
    unittest.main()
