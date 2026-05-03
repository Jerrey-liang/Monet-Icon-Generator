import os
import sys
import shutil
import json
import tkinter as tk
import re
import xml.etree.ElementTree as ET
from PIL import Image
import zipfile
import urllib.request
import urllib.error
import subprocess
import time
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# === 路径设置 ===
COLORS_JSON = "colors.json"
COLOR_TONES = (0, 10, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000)

CLIP_PNG_PATH = os.path.join("assets", "clip.png")   # size=320
CLIP_ROUND_PNG_PATH = os.path.join("assets", "clip-round.png")   # size=350 圆形留边多一点好看；这样内部图标就不用重采样了
SUB_XML_PATH = os.path.join("assets", "manifest.xml")
CALENDAR_XML_PATH = os.path.join("assets", "com.android.calendar", "manifest.xml")
CALENDAR_DUO_XML_PATH = os.path.join("assets", "com.android.calendar", "manifest-duo.xml")
NAME_MAPPING = os.path.join("assets", "name_mapping_by_MrBocchi.json")

DRAWABLE_ZIP_PATH = os.path.join("lawnicons_assets", "drawable.zip")
APPFILTER_XML = os.path.join("lawnicons_assets", "appfilter_plain.xml")
LAWNICONS_VERSION_JSON = os.path.join("lawnicons_assets", "version.json")
LAWNICONS_RELEASE_API = "https://api.github.com/repos/LawnchairLauncher/lawnicons/releases/latest"
LAWNICONS_RENDERER_CS = os.path.join("assets", "render_lawnicons_svgs.cs")
LAWNICONS_MIN_RESOURCE_COUNT = 1000

TEMP_DIR = "temp"
DRAWABLE_DIR = os.path.join("temp", "drawable")
PREPROCESS_DIR = os.path.join("temp", "_Preprocess")
PREPROCESS_NIGHT_DIR = os.path.join("temp", "_Preprocess-night")
THEME_FALLBACK_XML = os.path.join("temp", "theme_fallback.xml")
GENERAL_XML_PATH = os.path.join("temp", "transform_config.xml")

OUTPUT_ICONS = "icons"
FANCY_ICONS_DIR = "fancy_icons"
RES_DIR = os.path.join("res", "drawable-xxhdpi")

PACK_MAGISK = os.path.join("assets", "pack-magisk")
PACK_MAGISK_TEMP = os.path.join("temp", "pack-magisk")
PACK_MAGISK_OUTPUT = "HyperOS Monet Launcher.zip"
PACK_MTZ = os.path.join("assets", "pack-mtz")
PACK_MTZ_TEMP = os.path.join("temp", "pack-mtz")
PACK_MTZ_OUTPUT = "HyperOS Monet Launcher.mtz"

def CLEAR_LAST_LINE(n=1):
    for _ in range(n):
        sys.stdout.write("\033[F\033[K")
    sys.stdout.flush()

# === 修复 colors.json 尾部多余逗号 ===
def fix_color():
    with open(COLORS_JSON, 'r', encoding='utf-8') as f:
        content = f.read()

    # 从结尾向前找 '}' 前是否有多余逗号（逗号后面紧跟换行和 }）
    fixed_content = re.sub(r',\s*(\n\s*})', r'\1', content, count=1)

    # 只在内容变动时写入
    if fixed_content != content:
        with open(COLORS_JSON, 'w', encoding='utf-8') as f:
            f.write(fixed_content)

# === 查询并验证颜色配置文件 ===
def check_colors():
    def is_color(val):
        return isinstance(val, str) and val.startswith("#") and len(val) in (7, 9)

    while True:
        try:
            with open(COLORS_JSON, 'r', encoding="utf-8") as f:
                colors = json.load(f)

            required_keys = ["accent1_100", "accent1_200", "accent1_700"]

            # 遍历检查
            for key in required_keys:
                if not is_color(colors.get(key)):
                    raise ValueError("格式错误")

        except Exception:
            print("⚠ 配置信息格式错误，读取失败！请阅读说明文档重新填写！")
            print("保存并关闭文件以继续...")
            os.system(f'notepad "{COLORS_JSON}"')
            CLEAR_LAST_LINE(2)
            fix_color()
            continue
        else:
            return True

def normalize_adb_color(raw_value):
    text = (raw_value or "").strip()
    match = re.search(r"(?:#|0x)([0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b", text)
    if not match:
        raise ValueError(f"无法解析颜色值：{text}")

    hex_value = match.group(1).upper()
    if len(hex_value) == 8:
        hex_value = hex_value[2:]
    return f"#{hex_value}"

