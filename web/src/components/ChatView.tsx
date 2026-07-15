import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ChatItem } from '../types'
import ProgressGroup from './ProgressGroup'

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
            return (
              <div key={i} className="my-3 flex justify-start">
                <div className="md max-w-[85%] rounded-2xl rounded-bl-sm border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-800">
                  <ReactMarkdown>{item.content}</ReactMarkdown>
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
