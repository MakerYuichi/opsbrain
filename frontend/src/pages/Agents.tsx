import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Brain, AlertTriangle, Wrench, Loader2, CheckCircle, XCircle, Clock, FileText, Send, Sparkles } from 'lucide-react'
import { fetchAssets } from '../api/timeline'
import type { AssetItem } from '../types/timeline'
import AssetPicker from '../components/AssetPicker'

export default function Agents() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [activeTab, setActiveTab] = useState<'rca' | 'compliance' | 'maintenance'>('rca')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [thinking, setThinking] = useState<string[]>([])

  const assetId = searchParams.get('asset') ?? 'APS-3'
  const setAsset = (id: string) => setSearchParams(p => { p.set('asset', id); return p })

  useEffect(() => {
    fetchAssets().then(setAssets).catch(console.error)
  }, [])

  const runAgent = async (agentType: string) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setThinking([])

    // Simulate thinking steps
    const steps = agentType === 'rca' ? [
      'Analyzing incident patterns...',
      'Examining sensor anomalies...',
      'Reviewing maintenance history...',
      'Identifying causal chain...',
      'Generating root cause analysis...'
    ] : agentType === 'compliance' ? [
      'Checking Factory Act compliance...',
      'Reviewing OISD standards...',
      'Verifying PESO permits...',
      'Checking environmental clearances...',
      'Generating compliance report...'
    ] : [
      'Analyzing deferred maintenance...',
      'Reviewing sensor faults...',
      'Checking equipment health...',
      'Prioritizing maintenance tasks...',
      'Generating maintenance schedule...'
    ]

    for (const step of steps) {
      setThinking(prev => [...prev, step])
      await new Promise(r => setTimeout(r, 800))
    }

    try {
      const endpoint = agentType === 'rca' ? '/agents/rca' :
                      agentType === 'compliance' ? '/agents/compliance' :
                      '/agents/maintenance'

      const body = agentType === 'rca' ? { asset_id: assetId, query: 'incident analysis' } :
                    agentType === 'compliance' ? { asset_id: assetId } :
                    { asset_id: assetId }

      const res = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      if (!res.ok) throw new Error('Agent request failed')
      const data = await res.json()
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
      setThinking([])
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div className="shrink-0 p-6 border-b border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg"
                 style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}>
              <Brain size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold t-primary">AI Agents</h1>
              <p className="text-sm t-3">Specialized industrial intelligence workflows</p>
            </div>
          </div>
        </div>

        {/* Asset Selector */}
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium t-2">Target Asset:</label>
          <AssetPicker assets={assets} value={assetId} onChange={setAsset} disabled={loading} />
        </div>
      </div>

      {/* Tabs */}
      <div className="shrink-0 flex border-b border-base" style={{ background: 'var(--bg-1)' }}>
        {[
          { id: 'rca', label: 'Root Cause Analysis', icon: AlertTriangle },
          { id: 'compliance', label: 'Compliance Check', icon: FileText },
          { id: 'maintenance', label: 'Maintenance Schedule', icon: Wrench },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id as any); setResult(null); setError(null) }}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors border-b-2
              ${activeTab === tab.id
                ? 'border-indigo-500 text-indigo-600 bg-indigo-50'
                : 'border-transparent t-2 hover:t-primary'}`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'rca' && (
          <RCAPanel
            loading={loading}
            result={result}
            error={error}
            thinking={thinking}
            onRun={() => runAgent('rca')}
          />
        )}
        {activeTab === 'compliance' && (
          <CompliancePanel
            loading={loading}
            result={result}
            error={error}
            thinking={thinking}
            onRun={() => runAgent('compliance')}
          />
        )}
        {activeTab === 'maintenance' && (
          <MaintenancePanel
            loading={loading}
            result={result}
            error={error}
            thinking={thinking}
            onRun={() => runAgent('maintenance')}
          />
        )}
      </div>
    </div>
  )
}

function RCAPanel({ loading, result, error, thinking, onRun }: any) {
  const renderMarkdown = (text: string) => {
    // Simple markdown rendering
    return text
      .replace(/^### (.*$)/gim, '<h3 class="text-base font-semibold t-primary mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-lg font-semibold t-primary mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold t-primary mt-4 mb-2">$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^\* (.*$)/gim, '<li class="ml-4 text-sm t-2">$1</li>')
      .replace(/\n/g, '<br />')
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-red-100 text-red-600">
            <AlertTriangle size={24} />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold t-primary mb-2">Root Cause Analysis Agent</h2>
            <p className="text-sm t-2 mb-4">
              Analyzes incident patterns, sensor anomalies, and maintenance history to identify
              root causes of equipment failures or safety incidents.
            </p>
            <button
              onClick={onRun}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500 text-white font-medium
                         hover:bg-red-600 disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {loading ? 'Analyzing...' : 'Run RCA Analysis'}
            </button>
          </div>
        </div>
      </div>

      {/* Thinking Display */}
      {thinking.length > 0 && (
        <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-indigo-600" />
            <span className="text-sm font-semibold text-indigo-700">Agent Thinking</span>
          </div>
          <div className="space-y-2">
            {thinking.map((step: string, i: number) => (
              <div key={i} className="flex items-center gap-2 text-sm text-indigo-600">
                <Loader2 size={12} className="animate-spin" />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
            <h3 className="text-lg font-semibold t-primary mb-4">Analysis Results</h3>
            <div className="space-y-4">
              {result.causal_chain && (
                <div>
                  <h4 className="text-sm font-semibold t-2 mb-2">Causal Chain</h4>
                  <div className="space-y-2">
                    {result.causal_chain.map((step: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white border border-gray-200">
                        <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold">
                          {i + 1}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm t-primary">{step.event}</p>
                          {step.confidence && (
                            <p className="text-xs t-3 mt-1">Confidence: {Math.round(step.confidence * 100)}%</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.sensor_anomalies && result.sensor_anomalies.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold t-2 mb-2">Sensor Anomalies</h4>
                  <div className="space-y-2">
                    {Array.isArray(result.sensor_anomalies) ? (
                      result.sensor_anomalies.map((anomaly: any, i: number) => (
                        <div key={i} className="p-3 rounded-lg bg-orange-50 border border-orange-200 text-orange-700">
                          <p className="text-sm font-medium">{anomaly.sensor_id || anomaly}</p>
                          {anomaly.description && <p className="text-xs mt-1">{anomaly.description}</p>}
                          {anomaly.timestamp && <p className="text-xs mt-1 text-orange-600">{anomaly.timestamp}</p>}
                        </div>
                      ))
                    ) : (
                      <div className="p-3 rounded-lg bg-orange-50 border border-orange-200 text-orange-700">
                        <p className="text-sm font-medium">{result.sensor_anomalies}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {result.report && (
                <div>
                  <h4 className="text-sm font-semibold t-2 mb-2">Detailed Report</h4>
                  <div
                    className="p-4 rounded-lg bg-white border border-gray-200 text-sm t-2"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(result.report) }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function CompliancePanel({ loading, result, error, thinking, onRun }: any) {
  const renderMarkdown = (text: string) => {
    return text
      .replace(/^### (.*$)/gim, '<h3 class="text-base font-semibold t-primary mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-lg font-semibold t-primary mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold t-primary mt-4 mb-2">$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^\* (.*$)/gim, '<li class="ml-4 text-sm t-2">$1</li>')
      .replace(/\n/g, '<br />')
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-blue-100 text-blue-600">
            <FileText size={24} />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold t-primary mb-2">Regulatory Compliance Agent</h2>
            <p className="text-sm t-2 mb-4">
              Checks compliance against Factory Act, OISD, PESO, environmental permits,
              and ISO standards. Identifies gaps and provides remediation recommendations.
            </p>
            <button
              onClick={onRun}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500 text-white font-medium
                         hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {loading ? 'Checking...' : 'Run Compliance Check'}
            </button>
          </div>
        </div>
      </div>

      {/* Thinking Display */}
      {thinking.length > 0 && (
        <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-indigo-600" />
            <span className="text-sm font-semibold text-indigo-700">Agent Thinking</span>
          </div>
          <div className="space-y-2">
            {thinking.map((step: string, i: number) => (
              <div key={i} className="flex items-center gap-2 text-sm text-indigo-600">
                <Loader2 size={12} className="animate-spin" />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold t-primary">Compliance Results</h3>
              <div className="flex items-center gap-2">
                <span className="text-sm t-2">Gaps Found:</span>
                <span className="text-2xl font-bold text-red-600">{result.gap_count || 0}</span>
              </div>
            </div>

            {result.gaps && result.gaps.length > 0 && (
              <div className="space-y-3 mb-6">
                <h4 className="text-sm font-semibold t-2">Compliance Gaps</h4>
                {result.gaps.map((gap: any, i: number) => (
                  <div key={i} className="p-4 rounded-lg border border-red-200 bg-red-50">
                    <div className="flex items-start gap-3">
                      <XCircle size={20} className="text-red-600 shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <p className="font-semibold text-red-700">{gap.name}</p>
                        <p className="text-sm text-red-600 mt-1">{gap.requirement}</p>
                        {gap.severity && (
                          <span className={`inline-block mt-2 px-2 py-1 rounded text-xs font-medium
                            ${gap.severity === 'CRITICAL' ? 'bg-red-600 text-white' : 'bg-orange-500 text-white'}`}>
                            {gap.severity}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {result.compliant && result.compliant.length > 0 && (
              <div className="space-y-3 mb-6">
                <h4 className="text-sm font-semibold t-2">Compliant Areas</h4>
                {result.compliant.map((item: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-green-200 bg-green-50">
                    <CheckCircle size={20} className="text-green-600" />
                    <span className="text-sm text-green-700">{item.name}</span>
                  </div>
                ))}
              </div>
            )}

            {result.report && (
              <div>
                <h4 className="text-sm font-semibold t-2 mb-2">Compliance Report</h4>
                <div
                  className="p-4 rounded-lg bg-white border border-gray-200 text-sm t-2"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(result.report) }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MaintenancePanel({ loading, result, error, thinking, onRun }: any) {
  const renderMarkdown = (text: string) => {
    return text
      .replace(/^### (.*$)/gim, '<h3 class="text-base font-semibold t-primary mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-lg font-semibold t-primary mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold t-primary mt-4 mb-2">$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^\* (.*$)/gim, '<li class="ml-4 text-sm t-2">$1</li>')
      .replace(/\n/g, '<br />')
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-orange-100 text-orange-600">
            <Wrench size={24} />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold t-primary mb-2">Predictive Maintenance Agent</h2>
            <p className="text-sm t-2 mb-4">
              Analyzes deferred maintenance, sensor faults, and equipment health to generate
              prioritized maintenance schedules and recommendations.
            </p>
            <button
              onClick={onRun}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 text-white font-medium
                         hover:bg-orange-600 disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {loading ? 'Scheduling...' : 'Generate Schedule'}
            </button>
          </div>
        </div>
      </div>

      {/* Thinking Display */}
      {thinking.length > 0 && (
        <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-indigo-600" />
            <span className="text-sm font-semibold text-indigo-700">Agent Thinking</span>
          </div>
          <div className="space-y-2">
            {thinking.map((step: string, i: number) => (
              <div key={i} className="flex items-center gap-2 text-sm text-indigo-600">
                <Loader2 size={12} className="animate-spin" />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="p-6 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
            <h3 className="text-lg font-semibold t-primary mb-4">Maintenance Schedule</h3>

            {result.priority_queue && result.priority_queue.length > 0 && (
              <div className="space-y-3 mb-6">
                <h4 className="text-sm font-semibold t-2">Priority Queue</h4>
                {result.priority_queue.map((item: any, i: number) => (
                  <div key={i} className="p-4 rounded-lg border border-gray-200 bg-white">
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold shrink-0
                        ${item.priority === 'HIGH' ? 'bg-red-500' : item.priority === 'MEDIUM' ? 'bg-orange-500' : 'bg-blue-500'}`}>
                        {i + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold t-primary">{item.task}</span>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium
                            ${item.priority === 'HIGH' ? 'bg-red-100 text-red-700' : item.priority === 'MEDIUM' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'}`}>
                            {item.priority}
                          </span>
                        </div>
                        <p className="text-sm t-2">{item.description}</p>
                        {item.estimated_hours && (
                          <p className="text-xs t-3 mt-1 flex items-center gap-1">
                            <Clock size={12} />
                            Est. {item.estimated_hours}h
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {result.deferred_work && result.deferred_work.length > 0 && (
              <div className="space-y-3 mb-6">
                <h4 className="text-sm font-semibold t-2">Deferred Work</h4>
                {result.deferred_work.map((item: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800">
                    <p className="text-sm font-medium">{item.task}</p>
                    <p className="text-xs mt-1">Deferred since: {item.deferred_since}</p>
                  </div>
                ))}
              </div>
            )}

            {result.recommendations && (
              <div>
                <h4 className="text-sm font-semibold t-2 mb-2">Recommendations</h4>
                <div
                  className="p-4 rounded-lg bg-white border border-gray-200 text-sm t-2"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(result.recommendations) }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
