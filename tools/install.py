import os
import shutil
import sys
from pathlib import Path

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("Usage: python install.py <version> <os> <arch>")
    print("Example: python install.py v1.0.0 win x86_64")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]


def get_dotnet_platform_tag():
    """自动检测当前平台并返回对应的dotnet平台标签"""
    if os_name == "win" and arch == "x86_64":
        platform_tag = "win-x64"
    elif os_name == "win" and arch == "aarch64":
        platform_tag = "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        platform_tag = "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        platform_tag = "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        platform_tag = "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        platform_tag = "linux-arm64"
    else:
        print("Unsupported OS or architecture.")
        print("available parameters:")
        print("version: e.g., v1.0.0")
        print("os: [win, macos, linux, android]")
        print("arch: [aarch64, x86_64]")
        sys.exit(1)

    return platform_tag


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        print('请先下载 MaaFramework 到 "deps"。')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )



def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    interface["version"] = version

    # 仅当内嵌便携 Python 确实存在时才改写 child_exec（相对安装根目录解析）；
    # 否则保持源文件原值 "python"，回退系统 Python，与 check_embedded_python 的警告承诺一致
    if (
        os_name == "win"
        and "agent" in interface
        and (install_path / "python" / "python.exe").exists()
    ):
        interface["agent"]["child_exec"] = "python/python.exe"

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )

    logo = working_dir / "logo.ico"
    if logo.exists():
        shutil.copy2(logo, install_path / "logo.ico")
        os.makedirs(install_path / "Assets", exist_ok=True)
        shutil.copy2(logo, install_path / "Assets" / "logo.ico")


def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )


def rename_executable():
    if os_name == "android":
        return

    if os_name == "win":
        src = install_path / "MFAAvalonia.exe"
        dst = install_path / "MaaLZ.exe"
    else:
        src = install_path / "MFAAvalonia"
        dst = install_path / "MaaLZ"

    # 先校验 dll 存在性，再执行改名，避免半改名状态
    # （不使用 assert：python -O 下会被剥离）
    if not (install_path / "MFAAvalonia.dll").exists():
        print(f"Error: MFAAvalonia.dll not found in {install_path}, cannot rename the executable.")
        print("错误：安装目录中缺少 MFAAvalonia.dll，无法完成可执行文件改名。")
        sys.exit(1)

    if not src.exists():
        print(f"Skip renaming: {src} not found.")
        return

    try:
        src.replace(dst)
    except OSError as e:
        print(f"Error: failed to rename '{src}' to '{dst}': {e}")
        print(f"错误：将 '{src}' 改名为 '{dst}' 失败：{e}")
        sys.exit(1)

    print(f"Renamed {src.name} to {dst.name}")


def check_embedded_python():
    if os_name != "win":
        return

    python_exe = install_path / "python" / "python.exe"
    maa_pkg = install_path / "python" / "Lib" / "site-packages" / "maa" / "__init__.py"

    if python_exe.exists() and maa_pkg.exists():
        print(f"Embedded Python found: {python_exe}")
        return

    # 缺失时仅警告不退出：本地开发允许缺失（回退系统 Python）；
    # CI 由 Bundle embedded Python step 保证，该 step 失败会直接中断构建
    missing = [p for p in (python_exe, maa_pkg) if not p.exists()]
    print("=" * 72)
    print("WARNING: Embedded Python is missing in the install directory!")
    for p in missing:
        print(f"  Missing: {p}")
    print("  The release package will fall back to the user's system Python.")
    print("-" * 72)
    print("警告：安装目录中缺少内嵌便携 Python！")
    for p in missing:
        print(f"  缺失：{p}")
    print("  发行包将依赖用户系统的 Python 运行。")
    print("=" * 72)


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    rename_executable()
    check_embedded_python()

    print(f"Install to {install_path} successfully.")
