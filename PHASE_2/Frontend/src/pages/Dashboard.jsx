import React, {useState, useEffect} from 'react'
import { api } from '../api/client'
import MetricsRow from './components/MetricsRow'
const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'risk', label: 'Risk' },
  { key: 'critical-path', label: 'Critical Path' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'actions', label: 'Actions' },
]

function MetricCard({label, value}){
  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-900 p-4">
      <div className="text-sm uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-3 text-2xl font-semibold text-white">{value}</div>
    </div>
  )
}

function OverviewPage({session, metrics}){
  const summary = session.project_summary
  return (
    <div>
      <HeroBanner session={session} />
      <MonteCarloStrip session={session} />
      <ProjectSummaryCard session={session} />
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Project Overview</p>
            <h2 className="mt-2 text-3xl font-extrabold text-white">{summary.project_name}</h2>
            <p className="mt-2 text-sm text-slate-400">{summary.customer} · Managed by {summary.project_manager}</p>
          </div>
          <div className="rounded-3xl bg-slate-950 px-4 py-3 text-sm text-slate-300">Session {summary.session_id}</div>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard label="Target sprints" value={`${summary.completed_sprints}/${summary.total_sprints}`} />
          <MetricCard label="Work items" value={summary.total_work_items} />
          <MetricCard label="Dependencies" value={summary.total_dependencies} />
          <MetricCard label="Blockers" value={summary.total_blockers} />
          <MetricsRow metrics={metrics} />
        </div>
      </section>
    </div>
  )
}

function HeroBanner({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [mc, setMc] = useState(null)
  const sessionId = session?.project_summary?.session_id || ''

  const fetchData = async ()=>{
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try{
      const [f, m] = await Promise.all([api.forecast(sessionId), api.monteCarlo(sessionId)])
      setForecast(f?.forecast ?? f)
      setMc(m?.monte_carlo ?? m)
      setLoading(false)
    }catch(err){
      setError(err)
      setLoading(false)
    }
  }

  useEffect(()=>{
    fetchData()
  }, [sessionId])

  // Loading state
  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Project status</p>
            <h2 className="mt-2 text-3xl font-extrabold text-white">Loading project status…</h2>
            <p className="mt-2 text-sm text-slate-400">Fetching forecast and Monte Carlo results</p>
          </div>
        </div>
      </section>
    )
  }

  // Error state
  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Project status</p>
            <h2 className="mt-2 text-3xl font-extrabold text-rose-200">Status unavailable</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Failed to load forecast or Monte Carlo results'}</p>
          </div>
          <div>
            <button onClick={fetchData} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
          </div>
        </div>
      </section>
    )
  }

  // Empty state (no data)
  if(!forecast && !mc){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Project status</p>
        <h2 className="mt-2 text-3xl font-extrabold text-white">No forecast data</h2>
        <p className="mt-2 text-sm text-slate-400">Forecast and Monte Carlo results are not available for this session.</p>
      </section>
    )
  }

  // Normal display
  const onTrack = forecast && typeof forecast.on_track === 'boolean' ? forecast.on_track : null
  const prob = mc && mc.on_time_probability !== undefined ? Math.round(mc.on_time_probability * 100) : null
  const risk = mc && mc.on_time_risk_level ? mc.on_time_risk_level : null
  const expected = forecast && typeof forecast.expected_delay_days === 'number' ? Math.round(forecast.expected_delay_days) : null

  const statusLabel = onTrack === true ? 'ON TRACK' : 'AT RISK'
  const statusColor = onTrack === true ? 'text-emerald-400' : 'text-amber-400'

  let delayText = null
  if(expected !== null){
    if(expected < 0){
      delayText = `${Math.abs(expected)} days ahead of schedule`
    }else if(expected === 0){
      delayText = `On schedule`
    }else{
      delayText = `+${expected} days`
    }
  }

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-4">
          <div>
            <div className={`text-2xl font-extrabold ${statusColor}`}>{statusLabel}</div>
            {delayText && onTrack === false && <div className="mt-1 text-sm text-rose-300">Predicted delay: <span className="font-semibold text-rose-200">{delayText}</span></div>}
            {delayText && onTrack === true && <div className="mt-1 text-sm text-slate-400">{delayText}</div>}
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="text-sm uppercase tracking-[0.2em] text-slate-400">On-time probability</div>
            <div className="mt-1 text-4xl font-extrabold text-white">{prob !== null ? `${prob}%` : '—'}</div>
            {risk && <div className="mt-1 text-sm text-slate-400">{risk}</div>}
          </div>
        </div>
      </div>
    </section>
  )
}

function formatDate(iso){
  if(!iso) return '—'
  try{
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
  }catch(e){ return iso }
}

function daysBetween(a,b){
  const msPerDay = 1000*60*60*24
  return Math.round((b - a)/msPerDay)
}

