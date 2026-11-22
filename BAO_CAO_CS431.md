# Cải thiện độ bền của Depth Anything 3 khi tái dựng 3D từ ảnh lệch phơi sáng

*Báo cáo ngắn gọn · Đồ án CS431 · 22/11/2026*

## 1. Bài toán và mục tiêu

Khi tái dựng 3D từ nhiều góc nhìn thiếu sáng hoặc lệch phơi sáng, Depth Anything 3 (DA3) chọn một ảnh tham chiếu ngay trong quá trình suy luận (mặc định là chiến lược `saddle_balanced` dựa trên đặc trưng DINOv2). Nếu ảnh tham chiếu quá tối, mất chi tiết hoặc quá khác biệt về phơi sáng so với các góc nhìn còn lại, chất lượng đám mây điểm 3D suy giảm đáng kể.

Đồ án kiểm chứng hai giả thuyết trên bộ dữ liệu thực **RealX3D (`data4_varyexp`)** với mô hình **DA3-Base** cố định (không huấn luyện lại):
- **H1**: Độ nhạy của chất lượng tái dựng (`F1 @ 5 cm`) theo lựa chọn ảnh tham chiếu lớn hơn ở điều kiện lệch phơi sáng so với điều kiện phơi sáng đồng đều.
- **H2**: Một bộ xếp hạng ảnh tham chiếu chỉ dùng ảnh RGB đầu vào — kết hợp chất lượng phơi sáng trung tâm và độ chồng lấp hình học — cải thiện F1 so với mặc định `saddle_balanced` trên các cảnh giữ lại mà không làm suy giảm ảnh phơi sáng đồng đều.

## 2. Phương pháp đề xuất (chỉ dùng RGB, không huấn luyện lại)

Với mỗi tập $N$ ảnh RGB đầu vào (giới hạn cạnh dài 504 px khi chấm điểm, ~0,5–1,0 giây/cảnh trên CPU):

1. **Nhánh phơi sáng trung tâm (`exposure_bridge`)**:
   - Tính độ hữu dụng phơi sáng $e_i \in [0, 1]$ bằng hai hàm cắt tuyến tính giảm trọng số vùng tối bệt ($Y < 8$) và vùng cháy sáng ($Y > 250$).
   - Áp dụng bão hòa mềm $\tanh(e_i / 0.15)$ để một ảnh sáng nổi trội không áp đảo các ảnh đủ sáng khác, rồi nhân với độ gần trung vị log-độ sáng $b_i = \exp(-|m_i - \mathrm{median}(m)| / 0.75)$ nhằm ưu tiên ảnh làm **cầu nối phơi sáng** giữa các ảnh tối và sáng.
2. **Nhánh chồng lấp hình học bền sáng (`overlap`)**:
   - Chuẩn hóa gamma thích nghi về trung vị độ sáng 110 rồi tăng tương phản cục bộ CLAHE (`clipLimit=3.0`).
   - Trích xuất SIFT (`nfeatures=2000`, `contrastThreshold=0.02`), lọc tỷ lệ `0.80` hai chiều và kiểm tra hình học bằng ma trận cơ bản RANSAC (`3.0 px`, tối thiểu 8 cặp). Điểm cặp dựa trên độ phủ lưới $4 \times 4$ và số điểm hỗ trợ, lấy trung bình qua mọi cặp chứa ảnh $i$.
3. **Kết hợp (`combined`)**:
   - Chuẩn hóa min-max từng nhánh để cân bằng thang đo, sau đó lấy trung bình $s_i = 0.5\,\tilde{e}_i^{\text{bridge}} + 0.5\,\tilde{o}_i$. Đưa ảnh có $s_i$ cao nhất lên đầu danh sách và gọi `ref_view_strategy="first"` của DA3 trên **ảnh RGB gốc**.

## 3. Thiết lập thí nghiệm

- **Mô hình & kiểm soát**: `depth-anything/DA3-BASE` (commit `f4a6c9b`), 4 ảnh/cảnh, độ phân giải `504`, GPU Kaggle Tesla T4 (~1,9 GB VRAM đỉnh, ~1–2 giây/lần suy luận).
- **Dữ liệu & chia cảnh**: Toàn bộ **9 cảnh** của RealX3D `data4_varyexp` — tách **4 cảnh pilot** (`Ujikintoki`, `BlueHawaii`, `Chocolate`, `Cupcake`) để kiểm tra dữ liệu & chốt tham số, và **5 cảnh giữ lại (held-out)** (`GearWorks`, `Laboratory`, `MilkCookie`, `Popcorn`, `Sculpture`) để đánh giá độc lập.
- **Ba điều kiện chụp trên cùng 4 góc nhìn**:
  - `default_json`: bộ ảnh lệch phơi sáng gốc trong thư mục `train/` của RealX3D.
  - `varyexp_mixed`: ghép 4 mức phơi sáng tăng dần (`train_60`, `train_160`, `train_250`, `train_400`).
  - `uniform_mid`: cùng 4 góc nhìn ở một mức phơi sáng đồng đều (`train_250`).
