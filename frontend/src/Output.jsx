import { useEffect, useRef, useState } from 'react'
import { parseAnsi, stripAnsi } from './ansi'

// Follows the tail while new lines arrive, but gets out of the way the moment
// you scroll up to read something -- which, during a two-minute run, you will.
export default function Output({ run }) {
  const box = useRef(null)
  const [following, setFollowing] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (following && box.current) box.current.scrollTop = box.current.scrollHeight
  }, [run.lines, following])

  const onScroll = () => {
    const el = box.current
    if (!el) return
    setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < 40)
  }

  const copy = async () => {
    await navigator.clipboard.writeText(run.lines.map(stripAnsi).join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="output">
      <div className="output-bar">
        <span>{run.lines.length} lines</span>
        {!following && (
          <button className="link" onClick={() => setFollowing(true)}>
            jump to latest
          </button>
        )}
        <button className="link" onClick={copy}>
          {copied ? 'copied' : 'copy as text'}
        </button>
      </div>
      <pre ref={box} onScroll={onScroll} className="output-body">
        {run.lines.map((line, i) => (
          <div key={i} className="output-line">
            {parseAnsi(line).map((span, j) => (
              <span
                key={j}
                className={[
                  span.color ? `c-${span.color}` : '',
                  span.bold ? 'bold' : '',
                  span.dim ? 'dim' : '',
                ].join(' ').trim()}
              >
                {span.text}
              </span>
            ))}
          </div>
        ))}
        {run.status === 'running' && <div className="cursor">▋</div>}
      </pre>
    </div>
  )
}
