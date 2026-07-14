"""
DOM Scanner — phát hiện element tương tác dựa trên heuristic rules, dịch từ
logic gốc của browser-use (CDP DOMSnapshot) sang Playwright JS evaluate +
getComputedStyle.

Thứ tự kiểm tra (từ cao xuống thấp):
1. JS click listener (React onClick, Vue @click, Angular (click))
2. Interactive HTML tags (a, button, input, select, textarea...)
3. ARIA roles (role=button, role=link, role=combobox...)
4. Interactive attributes (onclick, tabindex, contenteditable)
5. Accessibility tree roles
6. Cursor style (cursor: pointer)
7. Form control detection trong label/span wrappers
8. Search element detection (class/id chứa từ khóa search, magnify...)
9. Icon nhỏ có interactive attributes

Lưu ý quan trọng (khác với tài liệu tham chiếu gốc): ở "Mức 1-2" (không CDP),
không có Accessibility Tree thật, nên `ax_properties` luôn là None khi gọi từ
BrowserTool — nghĩa là element `disabled` KHÔNG bị loại nếu chỉ dựa vào
ax_properties. Vì vậy phải loại trừ dựa trên attribute HTML thật
('disabled', 'aria-disabled') mà JS scan thu thập được.
"""

from __future__ import annotations


class ClickableElementDetector:
    INTERACTIVE_TAGS = {
        'a', 'button', 'input', 'select', 'textarea',
        'details', 'summary', 'option', 'optgroup',
    }
    INTERACTIVE_ROLES = {
        'button', 'link', 'menuitem', 'option', 'radio',
        'checkbox', 'tab', 'textbox', 'combobox', 'slider',
        'spinbutton', 'search', 'searchbox', 'row', 'cell', 'gridcell',
    }
    INTERACTIVE_ATTRIBUTES = {
        'onclick', 'onmousedown', 'onmouseup',
        'onkeydown', 'onkeyup', 'tabindex', 'contenteditable',
    }
    SEARCH_INDICATORS = {
        'search', 'magnify', 'glass', 'lookup',
        'find', 'query', 'search-icon', 'search-btn',
        'search-button', 'searchbox',
    }
    DISABLED_TAGS = {'style', 'script', 'head', 'meta', 'link', 'title'}
    SVG_DECORATIVE = {
        'path', 'rect', 'g', 'circle', 'ellipse', 'line',
        'polyline', 'polygon', 'use', 'defs', 'clipPath',
        'mask', 'pattern', 'image', 'text', 'tspan',
    }

    @classmethod
    def is_interactive(
        cls,
        tag: str,
        attributes: dict[str, str],
        computed_styles: dict[str, str],
        bounding_box: dict | None,
        has_js_click_listener: bool = False,
        ax_properties: dict[str, str | bool] | None = None,
    ) -> bool:
        # === LOẠI TRỪ ===
        if computed_styles:
            if computed_styles.get('display') == 'none':
                return False
            if computed_styles.get('visibility') == 'hidden':
                return False
            try:
                if float(computed_styles.get('opacity', '1')) == 0:
                    return False
            except (ValueError, TypeError):
                pass

        if bounding_box and (bounding_box['width'] == 0 or bounding_box['height'] == 0):
            return False

        if tag in cls.DISABLED_TAGS:
            return False

        if tag in cls.SVG_DECORATIVE:
            return False

        if tag in {'html', 'body'}:
            return False

        # Không có Accessibility Tree thật ở mức này (không CDP) — loại trừ
        # disabled dựa trên attribute HTML thật thay vì ax_properties.
        if 'disabled' in attributes:
            return False
        if attributes.get('aria-disabled') == 'true':
            return False

        # === PHÁT HIỆN INTERACTIVE (ưu tiên cao → thấp) ===
        if has_js_click_listener:
            return True

        if ax_properties and ax_properties.get('disabled') is True:
            return False

        if tag in cls.INTERACTIVE_TAGS:
            return True

        if attributes.get('role') in cls.INTERACTIVE_ROLES:
            return True

        if any(attr in attributes for attr in cls.INTERACTIVE_ATTRIBUTES):
            return True

        if ax_properties:
            if any(ax_properties.get(p) for p in ('checked', 'expanded', 'pressed', 'selected')):
                return True
            if ax_properties.get('focusable') or ax_properties.get('editable'):
                return True
            if ax_properties.get('keyshortcuts'):
                return True

        if computed_styles and computed_styles.get('cursor') == 'pointer':
            return True

        if tag in ('label', 'span'):
            if attributes.get('for'):
                return False

        if any(
            indicator in attributes.get('class', '').lower()
            or indicator in attributes.get('id', '').lower()
            for indicator in cls.SEARCH_INDICATORS
        ):
            return True

        for attr_name, attr_value in attributes.items():
            if attr_name.startswith('data-') and any(
                indicator in attr_value.lower()
                for indicator in cls.SEARCH_INDICATORS
            ):
                return True

        if (
            bounding_box
            and 10 <= bounding_box['width'] <= 50
            and 10 <= bounding_box['height'] <= 50
            and any(attr in attributes for attr in ('class', 'role', 'onclick', 'data-action', 'aria-label'))
        ):
            return True

        return False