- **Đo hình học**: Pose chuẩn lấy từ `sparse/0/images.bin` biến đổi qua `colmap2world.txt` (khớp hệ tọa độ của `cull_pointcloud.ply`). Đám mây điểm DA3 được căn chỉnh bằng phép **Sim(3) kết hợp cả ma trận xoay và tâm camera** (`align_poses_sim3`), lấy mẫu voxel 1 cm và đo **F1 điểm–điểm ở ngưỡng 5 cm** (chỉ số chính) cùng **AUC@10°** sai số tư thế tương đối (chỉ số phụ).

## 4. Kết quả thực nghiệm

### 4.1. Trên 5 cảnh giữ lại (Held-out — tham số chốt cố định)

| Điều kiện (`n = 5`) | Mặc định (`saddle_balanced`) | Chỉ phơi sáng | `exposure_bridge` | Chỉ chồng lấp | **Kết hợp (`combined`)** | **Δ F1 vs Mặc định** | Oracle F1 | Biên độ `Span F1` | Default AUC@10° | Combined AUC@10° |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `default_json` (`train/`) | 0.3420 | 0.3536 | 0.3687 | 0.3831 | **0.4067** | **`+0.0647`** | 0.4160 | **0.1677** | 0.8639 | 0.8283 |
| `varyexp_mixed` | 0.3347 | 0.3606 | 0.3482 | 0.3811 | **0.4184** | **`+0.0837`** | 0.4555 | **0.1833** | 0.8490 | **0.8568** |
| `uniform_mid` (`train_250/`) | 0.2884 | 0.3276 | 0.3279 | 0.3101 | **0.3321** | **`+0.0437`** | 0.3366 | 0.0885 | 0.8433 | **0.8580** |

### 4.2. Tổng hợp toàn bộ 9/9 cảnh RealX3D (4 pilot + 5 held-out)

| Điều kiện (`n = 9`) | Mặc định F1 | Exposure F1 | Bridge F1 | Overlap F1 | **Combined F1** | **Δ F1 vs Mặc định** | Thắng / Hòa / Thua | Oracle F1 | Span F1 | Default AUC@10° | Combined AUC@10° |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: |
| `default_json` (`train/`) | 0.4280 | 0.4071 | 0.4390 | 0.4477 | **0.4673** | **`+0.0393`** | **5 / 4 / 0** | 0.4813 | **0.1869** | 0.8548 | 0.8416 |
| `varyexp_mixed` | 0.3852 | 0.4051 | 0.4052 | 0.4129 | **0.4404** | **`+0.0551`** | **6 / 0 / 3** | 0.4954 | **0.1686** | 0.8536 | 0.8491 |
| `uniform_mid` | 0.3391 | 0.3682 | 0.3684 | 0.3800 | **0.3932** | **`+0.0541`** | **6 / 2 / 1** | 0.4045 | 0.1107 | 0.8494 | **0.8568** |

## 5. Phân tích và kết luận

1. **Xác nhận H1**: Biên độ chênh lệch F1 khi đổi ảnh tham chiếu (`Span F1`) trên điều kiện lệch phơi sáng (`0.1869` trên `default_json`, `0.1686` trên `varyexp_mixed`; trên tập giữ lại là `0.1677` và `0.1833`) lớn hơn rõ rệt so với phơi sáng đồng đều (`0.1107` trên 9 cảnh và `0.0885` trên 5 cảnh giữ lại).
2. **Xác nhận H2**: Phương pháp `combined` vượt DA3 mặc định (`saddle_balanced`) và vượt cả 3 nhánh riêng lẻ ở mọi điều kiện — tăng **`+6,47%` đến `+8,37%` F1** trên 5 cảnh giữ lại (tổng 9 cảnh: **`+3,93%` đến `+5,51%` F1**, đặc biệt đạt **0 cảnh thua** trên `default_json` và tiệm cận mức trần `Oracle F1`), đồng thời vẫn cải thiện **`+4,37%` đến `+5,41%` F1** trên điều kiện đồng đều `uniform_mid`.
3. **Phạm vi so sánh**: Cải thiện được kiểm chứng công bằng so với baseline DA3 gốc trong cùng giao thức đo (4 góc nhìn, `DA3-Base`, căn chỉnh Sim(3), F1 điểm–điểm 5 cm). Không so sánh trực tiếp trị số tuyệt đối với Bảng 15 của bài báo RealX3D (39,2% / 63,6%) do khác số góc nhìn và giao thức ICP điểm–bề mặt.
4. **Giới hạn**: Thử nghiệm thực hiện trên 4 ảnh/cảnh và 9 cảnh trong nhóm `varyexp` của RealX3D; một số cảnh ít kết cấu như `Sculpture` có F1 tuyệt đối thấp (~0,09–0,11) do hạn chế chung của tái dựng thưa 4 góc nhìn.

## 6. Tài liệu & tái lập

- **Notebook Kaggle (pilot 4 cảnh)**: `notebooks/cs431-da3-exposure-v2.ipynb` ([Kaggle](https://www.kaggle.com/code/ngtunthanh/cs431-da3-exposure-experiment-v2))
- **Notebook Kaggle (held-out 5 cảnh)**: `notebooks/cs431-da3-exposure-heldout.ipynb` ([Kaggle](https://www.kaggle.com/code/ngtunthanh/cs431-da3-exposure-heldout-eval))
- **Dữ liệu kết quả đầy đủ**: `results/pilot/summary_v2.csv`, `results/heldout/summary_heldout.csv` và 27 tệp JSON chi tiết từng cảnh.
