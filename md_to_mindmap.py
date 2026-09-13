from __future__ import annotations

import argparse
import configparser
import hashlib
import html
import os
import re
import shutil
import sys
import tempfile
import textwrap
import urllib.parse
from pathlib import Path
from typing import Callable, Sequence


REQUIRED_ICON_FILES = ("iconfont.woff2", "iconfont.woff", "iconfont.ttf")
REQUIRED_TEMPLATE_TOKENS = ("{title}", "{content}", "{custom_styles}", "{logo_html}")
OPTIONAL_TEMPLATE_TOKENS = ("{cover_html}",)
TEMPLATE_TOKENS = REQUIRED_TEMPLATE_TOKENS + OPTIONAL_TEMPLATE_TOKENS
HEADING_PATTERN = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*$")
LIST_PATTERN = re.compile(r"^([ \t]*)([-+*]|\d+[.)])\s+(.+?)\s*$")
SAFE_CSS_VALUE_PATTERN = re.compile(r"^[^;{}<>\r\n]+$")
CSS_LENGTH_PATTERN = re.compile(r"^(?:0|\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%))$")
COVER_TEXT_PRESETS = {"light", "dark"}


def warn(message: str) -> None:
    print(f"⚠️ {message}")


def _is_remote_asset(reference: str) -> bool:
    lowered = reference.lstrip().lower()
    return lowered.startswith(("http://", "https://", "//", "data:image/"))


