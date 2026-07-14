"""
Paint Order Filter — thuật toán hình học loại bỏ element bị che khuất bởi
element khác vẽ đè lên trên. Duy trì 1 tập hợp rectangle rời nhau (RectUnion);
khi thêm 1 rectangle mới, kiểm tra xem nó có bị "nuốt chửng" bởi các rectangle
đã có không.

LƯU Ý QUAN TRỌNG (khác với browser-use gốc): class này KHÔNG được wire vào
BrowserTool.get_state() mặc định. Lý do: PaintOrderFilter cần giá trị
`paint_order` thật cho mỗi element (browser-use lấy qua CDP DOMSnapshot, phản
ánh đúng stacking context/z-index đã resolve). Ở "Mức 1-2" (không CDP), không
có nguồn nào tính paint_order chính xác — nếu ép dùng thứ tự DOM làm proxy sẽ
cho kết quả sai trong nhiều trường hợp (z-index âm, position khác thường).
Giữ class này sẵn sàng để dùng khi cần (trang có nhiều popup/overlay) và có
nguồn paint_order đáng tin cậy hơn.
"""

from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True, slots=True)
class Rect:
    """Rectangle toán học: (x1,y1) góc trái trên, (x2,y2) góc phải dưới."""
    x1: float
    y1: float
    x2: float
    y2: float

    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def intersects(self, other: 'Rect') -> bool:
        return not (self.x2 <= other.x1 or other.x2 <= self.x1 or
                     self.y2 <= other.y1 or other.y2 <= self.y1)

    def contains(self, other: 'Rect') -> bool:
        return (self.x1 <= other.x1 and self.y1 <= other.y1 and
                self.x2 >= other.x2 and self.y2 >= other.y2)


class RectUnion:
    """Tập hợp các rectangle DISJOINT — kiểm tra 1 rectangle mới có bị che
    hoàn toàn bởi các rectangle đã có trong tập hợp không."""

    _MAX_RECTS = 5000  # Safety cap chống exponential explosion

    def __init__(self):
        self._rects: list[Rect] = []

    def _split_diff(self, a: Rect, b: Rect) -> list[Rect]:
        """Trả về tối đa 4 rectangle = a \\ b (phần của a không nằm trong b)."""
        parts = []
        if a.y1 < b.y1:
            parts.append(Rect(a.x1, a.y1, a.x2, b.y1))
        if b.y2 < a.y2:
            parts.append(Rect(a.x1, b.y2, a.x2, a.y2))
        y_lo = max(a.y1, b.y1)
        y_hi = min(a.y2, b.y2)
        if a.x1 < b.x1:
            parts.append(Rect(a.x1, y_lo, b.x1, y_hi))
        if b.x2 < a.x2:
            parts.append(Rect(b.x2, y_lo, a.x2, y_hi))
        return parts

    def contains(self, r: Rect) -> bool:
        """True nếu r bị che hoàn toàn bởi union hiện tại."""
        if not self._rects:
            return False

        stack = [r]
        for s in self._rects:
            new_stack = []
            for piece in stack:
                if s.contains(piece):
                    continue
                if piece.intersects(s):
                    new_stack.extend(self._split_diff(piece, s))
                else:
                    new_stack.append(piece)
            if not new_stack:
                return True
            stack = new_stack
        return False

    def add(self, r: Rect) -> bool:
        """Thêm r nếu nó chưa bị che. Returns True nếu union tăng trưởng."""
        if len(self._rects) >= self._MAX_RECTS:
            return False

        if self.contains(r):
            return False

        pending = [r]
        i = 0
        while i < len(self._rects):
            s = self._rects[i]
            new_pending = []
            for piece in pending:
                if piece.intersects(s):
                    new_pending.extend(self._split_diff(piece, s))
                else:
                    new_pending.append(piece)
            pending = new_pending
            i += 1

        self._rects.extend(pending)
        return True


class PaintOrderFilter:
    """Loại bỏ element dựa trên paint order (thứ tự vẽ).

    Nguyên lý:
    - Mỗi element có paint_order: số càng cao -> vẽ sau -> nằm trên
    - Duyệt từ paint_order cao nhất xuống thấp nhất
    - Với mỗi element: nếu rectangle của nó bị che hoàn toàn -> đánh dấu ignored
    - Bỏ qua element có opacity < 0.8 hoặc background-color transparent
      (vì chúng không thực sự che các element khác)
    """

    def __init__(self):
        self._union = RectUnion()

    def filter(self, elements: list[dict]) -> list[dict]:
        groups: dict[int, list[dict]] = defaultdict(list)
        for el in elements:
            po = el.get('paint_order', 0)
            groups[po].append(el)

        for paint_order in sorted(groups.keys(), reverse=True):
            for el in groups[paint_order]:
                r = el['rect']
                rect = Rect(r['x'], r['y'], r['x'] + r['width'], r['y'] + r['height'])

                if self._union.contains(rect):
                    el['ignored_by_paint_order'] = True

                styles = el.get('computed_styles', {})
                bg_color = styles.get('background-color', 'rgba(0, 0, 0, 0)')
                try:
                    opacity = float(styles.get('opacity', '1'))
                except (ValueError, TypeError):
                    opacity = 1.0

                if bg_color == 'rgba(0, 0, 0, 0)' or opacity < 0.8:
                    continue

                self._union.add(rect)

        return [el for el in elements if not el.get('ignored_by_paint_order')]
