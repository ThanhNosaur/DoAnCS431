# CS431 — Chọn ảnh tham chiếu và thích nghi phơi sáng cho Depth Anything 3

**Combined** chọn ảnh tham chiếu cho DA3-Base dựa trên mức phơi sáng và độ chồng lấp giữa các góc nhìn. Đồ án đánh giá thêm **Exposure-Consistency LoRA** để đo phần cải thiện khi thích nghi mô hình trên bốn cảnh huấn luyện.

## Mã nguồn và kết quả

- [Báo cáo đồ án](BAO_CAO_CS431.md) mô tả phương pháp và kết quả trên RealX3D.
- [Notebook tái lập RealX3D](notebooks/realx3d.ipynb) mặc định nạp checkpoint đã lưu và chạy đánh giá. Đặt `RETRAIN = True` để huấn luyện lại. Trên Kaggle, bật GPU và Internet rồi chạy toàn bộ, kết quả lưu vào `/kaggle/working/outputs`.
- [Kết quả pilot](results/pilot/summary.csv), [kết quả giữ lại](results/heldout/summary.csv), [kiểm tra luân phiên phơi sáng](results/exposure_rotations/summary.csv) và [so sánh các cấu hình có huấn luyện](results/train_ab/summary_ab.csv) được tạo từ lượt chạy Kaggle. [Thông tin tái lập](results/evaluation_provenance.json) ghi môi trường và SHA-256 của mã, checkpoint.
- [Checkpoint Exposure-Consistency LoRA](results/train_ab/da3_lora_r4.pt) dùng cho cấu hình mở rộng. [Checkpoint bộ chọn học được](results/train_ab/learned_selector_A.pt) dùng cho đối chứng.

## Chạy trên một cảnh RealX3D

Notebook đã cài sẵn các phụ thuộc khi chạy. Để dùng CLI riêng, cài PyTorch cho thiết bị của bạn và thêm mã nguồn DA3 gốc vào `PYTHONPATH`. Các lệnh dưới đây dùng Bash, chạy từ gốc repo đồ án.

```bash
git clone https://github.com/ByteDance-Seed/Depth-Anything-3.git ../Depth-Anything-3
git -C ../Depth-Anything-3 checkout 3d835ec1a5802d64a8b8b15f817a1ab54809bfe4
python -m pip install 'numpy<2' 'opencv-python-headless<4.12' scipy pillow torchvision \
  addict omegaconf 'einops>=0.8' 'huggingface_hub<1' safetensors evo plyfile \
  trimesh e3nn 'moviepy==1.0.3' imageio pycolmap pillow_heif
export PYTHONPATH="../Depth-Anything-3/src${PYTHONPATH:+:$PYTHONPATH}"
python -m unittest discover -v
```

Thay `SCENE` và tên tệp ảnh theo cảnh thực tế. Dùng `--device cpu` nếu máy chạy CPU.

```bash
python -m cs431.run_experiment \
  --colmap-sparse data/SCENE/sparse/0 \
  --images data/SCENE/train/0001.JPG data/SCENE/train/0010.JPG data/SCENE/train/0020.JPG data/SCENE/train/0030.JPG \
  --gt-cloud pointclouds/SCENE/cull_pointcloud.ply \
  --colmap-to-world data/SCENE/colmap2world.txt \
  --lora-weights results/train_ab/da3_lora_r4.pt \
  --sweep --device cuda:0 --resolution 504 --output out.json
```

Trong JSON đầu ra, `runs.combined` là kết quả của phương pháp chính và `runs.saddle_balanced` là kết quả DA3 mặc định. `--lora-weights` thêm `runs.lora_combined`. `--sweep` chạy DA3 gốc với từng ảnh làm tham chiếu. Phần tử đầu của `sweep` tương ứng thiết lập `first` trong benchmark DA3.
