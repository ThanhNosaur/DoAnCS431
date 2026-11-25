# Cải thiện độ bền của Depth Anything 3 khi tái dựng 3D từ ảnh lệch phơi sáng

*Báo cáo ngắn gọn · Đồ án CS431 · 25/11/2026*

## 1. Bài toán và mục tiêu

Khi tái dựng 3D từ nhiều góc nhìn thiếu sáng hoặc lệch phơi sáng, Depth Anything 3 (DA3) chọn một ảnh tham chiếu ngay trong quá trình suy luận (mặc định là chiến lược `saddle_balanced` dựa trên đặc trưng DINOv2). Nếu ảnh tham chiếu quá tối, mất chi tiết hoặc quá khác biệt về phơi sáng so với các góc nhìn còn lại, chất lượng đám mây điểm 3D suy giảm đáng kể.

Đồ án dùng **RealX3D (`data4_varyexp`)** để kiểm tra hai giả thuyết với **DA3-Base** cố định. **Combined** là đóng góp chính. Exposure-Consistency LoRA được đánh giá thêm để đo mức cải thiện khi thích nghi mô hình.
- **H1**: Độ nhạy của chất lượng tái dựng (`F1 @ 5 cm`) theo lựa chọn ảnh tham chiếu lớn hơn ở điều kiện lệch phơi sáng so với điều kiện phơi sáng đồng đều.
- **H2**: Bộ xếp hạng Combined cải thiện F1 trung bình trên các cảnh giữ lại so với chiến lược mặc định `saddle_balanced` và chiến lược benchmark `first`, kể cả trong điều kiện đồng đều.

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

Mô hình giáo viên là DA3-Base đóng băng, nhận các ảnh phơi sáng đồng đều. Mô hình học viên dùng cùng DA3-Base với LoRA và nhận ảnh cùng góc nhìn ở các mức phơi sáng khác nhau. Hàm mất mát khuyến khích đầu ra độ sâu và tư thế camera nhất quán. Phần đánh giá so sánh Combined có và không có LoRA trên cùng các ảnh.

## 3. Thiết lập thí nghiệm

- **Mô hình và đối chứng**. `depth-anything/DA3-BASE` (commit `f4a6c9b`), 4 ảnh mỗi cảnh, độ phân giải 504. `saddle_balanced` là mặc định của API DA3, còn `first` chọn ảnh đầu tiên theo thiết lập benchmark của DA3. Cả hai chạy trên cùng tập ảnh và cùng giao thức đo với Combined. [Tài liệu benchmark DA3](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/main/docs/BENCHMARK.md)
- **Dữ liệu & chia cảnh**: Toàn bộ **9 cảnh** của RealX3D `data4_varyexp` — tách **4 cảnh pilot** (`Ujikintoki`, `BlueHawaii`, `Chocolate`, `Cupcake`) để kiểm tra dữ liệu & chốt tham số, và **5 cảnh giữ lại (held-out)** (`GearWorks`, `Laboratory`, `MilkCookie`, `Popcorn`, `Sculpture`) để đánh giá độc lập.
- **Ba điều kiện chụp trên cùng 4 góc nhìn**:
  - `default_json`: bộ ảnh lệch phơi sáng gốc trong thư mục `train/` của RealX3D.
  - `varyexp_mixed`: ghép 4 mức phơi sáng tăng dần (`train_60`, `train_160`, `train_250`, `train_400`).
  - `uniform_mid`: cùng 4 góc nhìn ở một mức phơi sáng đồng đều (`train_250`).
- **Kiểm soát cách gán phơi sáng**. Trên mỗi cảnh giữ lại, giữ nguyên bốn góc nhìn và luân phiên bốn mức phơi sáng trong bốn lượt, gồm cấu hình `varyexp_mixed`. Mỗi góc nhìn nhận mỗi mức đúng một lần. Trung bình theo bốn lượt trong từng cảnh trước khi so sánh giữa năm cảnh.
- **Đo hình học**. Pose chuẩn lấy từ `sparse/0/images.bin`. Khi đo đám mây điểm, `colmap2world.txt` đưa pose về hệ đơn vị của đám mây chuẩn. Đám mây dự đoán được căn chỉnh Sim(3) bằng ma trận xoay và tâm camera, lấy mẫu voxel 1 cm và đo **F1 điểm–điểm ở ngưỡng 5 cm**. Chỉ số phụ **AUC@10°** dùng sai số góc lớn hơn giữa xoay và hướng tịnh tiến, lấy trung bình hai chiều của mỗi cặp camera để kết quả bất biến với thứ tự đầu vào.

