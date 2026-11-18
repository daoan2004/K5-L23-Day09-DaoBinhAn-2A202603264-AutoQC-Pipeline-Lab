"""Chạy bộ kiểm tra gốc với đường dẫn tương đối thống nhất trên Windows.

    python scripts/check_submission_windows.py --no-train

check_submission.py so tên file tương đối với danh sách bảo vệ dùng dấu '/'.
Windows trả dấu '\\', làm calibrate.py nguyên bản bị quét nhầm như code học viên.
Launcher này chỉ chuẩn hoá đường dẫn tương đối trong tiến trình kiểm tra;
không sửa file gốc, danh sách bảo vệ, hoặc bỏ qua bất kỳ phép kiểm nào.
"""
import os
from pathlib import Path, PurePosixPath
import runpy


def check_submission_with_portable_paths():
    original_relative_to = Path.relative_to

    def relative_path_with_forward_slashes(path, *other_paths, **options):
        relative_path = original_relative_to(path, *other_paths, **options)
        return PurePosixPath(relative_path.as_posix())

    checker_path = Path(__file__).resolve().with_name("check_submission.py")
    try:
        if os.name == "nt":
            Path.relative_to = relative_path_with_forward_slashes
        runpy.run_path(str(checker_path), run_name="__main__")
    finally:
        Path.relative_to = original_relative_to


if __name__ == "__main__":
    check_submission_with_portable_paths()
