import { useState } from 'react'
import { completePairing } from '../api/rest'

/** Panel ghép máy: hướng dẫn tải app + ô nhập mã 6 số (PLAN.md 4.3). */
export default function PairingPanel({ onClose }: { onClose: () => void }) {
  const [code, setCode] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'ok' | 'error'>('idle')
  const [deviceName, setDeviceName] = useState('')

  const submit = async () => {
    const clean = code.replace(/\D/g, '')
    if (clean.length !== 6) return
    setStatus('sending')
    try {
      const res = await completePairing(clean)
      setDeviceName(res.device_name)
      setStatus('ok')
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-bold text-zinc-900">Ghép máy của bạn</h2>
          <button className="text-zinc-400 hover:text-zinc-600" onClick={onClose}>✕</button>
        </div>

        {status === 'ok' ? (
          <div className="mt-4">
            <p className="text-sm text-emerald-700">
              ✓ Đã ghép thành công với <b>{deviceName}</b>. Khi app trên máy đó đang mở,
              agent có thể thao tác web ngay trên máy của bạn.
            </p>
            <button
              className="mt-4 w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700"
              onClick={onClose}
            >
              Xong
            </button>
          </div>
        ) : (
          <>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-zinc-600">
              <li>Tải và mở app <b>Personal Agent</b> trên máy tính của bạn (liên hệ quản trị để nhận bản cài).</li>
              <li>App sẽ hiện <b>mã ghép 6 số</b>.</li>
              <li>Nhập mã đó vào ô dưới đây.</li>
            </ol>
            <div className="mt-4 flex gap-2">
              <input
                className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-center text-lg tracking-[0.4em] outline-none focus:border-blue-500"
                placeholder="000000"
                maxLength={7}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
              <button
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                disabled={status === 'sending'}
                onClick={submit}
              >
                Ghép
              </button>
            </div>
            {status === 'error' && (
              <p className="mt-2 text-sm text-red-600">Mã không đúng hoặc đã hết hạn — kiểm tra lại trên app.</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