## 4. Kết quả thực nghiệm

Lượt đánh giá trên Kaggle Tesla T4 dùng lại hai checkpoint đã huấn luyện. Bảng chính tính trung bình trên năm cảnh giữ lại. Kết quả của bốn cảnh pilot có trong tệp đối chiếu riêng.

### 4.1. Chọn ảnh tham chiếu trên năm cảnh giữ lại

| Điều kiện | F1 mặc định | F1 `first` | F1 Exposure | F1 Bridge | F1 Overlap | F1 Combined | Δ so với mặc định (điểm %) | Δ so với `first` (điểm %) | F1 oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `default_json` | 0.3420 | 0.3887 | 0.3536 | 0.3687 | 0.3831 | **0.4067** | +6.47 | +1.80 | 0.4160 |
| `varyexp_mixed` | 0.3347 | 0.3606 | 0.3606 | 0.3482 | 0.3811 | **0.4184** | +8.37 | +5.78 | 0.4555 |
| `uniform_mid` | 0.2884 | 0.3198 | 0.3276 | 0.3279 | 0.3100 | **0.3321** | +4.37 | +1.23 | 0.3366 |

Oracle chọn ảnh tham chiếu có F1 cao nhất sau khi chấm cả bốn ảnh bằng đám mây điểm chuẩn. Biên độ F1 trung bình khi đổi ảnh tham chiếu là **0,1677** ở `default_json`, **0,1833** ở `varyexp_mixed` và **0,0885** ở `uniform_mid`. Điều này ủng hộ H1 trong các cấu hình đã đo. F1 trung bình của Combined cao hơn cả hai baseline ở cả ba điều kiện, ủng hộ H2 trên tập giữ lại.

| Điều kiện | AUC@10° mặc định | AUC@10° `first` | AUC@10° Combined | AUC@10° LoRA + Combined |
| --- | ---: | ---: | ---: | ---: |
| `default_json` | 0.8609 | 0.8530 | 0.8297 | 0.8331 |
| `varyexp_mixed` | 0.8526 | 0.8410 | 0.8573 | 0.8615 |
| `uniform_mid` | 0.8470 | 0.8607 | 0.8584 | 0.8615 |

Ở `default_json`, F1 của Combined tăng đồng thời với AUC@10° giảm từ 0,8609 xuống 0,8297 so với DA3 mặc định. Trong 15 lượt trên tập giữ lại, thời gian trung vị chấm điểm tham chiếu là 0,63 giây trên CPU. Thời gian suy luận DA3 trung vị là 1,64 giây với cả mặc định và Combined trên Tesla T4. Bộ nhớ GPU cấp phát đỉnh của lượt Combined là 1.937 MiB.

### 4.2. Luân phiên phơi sáng trên cùng góc nhìn

Mỗi hàng là F1@5 cm trung bình qua bốn cách gán phơi sáng trên cùng bốn góc nhìn. Hàng cuối tính trung bình theo cảnh.

| Cảnh | Mặc định | `first` | Overlap | Combined | LoRA + Combined |
| --- | ---: | ---: | ---: | ---: | ---: |
| GearWorks | 0.5190 | 0.5662 | 0.5458 | 0.6097 | 0.6285 |
| Laboratory | 0.3475 | 0.4040 | 0.3711 | 0.4173 | 0.3749 |
| MilkCookie | 0.5015 | 0.4670 | 0.5307 | 0.5222 | 0.5065 |
| Popcorn | 0.5109 | 0.5213 | 0.5038 | 0.5177 | 0.5280 |
| Sculpture | 0.0890 | 0.0916 | 0.0907 | 0.0965 | 0.0959 |
| **Trung bình** | 0.3936 | 0.4100 | 0.4084 | **0.4327** | 0.4268 |

