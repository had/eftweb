import axios from 'axios'

const fallbackMessage = 'Could not export the stock. Please try again.'

function exportFilename(disposition, stockId) {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)
  const plain = disposition?.match(/filename="([^"]+)"|filename=([^;]+)/i)
  let filename = plain?.[1] || plain?.[2]?.trim()
  if (encoded) {
    try {
      filename = decodeURIComponent(encoded[1])
    } catch {
      // Use the ordinary filename if the encoded header is malformed.
    }
  }
  return filename?.split(/[\\/]/).at(-1) || `stock-${stockId}-export.xlsx`
}

export async function downloadStockExport(stockId, signal) {
  try {
    const response = await axios.get(`/api/stocks/${stockId}/export`, {
      responseType: 'blob',
      signal,
    })
    if (signal.aborted) return
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    try {
      link.href = url
      link.download = exportFilename(response.headers['content-disposition'], stockId)
      document.body.appendChild(link)
      link.click()
    } finally {
      link.remove()
      // Allow the browser to start consuming the blob before revoking it.
      setTimeout(() => URL.revokeObjectURL(url), 0)
    }
  } catch (error) {
    if (signal.aborted || axios.isCancel(error)) return
    let data = error.response?.data
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text())
      } catch {
        data = null
      }
    }
    throw new Error(typeof data?.error === 'string' ? data.error : fallbackMessage)
  }
}