def _strip_heading_closing_marker(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


class AssetPackager:
    """Copy local assets into an output directory without filename collisions."""

    def __init__(self, output_dir: Path, relative_url_prefix: str = "images/") -> None:
        self.output_dir = output_dir
        self.relative_url_prefix = relative_url_prefix.rstrip("/") + "/"
        self._source_names: dict[Path, str] = {}
        self._name_digests: dict[str, str] = {}

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def package(self, reference: str, base_dir: Path) -> str | None:
        reference = reference.strip()
        if not reference:
            return ""
        if _is_remote_asset(reference):
            return reference

        is_windows_path = bool(re.match(r"^[A-Za-z]:[\\/]", reference))
        parsed = urllib.parse.urlsplit(reference)
        if parsed.scheme and parsed.scheme.lower() != "file" and not is_windows_path:
            warn(f"不支持的资源协议，已忽略: {reference}")
            return None

        raw_path = parsed.path if parsed.scheme.lower() == "file" else reference
        raw_path = raw_path.split("#", 1)[0].split("?", 1)[0]
        raw_path = urllib.parse.unquote(raw_path).replace(r"\ ", " ")
        source_path = Path(raw_path).expanduser()
        if not source_path.is_absolute():
            source_path = base_dir / source_path
        source_path = source_path.resolve()

        if not source_path.is_file():
            warn(f"未找到本地资源: {reference}")
            return None
        if source_path in self._source_names:
            name = self._source_names[source_path]
            return self.relative_url_prefix + urllib.parse.quote(name)

        digest = self._digest(source_path)
        name = source_path.name
        known_digest = self._name_digests.get(name)
        if known_digest is not None and known_digest != digest:
            name = f"{source_path.stem}-{digest[:8]}{source_path.suffix}"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / name
        shutil.copy2(source_path, destination)
        self._source_names[source_path] = name
        self._name_digests[name] = digest
        print(f"  📷 打包资源: {source_path.name} -> {name}")
        return self.relative_url_prefix + urllib.parse.quote(name)


class MarkdownToMindmapConverter:
    def __init__(
        self,
        markdown_content: str,
        source_dir: str | Path,
        output_image_dir: str | Path | None = None,
        relative_image_path: str = "images/",
        asset_packager: AssetPackager | None = None,
    ) -> None:
        self.markdown_text = textwrap.dedent(markdown_content).strip()
        self.source_dir = Path(source_dir).resolve()

        if not self.markdown_text:
            raise ValueError("Markdown 内容不能为空。")
        if asset_packager is not None:
            self.asset_packager = asset_packager
        elif output_image_dir is not None:
            self.asset_packager = AssetPackager(Path(output_image_dir), relative_image_path)
        else:
            self.asset_packager = None

        self.title = self._extract_title()

    def _extract_title(self) -> str:
        for raw_line in self.markdown_text.splitlines():
            heading_match = HEADING_PATTERN.match(raw_line.rstrip())
            if heading_match:
                title = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", heading_match.group(2))
                title = re.sub(r"[`*_~]", "", _strip_heading_closing_marker(title))
                if title:
                    return title
        return "思维导图"

    @staticmethod
    def _find_unescaped(text: str, character: str, start: int) -> int:
        index = start
        while index < len(text):
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == character:
                return index
            index += 1
        return -1

    @classmethod
    def _iter_markdown_images(cls, text: str):
        cursor = 0
        while cursor < len(text):
            start = text.find("![", cursor)
            if start < 0:
                return
            alt_end = cls._find_unescaped(text, "]", start + 2)
            if alt_end < 0 or alt_end + 1 >= len(text) or text[alt_end + 1] != "(":
                cursor = start + 2
                continue

            depth = 1
            index = alt_end + 2
            while index < len(text) and depth:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "(":
                    depth += 1
                elif text[index] == ")":
                    depth -= 1
                index += 1
            if depth:
                return

            yield start, index, text[start + 2 : alt_end], text[alt_end + 2 : index - 1]
            cursor = index

    @staticmethod
    def _parse_image_destination(destination: str) -> str:
        destination = destination.strip()
        if destination.startswith("<"):
            closing = destination.find(">")
            if closing > 0:
                return destination[1:closing]

        match = re.match(r"((?:\\.|\S)+)", destination)
        return match.group(1) if match else destination

    @staticmethod
    def _missing_image(alt_text: str, source: str) -> str:
        label = alt_text.strip() or source.strip() or "未命名图片"
        safe_label = html.escape(label, quote=False)
        safe_source = html.escape(source, quote=True)
        return f'<span class="image-missing" title="{safe_source}">[图片未找到：{safe_label}]</span>'

    def _render_image(self, alt_text: str, destination: str) -> str:
        source = self._parse_image_destination(destination)
        if not source:
            return self._missing_image(alt_text, destination)

        if self.asset_packager is None:
            packaged_source = source if _is_remote_asset(source) else None
        else:
            packaged_source = self.asset_packager.package(source, self.source_dir)
        if packaged_source is None:
            return self._missing_image(alt_text, source)

        safe_source = html.escape(packaged_source, quote=True)
        safe_alt = html.escape(alt_text, quote=True)
        return f'<img src="{safe_source}" alt="{safe_alt}" loading="lazy">'

    def _render_inline_content(self, text: str) -> str:
        parts: list[str] = []
        cursor = 0
        for start, end, alt_text, destination in self._iter_markdown_images(text):
            parts.append(html.escape(text[cursor:start], quote=False))
            parts.append(self._render_image(alt_text, destination))
            cursor = end
        parts.append(html.escape(text[cursor:], quote=False))
        return "".join(parts)

    def _parse_to_tree(self) -> list[dict]:
        root_node = {"text": "root", "level": -1, "children": []}
        parent_stack = [root_node]
        last_heading_level = -1
        list_indents: list[int] = []

        for raw_line in self.markdown_text.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue

            heading_match = HEADING_PATTERN.match(line)
            list_match = LIST_PATTERN.match(line)
            if heading_match:
                level = len(heading_match.group(1)) - 1
                raw_text = _strip_heading_closing_marker(heading_match.group(2))
                last_heading_level = level
                list_indents.clear()
            elif list_match:
                indentation = len(list_match.group(1).expandtabs(4))
                while list_indents and indentation < list_indents[-1]:
                    list_indents.pop()
                if not list_indents or indentation > list_indents[-1]:
                    list_indents.append(indentation)
                level = last_heading_level + len(list_indents)
                raw_text = list_match.group(3)
            else:
                continue

            node = {
                "text": self._render_inline_content(raw_text.strip()),
                "level": level,
                "children": [],
            }
            while parent_stack[-1]["level"] >= level:
                parent_stack.pop()
            parent_stack[-1]["children"].append(node)
            parent_stack.append(node)

        return root_node["children"]

    def _generate_html_recursive(self, nodes: list[dict], is_root: bool = True) -> str:
        if not nodes:
            return ""
        html_parts: list[str] = []
        for index, node in enumerate(nodes):
            level, text, children = node["level"], node["text"], node["children"]
            classes: list[str] = []
            if is_root and index == 0:
                classes.append("node-root")
            else:
                style_level = min(max(level, 1), 3)
                classes.append(f"node-level-{style_level}")
                if level > 3:
                    classes.append(f"node-depth-{level}")

            if children:
                classes.extend(("collapsible", "collapsed"))
            else:
                classes.append("node-leaf")

            html_parts.append(f'<li class="{" ".join(classes)}">')
            html_parts.append('    <div class="node-content">')
            if children:
                html_parts.append(
                    '        <button type="button" class="toggle-icon" '
                    'tabindex="-1" aria-label="展开子节点" '
                    'aria-expanded="false"></button>'
                )
            if children:
                html_parts.append(f'        <span class="node-label">{text}</span>')
            else:
                html_parts.append(f"        <p>{text}</p>")
            html_parts.append("    </div>")
            if children:
                html_parts.append("    <ul>")
                html_parts.append(self._generate_html_recursive(children, is_root=False))
                html_parts.append("    </ul>")
            html_parts.append("</li>")
        return "\n".join(html_parts)

    def convert(self) -> tuple[str, str]:
        tree = self._parse_to_tree()
        if not tree:
            raise ValueError("未识别到标题或列表，请使用 # 标题、- 列表或 1. 有序列表。")
        return self.title, self._generate_html_recursive(tree)


def _safe_css_value(value: str, fallback: str = "") -> str:
    value = value.strip()
    return value if value and SAFE_CSS_VALUE_PATTERN.fullmatch(value) else fallback


def _bounded_float(value: str, fallback: float, minimum: float, maximum: float) -> float:
    try:
        return min(max(float(value), minimum), maximum)
    except (TypeError, ValueError):
        return fallback


def _config_boolean(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    fallback: bool,
) -> bool:
    try:
        return config.getboolean(section, option, fallback=fallback)
    except ValueError:
        warn(f"配置项 [{section}] {option} 不是有效布尔值，已使用 {fallback}。")
        return fallback


def _resolve_cover_text_preset(
    config: configparser.ConfigParser,
    override: str | None = None,
) -> str:
    preset = (
        override
        or config.get("Cover", "default_text_preset", fallback="light")
    ).strip().casefold()
    if preset not in COVER_TEXT_PRESETS:
        raise ValueError("封面字体预设必须是 light 或 dark。")
    return preset


def _css_url(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "").replace("\r", "")


def generate_custom_styles_and_logo(config: configparser.ConfigParser) -> tuple[str, str]:
    css_vars: list[str] = []
    background_color = _safe_css_value(config.get("Background", "color", fallback=""))
    if background_color:
        css_vars.append(f"  --bg-color: {background_color};")

    background_image = config.get("Background", "image_url", fallback="").strip()
    if background_image:
        css_vars.append(f"  --bg-image: url('{_css_url(background_image)}');")
        image_size = config.get("Background", "image_size", fallback="cover").strip()
        image_repeat = config.get("Background", "image_repeat", fallback="no-repeat").strip()
        if image_size in {"auto", "cover", "contain"}:
            css_vars.append(f"  --bg-size: {image_size};")
        if image_repeat in {"repeat", "repeat-x", "repeat-y", "no-repeat", "space", "round"}:
            css_vars.append(f"  --bg-repeat: {image_repeat};")

    connector_color = _safe_css_value(config.get("Nodes", "connector_color", fallback=""))
    if connector_color:
        css_vars.append(f"  --connector-color: {connector_color};")

    for level in ("root", "level1", "level2", "level3"):
        for suffix, variable_suffix in (
            ("bg_color", "bg"),
            ("text_color", "text"),
            ("border_color", "border"),
        ):
            value = _safe_css_value(config.get("Nodes", f"{level}_{suffix}", fallback=""))
            if value:
                css_vars.append(f"  --node-{level}-{variable_suffix}: {value};")

    logo_html = ""
    logo_css = ""
    logo_url = config.get("Logo", "image_url", fallback="").strip()
    if logo_url:
        positions = {"top-left", "top-right", "bottom-left", "bottom-right"}
        position = config.get("Logo", "position", fallback="bottom-right").strip()
        if position not in positions:
            position = "bottom-right"
        margin = config.get("Logo", "margin", fallback="20px").strip()
        if not CSS_LENGTH_PATTERN.fullmatch(margin):
            margin = "20px"
        scale = _bounded_float(config.get("Logo", "scale", fallback="1"), 1, 0.05, 10)
        opacity = _bounded_float(config.get("Logo", "opacity", fallback="0.8"), 0.8, 0, 1)
        vertical, horizontal = position.split("-")
        logo_css = (
            "#custom-logo { position: fixed; z-index: 1000; pointer-events: none; "
            f"opacity: {opacity:g}; {vertical}: {margin}; {horizontal}: {margin}; "
            f"transform: scale({scale:g}); transform-origin: {vertical} {horizontal}; }}"
        )
        safe_url = html.escape(logo_url, quote=True)
        logo_html = (
            f'<img id="custom-logo" src="{safe_url}" alt="Logo" '
            f'data-position="{position}">'
        )

    css_body = os.linesep.join(css_vars)
    return f'<style id="custom-styles">:root {{{css_body}}} {logo_css}</style>', logo_html


def generate_cover(
    config: configparser.ConfigParser,
    document_title: str,
    enabled: bool,
    show_on_open: bool,
    text_preset: str | None = None,
) -> tuple[str, str]:
    if not enabled:
        return "", ""

    cover_title = config.get("Cover", "title", fallback="").strip() or document_title
    cover_subtitle = config.get("Cover", "subtitle", fallback="").strip()
    auto_split_title = _config_boolean(config, "Cover", "auto_split_title", True)
    if not cover_subtitle and auto_split_title:
        for separator in ("：", ":", "——", "—"):
            if separator not in cover_title:
                continue
            main_title, subtitle = cover_title.split(separator, 1)
            if main_title.strip() and subtitle.strip():
                cover_title = main_title.strip()
                cover_subtitle = subtitle.strip()
                break
    presenter = config.get("Cover", "presenter", fallback="").strip()
    presenter_label = config.get("Cover", "presenter_label", fallback="").strip()
    organization = config.get("Cover", "organization", fallback="").strip()
    date_text = config.get("Cover", "date", fallback="").strip()

    overlay = _safe_css_value(
        config.get("Cover", "background_overlay", fallback="rgba(8, 26, 58, 0.42)"),
        "rgba(8, 26, 58, 0.42)",
    )
    resolved_text_preset = _resolve_cover_text_preset(config, text_preset)

    legacy_text_color = config.get("Cover", "text_color", fallback="#ffffff")
    if resolved_text_preset == "light":
        text_color = _safe_css_value(
            config.get("Cover", "light_text_color", fallback=legacy_text_color),
            "#ffffff",
        )
        outline_color = _safe_css_value(
            config.get("Cover", "light_outline_color", fallback="rgba(5, 18, 32, 0.5)"),
            "rgba(5, 18, 32, 0.5)",
        )
        title_shadow = "0 3px 12px rgba(0, 0, 0, 0.26), 0 10px 30px rgba(0, 0, 0, 0.14)"
        subtitle_shadow = "0 2px 9px rgba(0, 0, 0, 0.24), 0 7px 24px rgba(0, 0, 0, 0.12)"
        metadata_shadow = "0 2px 8px rgba(0, 0, 0, 0.22)"
    else:
        text_color = _safe_css_value(
            config.get("Cover", "dark_text_color", fallback="#123456"),
            "#123456",
        )
        outline_color = _safe_css_value(
            config.get("Cover", "dark_outline_color", fallback="rgba(255, 255, 255, 0.68)"),
            "rgba(255, 255, 255, 0.68)",
        )
        title_shadow = "0 1px 4px rgba(255, 255, 255, 0.5), 0 9px 26px rgba(18, 52, 86, 0.16)"
        subtitle_shadow = "0 1px 3px rgba(255, 255, 255, 0.46), 0 6px 20px rgba(18, 52, 86, 0.14)"
        metadata_shadow = "0 1px 3px rgba(255, 255, 255, 0.42)"
    accent_color = _safe_css_value(
        config.get("Cover", "accent_color", fallback="#8ed7ff"),
        "#8ed7ff",
    )
    logo_size = config.get("Cover", "logo_size", fallback="96px").strip()
    logo_margin = config.get("Cover", "logo_margin", fallback="32px").strip()
    if not CSS_LENGTH_PATTERN.fullmatch(logo_size):
        logo_size = "96px"
    if not CSS_LENGTH_PATTERN.fullmatch(logo_margin):
        logo_margin = "32px"

    css_vars = [
        f"  --cover-overlay: {overlay};",
        f"  --cover-text-color: {text_color};",
        f"  --cover-outline-color: {outline_color};",
        f"  --cover-title-shadow: {title_shadow};",
        f"  --cover-subtitle-shadow: {subtitle_shadow};",
        f"  --cover-metadata-shadow: {metadata_shadow};",
        f"  --cover-accent-color: {accent_color};",
        f"  --cover-logo-size: {logo_size};",
        f"  --cover-logo-margin: {logo_margin};",
    ]
    background_image = config.get("Cover", "background_image", fallback="").strip()
    if background_image:
        css_vars.append(f"  --cover-bg-image: url('{_css_url(background_image)}');")

    logo_html_parts: list[str] = []
    position_labels = {
        "top_left": ("top-left", "左上角"),
        "top_right": ("top-right", "右上角"),
        "bottom_left": ("bottom-left", "左下角"),
        "bottom_right": ("bottom-right", "右下角"),
    }
    for option, (css_position, position_label) in position_labels.items():
        logo_url = config.get("Cover", f"logo_{option}", fallback="").strip()
        if not logo_url:
            continue
        safe_url = html.escape(logo_url, quote=True)
        logo_html_parts.append(
            f'<img class="cover-logo cover-logo-{css_position}" src="{safe_url}" '
            f'alt="封面 Logo（{position_label}）">'
        )

    metadata_parts: list[str] = []
    if presenter:
        safe_presenter = html.escape(presenter, quote=False)
        safe_label = html.escape(presenter_label, quote=False)
        displayed_presenter = f"{safe_label}：{safe_presenter}" if safe_label else safe_presenter
        metadata_parts.append(f'<p class="cover-presenter">{displayed_presenter}</p>')
    if organization:
        metadata_parts.append(
            f'<p class="cover-organization">{html.escape(organization, quote=False)}</p>'
        )
    if date_text:
        metadata_parts.append(f'<p class="cover-date">{html.escape(date_text, quote=False)}</p>')

    visible_class = " is-visible" if show_on_open else ""
    aria_hidden = "false" if show_on_open else "true"
    title_length = len(re.sub(r"\s+", "", cover_title))
    if title_length <= 14:
        title_size_class = "cover-title-short"
    elif title_length <= 24:
        title_size_class = "cover-title-medium"
    elif title_length <= 36:
        title_size_class = "cover-title-long"
    else:
        title_size_class = "cover-title-extra-long"
    subtitle_html = ""
    if cover_subtitle:
        subtitle_html = (
            f'<p class="cover-subtitle">{html.escape(cover_subtitle, quote=False)}</p>'
        )
    metadata_html = ""
    if metadata_parts:
        metadata_html = (
            '<div class="cover-separator" aria-hidden="true"></div>'
            f'<div class="cover-metadata">{"".join(metadata_parts)}</div>'
        )
    cover_html = (
        f'<section id="mindmap-cover" class="mindmap-cover{visible_class}" '
        f'aria-hidden="{aria_hidden}" role="dialog" aria-modal="true" '
        f'aria-labelledby="cover-title" aria-label="演示封面，点击或按回车、空格、方向键进入思维导图" '
        f'tabindex="0" data-show-on-open="{str(show_on_open).lower()}" '
        f'data-text-preset="{resolved_text_preset}">'
        f'{"".join(logo_html_parts)}'
        '<div class="cover-content">'
        '<div class="cover-heading">'
        f'<h1 id="cover-title" class="cover-title {title_size_class}">{html.escape(cover_title, quote=False)}</h1>'
        f'{subtitle_html}</div>'
        f'{metadata_html}'
        '</div></section>'
    )
    css_body = os.linesep.join(css_vars)
    cover_styles = f'<style id="cover-custom-styles">:root {{{css_body}}}</style>'
    return cover_styles, cover_html


def _load_config(config_path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    if config_path.is_file():
        with config_path.open("r", encoding="utf-8") as file_obj:
            config.read_file(file_obj)
    else:
        warn(f"未找到配置文件，将使用模板默认样式: {config_path}")
    return config


def _package_config_assets(
    config: configparser.ConfigParser,
    config_dir: Path,
    packager: AssetPackager,
) -> None:
    asset_options = (
        ("Background", "image_url"),
        ("Logo", "image_url"),
        ("Cover", "background_image"),
        ("Cover", "logo_top_left"),
        ("Cover", "logo_top_right"),
        ("Cover", "logo_bottom_left"),
        ("Cover", "logo_bottom_right"),
    )
    for section, option in asset_options:
        reference = config.get(section, option, fallback="").strip()
        if not reference:
            continue
        packaged = packager.package(reference, config_dir)
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, packaged or "")


def _render_template(
    template: str,
    title: str,
    content: str,
    custom_styles: str,
    logo_html: str,
    cover_html: str = "",
) -> str:
    missing = [token for token in REQUIRED_TEMPLATE_TOKENS if token not in template]
    if missing:
        raise ValueError(f"模板缺少必要占位符: {', '.join(missing)}")
    if "{cover_html}" not in template and cover_html:
        if "<body>" not in template:
            raise ValueError("模板没有 {cover_html} 占位符，也无法在 <body> 后自动插入封面。")
        template = template.replace("<body>", f"<body>{cover_html}", 1)
        cover_html = ""
    replacements = {
        "{title}": html.escape(title, quote=False),
        "{content}": content,
        "{custom_styles}": custom_styles,
        "{logo_html}": logo_html,
        "{cover_html}": cover_html,
    }
    token_pattern = re.compile("|".join(re.escape(token) for token in TEMPLATE_TOKENS))
    return token_pattern.sub(lambda match: replacements[match.group(0)], template)


def discover_markdown_files(directory: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in directory.glob("*.md")
            if path.name.casefold() != "readme.md" and not path.name.startswith(".")
        ),
        key=lambda path: path.name.casefold(),
    )


