import { useState, useEffect } from 'react'
import { Smartphone, Search, AlertTriangle, CheckCircle, Clock, MapPin, Plus, QrCode, RefreshCw } from 'lucide-react'
import { fetchAssets } from '../api/timeline'
import type { AssetItem } from '../types/timeline'
import AssetPicker from '../components/AssetPicker'

export default function MobileField() {
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [selectedAsset, setSelectedAsset] = useState<string>('APS-3')
  const [loading, setLoading] = useState(false)
  const [assetData, setAssetData] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'status' | 'report'>('overview')

  useEffect(() => {
    fetchAssets().then(setAssets).catch(console.error)
  }, [])

  const loadAssetData = async (assetId: string) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/mobile/asset/${assetId}`)
      if (!res.ok) throw new Error('Failed to load asset data')
      const data = await res.json()
      setAssetData(data)
    } catch (e: unknown) {
      console.error('Error loading asset:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAssetData(selectedAsset)
  }, [selectedAsset])

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Mobile Header */}
      <div className="shrink-0 p-4 border-b border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white"
                 style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
              <Smartphone size={16} />
            </div>
            <div>
              <h1 className="text-lg font-bold t-primary">Field Technician</h1>
              <p className="text-xs t-3">Mobile field interface</p>
            </div>
          </div>
          <button
            onClick={() => loadAssetData(selectedAsset)}
            className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Quick Search */}
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 t-3" />
          <input
            type="text"
            placeholder="Search asset ID or QR code..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          />
        </div>
      </div>

      {/* Asset Selector */}
      <div className="shrink-0 p-4 border-b border-base">
        <AssetPicker assets={assets} value={selectedAsset} onChange={setSelectedAsset} disabled={loading} />
      </div>

      {/* Mobile Tabs */}
      <div className="shrink-0 flex border-b border-base overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: CheckCircle },
          { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
          { id: 'status', label: 'Status', icon: Clock },
          { id: 'report', label: 'Report', icon: Plus },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2
              ${activeTab === tab.id
                ? 'border-green-500 text-green-600 bg-green-50'
                : 'border-transparent t-2 hover:t-primary'}`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw size={24} className="animate-spin text-green-500" />
          </div>
        ) : assetData ? (
          <>
            {activeTab === 'overview' && <OverviewTab assetData={assetData} />}
            {activeTab === 'alerts' && <AlertsTab assetData={assetData} />}
            {activeTab === 'status' && <StatusTab assetData={assetData} />}
            {activeTab === 'report' && <ReportTab assetId={selectedAsset} />}
          </>
        ) : (
          <div className="text-center t-3">Select an asset to view details</div>
        )}
      </div>

      {/* Quick Actions Bar */}
      <div className="shrink-0 p-4 border-t border-base flex gap-2" style={{ background: 'var(--bg-1)' }}>
        <button className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-green-500 text-white text-sm font-medium">
          <QrCode size={16} />
          Scan QR
        </button>
        <button className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg border border-gray-200 t-2 text-sm">
          <MapPin size={16} />
          Location
        </button>
      </div>
    </div>
  )
}

