import { useState, useEffect } from 'react'
import { LayoutDashboard, ListTree, Bug, Play, Pause, Server, RotateCw, FileText } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'
const DEFAULT_PROJ_ID = '87453ee8-cadf-4200-bf81-630edadde7b6'

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [queues, setQueues] = useState<any[]>([])
  const [jobs, setJobs] = useState<any[]>([])

  const [dlqJobs, setDlqJobs] = useState<any[]>([])
  const [workers, setWorkers] = useState<any[]>([])
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [jobLogs, setJobLogs] = useState<any[]>([])

  // Polling logic
  useEffect(() => {
    const fetchData = async () => {
      try {
        // 0. Auto-Login
        const formData = new URLSearchParams()
        formData.append('username', 'admin')
        formData.append('password', 'admin')
        const authRes = await axios.post(`${API_BASE}/auth/token`, formData, {
            headers: {'Content-Type': 'application/x-www-form-urlencoded'}
        })
        axios.defaults.headers.common['Authorization'] = `Bearer ${authRes.data.access_token}`

        // 1. Fetch Projects
        let projRes = await axios.get(`${API_BASE}/projects/`)
        let project_id = projRes.data.length > 0 ? projRes.data[0].id : null

        // 2. If no project exists, idempotently create a default org and project
        if (!project_id) {
            console.log("No projects found, initializing defaults...")
            const orgRes = await axios.post(`${API_BASE}/projects/organizations/?name=Default Org`)
            const newProjRes = await axios.post(`${API_BASE}/projects/`, { name: "Default Project", organization_id: orgRes.data.id })
            project_id = newProjRes.data.id
            // Also create a default queue
            await axios.post(`${API_BASE}/queues/`, { name: "Default Queue", project_id: project_id, retry_strategy: "fixed" })
        }

        // 3. Fetch Queues for the active project
        const qRes = await axios.get(`${API_BASE}/queues/?project_id=${project_id}`)
        setQueues(qRes.data)
        
        // 4. Fetch jobs for each queue
        let allJobs: any[] = []
        for (const q of qRes.data) {
          const res = await axios.get(`${API_BASE}/jobs/queue/${q.id}?limit=20`)
          allJobs = [...allJobs, ...res.data]
        }
        allJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        setJobs(allJobs)

        // 5. Fetch DLQ
        const dlqRes = await axios.get(`${API_BASE}/jobs/dlq/all`)
        setDlqJobs(dlqRes.data)

        // 6. Fetch Workers
        const workersRes = await axios.get(`${API_BASE}/workers/`)
        setWorkers(workersRes.data)
      } catch (err) {
        console.error("Polling error", err)
      }
    }
    
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  const toggleQueue = async (queue: any) => {
    try {
      await axios.patch(`${API_BASE}/queues/${queue.id}`, { is_paused: !queue.is_paused })
    } catch (e) {
      console.error("Failed to toggle queue", e)
    }
  }

  const retryDlqJob = async (jobId: string) => {
    try {
      await axios.post(`${API_BASE}/jobs/${jobId}/retry`)
      // Optimistically remove from DLQ list
      setDlqJobs(dlqJobs.filter(j => j.job_id !== jobId))
    } catch (e) {
      console.error("Failed to retry job", e)
    }
  }

  const toggleJobLogs = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null)
      return
    }
    setExpandedJobId(jobId)
    try {
      const logsRes = await axios.get(`${API_BASE}/jobs/${jobId}/logs`)
      setJobLogs(logsRes.data)
    } catch (e) {
      console.error("Failed to fetch logs", e)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'QUEUED': return <Badge variant="info">QUEUED</Badge>
      case 'RUNNING': return <Badge variant="warning">RUNNING</Badge>
      case 'COMPLETED': return <Badge variant="success">COMPLETED</Badge>
      case 'FAILED': return <Badge variant="destructive">FAILED</Badge>
      default: return <Badge variant="secondary">{status}</Badge>
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <div className="w-64 border-r border-border bg-card p-4 space-y-4">
        <div className="font-bold text-2xl tracking-tighter mb-8 text-primary">Codity Flow</div>
        
        <button onClick={() => setActiveTab('overview')} className={`flex items-center w-full space-x-2 px-3 py-2 rounded-lg transition-colors ${activeTab === 'overview' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}>
          <LayoutDashboard size={20} />
          <span>Overview</span>
        </button>
        <button onClick={() => setActiveTab('queues')} className={`flex items-center w-full space-x-2 px-3 py-2 rounded-lg transition-colors ${activeTab === 'queues' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}>
          <ListTree size={20} />
          <span>Queues</span>
        </button>
        <button onClick={() => setActiveTab('dlq')} className={`flex items-center w-full space-x-2 px-3 py-2 rounded-lg transition-colors ${activeTab === 'dlq' ? 'bg-destructive/10 text-destructive' : 'hover:bg-muted'}`}>
          <Bug size={20} />
          <span>Dead Letter</span>
        </button>
        <button onClick={() => setActiveTab('workers')} className={`flex items-center w-full space-x-2 px-3 py-2 rounded-lg transition-colors ${activeTab === 'workers' ? 'bg-indigo-500/10 text-indigo-500' : 'hover:bg-muted'}`}>
          <Server size={20} />
          <span>Workers</span>
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-8 overflow-y-auto">
        
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
            
            <div className="grid grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Jobs</CardDescription>
                  <CardTitle className="text-4xl">{jobs.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>In Progress</CardDescription>
                  <CardTitle className="text-4xl text-blue-500">{jobs.filter(j => ['QUEUED', 'SCHEDULED', 'CLAIMED', 'RUNNING'].includes(j.status)).length}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-4xl text-emerald-500">{jobs.filter(j => j.status === 'COMPLETED').length}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Failed (DLQ)</CardDescription>
                  <CardTitle className="text-4xl text-red-500">{jobs.filter(j => j.status === 'FAILED').length}</CardTitle>
                </CardHeader>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Live feed of job executions across all queues.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {jobs.slice(0, 10).map(job => (
                    <div key={job.id} className="flex flex-col p-4 border border-border rounded-lg bg-muted/20">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-mono text-xs text-muted-foreground mb-1">{job.id}</div>
                          <div className="font-semibold">{JSON.stringify(job.payload)}</div>
                        </div>
                        <div className="flex items-center space-x-4">
                          <div className="text-sm text-muted-foreground">Attempts: {job.attempts}/{job.max_retries}</div>
                          {getStatusBadge(job.status)}
                          <button 
                            onClick={() => toggleJobLogs(job.id)}
                            className="p-1.5 rounded bg-secondary hover:bg-secondary/80 text-secondary-foreground"
                            title="View Logs"
                          >
                            <FileText size={16} />
                          </button>
                        </div>
                      </div>
                      
                      {expandedJobId === job.id && (
                        <div className="mt-4 pt-4 border-t border-border">
                          <h4 className="text-sm font-semibold mb-2 flex items-center">
                            <FileText className="w-4 h-4 mr-2" /> Execution Logs
                          </h4>
                          {jobLogs.length === 0 ? (
                            <div className="text-xs text-muted-foreground">No logs available for this job.</div>
                          ) : (
                            <div className="bg-black/90 text-green-400 p-3 rounded text-xs font-mono max-h-40 overflow-y-auto space-y-1">
                              {jobLogs.map(log => (
                                <div key={log.id} className="flex space-x-3">
                                  <span className="text-gray-500 w-32 shrink-0">{new Date(log.created_at).toISOString().replace('T', ' ').substring(0, 19)}</span>
                                  <span>{log.message}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'queues' && (
          <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Queues</h1>
            
            <div className="grid grid-cols-2 gap-4">
              {queues.map(queue => (
                <Card key={queue.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>{queue.name}</CardTitle>
                      <button 
                        onClick={() => toggleQueue(queue)}
                        className={`p-2 rounded-full transition-colors ${queue.is_paused ? 'bg-amber-500/20 text-amber-500 hover:bg-amber-500/30' : 'bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500/30'}`}
                        title={queue.is_paused ? "Resume Queue" : "Pause Queue"}
                      >
                        {queue.is_paused ? <Play size={18} /> : <Pause size={18} />}
                      </button>
                    </div>
                    <CardDescription>ID: {queue.id}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Concurrency:</span>
                      <span className="font-mono">{queue.concurrency_limit}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Retry Strategy:</span>
                      <Badge variant="outline" className="uppercase">{queue.retry_strategy}</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status:</span>
                      {queue.is_paused ? <Badge variant="warning">PAUSED</Badge> : <Badge variant="success">ACTIVE</Badge>}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'dlq' && (
          <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight text-destructive">Dead Letter Queue</h1>
            <p className="text-muted-foreground">Jobs that have exceeded their maximum retries and failed permanently.</p>
            
            <div className="space-y-4">
              {dlqJobs.length === 0 && (
                <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                  No dead letter jobs found.
                </div>
              )}
              {dlqJobs.map(job => (
                <Card key={job.id} className="border-destructive/50 overflow-hidden">
                  <div className="bg-destructive/10 px-6 py-2 border-b border-destructive/20 flex justify-between items-center">
                    <span className="font-mono text-sm font-semibold text-destructive">{job.job_id}</span>
                    <div className="flex items-center space-x-4">
                      <span className="text-xs text-muted-foreground">{new Date(job.failed_at).toLocaleString()}</span>
                      <button 
                        onClick={() => retryDlqJob(job.job_id)}
                        className="flex items-center space-x-1 px-2 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors"
                      >
                        <RotateCw size={12} />
                        <span>Retry</span>
                      </button>
                    </div>
                  </div>
                  <CardContent className="p-6 space-y-4">
                    <div>
                      <h4 className="text-sm font-semibold mb-1">Payload</h4>
                      <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">{JSON.stringify(job.payload, null, 2)}</pre>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold mb-1 text-destructive">Error Summary</h4>
                      <p className="text-sm">{job.error_summary}</p>
                    </div>
                    {job.ai_failure_summary && (
                      <div className="bg-primary/5 p-4 rounded-lg border border-primary/20">
                        <h4 className="text-sm font-semibold mb-1 text-primary flex items-center">
                          <Bug className="w-4 h-4 mr-1"/> AI Failure Analysis
                        </h4>
                        <p className="text-sm text-primary/90">{job.ai_failure_summary}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'workers' && (
          <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight flex items-center">
              <Server className="w-8 h-8 mr-3 text-indigo-500" /> Worker Monitoring
            </h1>
            <p className="text-muted-foreground">Live overview of active background worker nodes processing queues.</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {workers.map(worker => (
                <Card key={worker.id} className="border-indigo-500/20">
                  <CardHeader className="bg-indigo-500/5 pb-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-lg">{worker.hostname}</CardTitle>
                        <CardDescription className="font-mono text-xs mt-1">{worker.id.substring(0, 8)}...</CardDescription>
                      </div>
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-4 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Last Heartbeat</span>
                      <span className="font-medium">{new Date(worker.last_heartbeat).toLocaleTimeString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Status</span>
                      <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">ONLINE</Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {workers.length === 0 && (
                <div className="col-span-full p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                  No active workers detected. Start the worker process to see it here.
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
