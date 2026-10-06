import React, { useState, useEffect } from 'react';
import {
  ServerIcon as Server,
  WrenchIcon as Wrench,
  AlertTriangleIcon as AlertTriangle,
  ShieldAlertIcon as ShieldAlert,
  PlayIcon as Play,
  CheckCircleIcon as CheckCircle2,
  XCircleIcon as XCircle,
  RefreshIcon as RefreshCw,
  PlusIcon as Plus,
  CompassIcon as Compass,
  ArrowRightIcon as ArrowRight,
  KeyIcon as Fingerprint,
  SparklesIcon as Zap,
} from '../components/common/Icons';
import { mcpApi } from '../api/mcp';
import { useOrg } from '../context/OrgContext';
import { MCPServer, MCPTool, MCPMetrics, MCPDiscoveryResult, MCPToolCallResult } from '../types';

export const MCPSecurityPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const orgId = currentOrg?.id;

  const [activeTab, setActiveTab] = useState<'servers' | 'tools'>('servers');
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [metrics, setMetrics] = useState<MCPMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals
  const [isRegisterOpen, setIsRegisterOpen] = useState<boolean>(false);
  const [registerForm, setRegisterForm] = useState({
    name: '',
    endpoint: '',
    transport: 'HTTP',
    server_type: 'REMOTE',
    trust_level: 'UNTRUSTED',
    description: '',
    environment: 'production',
  });
  const [registering, setRegistering] = useState<boolean>(false);

  // Discovery Action State
  const [discoveringServerId, setDiscoveringServerId] = useState<string | null>(null);
  const [discoveryResult, setDiscoveryResult] = useState<MCPDiscoveryResult | null>(null);

  // Test Tool Call Modal
  const [testTool, setTestTool] = useState<MCPTool | null>(null);
  const [testArguments, setTestArguments] = useState<string>('{}');
  const [calling, setCalling] = useState<boolean>(false);
  const [callResult, setCallResult] = useState<MCPToolCallResult | null>(null);

  const fetchData = async () => {
    if (!orgId) return;
    setLoading(true);
    setError(null);
    try {
      const [serversRes, toolsRes, metricsRes] = await Promise.all([
        mcpApi.listServers(orgId),
        mcpApi.listTools(orgId),
        mcpApi.getMetrics(orgId).catch(() => null),
      ]);
      setServers(serversRes.items || []);
      setTools(toolsRes.items || []);
      if (metricsRes) setMetrics(metricsRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load MCP resources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [orgId]);

  const handleRegisterServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgId) return;
    setRegistering(true);
    try {
      await mcpApi.createServer(orgId, registerForm);
      setIsRegisterOpen(false);
      setRegisterForm({
        name: '',
        endpoint: '',
        transport: 'HTTP',
        server_type: 'REMOTE',
        trust_level: 'UNTRUSTED',
        description: '',
        environment: 'production',
      });
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to register MCP server');
    } finally {
      setRegistering(false);
    }
  };

  const handleDiscover = async (serverId: string) => {
    if (!orgId) return;
    setDiscoveringServerId(serverId);
    try {
      const res = await mcpApi.discoverServerTools(orgId, serverId);
      setDiscoveryResult(res);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Discovery failed');
    } finally {
      setDiscoveringServerId(null);
    }
  };

  const handleActivateTool = async (toolId: string) => {
    if (!orgId) return;
    try {
      await mcpApi.activateTool(orgId, toolId);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to activate tool');
    }
  };

  const handleSuspendTool = async (toolId: string) => {
    if (!orgId) return;
    try {
      await mcpApi.suspendTool(orgId, toolId);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to suspend tool');
    }
  };

  const handleExecuteTool = async () => {
    if (!orgId || !testTool) return;
    setCalling(true);
    setCallResult(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(testArguments);
      } catch (e) {
        alert('Invalid JSON in arguments');
        setCalling(false);
        return;
      }
      const res = await mcpApi.callTool(orgId, testTool.id, { arguments: parsedArgs }, 'development');
      setCallResult(res);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Execution request failed');
    } finally {
      setCalling(false);
    }
  };

  const driftedTools = tools.filter((t) => t.schema_changed);

  const filteredTools = tools.filter((t) => {
    const matchesStatus = statusFilter === 'ALL' || t.status.toUpperCase() === statusFilter.toUpperCase();
    const matchesSearch =
      !searchQuery ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.description && t.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <Compass className="w-7 h-7 text-indigo-600" />
            MCP Security Layer
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Authoritative Model Context Protocol boundary governance, schema fingerprinting, and execution containment.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsRegisterOpen(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none"
          >
            <Plus className="w-4 h-4 mr-2" />
            Register MCP Server
          </button>
        </div>
      </div>

      {/* Schema Drift Alert Banner */}
      {driftedTools.length > 0 && (
        <div className="rounded-lg bg-amber-50 border-l-4 border-amber-500 p-4 shadow-sm">
          <div className="flex items-start">
            <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 mr-3 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-amber-800">
                Schema Drift Detected ({driftedTools.length} {driftedTools.length === 1 ? 'Tool' : 'Tools'})
              </h3>
              <p className="text-sm text-amber-700 mt-1">
                The canonical SHA-256 schema hash mutated since previous operator approval. In accordance with zero-trust principles, tool execution is suspended until operator review and re-activation.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {driftedTools.map((t) => (
                  <span
                    key={t.id}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-900"
                  >
                    {t.name} (Drifted)
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">MCP Servers</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {metrics?.total_servers ?? servers.length}
              </p>
            </div>
            <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg">
              <Server className="w-6 h-6" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs text-gray-500">
            <span className="text-emerald-600 font-medium mr-1.5">
              {metrics?.active_servers ?? servers.filter((s) => s.status === 'ACTIVE').length} Active
            </span>
            <span>• {servers.filter((s) => s.status !== 'ACTIVE').length} Inactive</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Discovered Tools</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {metrics?.total_tools ?? tools.length}
              </p>
            </div>
            <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
              <Wrench className="w-6 h-6" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs text-gray-500">
            <span className="text-emerald-600 font-medium mr-1.5">
              {tools.filter((t) => t.status === 'ACTIVE').length} Active
            </span>
            <span>• {tools.filter((t) => t.status === 'DISCOVERED').length} Discovered</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Schema Drift Alerts</p>
              <p className={`text-2xl font-bold mt-1 ${driftedTools.length > 0 ? 'text-amber-600' : 'text-gray-900'}`}>
                {metrics?.schema_drift_tools ?? driftedTools.length}
              </p>
            </div>
            <div className={`p-3 rounded-lg ${driftedTools.length > 0 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>
              <Fingerprint className="w-6 h-6" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs text-gray-500">
            <span>Deterministic SHA-256 fingerprinting</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool Invocations</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {metrics?.total_calls ?? 0}
              </p>
            </div>
            <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
              <Zap className="w-6 h-6" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs text-gray-500">
            <span className="text-red-600 font-medium mr-1.5">
              {metrics?.blocked_calls ?? 0} Blocked
            </span>
            <span>by CUSTODE Control Plane</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('servers')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'servers'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Server className="w-4 h-4" />
            Registered Servers ({servers.length})
          </button>
          <button
            onClick={() => setActiveTab('tools')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'tools'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Wrench className="w-4 h-4" />
            Discovered & Active Tools ({tools.length})
          </button>
        </nav>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 text-sm rounded">
          {error}
        </div>
      )}

      {/* TAB 1: SERVERS */}
      {activeTab === 'servers' && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Server Name / Slug
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Endpoint
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Transport
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Trust Tier
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {servers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500 text-sm">
                      No MCP servers registered yet. Click "Register MCP Server" to define an untrusted boundary.
                    </td>
                  </tr>
                ) : (
                  servers.map((s) => (
                    <tr key={s.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900">{s.name}</div>
                        <div className="text-xs text-gray-500 font-mono">{s.slug}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 font-mono text-xs">
                        {s.endpoint}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {s.transport}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            s.trust_level === 'TRUSTED'
                              ? 'bg-emerald-100 text-emerald-800'
                              : s.trust_level === 'VERIFIED'
                              ? 'bg-indigo-100 text-indigo-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {s.trust_level}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            s.status === 'ACTIVE'
                              ? 'bg-emerald-100 text-emerald-800'
                              : s.status === 'SUSPENDED'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                        <button
                          onClick={() => handleDiscover(s.id)}
                          disabled={discoveringServerId === s.id || s.status !== 'ACTIVE'}
                          className="inline-flex items-center px-3 py-1.5 border border-indigo-600 text-xs font-medium rounded text-indigo-600 bg-white hover:bg-indigo-50 disabled:opacity-50"
                        >
                          <Compass className={`w-3.5 h-3.5 mr-1 ${discoveringServerId === s.id ? 'animate-spin' : ''}`} />
                          Discover
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: TOOLS */}
      {activeTab === 'tools' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-72">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tools..."
                className="w-full pl-3 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Status:</span>
              {['ALL', 'DISCOVERED', 'ACTIVE', 'SUSPENDED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1 rounded-md text-xs font-medium ${
                    statusFilter === st
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tool Name / Schema
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Schema Fingerprint
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Risk Tier
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredTools.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500 text-sm">
                        No MCP tools discovered yet. Discover tools from an active server to inspect schemas.
                      </td>
                    </tr>
                  ) : (
                    filteredTools.map((t) => (
                      <tr key={t.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <div className="font-medium text-gray-900">{t.name}</div>
                          <div className="text-xs text-gray-500 line-clamp-1">{t.description || 'No description'}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col gap-1">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                                t.status === 'ACTIVE'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : t.status === 'DISCOVERED'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {t.status}
                            </span>
                            {t.schema_changed && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-500 text-white">
                                SCHEMA_CHANGED
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="font-mono text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                            {t.schema_hash.slice(0, 12)}...
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              t.risk_level === 'critical'
                                ? 'bg-red-100 text-red-800'
                                : t.risk_level === 'high'
                                ? 'bg-amber-100 text-amber-800'
                                : t.risk_level === 'medium'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {t.risk_level.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                          {t.status !== 'ACTIVE' ? (
                            <button
                              onClick={() => handleActivateTool(t.id)}
                              className="inline-flex items-center px-2.5 py-1.5 border border-transparent text-xs font-medium rounded text-white bg-emerald-600 hover:bg-emerald-700"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                              Activate
                            </button>
                          ) : (
                            <button
                              onClick={() => handleSuspendTool(t.id)}
                              className="inline-flex items-center px-2.5 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                            >
                              <XCircle className="w-3.5 h-3.5 mr-1 text-amber-600" />
                              Suspend
                            </button>
                          )}
                          <button
                            onClick={() => {
                              setTestTool(t);
                              setTestArguments('{}');
                              setCallResult(null);
                            }}
                            className="inline-flex items-center px-2.5 py-1.5 border border-indigo-600 text-xs font-medium rounded text-indigo-600 bg-white hover:bg-indigo-50"
                          >
                            <Play className="w-3.5 h-3.5 mr-1" />
                            Test Call
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Register Server */}
      {isRegisterOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Register New MCP Server</h3>
            <form onSubmit={handleRegisterServer} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700">Server Name</label>
                <input
                  type="text"
                  required
                  value={registerForm.name}
                  onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="e.g. GitHub Repository Context"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Endpoint URL</label>
                <input
                  type="text"
                  required
                  value={registerForm.endpoint}
                  onChange={(e) => setRegisterForm({ ...registerForm, endpoint: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono text-xs"
                  placeholder="https://mcp.github.com/v1"
                />
                <p className="text-xs text-gray-500 mt-1">SSRF protection rejects localhost, 127.0.0.1, and cloud metadata.</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700">Transport</label>
                  <select
                    value={registerForm.transport}
                    onChange={(e) => setRegisterForm({ ...registerForm, transport: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="HTTP">HTTP (JSON-RPC)</option>
                    <option value="SSE">SSE</option>
                    <option value="MOCK">MOCK (Test Server)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700">Trust Tier</label>
                  <select
                    value={registerForm.trust_level}
                    onChange={(e) => setRegisterForm({ ...registerForm, trust_level: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="UNTRUSTED">UNTRUSTED</option>
                    <option value="VERIFIED">VERIFIED</option>
                    <option value="TRUSTED">TRUSTED</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Description</label>
                <textarea
                  rows={2}
                  value={registerForm.description}
                  onChange={(e) => setRegisterForm({ ...registerForm, description: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsRegisterOpen(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registering}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
                >
                  {registering ? 'Validating & Registering...' : 'Register Server'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Discovery Result */}
      {discoveryResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Compass className="w-5 h-5 text-indigo-600" />
                Discovery Completed
              </h3>
              <button
                onClick={() => setDiscoveryResult(null)}
                className="text-gray-400 hover:text-gray-600 text-sm"
              >
                ✕
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-gray-50 p-3 rounded">
                <span className="text-gray-500 block text-xs">Total Discovered</span>
                <span className="text-lg font-bold text-gray-900">{discoveryResult.discovered_count}</span>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <span className="text-gray-500 block text-xs">New Tools Fingerprinted</span>
                <span className="text-lg font-bold text-emerald-600">{discoveryResult.new_tools_count}</span>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <span className="text-gray-500 block text-xs">Schema Drift Detected</span>
                <span className="text-lg font-bold text-amber-600">{discoveryResult.schema_drift_count}</span>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <span className="text-gray-500 block text-xs">Sentinel Security Findings</span>
                <span className="text-lg font-bold text-red-600">{discoveryResult.findings_count}</span>
              </div>
            </div>
            {discoveryResult.findings && discoveryResult.findings.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs font-semibold text-gray-700 block">Flagged Findings:</span>
                <div className="max-h-40 overflow-y-auto space-y-1 text-xs">
                  {discoveryResult.findings.map((f, i) => (
                    <div key={i} className="p-2 bg-red-50 text-red-800 rounded border border-red-200">
                      <strong>[{f.severity?.toUpperCase()}]</strong> {f.title}: {f.description}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setDiscoveryResult(null)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Test Tool Call */}
      {testTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="bg-white rounded-lg max-w-xl w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Play className="w-5 h-5 text-indigo-600" />
                Test MCP Tool: {testTool.name}
              </h3>
              <button
                onClick={() => setTestTool(null)}
                className="text-gray-400 hover:text-gray-600 text-sm"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700">Input Arguments (JSON)</label>
              <textarea
                rows={4}
                value={testArguments}
                onChange={(e) => setTestArguments(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-xs"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setTestTool(null)}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteTool}
                disabled={calling}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
              >
                {calling && <RefreshCw className="w-4 h-4 animate-spin" />}
                Execute Tool Call
              </button>
            </div>

            {callResult && (
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-xs space-y-2">
                <div className="flex items-center justify-between font-semibold">
                  <span>Decision: <strong className={callResult.decision === 'allow' ? 'text-emerald-600' : 'text-red-600'}>{callResult.decision.toUpperCase()}</strong></span>
                  <span>Status: {callResult.status}</span>
                  <span>Latency: {callResult.latency_ms?.toFixed(1)}ms</span>
                </div>
                {callResult.error && (
                  <div className="p-2 bg-red-100 text-red-800 rounded">
                    {callResult.error}
                  </div>
                )}
                {callResult.result && (
                  <div>
                    <span className="font-semibold block text-gray-700">Response Payload:</span>
                    <pre className="mt-1 p-2 bg-white rounded border border-gray-200 overflow-x-auto">
                      {JSON.stringify(callResult.result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
