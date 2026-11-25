// State machine shared by the four calculators:
//  inputs (autosaved as a draft) -> run on the engine -> result, with an
//  explicit "outdated" flag whenever the inputs change after a run.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { runCalc } from './api'
import { stableKey } from './format'
import { db, drafts } from './store'

export function useCalculator(mode, makeDefaults, toPayload = (x) => x, fromPayload = (p) => ({ ...makeDefaults(), ...p })) {
  const [params, setParams] = useSearchParams()
  const [inputs, setInputs] = useState(() => drafts.get(mode)?.data?.inputs || makeDefaults())
  const [run, setRun] = useState(null) // { result, summary, inputsKey, engine_version, at }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null) // the saved record this session is editing (if any)
  const [restoredDraft, setRestoredDraft] = useState(() => !!drafts.get(mode))
  const abort = useRef(null)

  // open a saved calculation or template via ?load=<id> / ?template=<id>
  useEffect(() => {
    const load = params.get('load')
    const tpl = params.get('template')
    if (load) {
      db.get('calculations', load).then((rec) => {
        if (rec && rec.mode === mode) {
          setInputs(fromPayload(rec.inputs))
          setSaved(rec)
          if (rec.result) setRun({ result: rec.result, summary: rec.summary, inputsKey: stableKey(rec.inputs), engine_version: rec.engineVersion, at: rec.updatedAt, stored: true })
          setRestoredDraft(false)
        }
      })
    } else if (tpl) {
      db.get('templates', tpl).then((t) => {
        if (t && t.mode === mode) {
          setInputs(fromPayload(t.inputs))
          setRun(null)
          setRestoredDraft(false)
        }
      })
    }
    if (load || tpl) {
      params.delete('load')
      params.delete('template')
      setParams(params, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // autosave draft (debounced)
  useEffect(() => {
    const t = setTimeout(() => drafts.set(mode, { inputs }), 600)
    return () => clearTimeout(t)
  }, [mode, inputs])

  const set = useCallback((patch) => setInputs((p) => ({ ...p, ...(typeof patch === 'function' ? patch(p) : patch) })), [])

  const payload = toPayload(inputs)
  const execute = useCallback(async (override) => {
    const inp = override ? toPayload(override) : payload
    abort.current?.abort()
    const ctl = new AbortController()
    abort.current = ctl
    setBusy(true)
    setError(null)
    try {
      const r = await runCalc(mode, inp, ctl.signal)
      setRun({ result: r.result, summary: r.summary, inputsKey: stableKey(inp), engine_version: r.engine_version, at: new Date().toISOString() })
      return r
    } catch (e) {
      if (e.name !== 'AbortError') setError(e)
      return null
    } finally {
      setBusy(false)
    }
  }, [payload, mode]) // eslint-disable-line react-hooks/exhaustive-deps

  const reset = useCallback(() => {
    drafts.clear(mode)
    setInputs(makeDefaults())
    setRun(null)
    setError(null)
    setSaved(null)
    setRestoredDraft(false)
  }, [mode, makeDefaults])

  const loadPayload = useCallback((p) => { setInputs(fromPayload(p)); setRun(null); setSaved(null) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const outdated = !!run && run.inputsKey !== stableKey(payload)
  return { inputs, payload, setInputs, set, run, setRun, busy, error, setError, execute, reset, outdated, saved, setSaved, restoredDraft, setRestoredDraft, loadPayload }
}
