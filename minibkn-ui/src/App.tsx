import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Json, MiniBknApi } from './api'
import { ModelingSession, NetworkSummary, RoutedAnswer } from './types'

const views = [
  ['sources', '01', '数据源'],
  ['modeling', '02', 'AI 建模'],
  ['networks', '03', '知识网络'],
  ['ask', '04', '业务问答'],
  ['actions', '05', '动作与风险'],
  ['evaluation', '06', '评测'],
] as const

type View = (typeof views)[number][0]

export function App() {
  const [view, setView] = useState<View>('sources')
  const [baseUrl, setBaseUrl] = useState(
    () => localStorage.getItem('minibkn-api') || 'http://127.0.0.1:8000',
  )
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('minibkn-key') || '')
  const api = useMemo(() => new MiniBknApi(baseUrl, apiKey), [baseUrl, apiKey])

  const saveConnection = () => {
    localStorage.setItem('minibkn-api', baseUrl)
    localStorage.setItem('minibkn-key', apiKey)
  }

  return (
    <div className="shell">
      <a className="skip-nav" href="#main">跳到主要内容</a>
      <div className="grain" aria-hidden="true" />
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark">BKN</span>
          <span>CONTROL ROOM</span>
        </div>
        <nav aria-label="主导航">
          {views.map(([id, number, label]) => (
            <button
              key={id}
              className={view === id ? 'nav-item active' : 'nav-item'}
              onClick={() => setView(id)}
              aria-current={view === id ? 'page' : undefined}
            >
              <span>{number}</span>{label}
            </button>
          ))}
        </nav>
        <div className="connection">
          <p className="eyebrow">FOUNDATION API</p>
          <label>地址<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label>
          <label>API Key<input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="可选" /></label>
          <button className="secondary" onClick={saveConnection}>保存连接</button>
        </div>
      </aside>
      <main id="main">
        <header className="topline">
          <div><span className="signal" /> LOCAL KNOWLEDGE OPERATIONS</div>
          <time>BUILD / REVIEW / PUBLISH</time>
        </header>
        {view === 'sources' && <SourcesPanel api={api} />}
        {view === 'modeling' && <ModelingPanel api={api} />}
        {view === 'networks' && <NetworksPanel api={api} />}
        {view === 'ask' && <AskPanel api={api} />}
        {view === 'actions' && <ActionsPanel api={api} />}
        {view === 'evaluation' && <EvaluationPanel api={api} />}
      </main>
    </div>
  )
}

function PageHead({ code, title, copy }: { code: string; title: string; copy: string }) {
  return (
    <header className="page-head reveal">
      <span className="coordinate">MODULE / {code}</span>
      <h1>{title}</h1>
      <p>{copy}</p>
    </header>
  )
}

function SourcesPanel({ api }: { api: MiniBknApi }) {
  const [sources, setSources] = useState<Json[]>([])
  const [message, setMessage] = useState('等待连接')
  const [form, setForm] = useState({ id: 'crm_files', name: 'CRM 数据', kind: 'csv', path: '' })
  const load = () => api.get<Json[]>('/api/v1/sources').then(setSources).catch((error) => setMessage(error.message))
  useEffect(() => { void load() }, [api])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await api.post('/api/v1/sources', form)
      await api.post(`/api/v1/sources/${form.id}/discover`)
      setMessage('数据源已注册并完成字段发现')
      load()
    } catch (error) { setMessage((error as Error).message) }
  }
  return <section>
    <PageHead code="01" title="把业务数据接进来" copy="登记本地 CSV 或 SQLite 路径，系统读取字段结构，不上传原始文件。" />
    <div className="split">
      <form className="panel" onSubmit={submit}>
        <h2>登记数据源</h2>
        <label>数据源 ID<input value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} required /></label>
        <label>显示名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
        <label>类型<select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="csv">CSV 文件夹</option><option value="sqlite">SQLite</option></select></label>
        <label>本地路径<input value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} placeholder="D:\data\crm" required /></label>
        <button>注册并发现字段</button><Status text={message} />
      </form>
      <div className="panel inventory"><h2>已连接 / {sources.length}</h2>{sources.length === 0 ? <Empty /> : sources.map((source) => <article className="record" key={String(source.id)}><b>{String(source.name)}</b><code>{String(source.id)}</code><span>{String(source.kind)} · {Array.isArray(source.resources) ? source.resources.length : 0} 张表</span></article>)}</div>
    </div>
  </section>
}

