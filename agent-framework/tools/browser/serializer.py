"""
DOM Serializer — đóng gói danh sách interactive element thành cây text cho LLM
đọc, kèm selector_map (index -> element dict) để browser__click/browser__type
tra ngược ra tọa độ thật.
"""

from __future__ import annotations


class DOMSerializer:
    """Serialize DOM state thành text cho LLM.

    Output format:
        URL: https://example.com
        Title: Example Page

        Interactive elements:
          [1] <a href=/page1>Link text</a>
          [2] <button type=submit>Click me</button>
          [3] <input type=text placeholder=Search />
    """

    def __init__(self, max_elements: int = 100):
        self.max_elements = max_elements
        self._counter = 0
        self._selector_map: dict[int, dict] = {}

    def serialize(self, elements: list[dict], url: str, title: str) -> tuple[str, dict]:
        self._counter = 0
        self._selector_map = {}

        lines = []
        lines.append(f"URL: {url}")
        lines.append(f"Title: {title}")
        lines.append("")
        lines.append("Interactive elements:")

        for el in elements[:self.max_elements]:
            self._counter += 1
            idx = self._counter
            self._selector_map[idx] = el
            lines.append(self._format_element(idx, el))

        return '\n'.join(lines), self._selector_map

    def _format_element(self, idx: int, el: dict) -> str:
        tag = el['tag']
        attrs = el.get('attributes', {})
        text = el.get('text', '')[:80]

        attr_parts = []
        priority_attrs = ['type', 'placeholder', 'role', 'name', 'id', 'aria-label',
                          'href', 'value', 'checked', 'disabled']
        for attr in priority_attrs:
            if attr in attrs:
                v = str(attrs[attr])[:50]
                attr_parts.append(f'{attr}="{v}"')

        attr_str = ' '.join(attr_parts)

        if tag in ('input', 'img', 'br', 'hr'):
            line = f"[{idx}] <{tag} {attr_str} />"
        else:
            # text phải nằm trong output — đây là cách duy nhất LLM biết
            # link/button ghi chữ gì khi use_vision=False (không có screenshot).
            line = f"[{idx}] <{tag} {attr_str}>{text}</{tag}>"

        scroll_info = el.get('scroll_info')
        if scroll_info:
            pages_below = scroll_info.get('pages_below', 0)
            if pages_below > 0:
                line = f"|SCROLL| {line} ({pages_below:.1f} pages below)"

        if el.get('is_new'):
            line = f"*{line}"

        return line
