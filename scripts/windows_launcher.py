"""Interactive Windows entry point; subprocess arguments preserve Unicode paths."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.version_info < (3, 10):
        print("Python 3.10+ is required.")
        return 1
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    mode = sys.argv[1] if len(sys.argv) > 1 else "xiaohongshu"
    platform = os.environ.get("INS2ANKI_PLATFORM", mode) if mode == "xiaohongshu" else mode
    instagram = platform in {"instagram", "probe"}
    tool = root / "scripts" / ("browser_sync.py" if instagram else "favorites_sync.py")
    prefix = [sys.executable, str(tool)]
    session_args = [] if instagram else ["--platform", platform]
    if os.environ.get("INS2ANKI_BROWSER"):
        session_args += ["--browser", os.environ["INS2ANKI_BROWSER"]]
    default = "instagram-saved" if instagram else ("douyin-saved/收藏" if platform == "douyin" else "xhs-saved/收藏")
    output = os.environ.get("INS2ANKI_OUTPUT", str(root / default))
    if mode == "probe":
        return subprocess.call(prefix + ["probe", "--output-root", output])
    print("检查浏览器会话……", flush=True)
    if subprocess.call(prefix + ["check"] + session_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        print("即将打开专用浏览器。请登录并打开收藏页，再回到这里。", flush=True)
        code = subprocess.call(prefix + ["launch"] + session_args)
        if code:
            return code
        input("登录完成后按回车继续……")
    sync_args = ["--all-collections", "--output-root", output] if instagram else ["--output-dir", output]
    if not instagram and os.environ.get("INS2ANKI_FOLDER"):
        sync_args += ["--folder", os.environ["INS2ANKI_FOLDER"]]
    sync_args += ["--jobs", os.environ.get("INS2ANKI_JOBS", "6" if instagram else "4")]
    code = subprocess.call(prefix + ["sync"] + session_args + sync_args)
    print(f"文件位置：{output}", flush=True)
    if code:
        print(f"同步未全部完成（退出码 {code}），请查看上面的错误；再次运行会重试。")
    return code


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, ValueError) as exc:
        print(f"无法启动：{exc}")
        result = 1
    except KeyboardInterrupt:
        result = 130
    sys.exit(result)