def select_markdown_file(
    files: Sequence[Path],
    input_func: Callable[[str], str] = input,
) -> Path:
    if not files:
        raise ValueError("未找到可转换的 Markdown 文件。")
    print("发现以下 Markdown 文件:")
    for index, path in enumerate(files, 1):
        print(f"  [{index}] {path.name}")
    raw_choice = input_func(f"\n请输入编号 (1-{len(files)}): ").strip()
    try:
        choice = int(raw_choice)
    except ValueError as exc:
        raise ValueError("请输入有效的整数编号。") from exc
    if not 1 <= choice <= len(files):
        raise ValueError(f"编号必须在 1 到 {len(files)} 之间。")
    return files[choice - 1]


def select_boolean(
    prompt: str,
    default: bool,
    input_func: Callable[[str], str] = input,
) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw_value = input_func(f"{prompt} {suffix}: ").strip().casefold()
    if not raw_value:
        return default
    if raw_value in {"y", "yes", "1", "true", "是"}:
        return True
    if raw_value in {"n", "no", "0", "false", "否"}:
        return False
    raise ValueError("请输入 y/yes/是 或 n/no/否。")


def select_cover_text_preset(
    default: str,
    input_func: Callable[[str], str] = input,
) -> str:
    if default not in COVER_TEXT_PRESETS:
        raise ValueError("封面字体预设必须是 light 或 dark。")
    print("封面字体预设:")
    print("  [1] 浅色字（适合深色背景）")
    print("  [2] 深色字（适合浅色背景）")
    default_number = "1" if default == "light" else "2"
    raw_choice = input_func(f"请选择 (1/2，默认 {default_number}): ").strip().casefold()
    if not raw_choice:
        return default
    choices = {
        "1": "light",
        "light": "light",
        "浅色": "light",
        "浅色字": "light",
        "2": "dark",
        "dark": "dark",
        "深色": "dark",
        "深色字": "dark",
    }
    if raw_choice not in choices:
        raise ValueError("字体预设请输入 1/light/浅色 或 2/dark/深色。")
    return choices[raw_choice]


