import configparser
import hashlib
import tempfile
import unittest
from pathlib import Path

from md_to_mindmap import (
    AssetPackager,
    MarkdownToMindmapConverter,
    _render_template,
    build_mindmap,
    discover_markdown_files,
    generate_cover,
    generate_custom_styles_and_logo,
    select_boolean,
    select_markdown_file,
)


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def converter(self, markdown: str) -> MarkdownToMindmapConverter:
        return MarkdownToMindmapConverter(
            markdown,
            source_dir=self.root,
            output_image_dir=self.root / "output-images",
        )

    def test_text_and_document_title_are_html_escaped(self):
        converter = self.converter('# A & <B>\n- <script>alert("x")</script>')
        title, content = converter.convert()
        document = _render_template(
            "<title>{title}</title>{custom_styles}{logo_html}<main>{content}</main>",
            title,
            content,
            "",
            "",
        )

        self.assertIn("<title>A &amp; &lt;B&gt;</title>", document)
        self.assertIn('<span class="node-label">A &amp; &lt;B&gt;</span>', content)
        self.assertIn("&lt;script&gt;alert(\"x\")&lt;/script&gt;", document)
        self.assertNotIn("<script>", document)

    def test_nested_lists_accept_two_or_four_space_indentation(self):
        tree = self.converter("# Root\n- A\n    - B\n      - C")._parse_to_tree()

        self.assertEqual(tree[0]["text"], "Root")
        self.assertEqual(tree[0]["children"][0]["text"], "A")
        self.assertEqual(tree[0]["children"][0]["children"][0]["text"], "B")
        self.assertEqual(
            tree[0]["children"][0]["children"][0]["children"][0]["text"],
            "C",
        )

    def test_same_named_images_are_packaged_without_overwriting(self):
        first_dir = self.root / "first"
        second_dir = self.root / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        (first_dir / "same.png").write_bytes(b"first")
        (second_dir / "same.png").write_bytes(b"second")
        converter = self.converter(
            "# Root\n- ![first](first/same.png)\n- ![second](second/same.png)"
        )

        _, content = converter.convert()

        digest = hashlib.sha256(b"second").hexdigest()[:8]
        self.assertIn('src="images/same.png"', content)
        self.assertIn(f'src="images/same-{digest}.png"', content)
        self.assertEqual((self.root / "output-images" / "same.png").read_bytes(), b"first")
        self.assertEqual(
            (self.root / "output-images" / f"same-{digest}.png").read_bytes(),
            b"second",
        )

    def test_missing_or_unsafe_image_becomes_safe_placeholder(self):
        _, content = self.converter(
            "# Root\n- ![missing](javascript:alert(1))"
        ).convert()

        self.assertIn("image-missing", content)
        self.assertNotIn("<img", content)
        self.assertNotIn('src="javascript:', content)

    def test_markdown_image_path_may_contain_parentheses(self):
        image_path = self.root / "chart(1).png"
        image_path.write_bytes(b"chart")

        _, content = self.converter("# Root\n- ![chart](chart(1).png)").convert()

        self.assertIn('src="images/chart%281%29.png"', content)


