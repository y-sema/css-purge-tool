
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
import tinycss2

# ============================================
# Streamlit 設定
# ============================================

st.set_page_config(
    page_title="CSS Purge Tool",
    layout="wide"
)

st.title("🎨 CSS Purge Tool")
st.write("使用中CSSだけを抽出します")

# ============================================
# 入力UI
# ============================================

html_urls_text = st.text_area(
    "HTML URL一覧（1行1URL）",
    height=200,
    placeholder="https://example.com/\nhttps://example.com/about/"
)

css_url = st.text_input(
    "CSS URL",
    placeholder="https://example.com/style.css"
)

basic_id = st.text_input("Basic ID")

basic_pw = st.text_input(
    "Basic Password",
    type="password"
)

ignore_text = st.text_area(
    "除外キーワード（1行1個）",
    value="""is-
js-
active
open
current
selected
hidden
visible
show
hide
slick
swiper
fade
slide
modal
accordion
loading
error
success
drawer
hamburger
menu
nav
sp-
mobile""",
    height=220
)

# ============================================
# 実行
# ============================================

if st.button("🚀 CSS整理開始"):

    try:

        html_urls = [
            u.strip()
            for u in html_urls_text.splitlines()
            if u.strip()
        ]

        ignore_keywords = [
            i.strip()
            for i in ignore_text.splitlines()
            if i.strip()
        ]

        auth = None

        if basic_id or basic_pw:
            auth = HTTPBasicAuth(
                basic_id,
                basic_pw
            )

        # ============================================
        # HTML取得
        # ============================================

        all_html = ""

        progress = st.progress(0)

        for i, url in enumerate(html_urls):

            st.write(f"🌐 HTML取得中: {url}")

            res = requests.get(
                url,
                auth=auth,
                timeout=15
            )

            res.raise_for_status()

            res.encoding = res.apparent_encoding

            all_html += "\n" + res.text

            progress.progress(
                (i + 1) / len(html_urls)
            )

        st.success("✅ HTML取得完了")

        # ============================================
        # CSS取得
        # ============================================

        st.write(f"🎨 CSS取得中: {css_url}")

        css_res = requests.get(
            css_url,
            auth=auth,
            timeout=15
        )

        css_res.raise_for_status()

        css_res.encoding = 'utf-8'

        original_css_content = css_res.text

        st.success("✅ CSS取得完了")

        # ============================================
        # BeautifulSoup
        # ============================================

        soup = BeautifulSoup(
            all_html,
            "lxml"
        )

        used_classes = set()
        used_ids = set()
        used_tags = set()

        for tag in soup.find_all(True):

            used_tags.add(tag.name)

            classes = tag.get("class", [])

            for cls in classes:
                used_classes.add(cls)

            tag_id = tag.get("id")

            if tag_id:
                used_ids.add(tag_id)

        st.write(f"📦 検出クラス数: {len(used_classes)}")
        st.write(f"📦 検出ID数: {len(used_ids)}")

        # ============================================
        # セレクタ正規化
        # ============================================

        def normalize_selector(selector):

            selector = selector.strip()

            # 疑似要素削除
            selector = re.sub(
                r'::?[a-zA-Z0-9_-]+(\(.*?\))?',
                '',
                selector
            )

            selector = selector.replace(":not", "")

            return selector.strip()

        # ============================================
        # 除外判定
        # ============================================

        def contains_ignore_keyword(selector):

            for keyword in ignore_keywords:

                if keyword in selector:
                    return True

            return False

        # ============================================
        # 使用判定
        # ============================================

        def is_selector_used(selector_text):

            selector_text = selector_text.strip()

            if not selector_text:
                return True

            # コメント除去
            selector_text = re.sub(
                r'/\*.*?\*/',
                '',
                selector_text,
                flags=re.DOTALL
            ).strip()

            selectors = [
                s.strip()
                for s in selector_text.split(",")
            ]

            for selector in selectors:

                if not selector:
                    continue

                # ホワイトリスト
                if contains_ignore_keyword(selector):
                    return True

                normalized = normalize_selector(selector)

                if not normalized:
                    return True

                # クラス判定
                class_matches = re.findall(
                    r'\.([a-zA-Z0-9_-]+)',
                    normalized
                )

                for cls in class_matches:

                    if cls in used_classes:
                        return True

                # ID判定
                id_matches = re.findall(
                    r'#([a-zA-Z0-9_-]+)',
                    normalized
                )

                for id_name in id_matches:

                    if id_name in used_ids:
                        return True

                # タグ判定
                tag_matches = re.findall(
                    r'(^|\s|\+|>|~)([a-zA-Z][a-zA-Z0-9_-]*)',
                    normalized
                )

                for _, tag_name in tag_matches:

                    if tag_name in used_tags:
                        return True

                # BeautifulSoup fallback
                try:

                    if soup.select_one(normalized):
                        return True

                except Exception:
                    # 特殊セレクタは安全側
                    return True

            return False

        # ============================================
        # CSS解析
        # ============================================

        stylesheet = tinycss2.parse_stylesheet(
            original_css_content,
            skip_whitespace=False,
            skip_comments=False
        )

        purged_css = []
        deleted_css = []

        KEEP_AT_RULES = [
            '@keyframes',
            '@font-face',
            '@property',
        ]

        # ============================================
        # ルール解析
        # ============================================

        for rule in stylesheet:

            # コメント・空白保持
            if rule.type in ['comment', 'whitespace']:

                purged_css.append(
                    rule.serialize()
                )

                continue

            # ============================================
            # at-rule
            # ============================================

            if rule.type == 'at-rule':

                at_name = f"@{rule.lower_at_keyword}"

                # 強制保持
                if at_name in KEEP_AT_RULES:

                    purged_css.append(
                        rule.serialize()
                    )

                    continue

                # ============================================
                # @media
                # ============================================

                if at_name == "@media":

                    if not rule.content:

                        purged_css.append(
                            rule.serialize()
                        )

                        continue

                    media_inner = tinycss2.parse_rule_list(
                        rule.content,
                        skip_whitespace=False,
                        skip_comments=False
                    )

                    kept_inner = []
                    deleted_inner = []

                    for inner_rule in media_inner:

                        if inner_rule.type in ['comment', 'whitespace']:

                            kept_inner.append(
                                inner_rule.serialize()
                            )

                            continue

                        if inner_rule.type != 'qualified-rule':

                            kept_inner.append(
                                inner_rule.serialize()
                            )

                            continue

                        selector = tinycss2.serialize(
                            inner_rule.prelude
                        ).strip()

                        if is_selector_used(selector):

                            kept_inner.append(
                                inner_rule.serialize()
                            )

                        else:

                            deleted_inner.append(
                                inner_rule.serialize()
                            )

                    # 使用中
                    if kept_inner:

                        media_text = (
                            f"@media {tinycss2.serialize(rule.prelude)}"
                            "{\n"
                            + "".join(kept_inner)
                            + "\n}\n"
                        )

                        purged_css.append(
                            media_text
                        )

                    # 削除候補
                    if deleted_inner:

                        media_deleted = (
                            f"@media {tinycss2.serialize(rule.prelude)}"
                            "{\n"
                            + "".join(deleted_inner)
                            + "\n}\n"
                        )

                        deleted_css.append(
                            media_deleted
                        )

                    continue

                # その他 at-rule
                purged_css.append(
                    rule.serialize()
                )

                continue

            # ============================================
            # 通常ルール
            # ============================================

            if rule.type == 'qualified-rule':

                selector = tinycss2.serialize(
                    rule.prelude
                ).strip()

                if is_selector_used(selector):

                    purged_css.append(
                        rule.serialize()
                    )

                else:

                    deleted_css.append(
                        rule.serialize()
                    )

                continue

            # 不明ルールは保持
            purged_css.append(
                rule.serialize()
            )

        # ============================================
        # 文字列化
        # ============================================

        purged_text = "".join(purged_css)
        deleted_text = "".join(deleted_css)

        # ============================================
        # session保存
        # ============================================

        st.session_state["purged_css"] = purged_text
        st.session_state["deleted_css"] = deleted_text

        # ============================================
        # 削減率
        # ============================================

        original_size = len(original_css_content)
        purged_size = len(purged_text)

        reduction = round(
            (1 - purged_size / original_size) * 100,
            1
        )

        st.success(
            f"🎉 完了！ 削減率: {reduction}%"
        )

    except Exception as e:

        st.error(f"❌ エラー: {e}")

# ============================================
# DLボタン
# ============================================

if "purged_css" in st.session_state:

    st.download_button(
        label="⬇ purged.css ダウンロード",
        data=st.session_state["purged_css"],
        file_name="purged.css",
        mime="text/css"
    )

if "deleted_css" in st.session_state:

    st.download_button(
        label="⬇ deleted.css ダウンロード",
        data=st.session_state["deleted_css"],
        file_name="deleted.css",
        mime="text/css"
    )