function OverviewTab({ assetData }: any) {
  return (
    <div className="space-y-4">
      {/* Asset Info Card */}
      <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-green-100 text-green-600">
            <CheckCircle size={20} />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold t-primary">{assetData.asset?.name}</h3>
            <p className="text-sm t-2 font-mono">{assetData.asset?.asset_id}</p>
            <p className="text-xs t-3 mt-1">{assetData.asset?.type} • {assetData.asset?.location}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 pt-3 border-t border-base">
          <span className="text-xs t-3">Status:</span>
          <span className={`px-2 py-1 rounded text-xs font-medium
            ${assetData.status?.overall_status === 'CRITICAL' ? 'bg-red-500 text-white' :
              assetData.status?.overall_status === 'WARNING' ? 'bg-orange- text-white' :
              assetData.status?.overall_status === 'ATTENTION' ? 'bg-yellow-500 text-white' :
              'bg-green-500 text-white'}`}>
            {assetData.status?.overall_status || 'NORMAL'}
          </span>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg border border-base text-center" style={{ background: 'var(--bg-1)' }}>
          <p className="text-2xl font-bold text-green-600">{assetData.status?.deferred_maintenance_count || 0}</p>
          <p className="text-xs t-3">Deferred Items</p>
        </div>
        <div className="p-3 rounded-lg border border-base text-center" style={{ background: 'var(--bg-1)' }}>
          <p className="text-2xl font-bold text-red-600">{assetData.active_alerts?.length || 0}</p>
          <p className="text-xs t-3">Active Alerts</p>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <h4 className="text-sm font-semibold t-primary mb-3">Recent Activity</h4>
        <div className="space-y-2">
          {assetData.recent_activity?.slice(0, 5).map((activity: any, i: number) => (
            <div key={i} className="p-2 rounded-lg bg-white border border-gray-200">
              <p className="text-xs font-medium t-primary">{activity.type}</p>
              <p className="text-xs t-2 mt-1 truncate">{activity.content}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function AlertsTab({ assetData }: any) {
  return (
    <div className="space-y-3">
      {assetData.active_alerts?.length > 0 ? (
        assetData.active_alerts.map((alert: any, i: number) => (
          <div key={i} className="p-4 rounded-lg border border-red-200 bg-red-50">
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className="text-red-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-red-700">{alert.pattern_type}</p>
                <p className="text-sm text-red-600 mt-1">{alert.description}</p>
                <p className="text-xs text-red-500 mt-2">{alert.created_at}</p>
              </div>
            </div>
          </div>
        ))
      ) : (
        <div className="p-8 text-center">
          <CheckCircle size={32} className="mx-auto text-green-500 mb-2" />
          <p className="text-sm t-2">No active alerts</p>
        </div>
      )}
    </div>
  )
}

function StatusTab({ assetData }: any) {
  return (
    <div className="space-y-4">
      {/* Sensor Status */}
      {assetData.status?.sensor_status && (
        <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
          <h4 className="text-sm font-semibold t-primary mb-3">Sensor Status</h4>
          <div className="p-3 rounded-lg bg-white border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm t-2">{assetData.status.sensor_status.metric}</span>
              <span className={`px-2 py-1 rounded text-xs font-medium
                ${assetData.status.sensor_status.status === 'OK' ? 'bg-green-100 text-green-700' :
                  assetData.status.sensor_status.status === 'FAULT' ? 'bg-red-100 text-red-700' :
                  'bg-yellow-100 text-yellow-700'}`}>
                {assetData.status.sensor_status.status}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold t-primary">{assetData.status.sensor_status.value}</span>
              <span className="text-sm t-3">{assetData.status.sensor_status.unit}</span>
            </div>
            <p className="text-xs t-3 mt-2">Last reading: {assetData.status.sensor_status.last_reading}</p>
          </div>
        </div>
      )}

      {/* Maintenance Summary */}
      {assetData.status?.maintenance_summary && assetData.status.maintenance_summary.length > 0 && (
        <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
          <h4 className="text-sm font-semibold t-primary mb-3">Maintenance Summary</h4>
          <div className="space-y-2">
            {assetData.status.maintenance_summary.map((item: any, i: number) => (
              <div key={i} className="p-2 rounded-lg bg-white border border-gray-200">
                <p className="text-xs font-medium t-primary">{item.type}</p>
                <p className="text-xs t-2 mt-1 truncate">{item.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {assetData.status?.recommended_actions && assetData.status.recommended_actions.length > 0 && (
        <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
          <h4 className="text-sm font-semibold t-primary mb-3">Recommended Actions</h4>
          <div className="space-y-2">
            {assetData.status.recommended_actions.map((action: any, i: number) => (
              <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-green-50 border border-green-200">
                <CheckCircle size={16} className="text-green-600 shrink-0 mt-0.5" />
                <p className="text-xs text-green-700">{action}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ReportTab({ assetId }: { assetId: string }) {
  const [submitted, setSubmitted] = useState(false)
  const [formData, setFormData] = useState({
    incident_type: '',
    description: '',
    severity: 'MEDIUM',
  })

  const handleSubmit = async () => {
    try {
      const res = await fetch('/api/mobile/incident', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: assetId,
          incident_type: formData.incident_type,
          description: formData.description,
          severity: formData.severity,
          reported_by: 'field_technician',
        })
      })

      if (res.ok) {
        setSubmitted(true)
        setTimeout(() => setSubmitted(false), 3000)
      }
    } catch (e) {
      console.error('Error submitting incident:', e)
    }
  }

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl border border-base" style={{ background: 'var(--bg-1)' }}>
        <h4 className="text-sm font-semibold t-primary mb-4">Report Incident</h4>

        {submitted ? (
          <div className="p-4 rounded-lg bg-green-50 border border-green-200 text-green-700 text-center">
            <CheckCircle size={24} className="mx-auto mb-2" />
            <p className="text-sm font-medium">Incident reported successfully</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium t-2 block mb-1">Incident Type</label>
              <select
                value={formData.incident_type}
                onChange={e => setFormData({ ...formData, incident_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
              >
                <option value="">Select type...</option>
                <option value="safety">Safety Issue</option>
                <option value="equipment">Equipment Failure</option>
                <option value="environmental">Environmental</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium t-2 block mb-1">Severity</label>
              <select
                value={formData.severity}
                onChange={e => setFormData({ ...formData, severity: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium t-2 block mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe the incident..."
                rows={3}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm resize-none"
              />
            </div>

            <button
              onClick={handleSubmit}
              disabled={!formData.incident_type || !formData.description}
              className="w-full py-2 rounded-lg bg-green-500 text-white font-medium
                         hover:bg-green-600 disabled:opacity-50 transition-colors"
            >
              Submit Report
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
