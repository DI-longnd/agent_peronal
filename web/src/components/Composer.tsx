import { useState } from 'react'

export default function Composer({
  running,
  onSend,
  onStop,
}: {
  running: boolean
  onSend: (message: string) => void
  onStop: () => void
}) {
  const [text, setText] = useState('')

  const submit = () => {
    const message = text.trim()
    if (!message || running) return
    onSend(message)
    setText('')
  }

  return (
    <div className="border-t border-zinc-200 bg-white p-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          className="max-h-40 flex-1 resize-none rounded-xl border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-zinc-50"
          rows={2}
          placeholder={running ? 'Agent đang xử lý...' : 'Nhập yêu cầu... (Enter để gửi, Shift+Enter xuống dòng)'}
          value={text}
          disabled={running}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
        />
        {running ? (
          <button
            className="rounded-xl bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600"
            onClick={onStop}
          >
            ■ Dừng
          </button>
        ) : (
          <button
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            disabled={!text.trim()}
            onClick={submit}
          >
            Gửi
          </button>
        )}
      </div>
    </div>
  )
}
