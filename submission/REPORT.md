# Báo cáo Day 09 — Đào Bình An, 2A202603264

## 1. Kết luận trước
Pipeline kết luận **Hold**. Đầu vào 224 ảnh, loại 19 ảnh ở intake, giữ và xuất 205 ảnh dưới dạng bản nháp để thử nghiệm, chưa phát hành. Sau khi người duyệt mô phỏng xem 80 ảnh, không còn lỗi bắt buộc nhưng 38/205 ảnh (18,54%) còn cảnh báo chưa duyệt, vượt ngưỡng Hold 10% (nguồn: `reports/08_summary.json`).

## 2. Lỗi và phân việc
Nguồn: `reports/02_error_list_v1.csv`. Bảng ghi số issue / số ảnh khác nhau; lỗi intake có mẫu số 224 ảnh, QC có mẫu số 205 ảnh. `BAD_CLASS_NAME` và `CLASS_RARE` là lỗi/cảnh báo cấp dataset, không tính như ảnh. Tổng v1 có 208 issue, gồm cả 19 issue intake đã bị loại; riêng QC là 36 ERROR và 153 WARN.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| BAD_SIZE / CORRUPT_IMAGE | 3/3; 2/2 (trên 224 ảnh) | Máy, intake | Loại ảnh quá nhỏ/hỏng |
| DUP_IMAGE_EXACT / DUP_IMAGE_NEAR / LEAK_TEST | 8/8; 2/2; 4/4 (trên 224 ảnh) | Máy, intake | Loại ảnh trùng và rò rỉ |
| BAD_CLASS_NAME | 2 issue, 1 data.yaml | Máy | Chuẩn hoá tên lớp theo cấu hình |
| BAD_FORMAT / BAD_CLASS_ID / BOX_ZERO / DUP_BOX | 3/3; 6/6; 4/4; 7/7 | Máy + người kiểm lại | Xoá dòng không dùng được, ưu tiên duyệt ảnh đã xoá dòng |
| BOX_OUT_OF_IMAGE | 8/8 | Máy + người kiểm lại | Cắt về biên ảnh, ghi trước/sau |
| MISSING_LABEL_FILE | 6/6 | Người | Máy không tự bịa nhãn |
| BOX_TINY / BOX_HUGE / EMPTY_LABEL | 6/4; 3/3; 12/12 | Người | Xem vật nhỏ, box quá lớn, ảnh nền hay thiếu nhãn |
| POSSIBLE_MISSING | 53/52 | Người | Kiểm vật có thể bị bỏ sót |
| POSSIBLE_WRONG_CLASS | 18/18 | Người | Kiểm lớp theo nội dung ảnh |
| POSSIBLE_LOOSE_BOX | 28/24 | Người | Kiểm độ khít của box |
| POSSIBLE_FALSE_POS | 29/27 | Người | Kiểm box thừa hoặc model bỏ sót |
| CLASS_RARE | 4 issue cấp dataset | Người | Xem phân bố lớp; thống kê v1 còn chứa ID sai |

`03_fixes.csv` có 35 bản ghi: 1 chuẩn hoá tên lớp, 20 xoá dòng, 8 cắt box, 6 chuyển người gán (6 bản ghi này chưa sửa nhãn). Hàng đợi gồm 125/205 ảnh, xếp theo tổng trọng số lỗi và confidence; ảnh đã bị máy xoá dòng/cắt box được cộng ưu tiên. `img_0020` đứng đầu với 11,524 điểm do FIXED_DROP_LINE, POSSIBLE_MISSING và POSSIBLE_WRONG_CLASS; các ảnh thiếu nhãn như `img_0031` có NEEDS_LABEL = 10 điểm. Ngân sách 80 ảnh xử lý 80/125 ảnh trong hàng đợi: 74 ảnh có 94 cảnh báo ngữ nghĩa ở v2 (51 MISSING, 18 WRONG_CLASS, 13 FALSE_POS, 12 LOOSE_BOX), còn 6 ảnh cần gán nhãn. Đây là cảnh báo được đưa cho người, không khẳng định cả 94 đều là lỗi thật.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 4 | NEAR: 1.000 / 0.500 → 1.000 / 0.667 | Bắt 4/6 thay vì 3/6 ảnh gần trùng trên calib, không có FP ở cả hai mức; chọn mức nhỏ nhất đạt cải thiện này để giảm rủi ro loại nhầm ảnh. EXACT giữ P/R = 1.000/1.000. |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS: 0.556 / 0.833 → 0.625 / 0.833; MISSING: 0.500 / 1.000 → 0.571 / 1.000 | Giảm báo động giả mà vẫn giữ recall cho nhầm lớp (5/6) và thiếu box (8/8). Đánh đổi: LOOSE_BOX giảm từ P/R 0.286/0.400 xuống 0.200/0.200 (2/5 → 1/5); FALSE_POS không đổi 0.312/1.000 vì dùng fp_conf riêng. |

