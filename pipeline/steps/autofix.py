"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, ROOT, parse_yolo_line


def fix(ds, issues, cfg):
    if ds.root.resolve() == (ROOT / "data" / "raw").resolve():
        raise ValueError("Chỉ sửa bản sao dataset, không sửa data/raw.")

    changes = []
    errors = [issue for issue in issues if issue.severity == ERROR]
    removable_image_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    dropped_line_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    removed_images = set()

    # Xoá ảnh trước để không sửa nhãn của ảnh sẽ bị loại.
    for issue in errors:
        if not (issue.code.startswith("DUP_IMAGE_") or issue.code in removable_image_codes):
            continue
        if issue.image in removed_images:
            continue
        removed_images.add(issue.image)
        image_path = ds.image_path(issue.image)
        label_path = ds.label_path(issue.image)
        removed_paths = []
        if image_path is not None:
            image_path.unlink()
            removed_paths.append(str(image_path))
        if label_path.exists():
            label_path.unlink()
            removed_paths.append(str(label_path))
        if removed_paths:
            changes.append({"image": issue.image, "line": None, "action": "remove_image",
                            "before": "; ".join(removed_paths), "after": "đã xoá ảnh và nhãn"})

    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        original_text = ds.yaml_path.read_text(encoding="utf-8") if ds.yaml_path.exists() else ""
        configuration = yaml.safe_load(original_text) or {}
        expected_names = dict(enumerate(cfg["classes"]))
        if configuration.get("names") != expected_names:
            previous_names = configuration.get("names")
            configuration["names"] = expected_names
            ds.yaml_path.write_text(yaml.safe_dump(configuration, allow_unicode=True), encoding="utf-8")
            changes.append({"image": "data.yaml", "line": None, "action": "rename_classes",
                            "before": str(previous_names), "after": str(expected_names)})

    line_errors_by_image = defaultdict(lambda: defaultdict(set))
    missing_label_images = set()
    for issue in errors:
        if issue.image in removed_images:
            continue
        if issue.code == "MISSING_LABEL_FILE":
            if issue.image not in missing_label_images and not ds.label_path(issue.image).exists():
                missing_label_images.add(issue.image)
                changes.append({"image": issue.image, "line": None, "action": "needs_label",
                                "before": "(không có file)", "after": "chuyển người gán"})
        elif issue.line is not None and (issue.code in dropped_line_codes or issue.code == "BOX_OUT_OF_IMAGE"):
            line_errors_by_image[issue.image][issue.line].add(issue.code)

    for image_stem in sorted(line_errors_by_image):
        label_path = ds.label_path(image_stem)
        if not label_path.exists():
            continue
        original_lines = label_path.read_text(encoding="utf-8").splitlines()
        rewritten_lines = []
        file_changed = False
        for line_number, original_line in enumerate(original_lines, start=1):
            error_codes = line_errors_by_image[image_stem].get(line_number, set())
            if not error_codes:
                rewritten_lines.append(original_line)
                continue

            replacement_line = ""
            action = "drop_line"
            # Xoá dòng được ưu tiên hơn cắt box khi cùng dòng có nhiều lỗi.
            if not error_codes.intersection(dropped_line_codes):
                try:
                    class_id, center_x, center_y, width, height = parse_yolo_line(original_line)
                except (ValueError, OverflowError):
                    pass  # Dòng không đọc được phải bị loại, ghi log bên dưới.
                else:
                    left_edge = max(0.0, center_x - width / 2)
                    top_edge = max(0.0, center_y - height / 2)
                    right_edge = min(1.0, center_x + width / 2)
                    bottom_edge = min(1.0, center_y + height / 2)
                    clipped_width = right_edge - left_edge
                    clipped_height = bottom_edge - top_edge
                    if clipped_width > 0 and clipped_height > 0:
                        # Box đã nằm trong ảnh thì không cần sửa hoặc ghi log lần nữa.
                        if (left_edge == center_x - width / 2 and top_edge == center_y - height / 2
                                and right_edge == center_x + width / 2 and bottom_edge == center_y + height / 2):
                            rewritten_lines.append(original_line)
                            continue
                        clipped_values = ((left_edge + right_edge) / 2, (top_edge + bottom_edge) / 2,
                                          clipped_width, clipped_height)
                        replacement_line = f"{class_id} " + " ".join(format(value, ".15g") for value in clipped_values)
                        action = "clip_box"

            if replacement_line:
                rewritten_lines.append(replacement_line)
            file_changed = True
            changes.append({"image": image_stem, "line": line_number, "action": action,
                            "before": original_line, "after": replacement_line})

        # Ghi một lần sau khi xử lý toàn bộ số dòng GỐC của file.
        if file_changed:
            label_path.write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")

    return changes
