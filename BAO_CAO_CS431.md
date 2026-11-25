# Cải thiện độ bền của Depth Anything 3 khi tái dựng 3D từ ảnh lệch phơi sáng

*Báo cáo ngắn gọn · Đồ án CS431 · 22/11/2026*

## 1. Bài toán và mục tiêu

Khi tái dựng 3D từ nhiều góc nhìn thiếu sáng hoặc lệch phơi sáng, Depth Anything 3 (DA3) chọn một ảnh tham chiếu ngay trong quá trình suy luận (mặc định là chiến lược `saddle_balanced` dựa trên đặc trưng DINOv2). Nếu ảnh tham chiếu quá tối, mất chi tiết hoặc quá khác biệt về phơi sáng so với các góc nhìn còn lại, chất lượng đám mây điểm 3D suy giảm đáng kể.

Đồ án dùng **RealX3D (`data4_varyexp`)** để kiểm tra hai giả thuyết với **DA3-Base** cố định, sau đó đo mức cải thiện khi gắn Exposure-Consistency LoRA.
- **H1**: Độ nhạy của chất lượng tái dựng (`F1 @ 5 cm`) theo lựa chọn ảnh tham chiếu lớn hơn ở điều kiện lệch phơi sáng so với điều kiện phơi sáng đồng đều.
- **H2**: Một bộ xếp hạng ảnh tham chiếu chỉ dùng ảnh RGB đầu vào — kết hợp chất lượng phơi sáng trung tâm và độ chồng lấp hình học — cải thiện F1 so với mặc định `saddle_balanced` trên các cảnh giữ lại mà không làm suy giảm ảnh phơi sáng đồng đều.

## 2. Phương pháp đề xuất

### Chọn ảnh tham chiếu bằng Combined

Với mỗi tập $N$ ảnh RGB đầu vào (giới hạn cạnh dài 504 px khi chấm điểm, ~0,5–1,0 giây/cảnh trên CPU):

1. **Nhánh phơi sáng trung tâm (`exposure_bridge`)**:
   - Tính độ hữu dụng phơi sáng $e_i \in [0, 1]$ bằng hai hàm cắt tuyến tính giảm trọng số vùng tối bệt ($Y < 8$) và vùng cháy sáng ($Y > 250$).
   - Áp dụng bão hòa mềm $\tanh(e_i / 0.15)$ để một ảnh sáng nổi trội không áp đảo các ảnh đủ sáng khác, rồi nhân với độ gần trung vị log-độ sáng $b_i = \exp(-|m_i - \mathrm{median}(m)| / 0.75)$ nhằm ưu tiên ảnh làm **cầu nối phơi sáng** giữa các ảnh tối và sáng.
2. **Nhánh chồng lấp hình học bền sáng (`overlap`)**:
   - Chuẩn hóa gamma thích nghi về trung vị độ sáng 110 rồi tăng tương phản cục bộ CLAHE (`clipLimit=3.0`).
   - Trích xuất SIFT (`nfeatures=2000`, `contrastThreshold=0.02`), lọc tỷ lệ `0.80` hai chiều và kiểm tra hình học bằng ma trận cơ bản RANSAC (`3.0 px`, tối thiểu 8 cặp). Điểm cặp dựa trên độ phủ lưới $4 \times 4$ và số điểm hỗ trợ, lấy trung bình qua mọi cặp chứa ảnh $i$.
3. **Kết hợp (`combined`)**:
   - Chuẩn hóa min-max từng nhánh để cân bằng thang đo, sau đó lấy trung bình $s_i = 0.5\,\tilde{e}_i^{\text{bridge}} + 0.5\,\tilde{o}_i$. Đưa ảnh có $s_i$ cao nhất lên đầu danh sách và gọi `ref_view_strategy="first"` của DA3 trên **ảnh RGB gốc**.

### Thích nghi phơi sáng bằng LoRA

Mô hình giáo viên là DA3-Base đóng băng, nhận các ảnh phơi sáng đồng đều. Mô hình học viên dùng cùng DA3-Base với LoRA và nhận ảnh cùng góc nhìn ở các mức phơi sáng khác nhau. Hàm mất mát khuyến khích đầu ra độ sâu và tư thế camera nhất quán. Khi suy luận, Combined chọn ảnh tham chiếu rồi DA3 gắn LoRA tái dựng cảnh.

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

### 4.3. Mở rộng có huấn luyện trên 4 cảnh train → kiểm thử trên 5 cảnh giữ lại (Hướng A & Hướng B)

