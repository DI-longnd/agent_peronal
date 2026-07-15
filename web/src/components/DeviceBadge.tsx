/** Chấm trạng thái: kết nối WS tới server + máy khách (companion app) online chưa. */
export default function DeviceBadge({
  connected,
  device,
  onPairClick,
}: {
  connected: boolean
  device: { online: boolean; name: string | null }
  onPairClick: () => void
}) {
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="flex items-center gap-1.5 text-zinc-500" title="Kết nối tới server">
        <span
          className={`inline-block h-2 w-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`}
        />
        {connected ? 'Server' : 'Mất kết nối'}
      </span>
      <button
        className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1 text-zinc-600 hover:bg-zinc-50"
        onClick={onPairClick}
        title={device.name ? 'Bấm để ghép máy khác' : 'Bấm để ghép máy của bạn'}
      >
        <span
          className={`inline-block h-2 w-2 rounded-full ${device.online ? 'bg-emerald-500' : 'bg-red-500'}`}
        />
        {device.name ? `Máy: ${device.name}` : 'Chưa ghép máy'}
      </button>
    </div>
  )
}
