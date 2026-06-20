export function toEAT(utcString: string): string {
  if (!utcString) return '—'
  const d = new Date(utcString)
  const formatted = d.toLocaleString('en-GB', {
    timeZone: 'Africa/Nairobi', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
  return formatted.replace(', ', ' · ') + ' EAT'
}

export function refreshedLabel(isoString: string): string {
  const secs = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (secs < 60) return `Refreshed ${secs}s ago`
  return `Refreshed ${Math.floor(secs / 60)}m ago`
}
