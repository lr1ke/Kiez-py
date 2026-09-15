export function diaryDate(now = new Date()) { return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now); }
export function shiftDate(date: string, days: number) { const d = new Date(`${date}T12:00:00Z`); d.setUTCDate(d.getUTCDate()+days); return d.toISOString().slice(0,10); }
export function prettyDate(date: string, short = false) { return new Intl.DateTimeFormat('en-GB', { day:'numeric', month:short?'short':'long', ...(short?{}:{year:'numeric'}), timeZone:'Europe/Berlin' }).format(new Date(`${date}T12:00:00Z`)); }
export function timeLabel(time: string) { return new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Berlin'}).format(new Date(time)); }