function ModelingPanel({ api }: { api: MiniBknApi }) {
  const [sessions, setSessions] = useState<ModelingSession[]>([])
  const [active, setActive] = useState<ModelingSession | null>(null)
  const [message, setMessage] = useState('所有 AI 结果必须人工审核')
  const [form, setForm] = useState({ source_id: 'crm_files', network_id: 'crm_reviewed', name: 'CRM 业务网络', instruction: '', use_ai: false })
  const load = () => api.get<ModelingSession[]>('/api/v1/modeling-sessions').then((items) => { setSessions(items); if (!active && items.length) setActive(items[items.length - 1]) }).catch(() => {})
  useEffect(() => { void load() }, [api])
  const create = async (event: FormEvent) => { event.preventDefault(); try { const session = await api.post<ModelingSession>('/api/v1/modeling-sessions', form); setActive(session); setSessions([...sessions, session]); setMessage(`已生成 ${session.proposals.length} 条待审提案`) } catch (error) { setMessage((error as Error).message) } }
  const review = async (proposalId: string, status: 'accepted' | 'rejected') => { if (!active) return; try { const session = await api.patch<ModelingSession>(`/api/v1/modeling-sessions/${active.id}/proposals/${proposalId}`, { status, reviewed_by: 'ui-reviewer' }); setActive(session); setSessions(sessions.map((item) => item.id === session.id ? session : item)) } catch (error) { setMessage((error as Error).message) } }
  const publish = async () => { if (!active) return; try { await api.post(`/api/v1/modeling-sessions/${active.id}/publish`, { published_by: 'ui-product-owner' }); setMessage('人工审核版本已发布，可以进入知识网络执行构建'); load() } catch (error) { setMessage((error as Error).message) } }
  return <section>
    <PageHead code="02" title="让 AI 起草，让人做决定" copy="自然语言只负责表达意图。对象、字段、关系、动作和风险会拆成逐条提案。" />
    <div className="split wide-left">
      <form className="panel" onSubmit={create}><h2>新建建模会话</h2><label>数据源 ID<input value={form.source_id} onChange={(e) => setForm({ ...form, source_id: e.target.value })} /></label><label>网络 ID<input value={form.network_id} onChange={(e) => setForm({ ...form, network_id: e.target.value })} /></label><label>网络名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label>业务要求<textarea value={form.instruction} onChange={(e) => setForm({ ...form, instruction: e.target.value })} placeholder="例如：客户订单需要审批动作，大额订单必须人工确认" /></label><label className="check"><input type="checkbox" checked={form.use_ai} onChange={(e) => setForm({ ...form, use_ai: e.target.checked })} /> 使用已配置的 LLM</label><button>生成可审核草案</button><Status text={message} /></form>
      <div className="panel proposals"><div className="panel-title"><h2>提案审查</h2><select aria-label="建模会话" value={active?.id || ''} onChange={(e) => setActive(sessions.find((item) => item.id === e.target.value) || null)}><option value="">选择会话</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>{!active ? <Empty /> : <><div className="status-strip"><span>{active.status}</span><b>{active.proposals.filter((item) => item.status === 'pending').length} 待审</b></div>{active.proposals.map((proposal) => <article className="proposal" key={proposal.id}><div><span className={`kind ${proposal.kind}`}>{proposal.kind}</span><b>{proposal.target_id}</b><small>可信度 {Math.round(proposal.confidence * 100)}%</small></div><p>{proposal.rationale}</p><div className="proposal-actions"><span>{proposal.status}</span>{proposal.status === 'pending' && <><button className="small" onClick={() => review(proposal.id, 'accepted')}>接受</button><button className="small ghost" onClick={() => review(proposal.id, 'rejected')}>拒绝</button></>}</div></article>)}<button className="publish" onClick={publish} disabled={active.proposals.some((item) => item.status === 'pending')}>人工确认并发布网络</button></>}</div>
    </div>
  </section>
}

function NetworksPanel({ api }: { api: MiniBknApi }) {
  const [networks, setNetworks] = useState<NetworkSummary[]>([])
  const [result, setResult] = useState<Json | null>(null)
  const [message, setMessage] = useState('选择一个网络执行增量构建')
  const load = () => api.get<{ entries: NetworkSummary[] }>('/api/v1/networks').then((data) => setNetworks(data.entries)).catch((error) => setMessage(error.message))
  useEffect(() => { void load() }, [api])
  const build = async (id: string) => { try { const job = await api.post<Json>(`/api/v1/networks/${id}/builds`); setResult(job); setMessage(job.status === 'published' ? '构建已发布' : `构建状态：${job.status}`) } catch (error) { setMessage((error as Error).message) } }
  return <section><PageHead code="03" title="知识网络与增量构建" copy="查看已发布结构，只有变化的对象、关系和向量会被更新。" /><div className="metric-grid">{networks.map((network) => <article className="metric-card" key={network.id}><span>NETWORK / V{network.version}</span><h2>{network.name}</h2><code>{network.id}</code><div className="metrics"><b>{network.object_type_count}<small>对象</small></b><b>{network.relation_type_count}<small>关系</small></b><b>{network.action_type_count}<small>动作</small></b><b>{network.risk_type_count}<small>风险</small></b></div><button onClick={() => build(network.id)}>运行增量构建</button></article>)}</div><div className="panel console"><div><h2>BUILD TELEMETRY</h2><Status text={message} /></div><pre>{result ? JSON.stringify(result, null, 2) : '// 尚无构建记录'}</pre></div></section>
}

