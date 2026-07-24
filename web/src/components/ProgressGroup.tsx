import { useState } from 'react'
import type { ChatItem, ToolRow } from '../types'

const TOOL_LABELS: Record<string, string> = {
  dispatch_subagent: 'Giao việc cho trợ lý chuyên môn',
  browser__navigate: 'Mở trang web',
  browser__get_state: 'Đọc trang',
  browser__click: 'Click',
  browser__type: 'Gõ text',
  browser__extract: 'Trích xuất dữ liệu',
  browser__search: 'Tìm kiếm web',
  browser__scroll: 'Cuộn trang',
  browser__press_key: 'Nhấn phím',
  browser__go_back: 'Quay lại',
  browser__wait: 'Chờ trang tải',
  browser__wait_for_human: '⏳ Chờ bạn xử lý xác minh trên cửa sổ Chrome',
  browser__type_sensitive: 'Nhập thông tin bảo mật',
  read_skill: 'Đọc hướng dẫn nghiệp vụ',
  run_skill_script: 'Chạy nghiệp vụ',
  write_note: 'Ghi chú',
  read_notes: 'Đọc ghi chú',
  tool_search: 'Tìm công cụ',
}

function ToolCallRow({ row }: { row: ToolRow }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="text-sm">
      <button
        className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-zinc-600 hover:bg-zinc-100"
        onClick={() => setOpen(!open)}
      >
        {row.done ? (
          <span className="text-emerald-600">✓</span>
        ) : (
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-300 border-t-blue-500" />
        )}
        <span>{TOOL_LABELS[row.tool] ?? row.tool}</span>
        <span className="ml-auto text-xs text-zinc-400">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="ml-5 mt-1 space-y-1 rounded bg-zinc-50 p-2 font-mono text-xs text-zinc-500">
          <div className="break-all"><b>{row.tool}</b> {row.argsPreview}</div>
          {row.resultPreview && (
            <div className="whitespace-pre-wrap break-all border-t border-zinc-200 pt-1">
              {row.resultPreview}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Block tiến trình của 1 run: gom row theo agent (event từ subagent hiện trong
 * sub-block "🤖 <tên>"). Xong việc thì tự thu gọn, click mở lại được. */
export default function ProgressGroup({
  item,
}: {
  item: Extract<ChatItem, { kind: 'progress' }>
}) {
  const [expanded, setExpanded] = useState<boolean | null>(null) // null = tự động
  const isOpen = expanded ?? !item.done

  // Gom các row LIÊN TIẾP cùng agent thành 1 nhóm hiển thị
  const groups: { agent: string; rows: ToolRow[] }[] = []
  for (const row of item.rows) {
    const last = groups[groups.length - 1]
    if (last && last.agent === row.agent) last.rows.push(row)
    else groups.push({ agent: row.agent, rows: [row] })
  }

  return (
    <div className="my-2 rounded-xl border border-zinc-200 bg-white px-3 py-2">
      <button
        className="flex w-full items-center gap-2 text-left text-sm font-medium text-zinc-700"
        onClick={() => setExpanded(!isOpen)}
      >
        {item.done ? (
          <span className="text-emerald-600">✓</span>
        ) : (
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-300 border-t-blue-500" />
        )}
        {item.done ? `Đã xử lý ${item.rows.length} bước` : 'Đang xử lý...'}
        <span className="ml-auto text-xs text-zinc-400">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="mt-2 space-y-1">
          {groups.map((g, i) =>
            g.agent === 'main' ? (
              <div key={i} className="space-y-0.5">
                {g.rows.map((row) => <ToolCallRow key={row.id} row={row} />)}
              </div>
            ) : (
              <div key={i} className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-2">
                <p className="mb-1 text-xs font-semibold text-indigo-600">🤖 {g.agent}</p>
                <div className="space-y-0.5">
                  {g.rows.map((row) => <ToolCallRow key={row.id} row={row} />)}
                </div>
              </div>
            ),
          )}
          {item.error && (
            <p className="rounded bg-red-50 px-2 py-1 text-xs text-red-600">{item.error}</p>
          )}
        </div>
      )}
    </div>
  )
}
