"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    thresholds = cfg["label_format"]
    issues = []

    for label_file in ds.label_files():
        stem = label_file.stem
        size = ds.image_size(stem)
        previous_boxes = []

        for line_number, text in ds.read_label_lines(stem) or []:
            # Hàm đọc giữ số dòng gốc, kể cả khi có dòng trống ở giữa.
            try:
                class_id, cx, cy, w, h = parse_yolo_line(text)
            except (ValueError, OverflowError) as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    str(exc), line=line_number))
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"ID lớp {class_id} không hợp lệ", line=line_number))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "Chiều rộng và chiều cao phải lớn hơn 0", line=line_number))
                continue

            # Mức tràn lớn nhất trong bốn mép; box nằm trong ảnh có mức tràn 0.
            overflow = max(0.0, w / 2 - cx, h / 2 - cy,
                           cx + w / 2 - 1, cy + h / 2 - 1)
            if overflow > thresholds["overflow_tol"]:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"Box tràn ảnh {overflow:.6f}", line=line_number,
                                    extra={"overflow": overflow}))

            box = (cx, cy, w, h)
            if any(old_class == class_id and
                   iou_xywh(box, old_box) > thresholds["dup_box_iou"]
                   for old_class, old_box in previous_boxes):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                    "Box trùng với một dòng trước cùng lớp", line=line_number))
            previous_boxes.append((class_id, box))

            if size is not None:
                width_px, height_px = size
                short_side_px = min(w * width_px, h * height_px)
                if short_side_px < thresholds["min_box_px"]:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        f"Cạnh ngắn chỉ {short_side_px:.2f} px", line=line_number))

            if w * h > thresholds["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    f"Box chiếm {w * h:.2%} diện tích ảnh", line=line_number))

    return issues