function AskPanel({ api }: { api: MiniBknApi }) {
  const [networkId, setNetworkId] = useState('crm')
  const [question, setQuestion] = useState('客户有哪些订单？')
  const [route, setRoute] = useState('auto')
  const [answer, setAnswer] = useState<RoutedAnswer | null>(null)
  const [message, setMessage] = useState('')
  const ask = async (event: FormEvent) => { event.preventDefault(); try { setMessage('正在整理证据…'); setAnswer(await api.post<RoutedAnswer>(`/api/v1/networks/${networkId}/ask-routed`, { question, route })); setMessage('') } catch (error) { setMessage((error as Error).message) } }
  return <section><PageHead code="04" title="先看证据，再看回答" copy="结构化数据、未来文档证据和实际执行路线都在同一份结果中透明展示。" /><form className="ask-bar" onSubmit={ask}><label>网络 ID<input value={networkId} onChange={(e) => setNetworkId(e.target.value)} /></label><label>路线<select value={route} onChange={(e) => setRoute(e.target.value)}><option value="auto">自动</option><option value="structured">结构化</option><option value="document">文档</option><option value="hybrid">混合</option></select></label><label className="question">问题<input value={question} onChange={(e) => setQuestion(e.target.value)} /></label><button>检索</button></form><Status text={message} />{answer && <div className="answer-layout"><article className="answer panel"><span className="coordinate">ROUTE / {answer.executed_routes.join(' + ')}</span><h2>回答</h2><p>{answer.answer}</p>{answer.warnings.map((warning) => <div className="warning" key={warning}>{warning}</div>)}</article><aside className="panel evidence"><h2>证据 / {answer.evidence.length}</h2>{answer.evidence.map((item) => <article key={item.id}><span>{item.kind}</span><b>{item.title}</b><p>{item.content}</p><code>{item.citation}</code></article>)}</aside></div>}</section>
}

function ActionsPanel({ api }: { api: MiniBknApi }) {
  const [form, setForm] = useState({ network: 'supply_chain', action: 'create_replenishment_alert', object_type_id: 'material', instance_id: 'MAT-001', parameters: '{}' })
  const [result, setResult] = useState<Json | null>(null)
  const [message, setMessage] = useState('先模拟风险；确认结果后再执行')
  const run = async (mode: 'simulate' | 'execute') => { try { const body = { object_type_id: form.object_type_id, instance_id: form.instance_id, parameters: JSON.parse(form.parameters) }; const suffix = mode === 'simulate' ? 'risks/simulate' : 'execute'; setResult(await api.post<Json>(`/api/v1/networks/${form.network}/actions/${form.action}/${suffix}`, body)); setMessage(mode === 'simulate' ? '风险模拟完成，未执行任何动作' : '动作请求已提交门禁') } catch (error) { setMessage((error as Error).message) } }
  return <section><PageHead code="05" title="动作必须穿过安全门" copy="模拟不会产生副作用；真实执行仍会经过 BKN 风险规则、审批、幂等与审计。" /><div className="split"><div className="panel"><h2>动作请求</h2><label>网络 ID<input value={form.network} onChange={(e) => setForm({ ...form, network: e.target.value })} /></label><label>动作 ID<input value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} /></label><label>对象类型<input value={form.object_type_id} onChange={(e) => setForm({ ...form, object_type_id: e.target.value })} /></label><label>对象实例<input value={form.instance_id} onChange={(e) => setForm({ ...form, instance_id: e.target.value })} /></label><label>参数 JSON<textarea value={form.parameters} onChange={(e) => setForm({ ...form, parameters: e.target.value })} /></label><div className="button-row"><button onClick={() => run('simulate')}>只模拟风险</button><button className="danger" onClick={() => run('execute')}>提交执行</button></div><Status text={message} /></div><div className="panel console"><h2>GATE DECISION</h2><pre>{result ? JSON.stringify(result, null, 2) : '// 等待模拟'}</pre></div></div></section>
}

function EvaluationPanel({ api }: { api: MiniBknApi }) {
  const [report, setReport] = useState<Json | null>(null)
  const [message, setMessage] = useState('S10 将冻结测试集、基线、延迟与 Token 统一放在这里')
  const load = async () => { try { setReport(await api.get<Json>('/api/v1/evaluations/latest')); setMessage('已读取最近一次正式评测') } catch (error) { setMessage((error as Error).message) } }
  return <section><PageHead code="06" title="只展示跑出来的数字" copy="评测面板不会预填简历结果；没有真实评测或 LLM Judge 时会明确标记缺失。" /><div className="evaluation-hero panel"><div><span className="coordinate">NO FABRICATED METRICS</span><h2>可复现，比好看更重要。</h2><p>比较 BM25、Dense、Hybrid 与 QueryPlan；记录数据集版本、运行环境、Token 和延迟。</p><button onClick={load}>读取最近评测</button><Status text={message} /></div><div className="score-ring"><b>{report ? 'READY' : '—'}</b><span>REPORT STATUS</span></div></div><div className="panel console"><pre>{report ? JSON.stringify(report, null, 2) : '// 完成 S10 后生成'}</pre></div></section>
}

function Status({ text }: { text: string }) { return <p className="status" aria-live="polite"><span className="signal" />{text}</p> }
function Empty() { return <div className="empty">NO RECORDS / 暂无记录</div> }