def build_mindmap(
    markdown_path: Path,
    output_dir: Path | None = None,
    template_path: Path | None = None,
    config_path: Path | None = None,
    cover_enabled: bool | None = None,
    show_cover_on_open: bool | None = None,
    cover_text_preset: str | None = None,
) -> Path:
    script_dir = Path(__file__).resolve().parent
    markdown_path = markdown_path.expanduser().resolve()
    if not markdown_path.is_file():
        raise FileNotFoundError(f"找不到 Markdown 文件: {markdown_path}")
    if markdown_path.suffix.lower() != ".md":
        raise ValueError(f"输入文件必须是 .md 文件: {markdown_path}")

    template_path = (template_path or script_dir / "template.html").expanduser().resolve()
    config_path = (config_path or script_dir / "config.conf").expanduser().resolve()
    source_icons_dir = script_dir / "source_icons"
    if not template_path.is_file():
        raise FileNotFoundError(f"找不到模板文件: {template_path}")
    missing_icons = [name for name in REQUIRED_ICON_FILES if not (source_icons_dir / name).is_file()]
    if missing_icons:
        raise FileNotFoundError(f"缺少运行时字体: {', '.join(missing_icons)}")

    output_dir = (output_dir or markdown_path.parent / markdown_path.stem).expanduser().resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(f"输出路径不是目录: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_icons_dir = output_dir / "icons"
    output_images_dir = output_dir / "images"
    output_icons_dir.mkdir(exist_ok=True)
    output_images_dir.mkdir(exist_ok=True)

    markdown_content = markdown_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")
    config = _load_config(config_path)
    resolved_cover_enabled = (
        _config_boolean(config, "Cover", "enabled", False)
        if cover_enabled is None
        else cover_enabled
    )
    resolved_show_cover = (
        _config_boolean(config, "Cover", "show_on_open", True)
        if show_cover_on_open is None
        else show_cover_on_open
    )
    resolved_show_cover = resolved_cover_enabled and resolved_show_cover
    resolved_cover_text_preset = _resolve_cover_text_preset(config, cover_text_preset)
    packager = AssetPackager(output_images_dir, "images/")
    _package_config_assets(config, config_path.parent, packager)

    converter = MarkdownToMindmapConverter(
        markdown_content=markdown_content,
        source_dir=markdown_path.parent,
        asset_packager=packager,
    )
    title, content_html = converter.convert()
    custom_styles, logo_html = generate_custom_styles_and_logo(config)
    cover_styles, cover_html = generate_cover(
        config,
        document_title=title,
        enabled=resolved_cover_enabled,
        show_on_open=resolved_show_cover,
        text_preset=resolved_cover_text_preset,
    )
    final_html = _render_template(
        template,
        title,
        content_html,
        custom_styles + cover_styles,
        logo_html,
        cover_html,
    )

    print("📦 正在打包离线图标资源...")
    for icon_file in REQUIRED_ICON_FILES:
        shutil.copy2(source_icons_dir / icon_file, output_icons_dir / icon_file)

    output_html_path = output_dir / f"{markdown_path.stem}.html"
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{markdown_path.stem}-",
        suffix=".html.tmp",
        dir=output_dir,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        temporary_path.write_text(final_html, encoding="utf-8")
        os.replace(temporary_path, output_html_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print("✅ 生成成功！")
    if resolved_cover_enabled:
        startup_text = "默认显示" if resolved_show_cover else "默认跳过"
        print(f"🎬 封面已生成（{startup_text}，可双击主页键打开）")
        preset_text = "浅色字" if resolved_cover_text_preset == "light" else "深色字"
        print(f"🔤 封面字体: {preset_text}预设")
    print(f"📂 输出目录: {output_dir}")
    print(f"   ├── {output_html_path.name}")
    print("   ├── icons/（离线字体）")
    print("   └── images/（Markdown、背景和 Logo 图片）")
    return output_html_path


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 Markdown 标题与列表转换为离线交互式思维导图。")
    parser.add_argument("input", nargs="?", type=Path, help="Markdown 文件；省略时从项目目录交互选择")
    parser.add_argument("-o", "--output-dir", type=Path, help="输出目录，默认与 Markdown 同目录且同名")
    parser.add_argument("--template", type=Path, help="自定义 HTML 模板路径")
    parser.add_argument("--config", type=Path, help="自定义配置文件路径")
    cover_group = parser.add_mutually_exclusive_group()
    cover_group.add_argument("--cover", dest="cover_enabled", action="store_true", help="生成封面")
    cover_group.add_argument("--no-cover", dest="cover_enabled", action="store_false", help="不生成封面")
    startup_group = parser.add_mutually_exclusive_group()
    startup_group.add_argument(
        "--show-cover-on-open",
        dest="show_cover_on_open",
        action="store_true",
        help="打开 HTML 时默认显示封面",
    )
    startup_group.add_argument(
        "--skip-cover-on-open",
        dest="show_cover_on_open",
        action="store_false",
        help="打开 HTML 时默认直接显示思维导图",
    )
    text_preset_group = parser.add_mutually_exclusive_group()
    text_preset_group.add_argument(
        "--light-cover-text",
        dest="cover_text_preset",
        action="store_const",
        const="light",
        help="封面使用浅色字体预设，适合深色背景",
    )
    text_preset_group.add_argument(
        "--dark-cover-text",
        dest="cover_text_preset",
        action="store_const",
        const="dark",
        help="封面使用深色字体预设，适合浅色背景",
    )
    parser.set_defaults(
        cover_enabled=None,
        show_cover_on_open=None,
        cover_text_preset=None,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = create_argument_parser().parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    try:
        markdown_path = args.input or select_markdown_file(discover_markdown_files(script_dir))
        resolved_config_path = (args.config or script_dir / "config.conf").expanduser().resolve()
        prompt_config = _load_config(resolved_config_path)
        resolved_cover_enabled = (
            _config_boolean(prompt_config, "Cover", "enabled", False)
            if args.cover_enabled is None
            else args.cover_enabled
        )
        default_show_cover = _config_boolean(prompt_config, "Cover", "show_on_open", True)
        resolved_show_cover = args.show_cover_on_open
        if resolved_cover_enabled and resolved_show_cover is None:
            if sys.stdin.isatty():
                resolved_show_cover = select_boolean(
                    "是否在打开生成文件时默认显示封面？",
                    default_show_cover,
                )
            else:
                resolved_show_cover = default_show_cover
        default_text_preset = _resolve_cover_text_preset(prompt_config)
        resolved_text_preset = args.cover_text_preset
        if resolved_cover_enabled and resolved_text_preset is None:
            if sys.stdin.isatty():
                resolved_text_preset = select_cover_text_preset(default_text_preset)
            else:
                resolved_text_preset = default_text_preset
        build_mindmap(
            markdown_path=markdown_path,
            output_dir=args.output_dir,
            template_path=args.template,
            config_path=resolved_config_path,
            cover_enabled=resolved_cover_enabled,
            show_cover_on_open=resolved_show_cover,
            cover_text_preset=resolved_text_preset,
        )
        return 0
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except (OSError, UnicodeError, ValueError, configparser.Error) as exc:
        print(f"❌ 生成失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