Calibration có thể đánh lừa: pHash = 16 đạt P/R = 1.000/0.833 trên 6 ca NEAR của calib, nhưng mở ảnh raw cho thấy `img_0011` (tennis) bị coi trùng `img_0008` (trượt tuyết), và `img_0177` (lướt sóng) bị coi trùng `img_0113` (người ngồi bàn). Số ảnh bị check duplicates gắn cờ tăng từ 14/224 ở ngưỡng 4 (8 EXACT, 2 NEAR, 4 LEAK_TEST) lên 26/224 ở ngưỡng 16 (8 EXACT, 7 NEAR, 11 LEAK_TEST); đây chưa bao gồm lỗi ảnh của check images. Vì vậy không chọn ngưỡng chỉ theo recall trên calib. Ảnh đối chiếu cục bộ: `work/viz/calibration_duplicate_pairs.jpg` (không commit work/). Ngưỡng 4 vẫn bỏ sót một số biến đổi thật như cặp `img_0061`/`img_0186` (khoảng cách 10), cần ghi nhận giới hạn này. Bộ calib chỉ có 39 ảnh; số liệu ở đây không chứng minh recall trên raw hay việc hàng đợi sẽ vừa ngân sách 80 ảnh.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Đã chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: còn 6 lỗi bắt buộc do thiếu file nhãn, gate trả **Rework**, mã thoát **20**. `work/rep_nb/08_summary.json` ghi `exported: null`; không có `work/exp_nb/clean_v1/manifest.json`, chứng minh lỗi bắt buộc thực sự chặn xuất dataset. Lần chạy kiểm chứng dùng thư mục báo cáo/xuất riêng, không ghi đè kết quả Hold trong `submission/`.

Hai điểm mù có bằng chứng: (1) ảnh trùng biến đổi có thể lọt pHash = 4: `img_0061`/`img_0186` có cùng cảnh người ngồi ghế nhưng khoảng cách 10, không bị gắn cờ NEAR ở ngưỡng đã chọn; (2) checker bỏ sót box lỏng: trên calib, conf = 0,6 chỉ bắt 1/5 ca LOOSE_BOX (recall 0,200), bỏ sót 4/5; tăng conf để giảm báo giả không giải quyết chất lượng box. Ngoài ra recall WRONG_CLASS trên calib là 5/6, cho thấy model thứ hai vẫn có thể đồng ý với nhãn sai hoặc không đủ chắc để cảnh báo.

Đã xem 10 ảnh raw bằng `viz_labels.py`. Ba quan sát trực quan: `img_0031` có xe bus/ô tô nhưng không có box vì thiếu file nhãn; `img_0020` có xe bus được bao bằng box màu truck (cần người phân lớp lại); `img_0001` có người mặc quân phục ở giữa chưa được bao đầy đủ bởi box riêng. Ảnh vẽ nằm trong `work/viz/`, không commit; có thể tái tạo bằng script có sẵn. Quan sát trực quan cần được người học kiểm lại, không dùng làm đáp án cố định trong code.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy** phần train Colab; hiện hoàn thành quy trình lõi trước khi làm thí nghiệm GPU tùy chọn. Chưa có số mAP và chưa thể kết luận clean tốt hơn raw. Khi train, cần giữ cùng model, val/test và siêu tham số, chạy raw/clean với seed 0 và 1 rồi so chênh lệch với nhiễu giữa seed.

## 6. Quyết định và ghi chú AI
Giữ **Hold**, không phát hành. Với 205 ảnh và ngưỡng 10%, cần giảm số ảnh cảnh báo chưa duyệt từ 38 xuống tối đa 20 (ít nhất 18 ảnh), đồng thời giữ ERROR = 0. Không tăng ngân sách 80 hoặc đổi quy tắc để ép Release: cần quy trình duyệt bổ sung được dự án cho phép rồi chạy QC lại. Kiểm tra lại các cảnh báo và box lỏng trước khi dùng bản nháp cho thí nghiệm; không nâng conf chỉ để hàng đợi nhỏ đi.

Ghi chú AI:
- Prompt chính: yêu cầu AI lần lượt hoàn thiện module theo docstring và test của đề; dùng tên hàm rõ nghĩa, giữ các tên giao diện bắt buộc run/fix/decide.
- Cách kiểm: chạy test từng module, toàn bộ 79 test đạt; chạy calibration hai ngưỡng, kiểm ảnh raw bằng mắt và ca ngân sách 0 xác nhận Rework/chặn xuất. Người học cần đọc và giải thích được code trước khi nộp.
- Một thiếu sót trong hướng dẫn AI ban đầu: chưa tính đến lỗi phân cách đường dẫn Windows của bộ kiểm tra gốc, khiến lệnh kiểm tra báo 2 lỗi giả tại calibrate.py nguyên bản. Đã đối chiếu tính toàn vẹn file và thêm `scripts/check_submission_windows.py` để chuẩn hoá đường dẫn tương đối khi chạy bộ kiểm tra gốc, giữ nguyên mọi phép kiểm và file đề. Chưa ghi nhận lỗi triển khai của 4 module qua 79 test; điều đó không chứng minh code không còn lỗi.
