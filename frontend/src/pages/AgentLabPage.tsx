import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity,
  Bot,
  Check,
  CheckCircle2,
  Clipboard,
  Copy,
  Cpu,
  Download,
  Loader2,
  Play,
  Power,
  RefreshCw,
  Server,
  Settings2,
  SlidersHorizontal,
  XCircle,
} from 'lucide-react';
import {
  checkHealth,
  executeSampleRun,
  fetchAgentLabServiceStatus,
  fetchModels,
  fetchSampleRuns,
  isTauri,
  startAgentLabService,
  stopAgentLabService,
} from '../lib/api';
import type { AgentLabServiceStatus, AgentTemplate, SampleRunResult, SampleScenario } from '../lib/api';
import { ToolCallCard } from '../components/Chat/ToolCallCard';
import type { ModelInfo, ToolCallInfo } from '../types';

type EngineChoice = 'auto' | 'current' | 'ollama' | 'mlx';
type ServiceAction = 'ollama' | 'mlx' | 'api' | 'all';

function statusTone(status?: SampleRunResult['status']) {
  if (status === 'passed') return 'var(--color-success)';
  if (status === 'failed' || status === 'error') return 'var(--color-error)';
  if (status === 'running' || status === 'queued') return 'var(--color-accent)';
  return 'var(--color-text-tertiary)';
}

function asToolCallInfo(item: unknown, index: number): ToolCallInfo {
  const raw = (item || {}) as Record<string, unknown>;
  return {
    id: String(raw.id || `sample-tool-${index}`),
    tool: String(raw.name || raw.tool || 'tool_call'),
    arguments: String(raw.arguments || ''),
    result: raw.result === undefined ? undefined : String(raw.result),
    status: raw.success === false ? 'error' : 'success',
  };
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  if (error && typeof error === 'object') {
    const maybeMessage = (error as { message?: unknown }).message;
    if (typeof maybeMessage === 'string' && maybeMessage.trim()) return maybeMessage;
  }
  return fallback;
}

