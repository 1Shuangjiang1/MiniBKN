import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('MiniBKN control room', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const payload = url.endsWith('/api/v1/networks')
        ? { entries: [], total: 0 }
        : []
      return { ok: true, json: async () => payload } as Response
    }))
  })

  it('renders six product workflows and switches pages accessibly', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: '把业务数据接进来' })).toBeInTheDocument()
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /04\s*业务问答/ }))
    expect(screen.getByRole('heading', { name: '先看证据，再看回答' })).toBeInTheDocument()
    expect(screen.getByLabelText('问题')).toHaveValue('客户有哪些订单？')
  })

  it('keeps evaluation numbers empty until a real report is loaded', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /06\s*评测/ }))
    expect(screen.getByText('NO FABRICATED METRICS')).toBeInTheDocument()
    expect(screen.getByText('// 完成 S10 后生成')).toBeInTheDocument()
  })

  it('persists the backend connection without exposing the API key', () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('地址'), {
      target: { value: 'http://localhost:9000/' },
    })
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'local-secret' } })
    fireEvent.click(screen.getByRole('button', { name: '保存连接' }))

    expect(localStorage.getItem('minibkn-api')).toBe('http://localhost:9000/')
    expect(localStorage.getItem('minibkn-key')).toBe('local-secret')
    expect(screen.getByLabelText('API Key')).toHaveAttribute('type', 'password')
    expect(screen.queryByText('local-secret')).not.toBeInTheDocument()
  })

  it('registers and discovers a source through the visible workflow', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/v1/sources') && init?.method === 'POST') {
        return { ok: true, json: async () => ({ id: 'crm_files' }) } as Response
      }
      if (url.endsWith('/discover')) {
        return { ok: true, json: async () => ({ resources: [] }) } as Response
      }
      if (url.endsWith('/api/v1/sources')) {
        return {
          ok: true,
          json: async () => [{ id: 'crm_files', name: 'CRM 数据', kind: 'csv', resources: [] }],
        } as Response
      }
      return { ok: true, json: async () => ({ entries: [], total: 0 }) } as Response
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('本地路径'), { target: { value: 'D:\\data\\crm' } })
    fireEvent.click(screen.getByRole('button', { name: '注册并发现字段' }))

    expect(await screen.findByText('数据源已注册并完成字段发现')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/sources/crm_files/discover',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows routed evidence and citations after asking a question', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/ask-routed')) {
        return {
          ok: true,
          json: async () => ({
            answer: '客户 CUST-0001 有订单 ORD-00001。',
            requested_route: 'auto',
            executed_routes: ['structured'],
            citations: ['resource://orders#row=2'],
            warnings: [],
            evidence: [{
              id: 'order-1', kind: 'instance', title: 'ORD-00001',
              content: '订单 ORD-00001 属于 CUST-0001', citation: 'resource://orders#row=2',
            }],
          }),
        } as Response
      }
      return { ok: true, json: async () => [] } as Response
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /04\s*业务问答/ }))
    fireEvent.click(screen.getByRole('button', { name: '检索' }))

    expect(await screen.findByText('客户 CUST-0001 有订单 ORD-00001。')).toBeInTheDocument()
    expect(screen.getByText('ROUTE / structured')).toBeInTheDocument()
    expect(screen.getByText('resource://orders#row=2')).toBeInTheDocument()
  })

  it('surfaces backend errors and never invents an answer', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/ask-routed')) {
        return {
          ok: false,
          status: 404,
          json: async () => ({ message: '知识网络不存在' }),
        } as Response
      }
      return { ok: true, json: async () => [] } as Response
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /04\s*业务问答/ }))
    fireEvent.click(screen.getByRole('button', { name: '检索' }))

    expect(await screen.findByText('知识网络不存在')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '回答' })).not.toBeInTheDocument()
  })

  it('loads a real evaluation report and changes status to ready', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const payload = url.endsWith('/api/v1/evaluations/latest')
        ? { report_version: '2.0', faithfulness: 0.9261 }
        : []
      return { ok: true, json: async () => payload } as Response
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /06\s*评测/ }))
    fireEvent.click(screen.getByRole('button', { name: '读取最近评测' }))

    expect(await screen.findByText('READY')).toBeInTheDocument()
    expect(screen.getByText(/0.9261/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('已读取最近一次正式评测')).toBeInTheDocument())
  })

  it('prevents publication until every modeling proposal is reviewed', async () => {
    const pendingSession = {
      id: 'session-1', network_id: 'crm_reviewed', name: 'CRM 业务网络', status: 'in_review',
      proposals: [{
        id: 'proposal-1', kind: 'object_type', target_id: 'customer', confidence: 0.9,
        rationale: '字段分析结果', status: 'pending', payload: {},
      }],
    }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/v1/modeling-sessions') && init?.method === 'POST') {
        return { ok: true, json: async () => pendingSession } as Response
      }
      if (url.includes('/proposals/proposal-1')) {
        return {
          ok: true,
          json: async () => ({
            ...pendingSession,
            proposals: [{ ...pendingSession.proposals[0], status: 'accepted' }],
          }),
        } as Response
      }
      return { ok: true, json: async () => [] } as Response
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /02\s*AI 建模/ }))
    fireEvent.click(screen.getByRole('button', { name: '生成可审核草案' }))

    const publish = await screen.findByRole('button', { name: '人工确认并发布网络' })
    expect(publish).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '接受' }))

    await waitFor(() => expect(publish).toBeEnabled())
    expect(screen.queryByRole('button', { name: '接受' })).not.toBeInTheDocument()
  })
})