Hai hướng huấn luyện nhẹ đều được train **chỉ trên 4 cảnh pilot** trên 1 GPU Kaggle T4 (peak VRAM **1,90 GB**, ~10 phút cho Hướng B) và đánh giá trên **5 cảnh giữ lại**:
- **Hướng A (`LearnedReferenceScorer`, ~6K tham số)**: mạng xếp hạng hoán vị-đẳng biến học từ 14 đặc trưng RGB + DINOv2 CLS token (48 tập 4 góc nhìn, listwise KL loss).
- **Hướng B (`Exposure-Consistency LoRA`, `rank=4`, 110.592 tham số = 0,082% DA3-Base, 441 KB)**: chưng cất tự giám sát thầy-trò (không cần nhãn 3D) giữa ảnh `varyexp` và `uniform_mid` trên `qkv`/`proj` của 6 block cuối DINOv2 (160 bước, `res=336`, 20% bước đồng nhất ảnh sạch).

| Điều kiện (`n = 5` held-out) | DA3 mặc định | DA3 + Combined | DA3 + bộ chọn học được | LoRA + mặc định | **LoRA + Combined** | **Δ so với DA3 mặc định** | LoRA + bộ chọn học được |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `default_json` — **F1 @ 5 cm** | 0.3420 | 0.4067 | 0.3111 | 0.3566 | **0.4183** | **`+0.0763`** | 0.3271 |
| `varyexp_mixed` — **F1 @ 5 cm** | 0.3347 | 0.4184 | 0.3178 | 0.3460 | **0.4236** | **`+0.0889`** | 0.3238 |
| `uniform_mid` — **F1 @ 5 cm** | 0.2884 | 0.3321 | 0.3223 | 0.2926 | **0.3387** | **`+0.0503`** | 0.3251 |
| `default_json` — AUC@10° | 0.8639 | 0.8283 | 0.8711 | 0.8668 | 0.8320 | `-0.0319` | **0.8726** |
| `varyexp_mixed` — AUC@10° | 0.8490 | 0.8568 | 0.8272 | 0.8527 | **0.8613** | **`+0.0123`** | 0.8313 |
| `uniform_mid` — AUC@10° | 0.8433 | 0.8580 | 0.8322 | 0.8451 | **0.8615** | **`+0.0182`** | 0.8385 |

- **LoRA + Combined có F1 trung bình cao nhất trong các cấu hình đã thử** trên cả ba điều kiện, hơn DA3 mặc định lần lượt **7,63**, **8,89** và **5,03 điểm phần trăm F1**. So với DA3 + Combined, phần tăng khi thêm LoRA là **1,16**, **0,52** và **0,66 điểm phần trăm F1**. Ở `default_json`, AUC@10° vẫn thấp hơn DA3 mặc định **3,19 điểm phần trăm**.
- **Bộ chọn học được có F1 trung bình thấp hơn Combined** trên cả ba điều kiện giữ lại, dù loss huấn luyện giảm từ `0.6522` xuống `0.0523` trên bốn cảnh huấn luyện.

## 5. Phân tích và kết luận

1. **Xác nhận H1**: Biên độ chênh lệch F1 khi đổi ảnh tham chiếu (`Span F1`) trên điều kiện lệch phơi sáng (`0.1869` trên `default_json`, `0.1686` trên `varyexp_mixed`; trên tập giữ lại là `0.1677` và `0.1833`) lớn hơn rõ rệt so với phơi sáng đồng đều (`0.1107` trên 9 cảnh và `0.0885` trên 5 cảnh giữ lại).
2. **H2 được ủng hộ trên tập giữ lại**. Combined tăng F1 trung bình so với DA3 mặc định **6,47** và **8,37 điểm phần trăm** trên hai điều kiện lệch phơi sáng, và **4,37 điểm phần trăm** trên `uniform_mid`. Bảng kết quả theo cảnh cho thấy mức cải thiện thay đổi theo cảnh và điều kiện chụp.
3. **Phạm vi so sánh**: Cải thiện được kiểm chứng công bằng so với baseline DA3 gốc trong cùng giao thức đo (4 góc nhìn, `DA3-Base`, căn chỉnh Sim(3), F1 điểm–điểm 5 cm). Không so sánh trực tiếp trị số tuyệt đối với Bảng 15 của bài báo RealX3D (39,2% / 63,6%) do khác số góc nhìn và giao thức ICP điểm–bề mặt.
4. **Giới hạn**. Thử nghiệm dùng bốn ảnh mỗi cảnh, với năm cảnh giữ lại để đánh giá. Trong `varyexp_mixed`, mức phơi sáng tăng theo thứ tự góc nhìn, nên hiệu ứng phơi sáng có thể đi cùng hiệu ứng góc nhìn. Cảnh `Sculpture` có F1 thấp trong giao thức đã đo.

## 6. Tài liệu & tái lập

- [Notebook tái lập RealX3D](notebooks/realx3d.ipynb) chạy các bước chuẩn bị, huấn luyện và đánh giá.
- [Kết quả pilot](results/pilot/summary.csv), [kết quả giữ lại](results/heldout/summary.csv), [so sánh các cấu hình huấn luyện](results/train_ab/summary_ab.csv) và [checkpoint LoRA](results/train_ab/da3_lora_r4.pt).