function ProjectSummaryCard({session}){
  const summary = session.project_summary || {}
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return () => { mounted = false }
    }
    setLoading(true)
    api.forecast(sessionId).then(f=>{ if(mounted){ setForecast(f?.forecast ?? f); setLoading(false) }}).catch(err=>{ if(mounted){ setError(err); setLoading(false) }})
    return ()=>{ mounted=false }
  }, [sessionId])

  if(loading) return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
      <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Project summary</p>
      <div className="mt-2 text-sm text-slate-400">Loading summary…</div>
    </section>
  )

  if(error) return (
    <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6">
      <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Project summary</p>
      <div className="mt-2 text-sm text-rose-300">{error.message || 'Failed to load forecast'}</div>
    </section>
  )

  // fields
  const startIso = summary.start_date
  const targetIso = summary.target_end_date || (forecast && forecast.target_end_date)
  const expectedIso = forecast && forecast.expected_finish_date

  // compute days elapsed/remaining
  const today = new Date()
  const startDate = startIso ? new Date(startIso) : null
  const targetDate = targetIso ? new Date(targetIso) : null
  let daysElapsed = null
  if(forecast && forecast.delay_breakdown && typeof forecast.delay_breakdown.days_elapsed === 'number'){
    daysElapsed = forecast.delay_breakdown.days_elapsed
  }else if(startDate){
    daysElapsed = daysBetween(startDate, today)
  }
  let daysRemaining = null
  if(forecast && forecast.delay_breakdown && typeof forecast.delay_breakdown.remaining_days_total === 'number'){
    daysRemaining = forecast.delay_breakdown.remaining_days_total
  }else if(targetDate){
    daysRemaining = daysBetween(today, targetDate)
  }

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
      <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Project summary</p>
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <div className="text-lg font-semibold text-white">{summary.project_name}</div>
          <div className="mt-1 text-sm text-slate-400">{summary.customer} · Managed by {summary.project_manager}</div>
        </div>
        <div className="space-y-1">
          <div className="text-sm text-slate-400">Start date</div>
          <div className="text-white font-medium">{formatDate(startIso)}</div>

          <div className="text-sm text-slate-400 mt-2">Target end date</div>
          <div className="text-white font-medium">{formatDate(targetIso)}</div>

          <div className="text-sm text-slate-400 mt-2">Expected finish</div>
          <div className="text-white font-medium">{formatDate(expectedIso)}</div>
        </div>
      </div>

      <div className="mt-4 flex gap-6">
        <div className="rounded-lg bg-slate-800/40 px-4 py-2">
          <div className="text-sm text-slate-400">Days elapsed</div>
          <div className="text-white font-semibold">{daysElapsed !== null ? `${daysElapsed} days` : '—'}</div>
        </div>
        <div className="rounded-lg bg-slate-800/40 px-4 py-2">
          <div className="text-sm text-slate-400">Days remaining</div>
          <div className="text-white font-semibold">{daysRemaining !== null ? `${daysRemaining} days` : '—'}</div>
        </div>
      </div>
    </section>
  )
}