def load_existing_colors():
    try:
        fix_color()
        with open(COLORS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def lookup_adb_color(resource_name):
    try:
        result = subprocess.run(
            [
                "adb",
                "shell",
                "cmd",
                "overlay",
                "lookup",
                "android",
                f"android:color/{resource_name}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 adb，请先安装 Android SDK Platform Tools 并将 adb 加入 PATH。") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ADB 读取超时，请确认手机已连接并允许 USB 调试。") from exc

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        raise RuntimeError(output or f"adb 执行失败，退出码：{result.returncode}")

    return normalize_adb_color(output)

def fetch_colors_from_adb():
    colors = load_existing_colors()

    for tone in COLOR_TONES:
        resource_name = f"system_accent1_{tone}"
        colors[f"accent1_{tone}"] = lookup_adb_color(resource_name)
        print(f"{resource_name} = {colors[f'accent1_{tone}']}")

    with open(COLORS_JSON, "w", encoding="utf-8") as f:
        json.dump(colors, f, ensure_ascii=False, indent=3)
        f.write("\n")

# === 色值设置（ARGB格式）===
def prepare_color():
    with open(COLORS_JSON, 'r') as f:
        colors = json.load(f)

    accent1_100 = colors["accent1_100"]
    accent1_200 = colors["accent1_200"]
    accent1_700 = colors["accent1_700"]

    return accent1_100, accent1_200, accent1_700

# === 功能2 预览颜色配置 ===
def preview_color():
    # 读取 colors.json
    with open(COLORS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 过滤并按数字排序 accent1_xxx 项
    accent_colors = {
        k: v for k, v in data.items() if k.startswith("accent1_")
    }
    # 排序（按数字后缀排序）
    accent_colors = dict(sorted(accent_colors.items(), key=lambda item: int(item[0].split("_")[1])))

    # 矩形尺寸设置
    rect_width = 200
    rect_height = 50
    padding = 2

    # 计算窗口高度
    canvas_height = len(accent_colors) * (rect_height + padding)
    canvas_width = rect_width

    # 创建窗口和画布
    root = tk.Tk()
    root.title("预览")
    root.resizable(False, False)

    # 使窗口首次显示时置顶
    root.lift()
    root.attributes("-topmost", True)
    root.after(0, lambda: root.attributes("-topmost", False))

    canvas = tk.Canvas(root, width=canvas_width, height=canvas_height, bg="white")
    canvas.pack()

    # 绘制颜色块
    y = 0
    for name, hex_color in accent_colors.items():
        canvas.create_rectangle(
            0, y, rect_width, y + rect_height,
            fill=hex_color, outline=""
        )
        canvas.create_text(
            rect_width // 2, y + rect_height // 2,
            text="system_" + name,
            fill="white" if int(hex_color.lstrip("#")[0:2], 16) < 128 else "black"
        )
        y += rect_height + padding

    # 启动窗口循环
    root.mainloop()

# === 功能3 预处理图片 以下三个函数 ===
def generate_icon(foreground_color, background_color, base_img: Image.Image, clip_alpha: Image.Image) -> Image.Image:
    # 创建背景层
    bg = Image.new("RGBA", clip_alpha.size, background_color)

    # 创建前景图（215x215）并填充颜色 + alpha
    fg_raw = Image.new("RGBA", base_img.size, foreground_color)
    fg_raw.putalpha(base_img.getchannel("A"))

    # 创建前景层画布（320x320）并将小图居中粘贴进去
    fg = Image.new("RGBA", clip_alpha.size, (0, 0, 0, 0))
    offset = (
        (clip_alpha.width - base_img.width) // 2,
        (clip_alpha.height - base_img.height) // 2
    )
    fg.paste(fg_raw, offset)

    # 合成图层
    composed = Image.alpha_composite(bg, fg)

    # 应用clip.png的alpha通道
    composed.putalpha(clip_alpha.getchannel("A"))

    return composed

def process_file(file_name, input_dir, accent1_100, accent1_200, accent1_700, clip_png):
    input_path = os.path.join(input_dir, file_name)
    os.makedirs(PREPROCESS_DIR, exist_ok=True)
    os.makedirs(PREPROCESS_NIGHT_DIR, exist_ok=True)

    # 读取图片
    base = Image.open(input_path).convert("RGBA")

    # 加载clip.png的alpha通道
    clip = Image.open(clip_png).convert("RGBA")

    # 生成浅色图标
    icon0 = generate_icon(accent1_700, accent1_100, base, clip)
    icon0.save(os.path.join(PREPROCESS_DIR, file_name))

    # 生成深色图标
    icon1 = generate_icon(accent1_200, accent1_700, base, clip)
    icon1.save(os.path.join(PREPROCESS_NIGHT_DIR, file_name))

def create_theme_fallback_xml():
    print(f"正在生成 {THEME_FALLBACK_XML}...")

    # 读取映射 JSON
    with open(NAME_MAPPING, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    filtered_mapping = {k: v for k, v in mapping_data.items() if not k.startswith("_comment-")}

    tree = ET.parse(APPFILTER_XML)
    root = tree.getroot()

    output_lines = [
        "<?xml version='1.0' encoding='utf-8' standalone='yes'?>",
        "<MIUI_Theme_Values>"
    ]

    # 处理 appfilter 中的包名
    written_packages = set()
    for item in root.findall("item"):
        component = item.attrib.get("component", "")
        drawable = item.attrib.get("drawable", "")
        if not component or not drawable:
            continue
        if not (component.startswith("ComponentInfo{") and component.endswith("}")):
            continue
        comp_str = component[len("ComponentInfo{"):-1]
        if "/" not in comp_str:
            continue
        pkg_name, cls_name = comp_str.split("/", 1)
        if "*" in cls_name:
            continue
        if pkg_name in written_packages:
            continue
        drawable_png = f"{drawable}.png"
        output_lines.append(f'<drawable name="{pkg_name}.png">{drawable_png}</drawable>')
        written_packages.add(pkg_name)

    # 处理 NAME_MAPPING 里的包名
    for key, drawable in filtered_mapping.items():
        if '/' in key:
            pkg_name = key.split('/', 1)[0]
        else:
            pkg_name = key
        drawable_png = f"{drawable}.png"
        output_lines.append(f'<drawable name="{pkg_name}.png">{drawable_png}</drawable>')

    output_lines.append("</MIUI_Theme_Values>")

    with open(THEME_FALLBACK_XML, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

# === 进度条 ===
def print_progress_bar(current, total, bar_length=40):
    percent = current / total
    filled_length = int(bar_length * percent)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write(f"\r进度: |{bar}| {current}/{total} ({percent*100:.1f}%)")
    sys.stdout.flush()

# === Lawnicons 自动同步 ===
def parse_version_tuple(tag):
    text = (tag or "").strip()
    if text.startswith("v"):
        text = text[1:]
    parts = []
    for part in re.split(r"[.\-+]", text):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])

def read_lawnicons_local_tag():
    try:
        with open(LAWNICONS_VERSION_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tag_name")
    except Exception:
        return None

def write_lawnicons_local_version(release, png_count, appfilter_count):
    os.makedirs(os.path.dirname(LAWNICONS_VERSION_JSON), exist_ok=True)
    data = {
        "tag_name": release.get("tag_name"),
        "name": release.get("name"),
        "html_url": release.get("html_url"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "png_count": png_count,
        "appfilter_item_count": appfilter_count
    }
    with open(LAWNICONS_VERSION_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def github_json(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "HyperOS-Monet-Icon-Generator"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def latest_stable_lawnicons_release():
    release = github_json(LAWNICONS_RELEASE_API)
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError("GitHub latest release 不是稳定版。")
    return release

def find_lawnicons_apk_asset(release):
    assets = release.get("assets", [])
    apks = [
        asset for asset in assets
        if asset.get("name", "").lower().endswith(".apk")
    ]
    if not apks:
        raise RuntimeError("最新稳定版没有找到 APK 附件。")
    apks.sort(key=lambda asset: (
        0 if "lawnicons" in asset.get("name", "").lower() else 1,
        asset.get("name", "")
    ))
    return apks[0]

def download_file(url, dst, label):
    req = urllib.request.Request(url, headers={"User-Agent": "HyperOS-Monet-Icon-Generator"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        last_print = 0
        with open(dst, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last_print >= 0.2:
                    if total:
                        print(f"\r{label} ({done / total * 100:.1f}%)...", end="", flush=True)
                    else:
                        print(f"\r{label} ({done // 1024} KB)...", end="", flush=True)
                    last_print = now
    print()

def safe_rmtree(path):
    if os.path.isdir(path):
        shutil.rmtree(path)

def safe_remove(path):
    if os.path.isfile(path):
        os.remove(path)

def missing_files(paths):
    return [path for path in paths if not os.path.isfile(path)]

def exit_missing_files(paths, hint="请重新完整解压项目。"):
    missing = missing_files(paths)
    if not missing:
        return

    clear()
    print("错误：文件检测不完整，缺少以下文件：")
    for path in missing:
        print(f" - {path}")
    print(hint)
    sys.exit(1)

def clear_lawnicons_generated_cache():
    safe_rmtree(DRAWABLE_DIR)
    safe_rmtree(PREPROCESS_DIR)
    safe_rmtree(PREPROCESS_NIGHT_DIR)
    safe_remove(THEME_FALLBACK_XML)
    safe_remove(GENERAL_XML_PATH)

def lawnicons_resource_problems():
    problems = []

    if not os.path.isfile(APPFILTER_XML):
        problems.append(f"缺少 {APPFILTER_XML}")
    else:
        try:
            appfilter_root = ET.parse(APPFILTER_XML).getroot()
            item_count = len(appfilter_root.findall("item"))
            if item_count < LAWNICONS_MIN_RESOURCE_COUNT:
                problems.append(f"{APPFILTER_XML} 条目数量异常：{item_count}")
        except Exception as exc:
            problems.append(f"{APPFILTER_XML} 无法读取：{exc}")

    if not os.path.isfile(DRAWABLE_ZIP_PATH):
        problems.append(f"缺少 {DRAWABLE_ZIP_PATH}")
    else:
        try:
            with zipfile.ZipFile(DRAWABLE_ZIP_PATH, "r") as zf:
                png_count = sum(
                    1
                    for info in zf.infolist()
                    if info.filename.lower().endswith(".png")
                )
                if png_count < LAWNICONS_MIN_RESOURCE_COUNT:
                    problems.append(f"{DRAWABLE_ZIP_PATH} 图标数量异常：{png_count}")
        except Exception as exc:
            problems.append(f"{DRAWABLE_ZIP_PATH} 无法读取：{exc}")

    return problems

def ensure_lawnicons_resources():
    problems = lawnicons_resource_problems()
    if not problems:
        return
    if os.environ.get("MONET_SKIP_LAWNICONS_UPDATE") == "1":
        raise RuntimeError(
            "Lawnicons 自动下载已被 MONET_SKIP_LAWNICONS_UPDATE=1 关闭："
            + "；".join(problems)
        )

    print("检测到 Lawnicons 本地资源缺失或损坏，将自动重新下载：")
    for problem in problems:
        print(f" - {problem}")
    release = latest_stable_lawnicons_release()
    update_lawnicons_resources(release)

    remaining_problems = lawnicons_resource_problems()
    if remaining_problems:
        raise RuntimeError("自动下载后资源仍不可用：" + "；".join(remaining_problems))

def u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)

def u32(data, offset):
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )

def read_utf8_len(data, offset):
    first = data[offset]
    offset += 1
    if first & 0x80:
        return ((first & 0x7f) << 8) | data[offset], offset + 1
    return first, offset

def read_utf16_len(data, offset):
    first = u16(data, offset)
    offset += 2
    if first & 0x8000:
        return ((first & 0x7fff) << 16) | u16(data, offset), offset + 2
    return first, offset

def parse_android_string_pool(data, offset):
    header_size = u16(data, offset + 2)
    string_count = u32(data, offset + 8)
    flags = u32(data, offset + 16)
    strings_start = u32(data, offset + 20)
    utf8 = bool(flags & 0x100)
    result = []
    for idx in range(string_count):
        str_offset = u32(data, offset + header_size + idx * 4)
        pos = offset + strings_start + str_offset
        if utf8:
            _, pos = read_utf8_len(data, pos)
            byte_len, pos = read_utf8_len(data, pos)
            result.append(data[pos:pos + byte_len].decode("utf-8", "replace"))
        else:
            char_len, pos = read_utf16_len(data, pos)
            result.append(data[pos:pos + char_len * 2].decode("utf-16le", "replace"))
    return result

def pool_string(strings, index):
    if index == 0xffffffff or index >= len(strings):
        return None
    return strings[index]

def parse_resource_table_values(arsc_data):
    entries = {}
    global_strings = []
    pos = u16(arsc_data, 2)
    while pos < len(arsc_data):
        chunk_type = u16(arsc_data, pos)
        header_size = u16(arsc_data, pos + 2)
        chunk_size = u32(arsc_data, pos + 4)
        if chunk_size <= 0:
            raise RuntimeError("resources.arsc 块大小异常。")

        if chunk_type == 0x0001:
            global_strings = parse_android_string_pool(arsc_data, pos)
        elif chunk_type == 0x0200:
            package_id = u32(arsc_data, pos + 8)
            type_strings = parse_android_string_pool(arsc_data, pos + u32(arsc_data, pos + 268))
            key_strings = parse_android_string_pool(arsc_data, pos + u32(arsc_data, pos + 276))
            sub = pos + header_size
            package_end = pos + chunk_size
            while sub < package_end:
                sub_type = u16(arsc_data, sub)
                sub_header = u16(arsc_data, sub + 2)
                sub_size = u32(arsc_data, sub + 4)
                if sub_size <= 0:
                    raise RuntimeError("resources.arsc 子块大小异常。")
                if sub_type == 0x0201:
                    type_id = arsc_data[sub + 8]
                    type_name = type_strings[type_id - 1] if 0 < type_id <= len(type_strings) else str(type_id)
                    entry_count = u32(arsc_data, sub + 12)
                    entries_start = u32(arsc_data, sub + 16)
                    for entry_index in range(entry_count):
                        entry_offset = u32(arsc_data, sub + sub_header + entry_index * 4)
                        if entry_offset == 0xffffffff:
                            continue
                        entry_pos = sub + entries_start + entry_offset
                        entry_size = u16(arsc_data, entry_pos)
                        flags = u16(arsc_data, entry_pos + 2)
                        key_index = u32(arsc_data, entry_pos + 4)
                        if flags & 0x0001 or key_index >= len(key_strings):
                            continue
                        value_pos = entry_pos + entry_size
                        data_type = arsc_data[value_pos + 3]
                        data_value = u32(arsc_data, value_pos + 4)
                        string_value = None
                        if data_type == 0x03 and data_value < len(global_strings):
                            string_value = global_strings[data_value]
                        res_id = (package_id << 24) | (type_id << 16) | entry_index
                        entries[(type_name, key_strings[key_index])] = {
                            "id": res_id,
                            "type": data_type,
                            "data": data_value,
                            "value": string_value
                        }
                sub += sub_size
        pos += chunk_size
    return entries

def typed_xml_value(strings, data, attr_pos):
    raw_idx = u32(data, attr_pos + 8)
    raw = pool_string(strings, raw_idx)
    if raw is not None:
        return raw

    data_type = data[attr_pos + 15]
    data_value = u32(data, attr_pos + 16)

    if data_type == 0x03:
        return pool_string(strings, data_value) or ""
    if data_type == 0x12:
        return "true" if data_value else "false"
    if data_type == 0x10:
        return str(data_value)
    if data_type == 0x11:
        return hex(data_value)
    if data_type == 0x01:
        return f"@0x{data_value:08x}"
    if 0x1c <= data_type <= 0x1f:
        return f"#{data_value:08x}"
    return str(data_value)

def binary_xml_to_element(xml_data):
    strings = []
    pos = u16(xml_data, 2)
    while pos < len(xml_data):
        chunk_type = u16(xml_data, pos)
        chunk_size = u32(xml_data, pos + 4)
        if chunk_type == 0x0001:
            strings = parse_android_string_pool(xml_data, pos)
            break
        pos += chunk_size
    if not strings:
        raise RuntimeError("二进制 XML 缺少字符串池。")

    root = None
    stack = []
    pos = u16(xml_data, 2)
    while pos < len(xml_data):
        chunk_type = u16(xml_data, pos)
        header_size = u16(xml_data, pos + 2)
        chunk_size = u32(xml_data, pos + 4)
        if chunk_size <= 0:
            raise RuntimeError("二进制 XML 块大小异常。")

        if chunk_type == 0x0102:
            name = pool_string(strings, u32(xml_data, pos + 20))
            if not name:
                raise RuntimeError("二进制 XML 元素名为空。")
            element = ET.Element(name)
            attr_start = u16(xml_data, pos + 24)
            attr_size = u16(xml_data, pos + 26)
            attr_count = u16(xml_data, pos + 28)
            attr_base = pos + header_size + attr_start
            for idx in range(attr_count):
                attr_pos = attr_base + idx * attr_size
                attr_name = pool_string(strings, u32(xml_data, attr_pos + 4))
                if attr_name:
                    element.set(attr_name, typed_xml_value(strings, xml_data, attr_pos))
            if stack:
                stack[-1].append(element)
            else:
                root = element
            stack.append(element)
        elif chunk_type == 0x0103 and stack:
            stack.pop()
        pos += chunk_size

    if root is None:
        raise RuntimeError("二进制 XML 没有根节点。")
    return root

def write_xml_element(element, path):
    tree = ET.ElementTree(element)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)

def build_appfilter_from_apk(apk_path, output_path):
    with zipfile.ZipFile(apk_path, "r") as apk:
        entries = parse_resource_table_values(apk.read("resources.arsc"))
        appfilter = entries.get(("xml", "appfilter"))
        if not appfilter or not appfilter.get("value"):
            raise RuntimeError("APK 中未找到 xml/appfilter。")
        xml_path = appfilter["value"]
        root = binary_xml_to_element(apk.read(xml_path))

    item_count = len(root.findall("item"))
    if item_count < 1000:
        raise RuntimeError(f"appfilter 条目数量异常：{item_count}")
    write_xml_element(root, output_path)
    ET.parse(output_path)
    return item_count

def extract_svgs_from_source_zip(source_zip, svg_dir):
    safe_rmtree(svg_dir)
    os.makedirs(svg_dir, exist_ok=True)
    count = 0
    with zipfile.ZipFile(source_zip, "r") as zf:
        for info in zf.infolist():
            normalized = info.filename.replace("\\", "/")
            if info.is_dir() or "/svgs/" not in normalized or not normalized.lower().endswith(".svg"):
                continue
            out_path = os.path.join(svg_dir, os.path.basename(normalized))
            with zf.open(info) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    if count < 1000:
        raise RuntimeError(f"源码包中的 SVG 数量异常：{count}")
    return count

def ps_quote(path):
    return "'" + os.path.abspath(path).replace("'", "''") + "'"

def render_svgs_to_drawable_zip(svg_dir, png_dir, zip_path):
    if not os.path.isfile(LAWNICONS_RENDERER_CS):
        raise RuntimeError(f"缺少 SVG 渲染器：{LAWNICONS_RENDERER_CS}")
    safe_rmtree(png_dir)
    os.makedirs(png_dir, exist_ok=True)
    script = (
        "Add-Type -Path {renderer} -ReferencedAssemblies "
        "@('PresentationCore','PresentationFramework','WindowsBase','System.Xaml',"
        "'System.IO.Compression','System.IO.Compression.FileSystem','System.Xml',"
        "'System.Xml.Linq','System.Core'); "
        "[RenderLawniconsSvgs]::Run({svg_dir},{png_dir},{zip_path})"
    ).format(
        renderer=ps_quote(LAWNICONS_RENDERER_CS),
        svg_dir=ps_quote(svg_dir),
        png_dir=ps_quote(png_dir),
        zip_path=ps_quote(zip_path)
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True
    )

def validate_lawnicons_resources(appfilter_path, drawable_zip_path, svg_dir):
    appfilter_root = ET.parse(appfilter_path).getroot()
    appfilter_drawables = {
        item.get("drawable")
        for item in appfilter_root.findall("item")
        if item.get("drawable")
    }
    svg_names = {
        os.path.splitext(name)[0]
        for name in os.listdir(svg_dir)
        if name.lower().endswith(".svg")
    }

    with zipfile.ZipFile(drawable_zip_path, "r") as zf:
        infos = zf.infolist()
        zip_names = set()
        for info in infos:
            name = info.filename.replace("\\", "/")
            if not name.startswith("drawable/"):
                raise RuntimeError("drawable.zip 顶层结构错误。")
            if not name.lower().endswith(".png"):
                continue
            if info.file_size <= 0:
                raise RuntimeError(f"drawable.zip 存在空 PNG：{name}")
            zip_names.add(os.path.splitext(os.path.basename(name))[0])
            with zf.open(info) as f:
                try:
                    img = Image.open(f)
                    img.verify()
                except Exception as exc:
                    raise RuntimeError(f"PNG 无法识别：{name} ({exc})")

    missing = sorted(appfilter_drawables - zip_names)
    if missing:
        raise RuntimeError("appfilter 中存在未生成的图标：" + ", ".join(missing[:10]))
    if not {"wechat", "coolapk", "themed_icon_calendar_31"}.issubset(zip_names):
        raise RuntimeError("关键样例图标缺失。")
    if len(svg_names) != len(zip_names):
        raise RuntimeError(f"SVG 与 PNG 数量不一致：{len(svg_names)} / {len(zip_names)}")

    return len(zip_names), len(appfilter_root.findall("item"))

def backup_lawnicons_assets(suffix):
    backup_root = os.path.join("lawnicons_assets", "backup", datetime.now().strftime("%Y%m%d-%H%M%S") + suffix)
    os.makedirs(backup_root, exist_ok=True)
    for path in [APPFILTER_XML, DRAWABLE_ZIP_PATH, LAWNICONS_VERSION_JSON]:
        if os.path.isfile(path):
            shutil.copy2(path, os.path.join(backup_root, os.path.basename(path)))
    return backup_root

def update_lawnicons_resources(release):
    tag = release.get("tag_name") or "unknown"
    apk_asset = find_lawnicons_apk_asset(release)
    work_dir = os.path.join(TEMP_DIR, "_lawnicons_auto_update", re.sub(r"[^A-Za-z0-9_.-]", "_", tag))
    safe_rmtree(work_dir)
    os.makedirs(work_dir, exist_ok=True)

    apk_path = os.path.join(work_dir, apk_asset["name"])
    source_zip = os.path.join(work_dir, "source.zip")
    svg_dir = os.path.join(work_dir, "svgs")
    png_dir = os.path.join(work_dir, "drawable")
    new_appfilter = os.path.join(work_dir, "appfilter_plain.xml")
    new_drawable_zip = os.path.join(work_dir, "drawable.zip")

    print(f"正在同步 Lawnicons {tag} 稳定版资源...")
    download_file(apk_asset["browser_download_url"], apk_path, "下载 Lawnicons APK")
    download_file(release["zipball_url"], source_zip, "下载 Lawnicons 源码")

    print("正在解析 appfilter...")
    appfilter_count = build_appfilter_from_apk(apk_path, new_appfilter)

    print("正在提取并渲染 SVG 图标...")
    extract_svgs_from_source_zip(source_zip, svg_dir)
    render_svgs_to_drawable_zip(svg_dir, png_dir, new_drawable_zip)

    print("正在校验资源对应关系...")
    png_count, appfilter_count = validate_lawnicons_resources(new_appfilter, new_drawable_zip, svg_dir)

    backup_dir = backup_lawnicons_assets("-auto-lawnicons")
    shutil.copy2(new_appfilter, APPFILTER_XML)
    shutil.copy2(new_drawable_zip, DRAWABLE_ZIP_PATH)
    write_lawnicons_local_version(release, png_count, appfilter_count)
    clear_lawnicons_generated_cache()
    safe_rmtree(work_dir)

    print(f"Lawnicons 已更新到 {tag}，旧资源已备份至 {backup_dir}")

def maybe_update_lawnicons_resources():
    if os.environ.get("MONET_SKIP_LAWNICONS_UPDATE") == "1":
        return
    try:
        release = latest_stable_lawnicons_release()
        latest_tag = release.get("tag_name")
        local_tag = read_lawnicons_local_tag()
        if local_tag and parse_version_tuple(local_tag) >= parse_version_tuple(latest_tag):
            return
        print(f"检测到 Lawnicons 稳定版更新：{local_tag or '未知版本'} -> {latest_tag}")
        update_lawnicons_resources(release)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Lawnicons 自动更新检查失败，已继续使用本地资源：{exc}")
        time.sleep(1.5)
    except Exception as exc:
        print(f"Lawnicons 自动更新失败，已继续使用本地资源：{exc}")
        time.sleep(2)

# === 功能4 打包导出 ===
def icon_package(switch_function, light_mode):
    if switch_function == "y":

        tree = ET.parse(APPFILTER_XML)
        root = tree.getroot()

        # 收集 appfilter 里的包名
        package_names = set()
        valid_items = []
        for item in root.findall('item'):
            component = item.get('component')
            drawable = item.get('drawable')
            if not component or not drawable:
                continue
            match = re.match(r'ComponentInfo\{(.+)\}', component)
            if not match:
                continue
            full_path = match.group(1)
            if '*' in full_path:
                continue
            parts = full_path.split('/')
            if len(parts) < 2:
                continue
            package_name = parts[0]
            package_names.add(package_name)
            valid_items.append((full_path, drawable))

        # 读取映射 JSON（直接用 NAME_MAPPING 常量路径）
        with open(NAME_MAPPING, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)

        # 去掉 _comment-* 键
        filtered_mapping = {
            k: v for k, v in mapping_data.items() if not k.startswith("_comment-")
        }

        # 计算 total：唯一包名数量 + 映射内的键数量 - 日历
        total = len(package_names) + len(filtered_mapping) - 1
        current = 0

        with zipfile.ZipFile(OUTPUT_ICONS, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 初始化时直接跳过日历包
            written_packages = {"com.android.calendar"}

            # 先处理 appfilter 里的
            for full_path, drawable in valid_items:
                parts = full_path.split('/')
                package_name = parts[0]

                if package_name in written_packages:
                    continue

                folder = os.path.join(FANCY_ICONS_DIR, package_name)

                src_light = os.path.join(PREPROCESS_DIR, f"{drawable}.png")
                src_dark = os.path.join(PREPROCESS_NIGHT_DIR, f"{drawable}.png")
                if not (os.path.exists(src_light) and os.path.exists(src_dark) and os.path.exists(SUB_XML_PATH)):
                    continue

                zipf.write(src_light, os.path.join(folder, "iconBg_0.png"))
                zipf.write(src_dark, os.path.join(folder, "iconBg_1.png"))
                zipf.write(SUB_XML_PATH, os.path.join(folder, "manifest.xml"))

                written_packages.add(package_name)
                current += 1
                print_progress_bar(current, total)

            # 再处理映射 JSON 里的
            for key, drawable in filtered_mapping.items():
                if '/' in key:  # 活动名（全路径）
                    folder = os.path.join(FANCY_ICONS_DIR, key)
                else:  # 包名
                    folder = os.path.join(FANCY_ICONS_DIR, key)

                src_light = os.path.join(PREPROCESS_DIR, f"{drawable}.png")
                src_dark = os.path.join(PREPROCESS_NIGHT_DIR, f"{drawable}.png")
                if not (os.path.exists(src_light) and os.path.exists(src_dark) and os.path.exists(SUB_XML_PATH)):
                    continue

                zipf.write(src_light, os.path.join(folder, "iconBg_0.png"))
                zipf.write(src_dark, os.path.join(folder, "iconBg_1.png"))
                zipf.write(SUB_XML_PATH, os.path.join(folder, "manifest.xml"))

                current += 1
                print_progress_bar(current, total)

            sys.stdout.flush()
            sys.stdout.write("\n")

            # 1. 白天模式日历图标
            for i in range(1, 32):
                src = os.path.join(PREPROCESS_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar_0/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 2. 夜间模式日历图标
            for i in range(1, 32):
                src = os.path.join(PREPROCESS_NIGHT_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar_1/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 3. manifest-duo.xml
            zipf.write(CALENDAR_DUO_XML_PATH, "fancy_icons/com.android.calendar/manifest.xml")

            # 加入 transform_config.xml
            zipf.write(GENERAL_XML_PATH, "transform_config.xml")

    else:  # switch_function == "n"

        input_dir = PREPROCESS_DIR if light_mode == "y" else PREPROCESS_NIGHT_DIR

        # 计算总量 = input_dir 内所有 png 数量
        total = len([f for f in os.listdir(input_dir) if f.lower().endswith(".png")])
        current = 0

        with zipfile.ZipFile(OUTPUT_ICONS, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 直接复制所有 png
            for filename in os.listdir(input_dir):
                if not filename.lower().endswith(".png"):
                    continue
                src_file = os.path.join(input_dir, filename)
                if not os.path.isfile(src_file):
                    continue
                zipf.write(src_file, os.path.join(RES_DIR, filename))
                current += 1
                print_progress_bar(current, total)

            sys.stdout.flush()
            sys.stdout.write("\n")

            # 1. 普通日历图标
            for i in range(1, 32):
                src = os.path.join(DRAWABLE_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 2. manifest.xml
            zipf.write(CALENDAR_XML_PATH, "fancy_icons/com.android.calendar/manifest.xml")

            # 加入 theme_fallback.xml 和 transform_config.xml
            zipf.write(THEME_FALLBACK_XML, "theme_fallback.xml")
            zipf.write(GENERAL_XML_PATH, "transform_config.xml")

# === 清屏 ===
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def drawable_cache_is_valid(zip_infos):
    if not os.path.isdir(DRAWABLE_DIR):
        return False

    expected_pngs = {
        os.path.basename(info.filename.replace("\\", "/"))
        for info in zip_infos
        if info.filename.lower().endswith(".png")
    }
    actual_pngs = {
        name for name in os.listdir(DRAWABLE_DIR)
        if name.lower().endswith(".png")
    }

    if actual_pngs != expected_pngs:
        return False

    for name in actual_pngs:
        path = os.path.join(DRAWABLE_DIR, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False

    return True

def extract_drawable_cache():
    with zipfile.ZipFile(DRAWABLE_ZIP_PATH, 'r') as zipf:
        file_list = zipf.infolist()

        if drawable_cache_is_valid(file_list):
            return

        if os.path.exists(DRAWABLE_DIR):
            shutil.rmtree(DRAWABLE_DIR)
        os.makedirs(DRAWABLE_DIR, exist_ok=True)

        total_files = len(file_list)
        for idx, member in enumerate(file_list, start=1):
            zipf.extract(member, path=TEMP_DIR)
            percent = (idx / total_files) * 100
            print(f"\r资源文件解压中 ({percent:.1f}%)...", end="", flush=True)

        if not drawable_cache_is_valid(file_list):
            print()
            print("错误：资源文件解压不完整，请删除 temp/drawable 后重试。")
            sys.exit(1)
        print()

# === 主程序 ===

def main():
    exit_missing_files([CLIP_PNG_PATH, SUB_XML_PATH])

    try:
        ensure_lawnicons_resources()
    except (urllib.error.URLError, TimeoutError) as exc:
        clear()
        print(f"错误：Lawnicons 资源文件缺失，自动下载失败：{exc}")
        print("请检查网络后重新运行脚本，或重新完整解压项目。")
        sys.exit(1)
    except Exception as exc:
        clear()
        print(f"错误：Lawnicons 资源文件缺失或损坏，自动修复失败：{exc}")
        print("请检查网络后重新运行脚本，或重新完整解压项目。")
        sys.exit(1)

    maybe_update_lawnicons_resources()

    exit_missing_files(
        [DRAWABLE_ZIP_PATH, APPFILTER_XML],
        "请检查网络后重新运行脚本，或重新完整解压项目。"
    )

    if not os.path.exists(DRAWABLE_DIR) or not any(os.scandir(DRAWABLE_DIR)):
        clear()
        extract_drawable_cache()
    else:
        with zipfile.ZipFile(DRAWABLE_ZIP_PATH, 'r') as zipf:
            if not drawable_cache_is_valid(zipf.infolist()):
                clear()
                print("检测到图标缓存不完整，正在重新解压资源文件...")
                extract_drawable_cache()

    while True:
        clear()
        print("╔═══════════════════════════════════╗")
        print("║     HyperOS桌面莫奈图标生成器     ║")
        print("║         by 酷安@Mr_Bocchi         ║")
        print("╟───────────────────────────────────╢")
        print("║ 【1】获取颜色配置                 ║")
        print("║ 【2】预览颜色配置                 ║")
        print("║ 【3】预处理图片                   ║")
        print("║ 【4】打包导出icons                ║")
        print("║ 【5】生成面具模块 / 【6】生成mtz  ║")
        print("║ 【0】退出                         ║")
        print("╚═══════════════════════════════════╝")
        user_input = input("请选择：").strip()

        if user_input == "1":

            print("正在通过 ADB 获取手机当前 Monet 颜色配置...")
            print("请确认手机已连接电脑，并已允许 USB 调试。")
            try:
                fetch_colors_from_adb()
                check_colors()
            except Exception as exc:
                print(f"获取失败：{exc}")
                print("请检查 ADB 连接状态后重新执行【功能1】。")
            else:
                print("配置读取成功！可使用【功能2】预览颜色！")
            input("回车键以继续...")

            continue

        elif user_input == "2":

            print("在新的窗口中预览。")
            print("关闭预览窗口以继续...")
            fix_color()


            preview_color()
            continue

        elif user_input == "3":

            fix_color()
            check_colors()
            print(" ")
            print("请选择使用的图标风格：")
            while True:
                icon_style = input("(1：圆角矩形 / 2：圆形): ").strip()

                if icon_style == "1":
                    clip_png = CLIP_PNG_PATH
                    shutil.copyfile(os.path.join("assets", "transform_config.xml"), GENERAL_XML_PATH)
                    break
                elif icon_style == "2":
                    clip_png = CLIP_ROUND_PNG_PATH
                    shutil.copyfile(os.path.join("assets", "transform_config-round.xml"), GENERAL_XML_PATH)
                    break
                else:
                    CLEAR_LAST_LINE()

            print("该步骤较慢，请耐心等待...")
            accent1_100, accent1_200, accent1_700 = prepare_color()
            png_files = [file for file in os.listdir(DRAWABLE_DIR) if file.lower().endswith(".png")]
            total_files = len(png_files)

            for idx, file in enumerate(png_files, 1):
                print_progress_bar(idx, total_files)
                process_file(file, DRAWABLE_DIR, accent1_100, accent1_200, accent1_700, clip_png)

            # 解决刷新问题
            sys.stdout.flush()
            sys.stdout.write("\n")

            create_theme_fallback_xml()
            print(" ")
            print("处理完成！接下来可以打包导出！")
            input("回车键以继续...")
            continue

        elif user_input == "4":

            if not os.path.exists(PREPROCESS_DIR) or not any(os.scandir(PREPROCESS_DIR)) or not os.path.exists(THEME_FALLBACK_XML) or not os.path.exists(GENERAL_XML_PATH):
                print("缓存区为空！请先执行【功能1、3】预处理图片！")
                input("回车键以继续...")
                continue

            print(" ")
            print("提示：如果您已修改颜色配置，请务必先执行【功能3】，否则打包的图标颜色不会生效！")
            user_confirm = input("回车键以继续；键入任意内容【返回功能选择】... ")

            if user_confirm:
                continue

            print(" ")
            print("是否启用“自动切换深色模式”功能？启用将显著增加文件体积。")
            while True:
                switch_function = input("(y：启用 / n：禁用): ").strip()

                if switch_function in ("y", "n"):
                    break
                else:
                    CLEAR_LAST_LINE()

            light_mode = "y"  # 不提前赋值的话，switch_function 启用时，代码会炸

            if switch_function == "n":
                print(" ")
                print("请选择要打包的“单色图标”风格：")
                while True:
                    light_mode = input("(y：浅色图标包 / n：深色图标包): ").strip()

                    if light_mode in ("y", "n"):
                        break
                    else:
                        CLEAR_LAST_LINE()

            # 执行
            print(" ")
            print("开始打包...")
            icon_package(switch_function, light_mode)
            print(" ")
            print("处理完成！icons 文件已生成于项目根目录。")
            print("接下来您可以：")
            print("方案1(推荐)：将icons直接复制至手机/data/system/theme/，然后重启桌面。具体细节见说明文档。")
            print("方案2：使用功能5生成面具模块，然后刷入并重启手机。")
            print("方案3：使用功能6生成mtz主题包，然后使用主题破解模块安装。")
            print(" ")
            input("回车键以继续...")
            continue

        elif user_input == "5":

            if not os.path.exists(OUTPUT_ICONS):
                print("找不到 icons 文件，请先执行【功能1、3、4】生成图标包！")
                continue

            print("打包中...")

            # 1. 复制 PACK_MAGISK 到 PACK_MAGISK_TEMP
            if os.path.exists(PACK_MAGISK_TEMP):
                shutil.rmtree(PACK_MAGISK_TEMP)
            shutil.copytree(PACK_MAGISK, PACK_MAGISK_TEMP)

            # 2. 修改 module.prop，加入构建时间
            module_prop_path = os.path.join(PACK_MAGISK_TEMP, "module.prop")
            if os.path.exists(module_prop_path):
                with open(module_prop_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if lines:
                    lines[-1] = lines[-1].strip() + now_str + "\n"
                
                with open(module_prop_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            # 3. 打包到 PACK_MAGISK_OUTPUT
            with zipfile.ZipFile(PACK_MAGISK_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(PACK_MAGISK_TEMP):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, PACK_MAGISK_TEMP)
                        zipf.write(file_path, arcname)
                
                zipf.write(
                    OUTPUT_ICONS,
                    os.path.join("product", "media", "theme", "default", "icons")
                )

            print(f"打包完成: {PACK_MAGISK_OUTPUT}")
            input("回车键以继续...")
            continue

        elif user_input == "6":

            if not os.path.exists(OUTPUT_ICONS):
                print("找不到 icons 文件，请先执行【功能1、3、4】生成图标包！")
                continue

            print("打包中...")

            # 1. 复制 PACK_MTZ 到 PACK_MTZ_TEMP
            if os.path.exists(PACK_MTZ_TEMP):
                shutil.rmtree(PACK_MTZ_TEMP)
            shutil.copytree(PACK_MTZ, PACK_MTZ_TEMP)

            # 2. 修改 description.xml，加入构建时间
            description_xml_path = os.path.join(PACK_MTZ_TEMP, "description.xml")
            with open(description_xml_path, "r", encoding="utf-8") as f:
                content = f.read()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pos = content.find("构建时间：")
            if pos != -1:
                pos += len("构建时间：")
                content = content[:pos] + now_str + content[pos:]
            with open(description_xml_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 3. 打包到 PACK_MTZ_OUTPUT
            with zipfile.ZipFile(PACK_MTZ_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(PACK_MTZ_TEMP):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, PACK_MTZ_TEMP)
                        zipf.write(file_path, arcname)
                
                zipf.write(OUTPUT_ICONS)

            print(f"打包完成: {PACK_MTZ_OUTPUT}")
            print("请使用主题破解模块安装！")
            input("回车键以继续...")
            continue

        elif user_input == "0":

            sys.exit(1)

        elif user_input == "999":

            print("999.开发者打包图标模式")
            print("打包中...")

            with zipfile.ZipFile(DRAWABLE_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(DRAWABLE_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(DRAWABLE_DIR))  # 保留 drawable 目录层级
                        zipf.write(file_path, arcname)

            # 删除目录及内容
            shutil.rmtree(DRAWABLE_DIR)

            print("打包成功！已解压的图标文件已删除。")
            sys.exit(1)

        else:
            continue  # 输入非法，自动清空并重来
        
        input("应该执行不到这一步。执行到了牛牛剪掉( *・ω・)✄╰ひ╯")

if __name__ == "__main__":
    main()
