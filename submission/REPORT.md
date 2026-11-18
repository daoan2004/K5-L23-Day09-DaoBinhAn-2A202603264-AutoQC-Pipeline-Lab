# Báo cáo Day 09 — Đào Bình An, 2A202603264

## 1. Kết quả chạy pipeline

Kết quả cuối cùng là **Hold**. Trong 224 ảnh đầu vào, pipeline loại 19 ảnh và giữ lại 205 ảnh. Sau lượt duyệt mô phỏng 80 ảnh, không còn lỗi bắt buộc nhưng vẫn có 38/205 ảnh chưa duyệt còn cảnh báo, tương đương 18,54%, cao hơn ngưỡng 10%. Vì vậy, bộ dữ liệu xuất ra chỉ là bản nháp để thử nghiệm, chưa đủ điều kiện phát hành. Số liệu lấy từ `reports/08_summary.json`.

## 2. Các lỗi tìm được và cách xử lý

Bảng dưới tổng hợp từ `reports/02_error_list_v1.csv`. Mỗi số được ghi theo dạng **số lỗi hoặc cảnh báo / số ảnh có lỗi hoặc cảnh báo đó**. Một ảnh có thể xuất hiện ở nhiều nhóm. Lỗi ở bước nhận dữ liệu được tính trên 224 ảnh; các lỗi QC sau đó tính trên 205 ảnh được giữ lại.

| Mã lỗi | Số lượng | Cách xử lý |
|---|---|---|
| BAD_SIZE / CORRUPT_IMAGE | 3/3; 2/2 | Máy loại ảnh quá nhỏ hoặc không đọc được |
| DUP_IMAGE_EXACT / DUP_IMAGE_NEAR / LEAK_TEST | 8/8; 2/2; 4/4 | Máy loại ảnh trùng và ảnh trùng với tập test/val |
| BAD_CLASS_NAME | 2 lỗi trong `data.yaml` | Máy sửa tên lớp theo cấu hình |
| BAD_FORMAT / BAD_CLASS_ID / BOX_ZERO / DUP_BOX | 3/3; 6/6; 4/4; 7/7 | Máy xoá dòng lỗi, đưa ảnh vào hàng đợi để người kiểm lại |
| BOX_OUT_OF_IMAGE | 8/8 | Máy cắt box về trong ảnh và ghi log |
| MISSING_LABEL_FILE | 6/6 | Chuyển người gán nhãn, không tạo file rỗng |
| BOX_TINY / BOX_HUGE / EMPTY_LABEL | 6/4; 3/3; 12/12 | Người xem lại kích thước box và xác nhận ảnh có thực sự là ảnh nền không |
| POSSIBLE_MISSING | 53/52 | Người kiểm tra vật bị bỏ sót |
| POSSIBLE_WRONG_CLASS | 18/18 | Người xác nhận lại lớp |
| POSSIBLE_LOOSE_BOX | 28/24 | Người chỉnh lại box nếu cần |
| POSSIBLE_FALSE_POS | 29/27 | Người kiểm tra box thừa hoặc trường hợp model bỏ sót vật |
| CLASS_RARE | 4 cảnh báo cấp dataset | Kiểm tra phân bố lớp; thống kê ban đầu còn chứa ID lớp sai |

Báo cáo v1 có 208 lỗi và cảnh báo, bao gồm 19 lỗi ở bước nhận dữ liệu. Riêng phần QC có 36 ERROR và 153 WARN. File `03_fixes.csv` ghi 35 thao tác: sửa tên lớp 1 lần, xoá 20 dòng, cắt 8 box và chuyển 6 ảnh thiếu nhãn cho người gán. Sáu thao tác chuyển người gán chưa làm thay đổi nhãn.

Hàng đợi có 125 ảnh nhưng ngân sách chỉ đủ duyệt 80 ảnh. Thứ tự ưu tiên dựa trên loại lỗi, trọng số và độ tin cậy của model; ảnh đã bị máy xoá dòng hoặc cắt box cũng được cộng điểm. Ví dụ, `img_0020` đứng đầu với 11,524 điểm do vừa bị xoá dòng vừa có cảnh báo thiếu vật và nhầm lớp. Ảnh thiếu nhãn như `img_0031` được 10 điểm để ưu tiên gán nhãn.

Trong 80 ảnh được duyệt mô phỏng, 6 ảnh cần gán nhãn và 74 ảnh có tổng cộng 94 cảnh báo ngữ nghĩa ở vòng QC thứ hai: 51 thiếu vật, 18 nhầm lớp, 13 nghi thừa box và 12 box lỏng. Các con số này là cảnh báo cần xem lại, không có nghĩa cả 94 trường hợp đều sai.

## 3. Chọn hai ngưỡng calibration

Kết quả sweep được lưu trong `calibration/calibration_report.md`. Hai ngưỡng được chọn như sau; P/R là precision/recall trên tập calib.

| Tham số | Ban đầu → Đã chọn | P/R trước → sau | Lý do |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → **4** | NEAR: 1,000/0,500 → 1,000/0,667 | Bắt được 4/6 thay vì 3/6 ảnh gần trùng, chưa có báo nhầm trên calib. Chọn mức nhỏ nhất có cải thiện để hạn chế loại nhầm ảnh tốt. |
| `second_opinion.conf` | 0,25 → **0,6** | WRONG_CLASS: 0,556/0,833 → 0,625/0,833; MISSING: 0,500/1,000 → 0,571/1,000 | Giảm báo động giả, vẫn bắt được 5/6 ca nhầm lớp và 8/8 ca thiếu box. |