Combined tăng **3,91 điểm phần trăm F1** so với mặc định và **2,26 điểm** so với `first`, với F1 trung bình theo cảnh cao hơn lần lượt ở **5/5** và **4/5** cảnh. So với Overlap, Combined tăng **2,43 điểm** và thắng **4/5** cảnh. Sau khi luân phiên phơi sáng, LoRA + Combined đạt F1 thấp hơn Combined **0,59 điểm**.

### 4.3. So sánh các cấu hình có huấn luyện

Hai checkpoint được huấn luyện trên bốn cảnh pilot và dùng lại trong lượt đánh giá.

- **Bộ chọn học được** có 4.657 tham số. Mô hình xếp hạng 14 đặc trưng RGB và DINOv2, học từ 48 tập bốn góc nhìn với F1 từng ảnh tham chiếu làm mục tiêu.
- **Exposure-Consistency LoRA** dùng rank 4 với 110.592 tham số. Adapter gắn vào `qkv` và `proj` của sáu block cuối. Lượt huấn luyện dùng 160 lượt teacher–student ở độ phân giải 336, tích lũy gradient qua bốn lượt trước mỗi bước tối ưu và dùng ảnh đồng đều cho cả hai mô hình với xác suất 20%.

| Điều kiện | DA3 mặc định | DA3 + Combined | DA3 + bộ chọn học được | LoRA + mặc định | LoRA + Combined | LoRA + bộ chọn học được |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `default_json` | 0.3420 | 0.4067 | 0.3111 | 0.3566 | **0.4183** | 0.3271 |
| `varyexp_mixed` | 0.3347 | 0.4184 | 0.3178 | 0.3460 | **0.4236** | 0.3238 |
| `uniform_mid` | 0.2884 | 0.3321 | 0.3223 | 0.2926 | **0.3387** | 0.3251 |

Bộ chọn học được có F1 trung bình thấp hơn Combined ở cả ba điều kiện. LoRA tăng thêm **1,16**, **0,52** và **0,66 điểm phần trăm F1** so với Combined trong ba cấu hình ban đầu, thắng **3/5 cảnh** ở từng điều kiện. Khi loại GearWorks trong phân tích độ nhạy, mức tăng ở `varyexp_mixed` và `uniform_mid` chuyển thành **−0,51** và **−0,63 điểm**. Kết quả luân phiên ở mục 4.2 củng cố nhận định rằng lợi ích của LoRA phụ thuộc cảnh và cách gán phơi sáng.

## 5. Kết luận và giới hạn

Combined cải thiện F1 trung bình so với hai baseline của DA3 trên tập giữ lại, kể cả khi phơi sáng được luân phiên trên cùng góc nhìn. Hiệu quả của Combined được đánh giá với một tập bốn góc nhìn mỗi cảnh, trên năm cảnh giữ lại, bằng DA3-Base và một giao thức căn chỉnh Sim(3) cố định. Bốn cách gán phơi sáng là các quan sát lặp trên mỗi cảnh. Kết quả chưa đánh giá độ bền khi thay tập góc nhìn hoặc chuyển sang bộ dữ liệu khác. Trị số tuyệt đối cần được đọc trong giao thức F1 điểm–điểm và số góc nhìn của đồ án.

## 6. Tài liệu và tái lập

- [Notebook RealX3D](notebooks/realx3d.ipynb) mặc định dùng checkpoint đã huấn luyện. Đặt `RETRAIN = True` để huấn luyện lại.
- [Kết quả pilot](results/pilot/summary.csv), [kết quả giữ lại](results/heldout/summary.csv), [luân phiên phơi sáng](results/exposure_rotations/summary.csv) và [so sánh các cấu hình huấn luyện](results/train_ab/summary_ab.csv).
- [Thông tin tái lập](results/evaluation_provenance.json) ghi mô hình, GPU và SHA-256 của mã cùng checkpoint. Các JSON theo cảnh lưu pose dự đoán và pose chuẩn để tính lại AUC.
- [Bài báo Depth Anything 3](https://arxiv.org/abs/2511.10647), [bài báo RealX3D](https://doi.org/10.1007/s11263-026-02963-4) và [bộ dữ liệu RealX3D](https://huggingface.co/datasets/ToferFish/RealX3D).