function MonteCarloStrip({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mc, setMc] = useState(null)

  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return () => { mounted = false }
    }
    setLoading(true)
    setError(null)
    api.monteCarlo(sessionId)
      .then(response=>{ if(mounted){ setMc(response?.monte_carlo ?? response); setLoading(false) }})
      .catch(err=>{ if(mounted){ setError(err); setLoading(false) }})
    return ()=>{ mounted = false }
  }, [sessionId])

  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Monte Carlo simulation</p>
        <p className="mt-3 text-sm text-slate-400">Loading simulated finish-date range…</p>
      </section>
    )
  }

  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20 mt-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Monte Carlo simulation</p>
            <h2 className="mt-2 text-2xl font-semibold text-rose-100">Unable to load simulations</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Monte Carlo data could not be retrieved.'}</p>
          </div>
          <button onClick={()=>{ setLoading(true); setError(null); api.monteCarlo(sessionId).then(response=>{ setMc(response?.monte_carlo ?? response); setLoading(false)}).catch(err=>{ setError(err); setLoading(false) }) }} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
        </div>
      </section>
    )
  }

  if(!mc){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Monte Carlo simulation</p>
        <p className="mt-3 text-sm text-slate-400">No simulation results are available for this session.</p>
      </section>
    )
  }

  const timeline = [
    { label: 'Best case (P10)', date: mc.best_case_finish_date, color: 'bg-emerald-500' },
    { label: 'Most likely (P50)', date: mc.most_likely_finish_date, color: 'bg-sky-500' },
    { label: 'P80', date: mc.p80_finish_date, color: 'bg-amber-500' },
    { label: 'P90', date: mc.p90_finish_date, color: 'bg-rose-500' },
  ]

  const formatDateLabel = (iso) => {
    if(!iso) return '—'
    try{ return new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) }catch(e){ return iso }
  }

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Monte Carlo simulation</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Simulated finish-date range</h2>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Based on {mc.simulation_count.toLocaleString()} simulated outcomes.</p>
        </div>
        <div className="rounded-3xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-300">
          {mc.simulation_count.toLocaleString()} simulations
        </div>
      </div>

      <div className="mt-6 space-y-4">
        <div className="relative h-14 rounded-full bg-slate-800/80 p-3">
          <div className="absolute inset-y-3 left-0 right-0 rounded-full bg-slate-700/60" />
          {timeline.map((point, index)=>(
            <div key={point.label} className="absolute top-0 grid h-full w-1/5 place-items-center" style={{ left: `${index * 24}%` }}>
              <div className={`h-7 w-7 rounded-full ${point.color} border border-slate-900 shadow-lg`} />
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          {timeline.map(point => (
            <div key={point.label} className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4 text-center">
              <div className="text-sm uppercase tracking-[0.2em] text-slate-400">{point.label}</div>
              <div className="mt-2 text-lg font-semibold text-white">{formatDateLabel(point.date)}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function DelayDiagnosis({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [forecast, setForecast] = useState(null)

  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return () => { mounted = false }
    }
    setLoading(true)
    setError(null)
    api.forecast(sessionId)
      .then(f=>{ if(mounted){ setForecast(f?.forecast ?? f); setLoading(false) }})
      .catch(err=>{ if(mounted){ setError(err); setLoading(false) }})
    return ()=>{ mounted = false }
  }, [sessionId])

  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Delay diagnosis</p>
        <p className="mt-3 text-sm text-slate-400">Loading delay diagnostics…</p>
      </section>
    )
  }

  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20 mt-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Delay diagnosis</p>
            <h2 className="mt-2 text-2xl font-semibold text-rose-100">Unable to load diagnostics</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Forecast diagnostics could not be retrieved.'}</p>
          </div>
          <button onClick={()=>{ setLoading(true); setError(null); api.forecast(sessionId).then(f=>{ setForecast(f?.forecast ?? f); setLoading(false)}).catch(err=>{ setError(err); setLoading(false) }) }} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
        </div>
      </section>
    )
  }

  if(!forecast || !forecast.schedule_diagnostics){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Delay diagnosis</p>
        <p className="mt-3 text-sm text-slate-400">No schedule diagnostics are available for this session.</p>
      </section>
    )
  }

  const diag = forecast.schedule_diagnostics
  const factors = [
    { key: 'base', label: 'Base schedule', value: diag.base_schedule_days, color: 'bg-emerald-500' },
    { key: 'spillover', label: 'Spillover impact', value: diag.spillover_days, color: 'bg-amber-500' },
    { key: 'blocker', label: 'Blocker impact', value: diag.blocker_days, color: 'bg-rose-500' },
    { key: 'critical', label: 'Critical path impact', value: diag.critical_path_days, color: 'bg-sky-500' },
  ]
  const maxValue = Math.max(...factors.map(item => Math.max(0, item.value || 0)), 1)
  const dominant = factors.reduce((best, item) => item.value > (best.value || 0) ? item : best, factors[0])
  const scopeGrowth = typeof forecast.scope_growth_percent === 'number' && forecast.scope_growth_percent > 0.01

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20 mt-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Delay diagnosis</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Why the schedule is shifted</h2>
          <p className="mt-2 text-sm text-slate-400">Breakdown of the forecast drivers affecting completion.</p>
        </div>
        <div className="rounded-3xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-300">
          Dominant driver: <span className="font-semibold text-white">{dominant.label}</span>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {factors.map(item => {
          const width = Math.round(((item.value || 0) / maxValue) * 100)
          return (
            <div key={item.key} className="space-y-2">
              <div className="flex items-center justify-between text-sm text-slate-300">
                <span>{item.label}</span>
                <span className="font-semibold text-white">{typeof item.value === 'number' ? `${item.value.toFixed(1)}d` : '—'}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-800">
                <div className={`${item.color} h-3 rounded-full`} style={{ width: `${width}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      {scopeGrowth && (
        <div className="mt-6 rounded-3xl border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-sm uppercase tracking-[0.3em] text-amber-300">Scope growth</p>
          <p className="mt-2 text-sm text-slate-100">{forecast.scope_growth_message || `Scope has grown by ${(forecast.scope_growth_percent * 100).toFixed(0)}% beyond the original estimate.`}</p>
        </div>
      )}

      {forecast.forecast_vs_montecarlo_note && (
        <div className="mt-4 text-sm text-slate-500">Note: {forecast.forecast_vs_montecarlo_note}</div>
      )}
    </section>
  )
}

function ForecastPage({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [mc, setMc] = useState(null)
  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return () => { mounted = false }
    }
    setLoading(true)
    setError(null)
    Promise.all([api.forecast(sessionId), api.monteCarlo(sessionId)])
      .then(([f, m])=>{ if(mounted){ setForecast(f?.forecast ?? f); setMc(m?.monte_carlo ?? m); setLoading(false) }})
      .catch(err=>{ if(mounted){ setError(err); setLoading(false) }})
    return ()=>{ mounted = false }
  }, [sessionId])

  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Forecast</p>
        <p className="mt-3 text-sm text-slate-400">Loading forecast and Monte Carlo details…</p>
      </section>
    )
  }

  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Forecast</p>
            <h2 className="mt-2 text-2xl font-semibold text-rose-100">Unable to load forecast data</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Failed to retrieve forecast or Monte Carlo results.'}</p>
          </div>
          <button onClick={()=>{ setLoading(true); setError(null); Promise.all([api.forecast(sessionId), api.monteCarlo(sessionId)]).then(([f,m])=>{ setForecast(f?.forecast ?? f); setMc(m?.monte_carlo ?? m); setLoading(false)}).catch(err=>{ setError(err); setLoading(false) }) }} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
        </div>
      </section>
    )
  }

  if(!forecast && !mc){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Forecast</p>
        <p className="mt-3 text-sm text-slate-400">No forecast or Monte Carlo results are available for this session.</p>
      </section>
    )
  }

  // Percentile timeline
  const stats = mc && mc.statistics ? mc.statistics : null
  const percentiles = stats ? [10,25,50,75,80,90,95].map(p => ({ p, iso: stats[`percentile_${p}`] })) : []
  const minIso = stats && stats.percentile_10 ? new Date(stats.percentile_10) : null
  const maxIso = stats && stats.percentile_95 ? new Date(stats.percentile_95) : null
  const rangeMs = minIso && maxIso ? (maxIso - minIso) : null

  const formatDateLabel = (iso) => { if(!iso) return '—'; try{ return new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) }catch(e){ return iso } }

  // Effort breakdown stats
  const eb = forecast && forecast.effort_breakdown ? forecast.effort_breakdown : null
  const effortItems = eb ? [
    { key: 'raw', label: 'Raw remaining effort', value: eb.raw_remaining_effort_hours, color: 'bg-emerald-500', description: 'Raw remaining effort from open work.' },
    { key: 'critical', label: 'Critical path remaining', value: eb.critical_path_remaining_hours, color: 'bg-sky-500', description: 'Remaining effort on the critical path.' },
    { key: 'spillover', label: 'Spillover penalty (equivalent hours)', value: eb.spillover_penalty_hours, color: 'bg-amber-400', description: 'Equivalent hours from spillover impact.' },
    { key: 'blocker', label: 'Blocker penalty (equivalent hours)', value: eb.blocker_penalty_hours, color: 'bg-rose-500', description: 'Equivalent hours from blocker impact.' },
  ] : []
  const adjusted = eb ? eb.forecast_adjusted_effort_hours : null

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Forecast</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Finish-date distribution</h2>
            <p className="mt-2 text-sm text-slate-400">Monte Carlo percentiles show likely completion windows.</p>
          </div>
          <div className="rounded-3xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-300">
            {mc && mc.simulation_count ? `${mc.simulation_count.toLocaleString()} simulations` : 'Simulations'}
          </div>
        </div>

        <div className="mt-6">
          <div className="relative h-8 rounded-full bg-slate-800">
            {minIso && maxIso && percentiles.map(pt => {
              const iso = pt.iso
              const left = iso ? Math.round(((new Date(iso) - minIso) / rangeMs) * 100) : 0
              const color = pt.p === 50 ? 'bg-sky-500' : (pt.p <= 25 ? 'bg-emerald-500' : pt.p >= 90 ? 'bg-rose-500' : 'bg-amber-400')
              return (
                <div key={pt.p} className="absolute top-0 h-8 w-0">
                  <div className={`absolute -top-3 h-14 w-0`} style={{ left: `${left}%` }}>
                    <div className={`h-3 w-3 ${color} rounded-full border border-slate-900`} />
                  </div>
                </div>
              )
            })}
            <div className="absolute inset-0 flex items-end justify-between px-2 text-xs text-slate-400">
              <div>{formatDateLabel(stats?.percentile_10)}</div>
              <div>{formatDateLabel(stats?.percentile_95)}</div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {percentiles.map(pt => (
              <div key={pt.p} className="rounded-3xl border border-slate-700 bg-slate-950/80 p-3 text-center">
                <div className="text-sm uppercase tracking-[0.2em] text-slate-400">P{pt.p}</div>
                <div className="mt-2 text-lg font-semibold text-white">{formatDateLabel(pt.iso)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Statistics</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Mean & median delay</h2>
            <p className="mt-2 text-sm text-slate-400">Comparison of mean and median delay vs target.</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4 text-center">
              <div className="text-sm text-slate-400">Mean delay</div>
              <div className="mt-1 text-2xl font-semibold text-white">{stats?.mean_delay_days !== undefined ? `${stats.mean_delay_days.toFixed(1)}d` : '—'}</div>
            </div>
            <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4 text-center">
              <div className="text-sm text-slate-400">Median delay</div>
              <div className="mt-1 text-2xl font-semibold text-white">{stats?.median_delay_days !== undefined ? `${stats.median_delay_days.toFixed(1)}d` : '—'}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Effort breakdown</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Effort breakdown</h2>
            <p className="mt-2 text-sm text-slate-400">Individual effort components and the forecast-adjusted effort value.</p>
          </div>
          <div className="text-sm text-slate-400">
            Forecast-adjusted effort:
            <div className="mt-1 font-semibold text-white">{adjusted ? `${Math.round(adjusted)}h` : '—'}</div>
            <div className="mt-1 text-xs text-slate-500">Raw remaining + critical path uplift only</div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {effortItems.map(item => (
            <div key={item.key} className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm text-slate-400">{item.label}</div>
                  <div className="mt-2 text-3xl font-semibold text-white">{item.value !== undefined ? `${Math.round(item.value)}h` : '—'}</div>
                </div>
                <div className={`h-4 w-4 rounded-full ${item.color}`} />
              </div>
              <div className="mt-3 text-xs leading-5 text-slate-500">{item.description}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function ActionsPage({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [recs, setRecs] = useState([])
  const [simulatingId, setSimulatingId] = useState(null)
  const [simulationResult, setSimulationResult] = useState(null)
  const [selected, setSelected] = useState([])
  const [scenarioLoading, setScenarioLoading] = useState(false)

  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return () => { mounted = false }
    }
    setLoading(true)
    api.recommendations(sessionId).then(resp=>{ if(mounted){ setRecs(resp.recommendations || resp || []); setLoading(false) }}).catch(err=>{ if(mounted){ setError(err); setLoading(false) }})
    return ()=> mounted = false
  }, [sessionId])

  const simulate = async (recommendation_id) => {
    setSimulatingId(recommendation_id)
    setSimulationResult(null)
    try{
      const body = { recommendation_id }
      const resp = await api.simulateRecommendation(body, sessionId)
      setSimulationResult(resp.simulation_result || resp)
    }catch(err){
      setError(err)
    }finally{
      setSimulatingId(null)
    }
  }

  const runScenario = async () => {
    if(selected.length === 0) return
    setScenarioLoading(true)
    setError(null)
    try{
      const resp = await api.simulateScenario({ recommendation_ids: selected.slice(0,3) }, sessionId)
      setSimulationResult(resp.simulation_result || resp)
    }catch(err){ setError(err) }finally{ setScenarioLoading(false) }
  }

  const toggleSelect = (id) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x=>x!==id) : [...prev.slice(-2), id])
  }

  if(loading) return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
      <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Actions</p>
      <p className="mt-3 text-sm text-slate-400">Loading recommendations…</p>
    </section>
  )

  if(error) return (
    <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20">
      <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Actions</p>
      <p className="mt-2 text-sm text-rose-300">{error.message || 'Failed to load recommendations.'}</p>
    </section>
  )

  if(!recs || recs.length === 0) return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
      <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Actions</p>
      <p className="mt-3 text-sm text-slate-400">No recommendations are available for this session.</p>
    </section>
  )

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Actions</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Recommendations</h2>
            <p className="mt-2 text-sm text-slate-400">Select recommendations to simulate their effect on delivery.</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={runScenario} disabled={selected.length===0 || scenarioLoading} className="rounded-2xl border border-emerald-500 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 disabled:opacity-50">{scenarioLoading ? 'Simulating selection…' : `Simulate selection (${selected.length})`}</button>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          {recs.map(rec => (
            <div key={rec.recommendation_id} className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{rec.impact_level}</div>
                  <h3 className="mt-1 text-lg font-semibold text-white">{rec.action}</h3>
                  <div className="mt-2 text-sm text-slate-300">{rec.impact_summary}</div>
                  <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 text-sm text-slate-400">
                    <div>Effort: <span className="text-white font-semibold">{rec.implementation_effort}</span></div>
                    <div>Confidence: <span className="text-white font-semibold">{rec.confidence}</span></div>
                    <div>Priority: <span className="text-white font-semibold">{Math.round(rec.priority_score)}</span></div>
                    <div>Impact: <span className="text-white font-semibold">{rec.impact_confidence || '—'}</span></div>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <label className="inline-flex items-center gap-2 text-sm text-slate-400">
                    <input type="checkbox" checked={selected.includes(rec.recommendation_id)} onChange={()=>toggleSelect(rec.recommendation_id)} />
                    <span>Select</span>
                  </label>
                  <button onClick={()=>simulate(rec.recommendation_id)} disabled={!!simulatingId} className="rounded-2xl border border-sky-500 bg-sky-500/10 px-3 py-1 text-sm font-semibold text-sky-200">{simulatingId===rec.recommendation_id ? 'Simulating…' : 'Simulate this fix'}</button>
                </div>
              </div>

              {simulationResult && simulationResult.recommendation_id === rec.recommendation_id && (
                <div className="mt-4 rounded-2xl border border-emerald-500 bg-emerald-500/5 p-3">
                  <div className="text-sm text-slate-300">Simulation result</div>
                  <div className="mt-2 grid grid-cols-3 gap-3 text-sm">
                    <div className="rounded-2xl bg-slate-900 p-2 text-center">
                      <div className="text-xs text-slate-400">On-time probability</div>
                      <div className="text-lg font-semibold text-white">{Math.round((simulationResult.after_probability||0)*100)}% <span className="text-slate-400">(was {Math.round((simulationResult.baseline_probability||0)*100)}%)</span></div>
                    </div>
                    <div className="rounded-2xl bg-slate-900 p-2 text-center">
                      <div className="text-xs text-slate-400">Expected delay</div>
                      <div className="text-lg font-semibold text-white">{(simulationResult.after_delay_days||0).toFixed(1)}d <span className="text-slate-400">(was {(simulationResult.baseline_delay_days||0).toFixed(1)}d)</span></div>
                    </div>
                    <div className="rounded-2xl bg-slate-900 p-2 text-center">
                      <div className="text-xs text-slate-400">Risk score</div>
                      <div className="text-lg font-semibold text-white">{Math.round(simulationResult.after_risk_score||0)} <span className="text-slate-400">(was {Math.round(simulationResult.baseline_risk_score||0)})</span></div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {simulationResult && simulationResult.recommendation_id == null && simulationResult.scenario_recommendation_ids && simulationResult.scenario_recommendation_ids.length > 0 && (
        <section className="rounded-3xl border border-emerald-500 bg-emerald-500/5 p-6">
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Scenario result</p>
          <div className="mt-1 text-sm text-slate-300">Applied: {simulationResult.scenario_recommendation_ids.join(', ')}</div>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-900 p-3 text-center">
              <div className="text-xs text-slate-400">On-time probability</div>
              <div className="text-lg font-semibold text-white">
                {Math.round((simulationResult.after_probability||0)*100)}%{' '}
                <span className="text-slate-400">(was {Math.round((simulationResult.baseline_probability||0)*100)}%)</span>
              </div>
            </div>
            <div className="rounded-2xl bg-slate-900 p-3 text-center">
              <div className="text-xs text-slate-400">Expected delay</div>
              <div className="text-lg font-semibold text-white">
                {(simulationResult.after_delay_days||0).toFixed(1)}d{' '}
                <span className="text-slate-400">(was {(simulationResult.baseline_delay_days||0).toFixed(1)}d)</span>
              </div>
            </div>
            <div className="rounded-2xl bg-slate-900 p-3 text-center">
              <div className="text-xs text-slate-400">Risk score</div>
              <div className="text-lg font-semibold text-white">
                {Math.round(simulationResult.after_risk_score||0)}{' '}
                <span className="text-slate-400">(was {Math.round(simulationResult.baseline_risk_score||0)})</span>
              </div>
            </div>
          </div>
          {simulationResult.summary && (
            <p className="mt-4 text-sm text-slate-300">{simulationResult.summary}</p>
          )}
        </section>
      )}
    </div>
  )
}

function getRiskColor(score){
  if(score >= 80) return {bg:'bg-rose-500', textBg:'bg-rose-500/15 text-rose-200', border:'border-rose-500'}
  if(score >= 60) return {bg:'bg-amber-400', textBg:'bg-amber-400/15 text-amber-200', border:'border-amber-400'}
  if(score >= 40) return {bg:'bg-orange-400', textBg:'bg-orange-400/15 text-orange-200', border:'border-orange-400'}
  if(score >= 20) return {bg:'bg-sky-500', textBg:'bg-sky-500/15 text-sky-200', border:'border-sky-500'}
  return {bg:'bg-emerald-500', textBg:'bg-emerald-500/15 text-emerald-200', border:'border-emerald-500'}
}

function RiskPage({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [risk, setRisk] = useState(null)
  const sessionId = session?.project_summary?.session_id || ''

  const fetchRisk = async ()=>{
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try{
      const response = await api.risk(sessionId)
      setRisk(response?.risk_analysis ?? response)
    }catch(err){
      setError(err)
    }finally{
      setLoading(false)
    }
  }

  useEffect(()=>{ fetchRisk() }, [sessionId])

  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Risk analysis</p>
        <div className="mt-4 text-sm text-slate-400">Loading risk results and drivers…</div>
      </section>
    )
  }

  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Risk analysis</p>
            <h2 className="mt-2 text-2xl font-semibold text-rose-100">Unable to load risk data</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Failed to retrieve risk insights.'}</p>
          </div>
          <button onClick={fetchRisk} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
        </div>
      </section>
    )
  }

  if(!risk){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Risk analysis</p>
        <div className="mt-4 text-sm text-slate-400">No risk insights are available for this session.</div>
      </section>
    )
  }

  const subRiskCards = [
    {key:'schedule', label:'Schedule risk', data:risk.schedule_risk},
    {key:'dependency', label:'Dependency risk', data:risk.dependency_risk},
    {key:'resource', label:'Resource risk', data:risk.resource_risk},
    {key:'scope', label:'Scope risk', data:risk.scope_risk},
  ]

  const sprintRisks = Array.isArray(risk.sprint_risks) ? [...risk.sprint_risks].sort((a,b)=>a.sprint_id - b.sprint_id) : []

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Overall risk</p>
            <h2 className="mt-2 text-4xl font-extrabold text-white">{Math.round(risk.overall_risk_score)}</h2>
            <div className={`mt-4 inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${getRiskColor(risk.overall_risk_score).textBg}`}>
              {risk.overall_risk_level}
            </div>
            <p className="mt-4 max-w-2xl text-sm text-slate-400">Overall risk is computed from schedule, dependency, resource, and scope exposure. Use the top drivers below to identify the highest-impact fixes.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-5 text-sm text-slate-300">
              <div className="uppercase tracking-[0.2em] text-slate-500">Score scale</div>
              <div className="mt-3 text-3xl font-semibold text-white">0–100</div>
              <div className="mt-2 text-sm text-slate-400">Higher is more risky.</div>
            </div>
            <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-5 text-sm text-slate-300">
              <div className="uppercase tracking-[0.2em] text-slate-500">Risk drivers</div>
              <div className="mt-3 text-3xl font-semibold text-white">{risk.top_risk_drivers?.length || 0}</div>
              <div className="mt-2 text-sm text-slate-400">Top contributors to project risk.</div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Risk breakdown</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Sub-score explanations</h2>
          </div>
          <div className="text-sm text-slate-400">Expand each category to inspect the top reasons.</div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {subRiskCards.map(item => (
            <SubRiskCard key={item.key} label={item.label} score={item.data?.score} reasons={item.data?.reasons || []} />
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <TopRiskDriversPanel drivers={risk.top_risk_drivers || []} />
        <SprintRiskChart sprintRisks={sprintRisks} />
      </div>
    </div>
  )
}

function SubRiskCard({label, score, reasons}){
  const displayScore = typeof score === 'number' ? Math.round(score) : 0
  const color = getRiskColor(displayScore)

  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-sm uppercase tracking-[0.2em] text-slate-400">{label}</div>
          <div className="mt-3 text-3xl font-semibold text-white">{displayScore}</div>
        </div>
        <div className={`rounded-full px-3 py-1 text-xs font-semibold ${color.textBg}`}>
          {displayScore}
        </div>
      </div>
      <div className="mt-4 h-3 rounded-full bg-slate-800">
        <div className={`${color.bg} h-3 rounded-full`} style={{ width: `${displayScore}%` }} />
      </div>
      <details className="mt-5 rounded-3xl border border-slate-800 bg-slate-900/80 p-4 text-sm text-slate-300">
        <summary className="cursor-pointer font-semibold text-slate-100">View reasons ({reasons.length})</summary>
        <ul className="mt-3 space-y-2 text-slate-300">
          {reasons.length > 0 ? reasons.map((reason, index) => (
            <li key={index} className="list-disc pl-5">{reason}</li>
          )) : (
            <li className="text-slate-500">No recorded reasons.</li>
          )}
        </ul>
      </details>
    </div>
  )
}

function TopRiskDriversPanel({drivers}){
  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-950/80 p-6 shadow-inner shadow-black/20">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Top risk drivers</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">What should be fixed first</h2>
          <p className="mt-2 text-sm text-slate-400">Ranked list of the highest-impact risks across the project.</p>
        </div>
        <div className="rounded-3xl bg-slate-900/80 px-4 py-3 text-sm text-slate-300">Showing top {Math.min(drivers.length, 10)} drivers</div>
      </div>

      <div className="mt-6 space-y-4">
        {drivers.map((driver, index) => (
          <div key={`${driver.title}-${index}`} className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">#{index + 1} · {driver.category}</div>
                <h3 className="mt-2 text-lg font-semibold text-white">{driver.title}</h3>
              </div>
              <div className="rounded-full bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-100">Score {Math.round(driver.score)}</div>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <div className="text-sm uppercase tracking-[0.2em] text-slate-500">Why this matters</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{driver.description}</p>
              </div>
              <div>
                <div className="text-sm uppercase tracking-[0.2em] text-slate-500">Recommended action</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{driver.recommendation_hint}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function SprintRiskChart({sprintRisks}){
  const chartItems = sprintRisks.slice(0, 12)

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-950/80 p-6 shadow-inner shadow-black/20">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Sprint risks</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">Risk trend by sprint</h2>
        <p className="mt-2 text-sm text-slate-400">Per-sprint risk score helps judges see when risk peaks across the timeline.</p>
      </div>

      <div className="mt-6 space-y-4">
        <div className="grid gap-3">
          {chartItems.map(item => (
            <div key={item.sprint_id} className="space-y-2">
              <div className="flex items-center justify-between text-sm text-slate-300">
                <span>Sprint {item.sprint_id}</span>
                <span>{Math.round(item.risk_score)}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-800">
                <div className={`${getRiskColor(item.risk_score).bg} h-3 rounded-full`} style={{ width: `${Math.round(item.risk_score)}%` }} />
              </div>
            </div>
          ))}
        </div>
        {sprintRisks.length === 0 && <div className="text-sm text-slate-500">Sprint risk details are not available.</div>}
      </div>
    </section>
  )
}

function CriticalPathPage({session}){
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deps, setDeps] = useState(null)
  const sessionId = session?.project_summary?.session_id || ''

  const fetchDependencies = async ()=>{
    if(!sessionId){
      setError(new Error('Missing session id'))
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try{
      const response = await api.dependencies(sessionId)
      setDeps(response)
    }catch(err){
      setError(err)
    }finally{
      setLoading(false)
    }
  }

  useEffect(()=>{ fetchDependencies() }, [sessionId])

  if(loading){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Critical path</p>
        <div className="mt-4 text-sm text-slate-400">Loading dependency graph and critical path details…</div>
      </section>
    )
  }

  if(error){
    return (
      <section className="rounded-3xl border border-rose-600 bg-rose-900/10 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Critical path</p>
            <h2 className="mt-2 text-2xl font-semibold text-rose-100">Unable to load dependency analysis</h2>
            <p className="mt-2 text-sm text-rose-300">{error.message || 'Failed to retrieve critical path data.'}</p>
          </div>
          <button onClick={fetchDependencies} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200">Retry</button>
        </div>
      </section>
    )
  }

  if(!deps){
    return (
      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Critical path</p>
        <div className="mt-4 text-sm text-slate-400">No dependency analysis is available for this session.</div>
      </section>
    )
  }

  const chain = Array.isArray(deps.critical_path) ? deps.critical_path : []
  const highRisk = Array.isArray(deps.high_risk_items) ? deps.high_risk_items : []
  const mediumRisk = Array.isArray(deps.medium_risk_items) ? deps.medium_risk_items : []
  const lowRisk = Array.isArray(deps.low_risk_items) ? deps.low_risk_items : []

  const renderIdNode = (id, index) => (
    <div key={id + index} className="inline-flex items-center gap-4">
      <div className="rounded-3xl border border-slate-700 bg-slate-950/90 px-4 py-3 text-sm font-semibold text-white shadow-sm shadow-black/20">{id}</div>
      {index < chain.length - 1 && <span className="text-slate-500">→</span>}
    </div>
  )

  return (
    <div className="space-y-6">
      {deps.has_cycles && (
        <section className="rounded-3xl border border-rose-500 bg-rose-950/80 p-6 text-slate-100 shadow-inner shadow-black/20">
          <div className="flex items-start gap-3">
            <div className="mt-1 rounded-full bg-rose-500/10 px-3 py-1 text-sm font-semibold text-rose-200">Warning</div>
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Circular dependency detected</p>
              <h2 className="mt-2 text-lg font-semibold text-white">The dependency graph contains cycles.</h2>
              <p className="mt-2 text-sm text-slate-300">A circular dependency can prevent the schedule from resolving. Investigate the listed items and break dependency loops.</p>
            </div>
          </div>
        </section>
      )}

      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Critical path</p>
            <h2 className="mt-2 text-3xl font-extrabold text-white">Project critical path</h2>
            <p className="mt-3 text-sm text-slate-400">This analysis shows the path of work items driving completion and whether the path is growing versus baseline.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Path duration" value={`${deps.critical_path_duration_days?.toFixed(1) ?? '—'} days`} />
            <MetricCard label="Path hours" value={`${deps.critical_path_duration_hours?.toFixed(1) ?? '—'}h`} />
            <MetricCard label="Items on path" value={deps.critical_path_item_count ?? chain.length} />
            <MetricCard label="Growth vs baseline" value={`${deps.critical_path_growth_percent?.toFixed(1) ?? '—'}%`} />
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-700 bg-slate-950/80 p-6 shadow-inner shadow-black/20">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Dependency chain</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Ordered critical path</h2>
          </div>
          <div className="text-sm text-slate-400">Works with item IDs only, as returned by the backend.</div>
        </div>
        <div className="mt-6 overflow-x-auto pb-2">
          <div className="inline-flex items-center gap-3 whitespace-nowrap">
            {chain.length > 0 ? chain.map(renderIdNode) : (
              <span className="text-slate-400">Critical path is not available for this session.</span>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-inner shadow-black/20">
        <div className="grid gap-4 lg:grid-cols-3">
          <RiskGroupList title="High risk items" items={highRisk} color="rose" />
          <RiskGroupList title="Medium risk items" items={mediumRisk} color="amber" />
          <RiskGroupList title="Low risk items" items={lowRisk} color="emerald" />
        </div>
      </section>
    </div>
  )
}

function RiskGroupList({title, items, color}){
  const colorStyles = {
    rose: 'bg-rose-500/10 text-rose-200 border-rose-500/20',
    amber: 'bg-amber-500/10 text-amber-200 border-amber-500/20',
    emerald: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20',
  }

  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-sm uppercase tracking-[0.2em] text-slate-400">{title}</div>
          <div className="mt-2 text-3xl font-semibold text-white">{items.length}</div>
        </div>
        <div className={`rounded-full px-3 py-1 text-xs font-semibold ${colorStyles[color]}`}>{title.split(' ')[0]}</div>
      </div>
      <div className="mt-5 space-y-2">
        {items.length > 0 ? items.map((itemId, index) => (
          <div key={`${itemId}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-sm text-slate-200">
            {itemId}
          </div>
        )) : (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-sm text-slate-500">No items in this group.</div>
        )}
      </div>
    </div>
  )
}

function SectionPlaceholder({title, description}){
  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-900 p-8 shadow-inner shadow-black/20">
      <p className="text-sm uppercase tracking-[0.3em] text-amber-400">{title}</p>
      <h2 className="mt-2 text-3xl font-semibold text-white">{title} content coming soon</h2>
      <p className="mt-3 text-sm text-slate-400">{description}</p>
    </section>
  )
}

