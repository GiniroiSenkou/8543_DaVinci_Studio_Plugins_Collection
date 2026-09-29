#!/usr/bin/env python3
"""
fetch_tools.py - downloads the build tools into _tools/ (not committed):
  lucide/icons    Lucide icons (ISC)            git sparse clone
  si/icons        Simple Icons brand marks (CC0) git sparse clone
  fonts/          Roboto static TTFs (Apache-2.0)
  resvg[.exe]     resvg SVG renderer (MPL-2.0 / Apache-2.0)
Needs git and Python 3 with Pillow.
"""
import io, os, platform, shutil, subprocess, sys, tarfile, urllib.request, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "_tools"))
RESVG = "0.45.1"
ROBOTO = "https://github.com/googlefonts/roboto-3-classic/releases/download/v3.011/Roboto_v3.011.zip"


def git_sparse(url, dest, paths):
    if os.path.isdir(dest):
        return
    subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", url, dest], check=True)
    subprocess.run(["git", "-C", dest, "sparse-checkout", "set", "--no-cone"] + paths, check=True)


def main():
    os.makedirs(ROOT, exist_ok=True)
    git_sparse("https://github.com/lucide-icons/lucide.git", os.path.join(ROOT, "lucide"), ["/icons/", "/LICENSE"])
    git_sparse("https://github.com/simple-icons/simple-icons.git", os.path.join(ROOT, "si"),
               ["/icons/instagram.svg", "/icons/tiktok.svg", "/icons/youtube.svg", "/icons/youtubeshorts.svg",
                "/icons/facebook.svg", "/LICENSE.md"])
    fonts = os.path.join(ROOT, "fonts")
    if not os.path.isdir(fonts):
        os.makedirs(fonts)
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(ROBOTO).read()))
        for n in z.namelist():
            base = os.path.basename(n)
            if "/static/" in n and base in ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf",
                                            "Roboto-Black.ttf") and "chromeos" in n:
                open(os.path.join(fonts, base), "wb").write(z.read(n))
    win = platform.system() == "Windows"
    exe = os.path.join(ROOT, "resvg.exe" if win else "resvg")
    if not os.path.exists(exe):
        base = f"https://github.com/linebender/resvg/releases/download/v{RESVG}/"
        if win:
            z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(base + "resvg-win64.zip").read()))
            open(exe, "wb").write(z.read("resvg.exe"))
        else:
            name = "resvg-macos-x86_64.zip" if platform.system() == "Darwin" else "resvg-linux-x86_64.tar.gz"
            data = urllib.request.urlopen(base + name).read()
            if name.endswith(".zip"):
                open(exe, "wb").write(zipfile.ZipFile(io.BytesIO(data)).read("resvg"))
            else:
                tarfile.open(fileobj=io.BytesIO(data)).extract("resvg", ROOT)
            os.chmod(exe, 0o755)
    print("tools ready in", ROOT)


if __name__ == "__main__":
    main()