class ConfigurationTests(unittest.TestCase):
    def test_invalid_css_fragments_and_logo_values_are_safely_normalized(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict(
            {
                "Background": {"color": "red; } body { display:none"},
                "Logo": {
                    "image_url": "images/logo.png",
                    "position": "somewhere",
                    "margin": "20px; color:red",
                    "scale": "999",
                    "opacity": "-2",
                },
            }
        )

        styles, logo = generate_custom_styles_and_logo(config)

        self.assertNotIn("display:none", styles)
        self.assertIn("bottom: 20px; right: 20px", styles)
        self.assertIn("scale(10)", styles)
        self.assertIn("opacity: 0", styles)
        self.assertIn('data-position="bottom-right"', logo)

    def test_cover_uses_document_title_and_escapes_metadata(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict(
            {
                "Cover": {
                    "title": "",
                    "presenter": "张三 <script>",
                    "organization": "示例大学",
                    "date": "2026年7月",
                    "logo_top_right": "images/logo.png",
                }
            }
        )

        styles, cover = generate_cover(
            config,
            document_title="研究标题",
            enabled=True,
            show_on_open=True,
        )

        self.assertIn("--cover-overlay", styles)
        self.assertIn('class="mindmap-cover is-visible"', cover)
        self.assertIn('data-show-on-open="true"', cover)
        self.assertIn('id="cover-title" class="cover-title cover-title-short">研究标题</h1>', cover)
        self.assertIn(">张三 &lt;script&gt;</p>", cover)
        self.assertNotIn("汇报人：", cover)
        self.assertIn("示例大学", cover)
        self.assertIn("2026年7月", cover)
        self.assertIn("cover-logo-top-right", cover)
        self.assertIn('class="cover-separator"', cover)
        self.assertNotIn("enter-mindmap-btn", cover)
        self.assertNotIn("cover-hint", cover)
        self.assertNotIn("张三 <script>", cover)

    def test_cover_automatically_splits_main_title_and_subtitle(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({"Cover": {"auto_split_title": "true"}})

        _, cover = generate_cover(
            config,
            document_title="主标题：这是一个说明研究范围的副标题",
            enabled=True,
            show_on_open=False,
        )

        self.assertIn(">主标题</h1>", cover)
        self.assertIn('<p class="cover-subtitle">这是一个说明研究范围的副标题</p>', cover)
        self.assertIn('tabindex="0"', cover)
        self.assertNotIn("cover-separator", cover)
        self.assertNotIn("cover-metadata", cover)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_discovery_excludes_readme_and_sorts_files(self):
        for name in ("README.md", ".hidden.md", "b.md", "A.md"):
            (self.root / name).write_text("# test", encoding="utf-8")

        files = discover_markdown_files(self.root)

        self.assertEqual([path.name for path in files], ["A.md", "b.md"])

    def test_default_cover_background_is_a_local_project_asset(self):
        project_root = Path(__file__).resolve().parents[1]
        config = configparser.ConfigParser(interpolation=None)
        config.read(project_root / "config.ini", encoding="utf-8")
        background = config.get("Cover", "background_image")

        self.assertEqual(background, "assets/cover-default.svg")
        self.assertTrue((project_root / background).is_file())

    def test_interactive_choice_rejects_zero_and_negative_numbers(self):
        files = [self.root / "a.md", self.root / "b.md"]
        for choice in ("0", "-1", "3", "abc"):
            with self.subTest(choice=choice):
                with self.assertRaises(ValueError):
                    select_markdown_file(files, input_func=lambda _prompt, value=choice: value)

    def test_boolean_selection_uses_default_and_validates_input(self):
        self.assertTrue(select_boolean("show", True, input_func=lambda _prompt: ""))
        self.assertTrue(select_boolean("show", False, input_func=lambda _prompt: "是"))
        self.assertFalse(select_boolean("show", True, input_func=lambda _prompt: "n"))
        with self.assertRaises(ValueError):
            select_boolean("show", True, input_func=lambda _prompt: "maybe")

    def test_build_packages_local_logo_and_refreshes_existing_images(self):
        markdown = self.root / "input.md"
        markdown.write_text("# Root\n- ![picture](picture.png)", encoding="utf-8")
        (self.root / "picture.png").write_bytes(b"new-picture")
        (self.root / "logo.png").write_bytes(b"logo")
        config = self.root / "custom.ini"
        config.write_text(
            "[Logo]\nimage_url = logo.png\nposition = top-right\n\n"
            "[Cover]\nenabled = true\nshow_on_open = false\n"
            "presenter = 张三\norganization = 示例大学\n"
            "background_image = picture.png\nlogo_top_right = logo.png\n",
            encoding="utf-8",
        )
        output = self.root / "result"
        (output / "images").mkdir(parents=True)
        (output / "images" / "picture.png").write_bytes(b"stale-picture")

        html_path = build_mindmap(
            markdown,
            output_dir=output,
            config_path=config,
            show_cover_on_open=True,
        )
        document = html_path.read_text(encoding="utf-8")

        self.assertIn('id="custom-logo" src="images/logo.png"', document)
        self.assertIn('id="mindmap-cover" class="mindmap-cover is-visible"', document)
        self.assertIn('style id="cover-custom-styles"', document)
        self.assertIn("双击显示封面", document)
        self.assertIn('id="image-lightbox"', document)
        self.assertIn("classList.contains('final-focus')", document)
        self.assertIn(".toggle-icon::after", document)
        self.assertIn('class="toggle-icon" tabindex="-1"', document)
        self.assertIn("navigatePresentation", document)
        self.assertIn("openFocusedImageForPresentation", document)
        self.assertIn("presentationPreviewedNode === lastFocusedNode", document)
        self.assertIn("forwardKeys.has(event.key) || backwardKeys.has(event.key)", document)
        self.assertIn("if (!openFocusedImageForPresentation()) navigatePresentation(1)", document)
        self.assertIn("PageDown", document)
        self.assertIn("mindmap-container.blur-disabled .node-content", document)
        self.assertIn('#mindmap-toolbar button[aria-pressed="true"]', document)
        self.assertIn('background-color: white; border-color: #409eff; color: #409eff;', document)
        self.assertLess(
            document.index('id="center-root-btn"'),
            document.index('id="toggle-blur-btn"'),
        )
        self.assertLess(
            document.index('id="toggle-blur-btn"'),
            document.index('id="fit-view-btn"'),
        )
        self.assertIn(
            'id="toggle-blur-btn" tabindex="-1" title="关闭节点模糊效果" '
            'aria-label="关闭节点模糊效果" aria-pressed="false"',
            document,
        )
        self.assertIn("isDisabled ? '&#xe62e;' : '&#xe62d;'", document)
        self.assertIn("String(isDisabled)", document)
        self.assertIn("collapseTerminalLeafGroupsForFit", document)
        self.assertIn("collapseTerminalLeafGroupsForFit(includeFocusedPath)", document)
        self.assertIn("function isFocusedNodeGlobalDeepestLeaf()", document)
        self.assertIn("function enterFitMode(includeFocusedPath = false, canUpgradeWithDouble = false)", document)
        self.assertIn("fitModeCanUpgradeWithDouble = canUpgradeWithDouble", document)
        self.assertIn("isFitMode && fitModeCanUpgradeWithDouble", document)
        self.assertIn("单击或双击取消缩放", document)
        self.assertIn("fitViewBtn.addEventListener('dblclick'", document)
        self.assertIn("requestAnimationFrame(() => enterFitMode(true, false))", document)
        self.assertIn("restoreAutoCollapsedLeafGroups", document)
        self.assertIn("directChildren.length > 0", document)
        self.assertIn("const globalMaxDepth = Math.max", document)
        self.assertIn("isGlobalDeepestLeaf", document)
        self.assertIn("allChildrenAreGlobalDeepestLeaves", document)
        self.assertIn("isOnFocusedPath(parentLi)", document)
        self.assertIn("needsOverviewCompaction", document)
        self.assertIn("const shouldCompact = includeFocusedPath || needsOverviewCompaction", document)
        self.assertIn("toolbar.addEventListener('click'", document)
        self.assertIn('id="center-root-btn" tabindex="-1"', document)
        self.assertIn('id="toggle-blur-btn" tabindex="-1"', document)
        self.assertIn('id="fit-view-btn" tabindex="-1"', document)
        self.assertIn("viewport.focus({ preventScroll: true })", document)
        self.assertIn("clarityButton.tabIndex = -1", document)
        self.assertIn("clickedButton.blur()", document)
        self.assertNotIn(".child-clarity-btn:focus-visible", document)
        self.assertIn("保持直接子节点清晰", document)
        self.assertIn("keep-children-clear", document)
        self.assertNotIn("临时显示/隐藏子节点", document)
        self.assertIn("--cover-bg-image: url('images/picture.png')", document)
        self.assertIn('class="cover-logo cover-logo-top-right" src="images/logo.png"', document)
        self.assertNotIn("汇报人：张三", document)
        self.assertEqual((output / "images" / "logo.png").read_bytes(), b"logo")
        self.assertEqual(
            (output / "images" / "picture.png").read_bytes(),
            b"new-picture",
        )
        self.assertTrue((output / "icons" / "iconfont.woff2").is_file())

    def test_cover_can_be_omitted_even_when_config_enables_it(self):
        markdown = self.root / "input.md"
        markdown.write_text("# Root\n- Item", encoding="utf-8")
        config = self.root / "custom.ini"
        config.write_text("[Cover]\nenabled = true\n", encoding="utf-8")

        html_path = build_mindmap(
            markdown,
            output_dir=self.root / "without-cover",
            config_path=config,
            cover_enabled=False,
        )

        self.assertNotIn('id="mindmap-cover"', html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
