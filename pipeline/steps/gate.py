"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    dataset_images = set(image_stems)
    reviewed_images = set(reviewed)
    number_of_errors = 0
    images_with_unreviewed_warnings = set()

    for issue in issues:
        # Mọi lỗi bắt buộc đều chặn, kể cả lỗi cấp dataset hoặc ảnh đã duyệt.
        if issue.severity == ERROR:
            number_of_errors += 1
        elif (issue.severity == WARN
              and issue.image in dataset_images
              and issue.image not in reviewed_images):
            images_with_unreviewed_warnings.add(issue.image)

    number_of_images = len(dataset_images)
    number_of_warning_images = len(images_with_unreviewed_warnings)
    warning_ratio = number_of_warning_images / number_of_images if number_of_images else 0.0
    warning_ratio_hold_threshold = cfg["gate"]["warn_ratio_hold"]

    if number_of_errors > 0:
        decision = "Rework"
        reasons = [f"Còn {number_of_errors} lỗi bắt buộc cần xử lý trước khi xuất dataset."]
    elif warning_ratio >= warning_ratio_hold_threshold:
        decision = "Hold"
        reasons = [
            f"Còn {number_of_warning_images}/{number_of_images} ảnh có cảnh báo chưa duyệt "
            f"({warning_ratio:.2%}), đạt hoặc vượt ngưỡng {warning_ratio_hold_threshold:.2%}."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; {number_of_warning_images}/{number_of_images} ảnh "
            f"có cảnh báo chưa duyệt ({warning_ratio:.2%}), "
            f"dưới ngưỡng {warning_ratio_hold_threshold:.2%}."
        ]

    return {
        "decision": decision,
        "n_errors": number_of_errors,
        "n_warn_images": number_of_warning_images,
        "n_images": number_of_images,
        "warn_ratio": round(warning_ratio, 4),
        "reasons": reasons,
    }
