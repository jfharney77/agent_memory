import { useCallback, useEffect, useRef, useState } from 'react'
import Output from './Output'
import './App.css'

const EMPTY = { status: 'idle', lines: [], code: null, startedAt: null, endedAt: null }

function elapsed(run, now) {
  if (!run.startedAt) return null
  const end = run.endedAt ?? now
  return ((end - run.startedAt) / 1000).toFixed(0)
}

export default function App() {
  const [demos, setDemos] = useState([])
  const [health, setHealth] = useState(null)
  const [runs, setRuns] = useState({})
  const [now, setNow] = useState(() => Date.now())
  const sources = useRef({})

  useEffect(() => {
    fetch('/api/demos').then((r) => r.json()).then((d) => setDemos(d.demos)).catch(() => {})
    fetch('/api/health').then((r) => r.json()).then(setHealth)
      .catch(() => setHealth({ ok: false, detail: 'The backend is not answering. Start it with: .venv/bin/python -m memory_lab.server' }))
  }, [])

  // Only ticks while something is actually running.
  const anyRunning = Object.values(runs).some((r) => r.status === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [anyRunning])

  useEffect(() => () => Object.values(sources.current).forEach((es) => es.close()), [])

  const patch = useCallback((id, changes) => {
    setRuns((prev) => ({ ...prev, [id]: { ...(prev[id] ?? EMPTY), ...changes } }))
  }, [])

  const start = useCallback((id) => {
    sources.current[id]?.close()
    patch(id, { status: 'running', lines: [], code: null, startedAt: Date.now(), endedAt: null })

    const es = new EventSource(`/api/run/${id}`)
    sources.current[id] = es

    es.addEventListener('line', (e) => {
      const { text } = JSON.parse(e.data)
      setRuns((prev) => {
        const run = prev[id] ?? EMPTY
        return { ...prev, [id]: { ...run, lines: [...run.lines, text] } }
      })
    })
    es.addEventListener('done', (e) => {
      const { code, cancelled } = JSON.parse(e.data)
      es.close()
      delete sources.current[id]
      patch(id, {
        status: cancelled ? 'stopped' : code === 0 ? 'finished' : 'failed',
        code,
        endedAt: Date.now(),
      })
    })
    es.addEventListener('error', () => {
      es.close()
      delete sources.current[id]
      setRuns((prev) => {
        const run = prev[id] ?? EMPTY
        if (run.status !== 'running') return prev
        return {
          ...prev,
          [id]: {
            ...run,
            status: 'failed',
            endedAt: Date.now(),
            lines: [...run.lines, '\u001b[2mThe connection to the backend dropped.\u001b[0m'],
          },
        }
      })
    })
  }, [patch])

  const stop = useCallback((id) => {
    sources.current[id]?.close()
    delete sources.current[id]
    patch(id, { status: 'stopped', endedAt: Date.now() })
  }, [patch])

  return (
    <div className="page">
      <header className="masthead">
        <h1>memory_lab</h1>
        <p>
          Four kinds of agent memory in one LangGraph agent. Each demo below is a
          self-contained story on a throwaway database. Run one and read what it
          prints — the interesting part is always the contrast between what memory
          was read and what got written back.
        </p>
        {health && !health.ok && (
          <div className="warning">
            <strong>Ollama is not reachable.</strong> {health.detail}
          </div>
        )}
        {health?.ok && (
          <p className="meta">
            {health.chat_model} · {health.embed_model} · {health.base_url}
          </p>
        )}
      </header>

      <main>
        {demos.map((demo) => {
          const run = runs[demo.id] ?? EMPTY
          const running = run.status === 'running'
          const secs = elapsed(run, now)
          return (
            <section key={demo.id} className="card">
              <div className="card-head">
                <span className="num">{String(demo.number).padStart(2, '0')}</span>
                <div className="card-title">
                  <h2>{demo.title}</h2>
                  <span className={`chip chip-${demo.kind}`}>{demo.kind}</span>
                </div>
              </div>

              <p className="tagline">{demo.tagline}</p>
              <p className="watch">
                <span className="watch-label">What to watch for</span>
                {demo.watch_for}
              </p>

              <div className="controls">
                <button
                  className="run"
                  onClick={() => start(demo.id)}
                  disabled={running || (health && !health.ok)}
                >
                  {running ? 'Running…' : run.status === 'idle' ? 'Run demo' : 'Run again'}
                </button>
                {running && (
                  <button className="stop" onClick={() => stop(demo.id)}>Stop</button>
                )}
                <span className="status">
                  {running && `${demo.minutes} · ${secs}s elapsed`}
                  {run.status === 'finished' && `Finished in ${secs}s`}
                  {run.status === 'stopped' && `Stopped after ${secs}s`}
                  {run.status === 'failed' && `Exited with code ${run.code ?? '—'}`}
                  {run.status === 'idle' && demo.minutes}
                </span>
              </div>

              {run.lines.length > 0 && <Output run={run} />}
            </section>
          )
        })}
      </main>

      <footer>
        <p>
          The same demos run in a terminal with <code>python demo/run_all.py</code>,
          and the agent itself is a REPL: <code>python -m memory_lab.cli</code>.
        </p>
      </footer>
    </div>
  )
}
