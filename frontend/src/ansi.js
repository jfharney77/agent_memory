// The demos print to a terminal, and the browser gets that output verbatim.
// Rather than strip the escape codes, parse the handful the demos actually
// emit so the page keeps the same colour coding as the CLI.

const COLORS = {
  32: 'semantic',
  33: 'procedural',
  35: 'episodic',
  36: 'working',
}

// eslint-disable-next-line no-control-regex
const ESCAPE = /\u001b\[([0-9;]*)m/g

export function parseAnsi(line) {
  const spans = []
  let state = { bold: false, dim: false, color: null }
  let cursor = 0

  const push = (text) => {
    if (text) spans.push({ text, ...state })
  }

  for (const match of line.matchAll(ESCAPE)) {
    push(line.slice(cursor, match.index))
    cursor = match.index + match[0].length
    for (const raw of (match[1] || '0').split(';')) {
      const code = Number(raw || 0)
      if (code === 0) state = { bold: false, dim: false, color: null }
      else if (code === 1) state = { ...state, bold: true }
      else if (code === 2) state = { ...state, dim: true }
      else if (COLORS[code]) state = { ...state, color: COLORS[code] }
    }
  }
  push(line.slice(cursor))
  return spans.length ? spans : [{ text: '', ...state }]
}

export function stripAnsi(line) {
  return line.replace(ESCAPE, '')
}
