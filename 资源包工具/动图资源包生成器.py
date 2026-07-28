# -*- coding: utf-8 -*-
"""
动图资源包生成器
把一个文件夹里的 GIF 表情包一键转换成 Minecraft Java 版动态贴图资源包（ZIP）。
核心流程：GIF -> 逐帧合成正方形竖长图 + 按真实帧时长生成 .mcmeta -> 随机替换原版方块/物品贴图 -> 打包 ZIP + 替换报告。
"""

import csv
import fnmatch
import json
import os
import random
import shutil
import sys
import threading
import traceback
import zipfile
from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ImportError:
    import tkinter.messagebox as _mb
    _mb.showerror("缺少依赖", "未安装 Pillow 图像库。\n请运行：python -m pip install pillow")
    sys.exit(1)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

TOOL_DIR = Path(__file__).resolve().parent
TEXTURE_LIST_FILE = TOOL_DIR / "vanilla_textures_1.21.10.json"
CONFIG_FILE = TOOL_DIR / "生成器配置.json"

# 各游戏版本对应的资源包格式号
PACK_FORMATS = {
    "1.21.9 - 1.21.10": 69,
    "1.21.7 - 1.21.8": 64,
    "1.21.6": 63,
    "1.21.5": 55,
    "1.21.4": 46,
    "1.21 - 1.21.1": 34,
    "1.20.5 - 1.20.6": 32,
    "1.20.2 - 1.20.4": 22,
    "1.20 - 1.20.1": 15,
}

# 常见方块清单（游戏里最容易见到的），生成时会自动过滤掉原版清单里不存在的名字
COMMON_BLOCKS = [
    "stone", "cobblestone", "mossy_cobblestone", "stone_bricks", "smooth_stone",
    "deepslate", "cobbled_deepslate", "deepslate_bricks", "deepslate_tiles",
    "granite", "diorite", "andesite", "polished_granite", "polished_diorite", "polished_andesite",
    "dirt", "coarse_dirt", "rooted_dirt", "mud", "podzol_top", "podzol_side",
    "dirt_path_top", "dirt_path_side",
    "sand", "red_sand", "gravel", "clay", "sandstone", "sandstone_top", "sandstone_bottom",
    "red_sandstone", "red_sandstone_top",
    "oak_planks", "spruce_planks", "birch_planks", "jungle_planks", "acacia_planks",
    "dark_oak_planks", "mangrove_planks", "cherry_planks", "bamboo_planks", "crimson_planks", "warped_planks",
    "oak_log", "oak_log_top", "spruce_log", "birch_log", "jungle_log", "acacia_log", "dark_oak_log",
    "bricks", "mud_bricks", "packed_mud",
    "white_wool", "orange_wool", "magenta_wool", "light_blue_wool", "yellow_wool", "lime_wool",
    "pink_wool", "gray_wool", "light_gray_wool", "cyan_wool", "purple_wool", "blue_wool",
    "brown_wool", "green_wool", "red_wool", "black_wool",
    "white_concrete", "orange_concrete", "yellow_concrete", "lime_concrete", "pink_concrete",
    "red_concrete", "blue_concrete", "light_blue_concrete", "green_concrete", "purple_concrete",
    "black_concrete", "white_concrete_powder", "red_concrete_powder",
    "terracotta", "white_terracotta", "orange_terracotta", "yellow_terracotta", "red_terracotta",
    "glass", "white_stained_glass", "red_stained_glass", "blue_stained_glass",
    "coal_ore", "iron_ore", "copper_ore", "gold_ore", "redstone_ore", "lapis_ore", "diamond_ore", "emerald_ore",
    "deepslate_coal_ore", "deepslate_iron_ore", "deepslate_gold_ore", "deepslate_redstone_ore",
    "deepslate_lapis_ore", "deepslate_diamond_ore", "deepslate_emerald_ore", "deepslate_copper_ore",
    "coal_block", "iron_block", "gold_block", "diamond_block", "emerald_block", "redstone_block",
    "lapis_block", "copper_block", "netherite_block",
    "obsidian", "crying_obsidian", "bedrock", "netherrack", "nether_bricks", "soul_sand", "soul_soil",
    "basalt_side", "basalt_top", "blackstone", "polished_blackstone", "glowstone", "shroomlight",
    "end_stone", "end_stone_bricks", "purpur_block", "purpur_pillar",
    "quartz_block_side", "quartz_block_top", "quartz_pillar", "quartz_bricks",
    "prismarine", "prismarine_bricks", "dark_prismarine", "sea_lantern",
    "snow", "ice", "packed_ice", "blue_ice",
    "pumpkin_side", "pumpkin_top", "carved_pumpkin", "jack_o_lantern", "melon_side", "melon_top",
    "hay_block_side", "hay_block_top", "bone_block_side", "bone_block_top",
    "bookshelf", "crafting_table_top", "crafting_table_front", "crafting_table_side",
    "furnace_front", "furnace_side", "furnace_top", "furnace_front_on",
    "tnt_side", "tnt_top", "tnt_bottom", "dispenser_front", "dropper_front", "observer_front",
    "piston_side", "piston_top", "note_block", "jukebox_side", "jukebox_top",
    "sponge", "wet_sponge", "slime_block", "honey_block_side", "honeycomb_block",
    "amethyst_block", "budding_amethyst", "calcite", "tuff", "dripstone_block",
    "moss_block", "sculk", "magma", "ancient_debris_side", "ancient_debris_top",
    "chiseled_stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks",
    "smooth_basalt", "reinforced_deepslate_side", "lodestone_side", "lodestone_top",
    "target_side", "target_top", "respawn_anchor_top_off", "beacon",
    "barrel_side", "barrel_top", "composter_side", "smoker_front", "blast_furnace_front",
    "loom_side", "cartography_table_top", "fletching_table_front", "smithing_table_front",
]