export function Dashboard({session, onReset}){
  const [active, setActive] = useState('overview')
  const [metrics, setMetrics] = useState(null)
  const [metricsLoading, setMetricsLoading] = useState(true)
  const [metricsError, setMetricsError] = useState(null)
  const sessionId = session?.project_summary?.session_id || ''

  useEffect(()=>{
    let mounted = true
    if(!sessionId){
      setMetricsError(new Error('Missing session id'))
      setMetricsLoading(false)
      return () => { mounted = false }
    }
    setMetricsLoading(true)
    setMetricsError(null)
    api.metrics(sessionId).then(m=>{ if(mounted){ setMetrics(m); setMetricsLoading(false) }}).catch(err=>{ if(mounted){ setMetricsError(err); setMetricsLoading(false) }})
    return ()=>{ mounted = false }
  }, [sessionId])

  if (!session) return null

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-700 bg-slate-950/90 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400">Session dashboard</p>
            <h2 className="mt-2 text-2xl font-bold text-white">Project analytics</h2>
          </div>
          <button onClick={onReset} className="rounded-2xl border border-rose-500 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/20">
            New Project
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          {tabs.map(tab => (
            <button key={tab.key} onClick={() => setActive(tab.key)} className={`rounded-full px-4 py-2 text-sm font-semibold ${active===tab.key ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {active === 'overview' && <>
        <OverviewPage session={session} metrics={metrics} />
        <DelayDiagnosis session={session} />
      </>}
      {active === 'risk' && <RiskPage session={session} />}
      {active === 'critical-path' && <CriticalPathPage session={session} />}
      {active === 'forecast' && <ForecastPage session={session} />}
      {active === 'actions' && <ActionsPage session={session} />}
    </div>
  )
}