export function AgentLabPage() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [scenarios, setScenarios] = useState<SampleScenario[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [prompt, setPrompt] = useState('');
  const [engine, setEngine] = useState<EngineChoice>('auto');
  const [model, setModel] = useState('');
  const [maxTurns, setMaxTurns] = useState(10);
  const [temperature, setTemperature] = useState(0.3);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [running, setRunning] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<AgentLabServiceStatus | null>(null);
  const [serviceBusy, setServiceBusy] = useState<string | null>(null);
  const [result, setResult] = useState<SampleRunResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchSampleRuns(),
      fetchModels().catch(() => [] as ModelInfo[]),
      checkHealth(),
    ])
      .then(([sampleData, modelData, health]) => {
        if (cancelled) return;
        setTemplates(sampleData.templates || []);
        setScenarios(sampleData.scenarios || []);
        setModels(modelData);
        setApiReady(health);
        if (sampleData.scenarios?.length) {
          setSelectedId(sampleData.scenarios[0].id);
          setPrompt(sampleData.scenarios[0].prompt);
        }
        if (modelData.length) setModel(modelData[0].id);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(errorText(err, 'Failed to load Agent Lab'));
        setApiReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function refreshServices() {
      const status = await fetchAgentLabServiceStatus();
      if (!cancelled) setServiceStatus(status);
    }
    refreshServices();
    const timer = window.setInterval(refreshServices, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.id === selectedId) || null,
    [scenarios, selectedId],
  );
  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedScenario?.template_id) || null,
    [templates, selectedScenario],
  );
  const canRun = !!selectedScenario && apiReady === true && !running;
  const toolCalls = (result?.tool_calls || []).map(asToolCallInfo);

  function selectScenario(scenario: SampleScenario) {
    setSelectedId(scenario.id);
    setPrompt(scenario.prompt);
    setResult(null);
    setError('');
  }

  async function runScenario() {
    if (!selectedScenario) return;
    setRunning(true);
    setError('');
    setResult({
      run_id: 'pending',
      scenario_id: selectedScenario.id,
      template_id: selectedScenario.template_id,
      status: 'running',
      engine,
      model,
      content: '',
      checks: [],
      tool_calls: [],
      allowed_tools: selectedScenario.allowed_tools,
      usage: {},
      latency_seconds: 0,
      trace_id: null,
      error: null,
      created_at: Date.now() / 1000,
    });
    try {
      const next = await executeSampleRun(selectedScenario.id, {
        prompt,
        engine,
        model: model || undefined,
        max_turns: maxTurns,
        temperature,
      });
      setResult(next);
    } catch (err: unknown) {
      setError(errorText(err, 'Sample run failed'));
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  async function refreshServiceStatus() {
    const status = await fetchAgentLabServiceStatus();
    setServiceStatus(status);
  }

  async function startService(service: ServiceAction) {
    setServiceBusy(`start-${service}`);
    setError('');
    try {
      const status = await startAgentLabService(service);
      setServiceStatus(status);
      const [modelData, health] = await Promise.all([
        fetchModels().catch(() => [] as ModelInfo[]),
        checkHealth(),
      ]);
      setModels(modelData);
      setApiReady(health);
      if (modelData.length && !model) setModel(modelData[0].id);
    } catch (err: unknown) {
      setError(errorText(err, `Failed to start ${service}`));
    } finally {
      setServiceBusy(null);
    }
  }

  async function stopService(service: ServiceAction) {
    setServiceBusy(`stop-${service}`);
    setError('');
    try {
      const status = await stopAgentLabService(service);
      setServiceStatus(status);
      setApiReady(await checkHealth());
    } catch (err: unknown) {
      setError(errorText(err, `Failed to stop ${service}`));
    } finally {
      setServiceBusy(null);
    }
  }

  async function copyResult() {
    if (!result) return;
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  function downloadResult() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-4 py-5 lg:px-6">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
              Agent Lab
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: apiReady ? 'var(--color-success)' : 'var(--color-error)' }}
                />
                Backend {apiReady === null ? 'checking' : apiReady ? 'ready' : 'offline'}
              </span>
              <span>{models.length} local models detected</span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowAdvanced((value) => !value)}
            className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2"
            style={{
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
            aria-label="Toggle advanced run settings"
          >
            <SlidersHorizontal size={16} />
            Advanced
          </button>
        </div>

        {error && (
          <div
            className="mb-4 rounded-md px-3 py-2 text-sm"
            style={{
              border: '1px solid color-mix(in srgb, var(--color-error) 30%, transparent)',
              color: 'var(--color-error)',
              background: 'color-mix(in srgb, var(--color-error) 8%, transparent)',
            }}
            role="alert"
          >
            {error}
          </div>
        )}

        <section
          className="mb-4 rounded-lg p-4"
          style={{ border: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
          aria-label="Agent Lab service controls"
        >
          <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                <Server size={16} />
                Services
              </div>
              <p className="mt-1 text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                {isTauri()
                  ? serviceStatus?.message || 'Checking local service status'
                  : 'Service start/stop is available in the OpenJarvis desktop app. Browser mode can only detect the API.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={refreshServiceStatus}
                className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-2"
                style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                aria-label="Refresh service status"
              >
                <RefreshCw size={14} />
                Refresh
              </button>
              {isTauri() && (
                <button
                  type="button"
                  onClick={() => startService('all')}
                  disabled={!!serviceBusy}
                  className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium focus:outline-none focus:ring-2 disabled:opacity-50"
                  style={{ background: 'var(--color-accent)', color: 'white' }}
                  aria-label="Start Agent Lab services"
                >
                  {serviceBusy === 'start-all' ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
                  Start Ollama + API
                </button>
              )}
            </div>
          </div>

          <div className="grid gap-2 md:grid-cols-3">
            {[
              {
                key: 'ollama' as ServiceAction,
                label: 'Ollama',
                icon: Cpu,
                ready: serviceStatus?.ollama_ready,
                managed: serviceStatus?.ollama_managed,
                detail: `${serviceStatus?.ollama_models.length || 0} models`,
              },
              {
                key: 'api' as ServiceAction,
                label: 'OpenJarvis API',
                icon: Server,
                ready: serviceStatus?.api_ready ?? apiReady,
                managed: serviceStatus?.api_managed,
                detail: `${serviceStatus?.api_models.length || models.length} models`,
              },
              {
                key: 'mlx' as ServiceAction,
                label: 'MLX',
                icon: Cpu,
                ready: serviceStatus?.mlx_ready,
                managed: serviceStatus?.mlx_managed,
                detail: `${serviceStatus?.mlx_models.length || 0} models`,
              },
            ].map((item) => {
              const Icon = item.icon;
              const ready = item.ready === true;
              return (
                <div
                  key={item.key}
                  className="flex items-center justify-between gap-3 rounded-md p-3"
                  style={{ border: '1px solid var(--color-border)', background: 'var(--color-bg)' }}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                      <Icon size={15} />
                      {item.label}
                    </div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      {ready ? 'Ready' : 'Offline'} · {item.detail} · {item.managed ? 'managed' : 'external'}
                    </div>
                  </div>
                  {isTauri() && (
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        onClick={() => startService(item.key)}
                        disabled={!!serviceBusy || ready}
                        className="rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 disabled:opacity-50"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                        aria-label={`Start ${item.label}`}
                      >
                        {serviceBusy === `start-${item.key}` ? '...' : 'Start'}
                      </button>
                      <button
                        type="button"
                        onClick={() => stopService(item.key)}
                        disabled={!!serviceBusy || !item.managed}
                        className="rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 disabled:opacity-50"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                        aria-label={`Stop ${item.label}`}
                      >
                        Stop
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <section
            className="rounded-lg p-3"
            style={{ border: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
            aria-label="Sample agent scenarios"
          >
            <div className="mb-3 flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              <Bot size={16} />
              Sample Agents
            </div>
            <div className="space-y-2">
              {scenarios.map((scenario) => {
                const active = scenario.id === selectedId;
                return (
                  <button
                    key={scenario.id}
                    type="button"
                    onClick={() => selectScenario(scenario)}
                    className="w-full rounded-md p-3 text-left transition-colors focus:outline-none focus:ring-2"
                    style={{
                      border: active ? '1px solid var(--color-accent)' : '1px solid var(--color-border)',
                      background: active ? 'var(--color-accent-subtle)' : 'var(--color-bg)',
                      color: 'var(--color-text)',
                    }}
                    aria-pressed={active}
                  >
                    <div className="text-sm font-medium">{scenario.title}</div>
                    <div className="mt-1 text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                      {scenario.template_name}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="min-w-0 space-y-4" aria-label="Sample run workspace">
            <div
              className="rounded-lg p-4"
              style={{ border: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
                    {selectedScenario?.title || 'Select a sample'}
                  </h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                    {selectedScenario?.summary || ''}
                  </p>
                  {selectedTemplate && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="rounded px-2 py-1 text-xs" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}>
                        {selectedTemplate.agent_type}
                      </span>
                      {(selectedScenario?.allowed_tools || []).map((tool) => (
                        <span key={tool} className="rounded px-2 py-1 text-xs" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}>
                          {tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={runScenario}
                  disabled={!canRun}
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-opacity focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{ background: 'var(--color-accent)', color: 'white' }}
                  aria-label="Run selected sample agent"
                >
                  {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  Run Sample
                </button>
              </div>

              {showAdvanced && (
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                    Engine
                    <select
                      value={engine}
                      onChange={(event) => setEngine(event.target.value as EngineChoice)}
                      className="mt-1 w-full rounded-md bg-transparent px-3 py-2 text-sm"
                      style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                    >
                      <option value="auto">Auto</option>
                      <option value="current">Current server</option>
                      <option value="ollama">Ollama</option>
                      <option value="mlx">MLX</option>
                    </select>
                  </label>
                  <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                    Model
                    <input
                      value={model}
                      onChange={(event) => setModel(event.target.value)}
                      list="agent-lab-models"
                      className="mt-1 w-full rounded-md bg-transparent px-3 py-2 text-sm"
                      style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                    />
                    <datalist id="agent-lab-models">
                      {models.map((item) => (
                        <option key={item.id} value={item.id} />
                      ))}
                    </datalist>
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                      Turns
                      <input
                        type="number"
                        min={1}
                        max={30}
                        value={maxTurns}
                        onChange={(event) => setMaxTurns(Number(event.target.value))}
                        className="mt-1 w-full rounded-md bg-transparent px-3 py-2 text-sm"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      />
                    </label>
                    <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                      Temp
                      <input
                        type="number"
                        min={0}
                        max={2}
                        step={0.05}
                        value={temperature}
                        onChange={(event) => setTemperature(Number(event.target.value))}
                        className="mt-1 w-full rounded-md bg-transparent px-3 py-2 text-sm"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      />
                    </label>
                  </div>
                </div>
              )}

              <label className="mt-4 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                Prompt
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={7}
                  className="mt-1 w-full resize-y rounded-md bg-transparent px-3 py-2 text-sm leading-6 focus:outline-none focus:ring-2"
                  style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              </label>
            </div>

            <div
              className="rounded-lg p-4"
              style={{ border: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
              aria-live="polite"
            >
              <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-2">
                  <Activity size={16} style={{ color: statusTone(result?.status) }} />
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                    {result ? result.status : 'No run yet'}
                  </span>
                  {result && (
                    <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                      {result.engine} / {result.model} / {result.latency_seconds.toFixed(2)}s
                    </span>
                  )}
                </div>
                {result && result.status !== 'running' && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={copyResult}
                      className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:ring-2"
                      style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      aria-label="Copy sample run JSON"
                    >
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      type="button"
                      onClick={downloadResult}
                      className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:ring-2"
                      style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      aria-label="Download sample run JSON"
                    >
                      <Download size={14} />
                      Export
                    </button>
                  </div>
                )}
              </div>

              {running && (
                <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  <Loader2 size={16} className="animate-spin" />
                  Running local sample
                </div>
              )}

              {result?.error && (
                <div className="rounded-md p-3 text-sm" style={{ color: 'var(--color-error)', background: 'color-mix(in srgb, var(--color-error) 8%, transparent)' }}>
                  {result.error}
                </div>
              )}

              {result?.content && (
                <div className="prose prose-sm max-w-none" style={{ color: 'var(--color-text)' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
                </div>
              )}

              {result && result.checks.length > 0 && (
                <div className="mt-4 grid gap-2 md:grid-cols-3">
                  {result.checks.map((check) => (
                    <div
                      key={check.key}
                      className="flex items-start gap-2 rounded-md p-3 text-sm"
                      style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                    >
                      {check.passed ? (
                        <CheckCircle2 size={16} style={{ color: 'var(--color-success)' }} />
                      ) : (
                        <XCircle size={16} style={{ color: 'var(--color-error)' }} />
                      )}
                      <span>{check.label}</span>
                    </div>
                  ))}
                </div>
              )}

              {result && (
                <div className="mt-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                    <Settings2 size={15} />
                    Tool Timeline
                  </div>
                  {toolCalls.length > 0 ? (
                    <div className="space-y-2">
                      {toolCalls.map((toolCall) => (
                        <ToolCallCard key={toolCall.id} toolCall={toolCall} />
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {(result.allowed_tools || selectedScenario?.allowed_tools || []).map((tool) => (
                        <span key={tool} className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}>
                          <Clipboard size={12} />
                          {tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