Việc tăng conf cũng có mặt hạn chế: số ca box lỏng bắt được giảm từ 2/5 xuống 1/5, P/R giảm từ 0,286/0,400 xuống 0,200/0,200. Cảnh báo FALSE_POS không đổi, P/R = 0,312/1,000, vì dùng ngưỡng `fp_conf` riêng. Với ảnh trùng từng byte, P/R vẫn là 1,000/1,000 ở cả hai mức pHash 2 và 4.

Một điểm đáng chú ý là ngưỡng tốt trên calib chưa chắc dùng tốt trên raw. Ở pHash = 16, recall ảnh gần trùng đạt 5/6 trên calib. Tuy nhiên, khi mở ảnh raw để đối chiếu, `img_0011` chụp tennis lại bị coi là trùng `img_0008` chụp trượt tuyết. Tương tự, ảnh lướt sóng `img_0177` bị ghép với ảnh người ngồi bàn `img_0113`. Tổng số ảnh bị đánh dấu trùng hoặc rò rỉ tăng từ 14/224 ở ngưỡng 4 lên 26/224 ở ngưỡng 16. Vì vậy, em chọn ngưỡng 4 thay vì chỉ lấy mức có recall cao nhất. Tập calib chỉ có 39 ảnh nên chưa thể đại diện hết lỗi trên raw.

## 4. Kiểm tra gate và các lỗi còn bỏ sót

Để kiểm tra gate có thực sự chặn hay không, em chạy:

```bash
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```

Khi không có người duyệt, 6 ảnh thiếu file nhãn vẫn còn. Pipeline trả **Rework**, mã thoát **20**, và không xuất dataset. File tóm tắt ghi `exported: null`, đồng thời không có `work/exp_nb/clean_v1/manifest.json`. Báo cáo của lần thử này được lưu riêng để giữ kết quả chạy chính.

Pipeline vẫn có ít nhất hai điểm hạn chế:

- **Bỏ sót ảnh trùng đã biến đổi:** `img_0061` và `img_0186` cùng cảnh người ngồi ghế nhưng khoảng cách pHash là 10, nên không bị bắt ở ngưỡng 4. Tăng ngưỡng có thể bắt thêm cặp này nhưng cũng tăng nguy cơ ghép nhầm như ở mục 3.
- **Bỏ sót box lỏng:** với conf = 0,6, checker chỉ bắt 1/5 ca trên calib, bỏ sót 4/5. Vì thế, hết lỗi cú pháp không có nghĩa là box đã chính xác.

Khi xem 10 ảnh raw đã vẽ nhãn bằng `viz_labels.py`, có ba trường hợp dễ nhận thấy: `img_0031` có bus và ô tô nhưng chưa có box do thiếu file nhãn; `img_0020` có bus được gán box lớp truck; `img_0001` có người mặc quân phục ở giữa chưa được bao đầy đủ bằng box riêng. Các ảnh vẽ nằm trong `work/viz/` và có thể tạo lại bằng script. Những trường hợp này cho thấy vẫn cần người xem nội dung ảnh, ngoài việc chạy kiểm tra tự động.

## 5. So sánh train raw và clean

**Chưa chạy** phần train trên Colab. Hiện em hoàn thành phần lõi trước, chưa có số mAP để kết luận clean tốt hơn raw. Nếu làm tiếp, em sẽ train hai bộ với cùng model, siêu tham số, tập val/test và hai seed 0, 1; sau đó so mức chênh lệch với độ dao động giữa các seed.

## 6. Quyết định cuối và việc sử dụng AI

Em giữ quyết định **Hold**. Với 205 ảnh, số ảnh còn cảnh báo chưa duyệt phải giảm từ 38 xuống tối đa 20 mới xuống dưới 10%, đồng thời không được còn ERROR. Như vậy, cần xử lý thêm ít nhất 18 ảnh đang có cảnh báo. Việc duyệt bổ sung cần theo quy trình được phép rồi chạy QC lại; không đổi ngân sách 80 hoặc nâng ngưỡng conf chỉ để đạt Release.

Em có dùng AI hỗ trợ viết bốn module và giải thích code:

- **Yêu cầu đưa cho AI:** làm lần lượt theo mô tả đầu file và test của đề, đặt tên hàm rõ nghĩa, giữ các tên giao diện có sẵn như `run`, `fix`, `decide`.
- **Cách kiểm tra:** chạy test riêng từng module, sau đó toàn bộ 79 test; chạy calibration, xem ảnh raw và thử ngân sách duyệt bằng 0. Việc duyệt 80 ảnh trong pipeline là mô phỏng bằng script của đề.
- **Một thiếu sót của hướng dẫn AI:** ban đầu chưa tính đến lỗi dấu phân cách đường dẫn Windows trong bộ kiểm tra, khiến `calibrate.py` nguyên bản bị báo nhầm hai lỗi. Đã kiểm tra file gốc và thêm `scripts/check_submission_windows.py` để chạy lại với đường dẫn thống nhất. Các phép kiểm và file đề vẫn giữ nguyên. Kết quả kiểm tra phần lõi là 0 lỗi; còn một cảnh báo vì chưa train.