def detect_element_from_playwright(el_info: dict) -> bool:
    """Helper: chuyển dict từ Playwright JS evaluate -> gọi ClickableElementDetector."""
    return ClickableElementDetector.is_interactive(
        tag=el_info['tag'],
        attributes=el_info.get('attributes', {}),
        computed_styles=el_info.get('computed_styles', {}),
        bounding_box=el_info.get('rect'),
        has_js_click_listener=el_info.get('has_listener', False),
    )


def filter_nested_elements(elements: list[dict], threshold: float = 0.95) -> list[dict]:
    """Loại element con bị bao trọn bởi element cha (click B == click A)."""
    result = []
    for i, el in enumerate(elements):
        box = el['rect']
        is_nested = False
        for j, other in enumerate(elements):
            if i == j:
                continue
            obox = other['rect']
            if (box['x'] >= obox['x'] and box['y'] >= obox['y'] and
                box['x'] + box['width'] <= obox['x'] + obox['width'] and
                box['y'] + box['height'] <= obox['y'] + obox['height']):
                el_area = box['width'] * box['height']
                other_area = obox['width'] * obox['height']
                if el_area < other_area * threshold:
                    is_nested = True
                    break
        if not is_nested:
            result.append(el)
    return result


# Selector tổng hợp element CÓ THỂ interactive, quét trực tiếp trong trang qua
# Playwright page.evaluate(). Thêm 'aria-disabled' vào important_attrs so với
# bản tham chiếu gốc, để is_interactive() có dữ liệu thật để loại trừ disabled
# (xem docstring đầu file).
INTERACTIVE_SCAN_JS = """
() => {
    const SELECTORS = [
        'a', 'button', 'input', 'select', 'textarea',
        '[role=button]', '[role=link]', '[role=combobox]',
        '[role=textbox]', '[role=checkbox]', '[role=radio]',
        '[role=tab]', '[role=menuitem]', '[role=option]',
        '[role=search]', '[role=searchbox]',
        '[onclick]', '[tabindex]:not([tabindex="-1"])',
        '[contenteditable=true]', 'details', 'summary',
    ].join(',');

    const results = [];
    const all = document.querySelectorAll(SELECTORS);

    for (const el of all) {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);

        if (rect.width === 0 || rect.height === 0) continue;
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        if (parseFloat(style.opacity) === 0) continue;

        if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
        if (rect.right < 0 || rect.left > window.innerWidth) continue;

        let text = '';
        if (el.tagName === 'A' || el.tagName === 'BUTTON') {
            text = (el.textContent || '').trim().slice(0, 100);
        } else if (el.tagName === 'INPUT') {
            text = el.value || el.placeholder || '';
        }

        const attrs = {};
        const important_attrs = [
            'type', 'name', 'placeholder', 'value', 'role',
            'aria-label', 'href', 'title', 'checked', 'disabled',
            'aria-expanded', 'aria-checked', 'aria-pressed', 'aria-disabled',
        ];
        for (const attr of important_attrs) {
            if (el.hasAttribute(attr)) {
                attrs[attr] = el.getAttribute(attr);
            }
        }

        results.push({
            tag: el.tagName.toLowerCase(),
            text: text,
            attributes: attrs,
            rect: {
                x: rect.x, y: rect.y,
                width: rect.width, height: rect.height,
            },
            computed_styles: {
                display: style.display,
                visibility: style.visibility,
                opacity: style.opacity,
                cursor: style.cursor,
            },
        });
    }

    return results.slice(0, 200);
}
"""
