import type { SessionMeta } from '../types'

export default function Sidebar({
  sessions,
  currentId,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: SessionMeta[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50">
      <div className="p-3">
        <button
          className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700"
          onClick={onNew}
        >
          + Cuộc trò chuyện mới
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group mb-1 flex cursor-pointer items-center rounded-lg px-3 py-2 text-sm ${
              s.id === currentId ? 'bg-zinc-200 text-zinc-900' : 'text-zinc-600 hover:bg-zinc-100'
            }`}
            onClick={() => onSelect(s.id)}
          >
            <span className="flex-1 truncate">{s.title}</span>
            <button
              className="ml-1 hidden text-zinc-400 hover:text-red-500 group-hover:block"
              title="Xóa cuộc trò chuyện"
              onClick={(e) => {
                e.stopPropagation()
                if (confirm('Xóa cuộc trò chuyện này?')) onDelete(s.id)
              }}
            >
              🗑
            </button>
          </div>
        ))}
        {sessions.length === 0 && (
          <p className="px-3 py-2 text-xs text-zinc-400">Chưa có cuộc trò chuyện nào.</p>
        )}
      </nav>
    </aside>
  )
}
