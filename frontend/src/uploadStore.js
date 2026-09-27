// Carries a locally-selected file between the Home upload panel and the Analyze page.
let pending = null
export function setPendingFile(file) { pending = file }
export function takePendingFile() { const f = pending; pending = null; return f }
