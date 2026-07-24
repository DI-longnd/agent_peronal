import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ChatItem } from '../types'
import ProgressGroup from './ProgressGroup'

// Rút các khối ```csv``` trong tin nhắn assistant (skill tra creator xuất CSV
// dạng code block). Trả về danh sách nội dung CSV (đã trim).
function extractCsvBlocks(md: string): string[] {
  const blocks: string[] = []
  const re = /```csv\s*\n([\s\S]*?)```/gi
  let m: RegExpExecArray | null
  while ((m = re.exec(md)) !== null) {
    const csv = m[1].trim()
    if (csv) blocks.push(csv)
  }
  return blocks
}

function downloadCsv(csv: string) {
  // '﻿' (BOM) để Excel mở đúng UTF-8 — tiếng Việt không bị lỗi font.
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tiktok-creators-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function ChatView({ items }: { items: ChatItem[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  // Auto-scroll khi có nội dung mới — TRỪ khi user đang cuộn lên đọc lại
  const onScroll = () => {
    const el = containerRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }
  useEffect(() => {
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [items])

  return (
    <div ref={containerRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4 py-4">
      <div className="mx-auto max-w-3xl">
        {items.length === 0 && (
          <div className="mt-24 text-center text-zinc-400">
            <p className="text-3xl">👋</p>
            <p className="mt-2 text-sm">
              Hãy nhập yêu cầu — ví dụ: <i>"Vào TikTok Affiliate tìm 20 TikToker ngành mỹ phẩm"</i>
            </p>
          </div>
        )}
        {items.map((item, i) => {
          if (item.kind === 'user') {
            return (
              <div key={i} className="my-3 flex justify-end">
                <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white">
                  {item.content}
                </div>
              </div>
            )
          }
          if (item.kind === 'assistant') {
            const csvBlocks = extractCsvBlocks(item.content)
            const csv = csvBlocks.join('\n')
            return (
              <div key={i} className="my-3 flex justify-start">
                <div className="md max-w-[85%] rounded-2xl rounded-bl-sm border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-800">
                  <ReactMarkdown>{item.content}</ReactMarkdown>
                  {csvBlocks.length > 0 && (
                    <div className="mt-2 flex gap-2 border-t border-zinc-100 pt-2">
                      <button
                        onClick={() => downloadCsv(csv)}
                        className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        ⬇ Tải CSV
                      </button>
                      <button
                        onClick={() => navigator.clipboard?.writeText(csv)}
                        className="rounded-md border border-zinc-300 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
                      >
                        📋 Copy
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          }
          return <ProgressGroup key={i} item={item} />
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
