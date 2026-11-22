# CS431 — Chọn ảnh tham chiếu bền vững phơi sáng cho Depth Anything 3

Mã nguồn, notebook Kaggle và kết quả thực nghiệm riêng của đồ án CS431, tách độc lập khỏi mã nguồn gốc `Depth-Anything-3` (commit `3d835ec`).

## Cấu trúc thư mục

- [BAO_CAO_CS431.md](BAO_CAO_CS431.md): Báo cáo tổng hợp ngắn gọn (bài toán, phương pháp, kết quả 9 cảnh RealX3D và phân tích).
- `cs431/`: Mã nguồn chọn ảnh tham chiếu RGB-only (`reference.py`), đo hình học & căn chỉnh Sim(3) (`geometry.py`), script chạy thực nghiệm (`run_experiment.py`) và unit test (`test_experiment.py`).
- `notebooks/`:
  - `cs431-da3-exposure-v2.ipynb`: Thực nghiệm 4 cảnh pilot (`Ujikintoki`, `BlueHawaii`, `Chocolate`, `Cupcake`) và chẩn đoán hệ tọa độ trên Kaggle GPU T4.
  - `cs431-da3-exposure-heldout.ipynb`: Đánh giá chốt tham số trên 5 cảnh giữ lại (`GearWorks`, `Laboratory`, `MilkCookie`, `Popcorn`, `Sculpture`).
- `results/`:
  - `pilot/`: Kết quả JSON và bảng tổng hợp (`summary_v2.csv`, `summary_v2.md`) của 4 cảnh pilot.
  - `heldout/`: Kết quả JSON và bảng tổng hợp (`summary_heldout.csv`, `summary_heldout.md`) của 5 cảnh giữ lại.

## Chạy nhanh

1. Cài đặt phụ thuộc từ repo gốc `../Depth-Anything-3` và thêm `PYTHONPATH=../Depth-Anything-3/src:.`.
2. Kiểm thử đơn vị:
   ```bash
   python -m unittest cs431.test_experiment -v
   ```
3. Chạy trên một cảnh RealX3D (dùng pose COLMAP `sparse/0` và `colmap2world.txt`):
   ```bash
   python -m cs431.run_experiment \
     --colmap-sparse data/SCENE/sparse/0 \
     --images data/SCENE/train/0001.JPG data/SCENE/train/0010.JPG data/SCENE/train/0020.JPG data/SCENE/train/0030.JPG \
     --gt-cloud pointclouds/SCENE/cull_pointcloud.ply \
     --colmap-to-world data/SCENE/colmap2world.txt \
     --sweep --device cuda:0 --resolution 504 --output out.json
   ```
