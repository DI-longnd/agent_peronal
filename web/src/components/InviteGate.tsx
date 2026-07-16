import { useState } from 'react'
import { saveToken } from '../api/rest'

/** Màn hình khi chưa có invite token (hoặc token bị từ chối).
 * Khách bình thường vào bằng link mời nên không thấy màn này —
 * ô dán link chỉ là đường dự phòng. */
export default function InviteGate({ failed }: { failed: boolean }) {
  const [value, setValue] = useState('')

  const submit = () => {
    // Xóa MỌI khoảng trắng (kể cả xuống dòng giữa chuỗi) — link copy từ
    // terminal/chat hay bị wrap dòng làm token đứt đôi.
    const raw = value.replace(/\s+/g, '')
    if (!raw) return
    // Chấp nhận cả link đầy đủ lẫn token trần
    try {
      const url = new URL(raw)
      const invite = url.searchParams.get('invite')
      saveToken(invite ?? raw)
    } catch {
      saveToken(raw)
    }
    window.location.reload()
  }

  return (
    <div className="flex h-screen items-center justify-center bg-zinc-100">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-bold text-zinc-900">Personal Agent</h1>
        {failed ? (
          <p className="mt-3 text-sm text-red-600">
            Link mời không hợp lệ hoặc đã bị thu hồi. Liên hệ người quản trị để nhận link mới.
          </p>
        ) : (
          <p className="mt-3 text-sm text-zinc-600">
            Bạn cần <b>link mời</b> để sử dụng. Hãy mở đúng đường link được gửi cho bạn —
            hoặc dán link/mã mời vào ô dưới đây.
          </p>
        )}
        <div className="mt-5 flex gap-2">
          <input
            className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
            placeholder="Dán link mời vào đây..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          <button
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            onClick={submit}
          >
            Vào
          </button>
        </div>
      </div>
    </div>
  )
}
