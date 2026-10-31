export const formatTime = (value, date = false) => {
  const parsed = new Date(value)
  if (!value || !Number.isFinite(parsed.getTime())) return '--'
  return parsed.toLocaleString('zh-CN', {
    ...(date ? { year: 'numeric', month: '2-digit', day: '2-digit' } : {}),
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  })
}
export const downloadCsv = (name, headers, rows) => {
  const escape = value => {
    let text = String(value ?? '')
    if (/^[=+@\-\t\r]/.test(text)) text = "'" + text
    return '"' + text.replaceAll('"', '""') + '"'
  }
  const csv = '\uFEFF' + [headers, ...rows].map(row => row.map(escape).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name + '.csv'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