# 会被游戏染色（变绿/变蓝）或有特殊机制的贴图，全量替换模式下自动跳过
EXCLUDE_BLOCK = [
    "water_*", "lava_*", "fire_*", "soul_fire_*", "*_leaves", "leaves_*",
    "destroy_stage_*", "debug*", "*_overlay", "redstone_dust_*",
    "melon_stem*", "pumpkin_stem*", "attached_*_stem", "grass_block_top", "short_grass", "tall_grass*",
    "fern*", "large_fern*", "vine*", "lily_pad", "sugar_cane",
    "seagrass*", "kelp*", "birch_leaves*", "spruce_leaves*",
]
EXCLUDE_ITEM = [
    "*_spawn_egg*", "leather_*", "potion*", "splash_potion*", "lingering_potion*",
    "tipped_arrow*", "clock*", "compass*", "recovery_compass*", "filled_map*",
    "firework_star*",
]


def _excluded(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


DEFAULT_CONFIG = {
    "gif_dir": str((TOOL_DIR.parent / "素材")),
    "out_dir": str((TOOL_DIR.parent / "输出")),
    "pack_name": "我的动图资源包",
    "description": "§6§l动态表情包资源包 §r§7· §e一键生成",
    "mc_version": "1.21.9 - 1.21.10",
    "resolution": 128,
    "scope": "常见方块",
    "alpha_mode": "填白色底",
    "seed": "奶龙",
    "max_frames": 100,
    "strategy": "全随机",
}


# ---------------- 核心图像处理 ----------------

def extract_frames(gif_path: Path, size: int, alpha_fill: bool, max_frames: int):
    """读取 GIF，返回 (正方形RGBA帧列表, 每帧tick时长列表)。Pillow 会自动处理帧叠加残影问题。"""
    im = Image.open(gif_path)
    frames, durations = [], []
    for frame in ImageSequence.Iterator(im):
        rgba = frame.convert("RGBA")
        durations.append(max(20, int(frame.info.get("duration", 100) or 100)))
        frames.append(rgba)

    if not frames:
        raise ValueError("GIF 没有可用帧")

    # 帧数过多时按均匀间隔抽帧，保持总时长不变
    if len(frames) > max_frames:
        total = sum(durations)
        idxs = [round(i * (len(frames) - 1) / (max_frames - 1)) for i in range(max_frames)]
        idxs = sorted(set(idxs))
        frames = [frames[i] for i in idxs]
        durations = [total // len(idxs)] * len(idxs)

    # 每帧统一缩放为正方形
    out_frames = []
    for f in frames:
        if alpha_fill:
            bg = Image.new("RGBA", f.size, (255, 255, 255, 255))
            bg.paste(f, (0, 0), f)
            f = bg
        out_frames.append(f.resize((size, size), Image.LANCZOS))

    # 毫秒转游戏刻（1刻=50ms），至少1刻
    ticks = [max(1, round(d / 50)) for d in durations]
    return out_frames, ticks


def build_strip(frames):
    """把帧列表竖向拼成 MC 要求的动画长图。"""
    w = frames[0].width
    strip = Image.new("RGBA", (w, w * len(frames)))
    for i, f in enumerate(frames):
        strip.paste(f, (0, i * w))
    return strip


def build_mcmeta(ticks):
    """按每帧真实时长生成 mcmeta。所有帧等长时用简单写法。"""
    if len(set(ticks)) == 1:
        anim = {"frametime": ticks[0]}
    else:
        anim = {"frametime": 1, "frames": [{"index": i, "time": t} for i, t in enumerate(ticks)]}
    return {"animation": anim}


# ---------------- 生成主流程 ----------------

def generate_pack(cfg, log, progress):
    gif_dir = Path(cfg["gif_dir"])
    out_dir = Path(cfg["out_dir"])
    pack_name = cfg["pack_name"].strip() or "动图资源包"
    size = int(cfg["resolution"])
    max_frames = max(2, int(cfg["max_frames"]))
    # 长图高度 = 宽×帧数，超过游戏贴图上限会导致该贴图不加载，按分辨率自动限制
    size_limit = max(2, 16384 // size)
    if max_frames > size_limit:
        log(f"提示：分辨率 {size} 下长图可能超高，单张最长帧数已自动限制为 {size_limit}")
        max_frames = size_limit
    alpha_fill = cfg["alpha_mode"] == "填白色底"
    pack_format = PACK_FORMATS[cfg["mc_version"]]

    gifs = sorted(set(gif_dir.rglob("*.gif")) | set(gif_dir.rglob("*.png")))
    if not gifs:
        raise ValueError(f"素材文件夹里没有 GIF：{gif_dir}")

    # 游戏版本可对应不同方块清单模板；目前内置 1.21.10 一套，其他版本自动回退到它
    VERSION_TEXTURE_MAP = {
        "1.21.9 - 1.21.10": "vanilla_textures_1.21.10.json",
    }
    list_file = TOOL_DIR / VERSION_TEXTURE_MAP.get(cfg["mc_version"], "vanilla_textures_1.21.10.json")
    if not list_file.exists():
        list_file = TEXTURE_LIST_FILE
    data = json.loads(list_file.read_text(encoding="utf-8-sig"))
    scope = cfg["scope"]
    if scope == "常见方块":
        avail = set(data["block"])
        targets = [("block", n) for n in COMMON_BLOCKS if n in avail]
    else:
        blocks = [("block", n) for n in data["block"] if not _excluded(n, EXCLUDE_BLOCK)]
        if scope == "全部方块":
            targets = blocks
        else:  # 方块+物品
            targets = blocks + [("item", n) for n in data["item"] if not _excluded(n, EXCLUDE_ITEM)]

    rng = random.Random(cfg["seed"] or None)
    gif_pool = gifs[:]
    rng.shuffle(gif_pool)

    # “优先常见方块用不同表情”：常见方块先各自拿到不同表情，其余格子再循环复用
    if cfg.get("strategy") == "优先常见方块用不同表情" and scope != "全部方块":
        common_set = set(COMMON_BLOCKS)
        is_common = lambda t: t[0] == "block" and t[1] in common_set
        common_ts = [t for t in targets if is_common(t)]
        rest_ts = [t for t in targets if not is_common(t)]
        mapping = [(t, gif_pool[i % len(gif_pool)]) for i, t in enumerate(common_ts)]
        mapping += [(t, gif_pool[i % len(gif_pool)]) for i, t in enumerate(rest_ts)]
    else:
        # 全随机：目标打乱后依次分配；素材多于目标只用一部分，目标多于素材则循环复用
        rng.shuffle(targets)
        if len(targets) <= len(gif_pool):
            mapping = list(zip(targets, gif_pool[:len(targets)]))
        else:
            mapping = [(t, gif_pool[i % len(gif_pool)]) for i, t in enumerate(targets)]

    pack_dir = out_dir / pack_name
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    tex_root = pack_dir / "assets" / "minecraft" / "textures"
    (tex_root / "block").mkdir(parents=True, exist_ok=True)

    # pack.mcmeta
    (pack_dir / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": pack_format, "description": cfg["description"]}},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # 相同 GIF 只转换一次（按文件内容去重）
    cache = {}
    report = []
    total = len(mapping)
    done_count = 0
    fail = 0

    import io
    for (kind, tex_name), gif_path in mapping:
        try:
            # 相同 GIF 只转换+编码一次，缓存 PNG 字节直接写盘，避免上千次重复编码
            if gif_path not in cache:
                frames, ticks = extract_frames(gif_path, size, alpha_fill, max_frames)
                buf = io.BytesIO()
                build_strip(frames).save(buf, "PNG", optimize=True)
                cache[gif_path] = (buf.getvalue(), json.dumps(build_mcmeta(ticks)), len(frames))
            png_bytes, mcmeta_str, nframes = cache[gif_path]

            dest_dir = tex_root / kind
            dest_dir.mkdir(parents=True, exist_ok=True)
            png_path = dest_dir / f"{tex_name}.png"
            png_path.write_bytes(png_bytes)
            (dest_dir / f"{tex_name}.png.mcmeta").write_text(
                mcmeta_str, encoding="utf-8")
            report.append([kind, tex_name, gif_path.name, nframes])
        except Exception as e:
            fail += 1
            log(f"  跳过 {gif_path.name} -> {tex_name}: {e}")
        done_count += 1
        if done_count % 10 == 0 or done_count == total:
            progress(done_count, total)
            log(f"进度 {done_count}/{total}")

    # pack.png：随机拿一张 GIF 首帧当图标
    try:
        icon_src = rng.choice(gifs)
        icon = Image.open(icon_src).convert("RGBA").resize((128, 128), Image.LANCZOS)
        bg = Image.new("RGBA", (128, 128), (255, 255, 255, 255))
        bg.paste(icon, (0, 0), icon)
        bg.convert("RGB").save(pack_dir / "pack.png", "PNG")
    except Exception:
        pass

    # 替换报告
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{pack_name}_替换报告.csv"
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类型", "被替换贴图", "表情包文件", "帧数"])
        w.writerows(report)

    # 打 ZIP：PNG 本身已压缩，再用 DEFLATED 几乎压不出体积却极慢，故用 STORED 直接存
    zip_path = out_dir / f"{pack_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for p in pack_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(pack_dir))

    size_mb = zip_path.stat().st_size / 1024 / 1024
    log("")
    log(f"完成！替换贴图 {len(report)} 张，失败 {fail} 张")
    log(f"ZIP：{zip_path}（{size_mb:.1f} MB）")
    log(f"报告：{report_path}")
    return zip_path


# ---------------- 图形界面 ----------------

class App:
    def __init__(self, root):
        self.root = root
        root.title("动图资源包生成器")
        root.geometry("640x560")
        root.minsize(560, 500)

        cfg = dict(DEFAULT_CONFIG)
        if CONFIG_FILE.exists():
            try:
                cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        self.vars = {}
        row = 0

        def add_path(label, key, is_dir=True):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=cfg[key])
            self.vars[key] = v
            ttk.Entry(frm, textvariable=v).grid(row=row, column=1, sticky="ew", padx=6)
            ttk.Button(frm, text="浏览", width=6,
                       command=lambda: self._browse(v)).grid(row=row, column=2)
            row += 1

        def add_entry(label, key):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(cfg[key]))
            self.vars[key] = v
            ttk.Entry(frm, textvariable=v).grid(row=row, column=1, columnspan=2, sticky="ew", padx=6)
            row += 1

        def add_combo(label, key, values):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(cfg[key]))
            self.vars[key] = v
            ttk.Combobox(frm, textvariable=v, values=values, state="readonly"
                         ).grid(row=row, column=1, columnspan=2, sticky="ew", padx=6)
            row += 1

        add_path("GIF 素材文件夹", "gif_dir")
        add_path("输出文件夹", "out_dir")
        add_entry("资源包名称", "pack_name")
        add_entry("资源包简介", "description")
        add_combo("游戏版本", "mc_version", list(PACK_FORMATS.keys()))
        add_combo("贴图分辨率", "resolution", [64, 128, 256])
        add_combo("替换范围", "scope", ["常见方块", "全部方块", "方块+物品"])
        add_combo("分配策略", "strategy", ["全随机", "优先常见方块用不同表情"])
        add_combo("透明底处理", "alpha_mode", ["填白色底", "保留透明"])
        add_entry("随机种子（相同种子结果一致）", "seed")
        add_entry("单张GIF最大帧数", "max_frames")

        self.btn = ttk.Button(frm, text="一键生成资源包", command=self.start)
        self.btn.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        row += 1

        self.pbar = ttk.Progressbar(frm, maximum=100)
        self.pbar.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        row += 1

        self.log_box = tk.Text(frm, height=10, state="disabled")
        self.log_box.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=4)
        frm.rowconfigure(row, weight=1)
        row += 1

        self.open_btn = ttk.Button(frm, text="打开输出文件夹", command=self.open_out, state="disabled")
        self.open_btn.grid(row=row, column=0, columnspan=3, sticky="ew")

    def _browse(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or str(TOOL_DIR))
        if d:
            var.set(d)

    def log(self, msg):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _do)

    def progress(self, done, total):
        self.root.after(0, lambda: self.pbar.configure(value=done / total * 100))

    def get_cfg(self):
        return {k: v.get() for k, v in self.vars.items()}

    def start(self):
        cfg = self.get_cfg()
        try:
            CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        self.btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.pbar.configure(value=0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._work, args=(cfg,), daemon=True).start()

    def _work(self, cfg):
        try:
            self.log("开始生成……")
            generate_pack(cfg, self.log, self.progress)
            self.root.after(0, lambda: self.open_btn.configure(state="normal"))
            self.root.after(0, lambda: messagebox.showinfo("完成", "资源包生成成功！"))
        except Exception as e:
            self.log("出错：" + str(e))
            self.log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("出错", str(e)))
        finally:
            self.root.after(0, lambda: self.btn.configure(state="normal"))

    def open_out(self):
        out = self.vars["out_dir"].get()
        if os.path.isdir(out):
            os.startfile(out)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
