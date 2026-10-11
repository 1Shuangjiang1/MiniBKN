export interface NetworkSummary {
  id: string
  name: string
  version: number
  lifecycle_status: string
  object_type_count: number
  relation_type_count: number
  action_type_count: number
  risk_type_count: number
}

export interface Proposal {
  id: string
  kind: string
  target_id: string
  confidence: number
  rationale: string
  status: string
  payload: Record<string, unknown>
}

export interface ModelingSession {
  id: string
  network_id: string
  name: string
  status: string
  proposals: Proposal[]
}

export interface RoutedAnswer {
  answer: string
  requested_route: string
  executed_routes: string[]
  citations: string[]
  warnings: string[]
  evidence: Array<{ id: string; kind: string; title: string; content: string; citation: string }>
}
