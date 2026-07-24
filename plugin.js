import {
  appendFileSync,
  copyFileSync,
  mkdirSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

const HOME = homedir();
const LOG_PATH = path.join(HOME, ".opencode", "opencode-dispatch.log");
const DEFAULT_REPORT_DIR = path.join(HOME, ".opencode", "opencode-dispatch-reports");
const DEFAULT_OPENCODE_CONFIG_PATH = path.join(HOME, ".config", "opencode", "opencode.json");
const DEBOUNCE_MS = 5000;
const REPORT_SETTLE_MS = 350;

function defaults() {
  return {
    enabled: true,
    cooldownMs: 120000,
    transientCooldownMs: 30000,
    fallbackModels: [],
    fallbackGroups: {},
    modelGroups: {},
    permanentStatusCodes: [402, 403, 404, 410],
    transientStatusCodes: [408, 500, 502, 503, 504],
    authFailureFallbackProviders: ["openai"],
    providerWideRateLimitProviders: ["openai"],
    providerWideRetryProviders: ["openai"],
    providerCooldownMs: 900000,
    retryFailoverAttempt: 1,
    opencodeConfigPath: DEFAULT_OPENCODE_CONFIG_PATH,
    orchestration: {
      enabled: true,
      enforce: true,
      autoClassify: true,
      maxAutoRemediations: 2,
      report: true,
    },
    telemetry: {
      enabled: true,
      reportDir: DEFAULT_REPORT_DIR,
      writeLiveReport: true,
      writeMarkdown: true,
      writeJson: true,
      includeSubagents: true,
    },
  };
}

function loadConfig(directory) {
  const base = defaults();
  const candidates = [
    path.join(HOME, ".opencode", "opencode-dispatch.json"),
    path.join(directory ?? process.cwd(), "opencode-dispatch.json"),
  ];
  for (const file of candidates) {
    try {
      const parsed = JSON.parse(readFileSync(file, "utf-8"));
      return {
        ...base,
        ...parsed,
        telemetry: { ...base.telemetry, ...(parsed.telemetry ?? {}) },
        orchestration: { ...base.orchestration, ...(parsed.orchestration ?? {}) },
        _source: file,
      };
    } catch {
    }
  }
  return { ...base, _source: null };
}

function log(message) {
  try {
    mkdirSync(path.dirname(LOG_PATH), { recursive: true });
    appendFileSync(LOG_PATH, `[${new Date().toISOString()}] ${message}\n`);
  } catch {
  }
}

function atomicWrite(file, content) {
  mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.tmp-${process.pid}-${Date.now()}`;
  writeFileSync(temp, content);
  try {
    renameSync(temp, file);
  } catch {
    copyFileSync(temp, file);
    unlinkSync(temp);
  }
}

function modelKey(model) {
  return `${model.providerID}/${model.modelID}`;
}

function normalizeStatus(value) {
  const status = Number(value);
  return Number.isFinite(status) ? status : undefined;
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeTokens(tokens) {
  if (!tokens || typeof tokens !== "object") {
    return {
      available: false,
      input: 0,
      output: 0,
      reasoning: 0,
      cacheRead: 0,
      cacheWrite: 0,
      total: 0,
    };
  }
  const result = {
    available: true,
    input: number(tokens.input),
    output: number(tokens.output),
    reasoning: number(tokens.reasoning),
    cacheRead: number(tokens.cache?.read),
    cacheWrite: number(tokens.cache?.write),
  };
  result.total =
    result.input +
    result.output +
    result.reasoning +
    result.cacheRead +
    result.cacheWrite;
  return result;
}

function addTokens(target, value) {
  target.input += value.input;
  target.output += value.output;
  target.reasoning += value.reasoning;
  target.cacheRead += value.cacheRead;
  target.cacheWrite += value.cacheWrite;
  target.total += value.total;
}

function emptyTokens() {
  return {
    input: 0,
    output: 0,
    reasoning: 0,
    cacheRead: 0,
    cacheWrite: 0,
    total: 0,
  };
}

function signalText(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function signalFromError(error) {
  return {
    statusCode: normalizeStatus(
      error?.data?.statusCode ??
        error?.statusCode ??
        error?.status ??
        error?.response?.status,
    ),
    responseHeaders:
      error?.data?.responseHeaders ?? error?.response?.headers ?? undefined,
    text: [
      error?.data?.message,
      error?.data?.responseBody,
      error?.data?.metadata,
      error?.data?.code,
      error?.message,
      error?.name,
      error?.body,
      error?.response?.data,
    ]
      .map(signalText)
      .filter(Boolean)
      .join(" "),
  };
}

function classify(config, signal) {
  const statusCode = normalizeStatus(signal?.statusCode);
  const text = String(signal?.text ?? "").toLowerCase();

  if (signal?.actionReason === "account_rate_limit" || signal?.actionReason === "free_tier_limit") {
    return "account_limit";
  }
  if (statusCode === 429) return "rate_limit";
  if (statusCode === 401) return "auth";
  if ((config.permanentStatusCodes ?? []).includes(statusCode)) return "permanent";
  if ((config.transientStatusCodes ?? []).includes(statusCode)) return "transient";

  if (
    text.includes("usage_limit_reached") ||
    text.includes("insufficient_quota") ||
    text.includes("usage limit reached") ||
    text.includes("codex usage limit") ||
    text.includes("weekly usage limit") ||
    text.includes("weekly limit") ||
    text.includes("monthly usage limit") ||
    text.includes("allowance reached") ||
    text.includes("included usage") ||
    text.includes("you have no weighted tokens left") ||
    text.includes("out of credits") ||
    text.includes("credits exhausted") ||
    text.includes("no credits remaining") ||
    text.includes("add credits") ||
    text.includes("purchase credits") ||
    text.includes("available balance") ||
    text.includes("wait for your limit to reset") ||
    text.includes("limit will reset") ||
    text.includes("resets on") ||
    text.includes("reset in")
  ) {
    return "account_limit";
  }

  if (
    text.includes("too many requests") ||
    text.includes("rate limit") ||
    text.includes("rate_limit") ||
    text.includes("quota exceeded") ||
    text.includes("usage limit") ||
    text.includes("limit reached") ||
    text.includes("resource exhausted") ||
    text.includes("capacity exceeded")
  ) {
    return "rate_limit";
  }

  if (
    text.includes("invalid authentication") ||
    text.includes("invalid api key") ||
    text.includes("oauth token expired") ||
    text.includes("token refresh failed")
  ) {
    return "auth";
  }

  if (
    text.includes("payment required") ||
    text.includes("insufficient credit") ||
    text.includes("insufficient balance") ||
    text.includes("billing required") ||
    text.includes("no longer free") ||
    text.includes("model not found") ||
    text.includes("not available for this account") ||
    text.includes("not authorized for this model") ||
    text.includes("forbidden") ||
    text.includes("has been retired") ||
    text.includes("end of life") ||
    text.includes("no longer available") ||
    text.includes("deprecated")
  ) {
    return "permanent";
  }

  if (
    text.includes("service unavailable") ||
    text.includes("temporarily unavailable") ||
    text.includes("bad gateway") ||
    text.includes("gateway timeout") ||
    text.includes("overloaded") ||
    text.includes("upstream error")
  ) {
    return "transient";
  }

  return null;
}

function uniqueModels(models) {
  const seen = new Set();
  const output = [];
  for (const model of models ?? []) {
    if (!model?.providerID || !model?.modelID) continue;
    const key = modelKey(model);
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(model);
  }
  return output;
}

function extractMessageInfo(info) {
  const metadata = info?.metadata ?? {};
  const assistant = metadata.assistant ?? {};
  const time = info?.time ?? metadata.time ?? {};
  return {
    id: info?.id,
    sessionID: info?.sessionID ?? metadata.sessionID,
    role: info?.role,
    providerID: info?.providerID ?? assistant.providerID,
    modelID: info?.modelID ?? assistant.modelID,
    agent: info?.agent ?? info?.mode ?? assistant.agent,
    createdAt: number(time.created),
    completedAt: number(time.completed),
    tokens: normalizeTokens(info?.tokens ?? assistant.tokens),
    cost: number(info?.cost ?? assistant.cost),
    finish: info?.finish,
    error: info?.error ?? metadata.error,
  };
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(number(value));
}

function formatPercent(value) {
  return `${number(value).toFixed(1)}%`;
}

function formatDuration(milliseconds) {
  const ms = Math.max(0, number(milliseconds));
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes} min ${remaining}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours} h ${mins} min`;
}

function safeFilename(value) {
  return String(value ?? "unknown").replace(/[^a-zA-Z0-9._-]+/g, "_");
}

function readDisplayMetadata(configPath) {
  const names = new Map();
  const agents = new Map();
  try {
    const config = JSON.parse(readFileSync(configPath ?? DEFAULT_OPENCODE_CONFIG_PATH, "utf-8"));
    for (const [providerID, provider] of Object.entries(config.provider ?? {})) {
      for (const [modelID, model] of Object.entries(provider?.models ?? {})) {
        names.set(`${providerID}/${modelID}`, model?.name ?? `${providerID}/${modelID}`);
      }
    }
    for (const [agentID, agent] of Object.entries(config.agent ?? {})) {
      agents.set(agentID, agent?.description ?? agentID);
    }
  } catch {
  }
  return { names, agents };
}

export const OpenCodeDispatch = async ({ client, directory, $ }) => {
  const config = loadConfig(directory);
  const globalModels = uniqueModels(config.fallbackModels);
  const telemetryConfig = config.telemetry ?? defaults().telemetry;
  const orchestrationConfig = config.orchestration ?? defaults().orchestration;
  const reportDir = String(
    telemetryConfig.reportDir ?? DEFAULT_REPORT_DIR,
  ).replace(/^~(?=\/)/, HOME);

  log(
    `opencode-dispatch 1.0 loaded; config=${config._source ?? "defaults"}; ` +
      `global=${globalModels.length}; groups=${Object.keys(config.fallbackGroups ?? {}).length}; ` +
      `orchestration=${orchestrationConfig.enabled ? "on" : "off"}; ` +
      `telemetry=${telemetryConfig.enabled ? "on" : "off"}`,
  );

  let toolFactory = null;
  try {
    const pluginModule = await import("@opencode-ai/plugin");
    toolFactory = pluginModule.tool;
    log("opencode-dispatch 1.0: orchestration tool dependency loaded");
  } catch (error) {
    orchestrationConfig.enabled = false;
    log(
      "opencode-dispatch 1.0: @opencode-ai/plugin unavailable; " +
        "fallback and telemetry remain active; orchestration tools disabled; " +
        `detail=${error?.message ?? error}`,
    );
  }

  if (!config.enabled || globalModels.length === 0) {
    log("disabled or no fallbackModels configured; plugin is inactive");
    return {};
  }

  const unavailableUntil = new Map();
  const providerUnavailableUntil = new Map();
  const sessionModel = new Map();
  const sessionGroup = new Map();
  const lastHandledFailure = new Map();

  const sessions = new Map();
  const messages = new Map();
  const fallbacks = new Map();
  const sessionUsage = new Map();
  const reportTimers = new Map();
  const orchestrationRuns = new Map();
  const suppressNextUserTurn = new Set();
  const fallbackInProgress = new Set();

  function ensureSession(sessionID) {
    if (!sessionID) return null;
    if (!sessions.has(sessionID)) {
      sessions.set(sessionID, {
        id: sessionID,
        parentID: null,
        title: null,
        directory,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        idleAt: null,
      });
    }
    return sessions.get(sessionID);
  }

  function updateSession(info) {
    const sessionID = info?.id ?? info?.sessionID;
    if (!sessionID) return;
    const current = ensureSession(sessionID);
    current.parentID = info?.parentID ?? current.parentID ?? null;
    current.title = info?.title ?? current.title ?? null;
    current.directory = info?.directory ?? current.directory ?? directory;
    current.createdAt = number(info?.time?.created) || current.createdAt;
    current.updatedAt = number(info?.time?.updated) || Date.now();
  }

  function messageMap(sessionID) {
    ensureSession(sessionID);
    if (!messages.has(sessionID)) messages.set(sessionID, new Map());
    return messages.get(sessionID);
  }

  function fallbackList(sessionID) {
    ensureSession(sessionID);
    if (!fallbacks.has(sessionID)) fallbacks.set(sessionID, []);
    return fallbacks.get(sessionID);
  }

  function rootSessionID(sessionID) {
    let current = sessionID;
    const seen = new Set();
    while (current && !seen.has(current)) {
      seen.add(current);
      const parentID = sessions.get(current)?.parentID;
      if (!parentID) return current;
      current = parentID;
    }
    return sessionID;
  }

  function sessionIDsForRoot(rootID) {
    const includeSubagents = telemetryConfig.includeSubagents !== false;
    if (!includeSubagents) return [rootID];
    const ids = new Set([rootID]);
    for (const sessionID of sessions.keys()) {
      if (rootSessionID(sessionID) === rootID) ids.add(sessionID);
    }
    return [...ids];
  }

  function recordMessage(info, updateLive = true) {
    if (!telemetryConfig.enabled) return;
    const metric = extractMessageInfo(info);
    if (
      metric.role !== "assistant" ||
      !metric.id ||
      !metric.sessionID ||
      !metric.providerID ||
      !metric.modelID
    ) {
      return;
    }
    const durationMs =
      metric.createdAt > 0 && metric.completedAt >= metric.createdAt
        ? metric.completedAt - metric.createdAt
        : 0;
    messageMap(metric.sessionID).set(metric.id, {
      ...metric,
      durationMs,
      modelKey: `${metric.providerID}/${metric.modelID}`,
      updatedAt: Date.now(),
    });
    const session = ensureSession(metric.sessionID);
    session.updatedAt = Date.now();
    const configuredGroup = config.agentGroups?.[metric.agent];
    if (configuredGroup) sessionGroup.set(metric.sessionID, configuredGroup);
    if (metric.agent && metric.agent !== "maestro" && metric.agent !== "title") {
      const run = currentOrchestrationRun(rootSessionID(metric.sessionID));
      if (run) {
        run.completedRoles.add(metric.agent);
        run.updatedAt = Date.now();
      }
    }
    if (metric.createdAt > 0) {
      session.createdAt = Math.min(session.createdAt || metric.createdAt, metric.createdAt);
    }
    if (updateLive) scheduleLiveReport(metric.sessionID);
  }

  async function hydrateSessionMessages(sessionID) {
    try {
      const result = await client.session.messages({ path: { id: sessionID } });
      for (const message of result?.data ?? []) {
        recordMessage(message?.info, false);
      }
    } catch (error) {
      log(`session ${sessionID}: telemetry hydration failed: ${error?.message ?? error}`);
    }
  }

  function recordFallback(sessionID, entry) {
    if (!telemetryConfig.enabled || !sessionID) return;
    fallbackList(sessionID).push({
      at: Date.now(),
      ...entry,
    });
    scheduleLiveReport(sessionID);
  }

  const ORCHESTRATION_CATEGORIES = [
    "trivial",
    "analysis",
    "implementation",
    "bug",
    "research",
    "visual",
  ];
  const RISK_KEYS = [
    "security",
    "persistence",
    "publicApi",
    "migration",
    "concurrency",
    "multiModule",
    "externalDocs",
    "visualInput",
  ];

  function orchestrationList(rootID) {
    if (!orchestrationRuns.has(rootID)) orchestrationRuns.set(rootID, []);
    return orchestrationRuns.get(rootID);
  }

  function currentOrchestrationRun(rootID) {
    const list = orchestrationRuns.get(rootID) ?? [];
    return list[list.length - 1] ?? null;
  }

  function requirementsFor(category, flags = {}) {
    const highRisk = Boolean(
      flags.security ||
        flags.persistence ||
        flags.publicApi ||
        flags.migration ||
        flags.concurrency ||
        flags.multiModule,
    );
    const requiredAll = [];
    const requiredAny = [];
    const optional = [];

    if (category === "analysis") {
      requiredAll.push("explorer", "architect");
      if (highRisk) requiredAll.push("reviewer");
      else optional.push("reviewer");
    } else if (category === "implementation") {
      requiredAll.push("explorer", "tester");
      requiredAny.push({ label: "executor", roles: ["backend", "frontend", "vision"] });
      if (highRisk) requiredAll.push("architect", "reviewer");
      else optional.push("architect", "reviewer");
    } else if (category === "bug") {
      requiredAll.push("explorer", "tester");
      requiredAny.push({ label: "executor", roles: ["backend", "frontend", "vision"] });
      if (highRisk) requiredAll.push("reviewer");
      else optional.push("reviewer");
    } else if (category === "research") {
      requiredAll.push("researcher");
      if (highRisk) requiredAll.push("reviewer");
      else optional.push("architect", "reviewer");
    } else if (category === "visual") {
      requiredAll.push("explorer", "tester");
      requiredAny.push({ label: "executor visual", roles: ["vision", "frontend"] });
      optional.push("reviewer");
    }

    return {
      requiredAll: [...new Set(requiredAll)],
      requiredAny,
      optional: [...new Set(optional)],
      highRisk,
    };
  }

  function inferOrchestration(text) {
    const raw = String(text ?? "").trim();
    const lower = raw.toLowerCase();
    if (
      !raw ||
      lower.includes("opencode-dispatch-report") ||
      lower.includes("operational report below")
    ) {
      return null;
    }
    if (lower.startsWith("[OpenCode Dispatch orchestration gate]")) return null;

    const has = (...words) => words.some((word) => lower.includes(word));
    const flags = {
      security: has("security", "segurança", "auth", "autenticação", "oauth", "permission"),
      persistence: has("database", "banco de dados", "persistência", "schema", "sql", "migration"),
      publicApi: has(
        "public api",
        "api pública",
        "endpoint público",
        "breaking change",
        "contrato público",
      ),
      migration: has("migration", "migração", "migrate", "upgrade major"),
      concurrency: has("concurrency", "concorrência", "race condition", "deadlock", "thread"),
      multiModule: has(
        "multi-module",
        "múltiplos módulos",
        "varios módulos",
        "vários módulos",
        "cross-module",
      ),
      externalDocs: has(
        "documentação",
        "documentation",
        "pesquise",
        "research",
        "latest",
        "atualizada",
      ),
      visualInput: has("screenshot", "imagem", "image", "layout", "visual", "css", "figma"),
    };

    let category = "trivial";
    if (flags.visualInput) category = "visual";
    else if (
      has(
        "pesquise",
        "research",
        "compare bibliotecas",
        "comparar bibliotecas",
        "documentação oficial",
      )
    ) {
      category = "research";
    }
    else if (
      has(
        "bug",
        "corrija",
        "corrigir",
        "fix",
        "erro",
        "falha",
        "regressão",
        "regression",
      )
    ) {
      category = "bug";
    }
    else if (
      has(
        "analise",
        "análise",
        "analisar",
        "analysis",
        "arquitetura",
        "architecture",
        "impacto",
        "planeje",
        "plano",
      )
    ) {
      category = "analysis";
    }
    else if (
      has(
        "implemente",
        "implementar",
        "implement",
        "crie",
        "adicionar",
        "refator",
        "migre",
        "migrate",
      )
    ) {
      category = "implementation";
    }
    else if (raw.length > 500 || raw.split(/\s+/).length > 80) category = "analysis";

    return {
      category,
      flags,
      rationale: `automatic classification by keywords and scope (${raw.slice(0, 160)})`,
    };
  }

  function startOrchestrationRun(rootID, plan, source = "automatic") {
    const category = ORCHESTRATION_CATEGORIES.includes(plan?.category) ? plan.category : "analysis";
    const flags = Object.fromEntries(
      RISK_KEYS.map((key) => [
        key,
        Boolean(plan?.flags?.[key] ?? plan?.[key]),
      ]),
    );
    const requirements = requirementsFor(category, flags);
    const run = {
      id: `${rootID}:${Date.now()}`,
      rootID,
      category,
      source,
      flags,
      rationale: String(plan?.rationale ?? ""),
      requiredAll: requirements.requiredAll,
      requiredAny: requirements.requiredAny,
      optional: requirements.optional,
      highRisk: requirements.highRisk,
      invokedRoles: new Set(),
      completedRoles: new Set(),
      completionAttempts: 0,
      gateApproved: category === "trivial",
      gateApprovedAt: category === "trivial" ? Date.now() : null,
      remediations: 0,
      failedOpen: false,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    orchestrationList(rootID).push(run);
    scheduleLiveReport(rootID);
    return run;
  }

  function updateOrchestrationPlan(rootID, plan, source = "dispatch_plan") {
    let run = currentOrchestrationRun(rootID);
    if (!run) return startOrchestrationRun(rootID, plan, source);
    const category = ORCHESTRATION_CATEGORIES.includes(plan?.category)
      ? plan.category
      : run.category;
    const flags = Object.fromEntries(
      RISK_KEYS.map((key) => [key, Boolean(plan?.flags?.[key] ?? plan?.[key] ?? run.flags?.[key])]),
    );
    const requirements = requirementsFor(category, flags);
    Object.assign(run, {
      category,
      source,
      flags,
      rationale: String(plan?.rationale ?? run.rationale ?? ""),
      requiredAll: requirements.requiredAll,
      requiredAny: requirements.requiredAny,
      optional: requirements.optional,
      highRisk: requirements.highRisk,
      gateApproved: category === "trivial",
      gateApprovedAt: category === "trivial" ? Date.now() : null,
      updatedAt: Date.now(),
    });
    scheduleLiveReport(rootID);
    return run;
  }

  function evaluateOrchestration(rootID, run = currentOrchestrationRun(rootID)) {
    if (!run) {
      return {
        exists: false,
        category: null,
        requiredUnits: 0,
        satisfiedUnits: 0,
        compliancePct: 100,
        missingAll: [],
        missingAny: [],
        complete: true,
      };
    }
    const observed = new Set([...run.invokedRoles, ...run.completedRoles]);
    const missingAll = run.requiredAll.filter((role) => !observed.has(role));
    const missingAny = run.requiredAny
      .filter((group) => !group.roles.some((role) => observed.has(role)))
      .map((group) => ({ ...group }));
    const requiredUnits = run.requiredAll.length + run.requiredAny.length;
    const satisfiedUnits = requiredUnits - missingAll.length - missingAny.length;
    const compliancePct = requiredUnits > 0 ? (satisfiedUnits / requiredUnits) * 100 : 100;
    return {
      exists: true,
      category: run.category,
      requiredUnits,
      satisfiedUnits,
      compliancePct,
      missingAll,
      missingAny,
      observed: [...observed].sort(),
      complete: missingAll.length === 0 && missingAny.length === 0,
    };
  }

  function serializeOrchestrationRun(run) {
    const evaluation = evaluateOrchestration(run.rootID, run);
    return {
      id: run.id,
      category: run.category,
      source: run.source,
      flags: run.flags,
      highRisk: run.highRisk,
      rationale: run.rationale,
      requiredAll: run.requiredAll,
      requiredAny: run.requiredAny,
      optional: run.optional,
      invokedRoles: [...run.invokedRoles].sort(),
      completedRoles: [...run.completedRoles].sort(),
      missingAll: evaluation.missingAll,
      missingAny: evaluation.missingAny,
      compliancePct: evaluation.compliancePct,
      gateApproved: run.gateApproved,
      gateApprovedAt: run.gateApprovedAt,
      completionAttempts: run.completionAttempts,
      remediations: run.remediations,
      failedOpen: run.failedOpen,
      createdAt: run.createdAt,
      updatedAt: run.updatedAt,
    };
  }

  function orchestrationReport(rootID) {
    const runs = (orchestrationRuns.get(rootID) ?? []).map(serializeOrchestrationRun);
    const requiredUnits = runs.reduce(
      (sum, run) => sum + run.requiredAll.length + run.requiredAny.length,
      0,
    );
    const satisfiedUnits = runs.reduce((sum, run) => {
      const missing = run.missingAll.length + run.missingAny.length;
      return sum + run.requiredAll.length + run.requiredAny.length - missing;
    }, 0);
    return {
      enabled: orchestrationConfig.enabled !== false,
      enforced: orchestrationConfig.enforce !== false,
      runs,
      latest: runs[runs.length - 1] ?? null,
      summary: {
        runs: runs.length,
        requiredUnits,
        satisfiedUnits,
        compliancePct: requiredUnits > 0 ? (satisfiedUnits / requiredUnits) * 100 : 100,
        approvedRuns: runs.filter((run) => run.gateApproved).length,
        nonCompliantRuns: runs.filter(
          (run) => run.missingAll.length || run.missingAny.length,
        ).length,
        remediations: runs.reduce((sum, run) => sum + run.remediations, 0),
      },
    };
  }

  function formatMissing(evaluation) {
    const items = [...evaluation.missingAll];
    for (const group of evaluation.missingAny) {
      items.push(
        `${group.label}: one of [${group.roles.join(", ")}]`,
      );
    }
    return items;
  }

  async function enforceOrchestrationOnIdle(sessionID) {
    if (
      orchestrationConfig.enabled === false ||
      orchestrationConfig.enforce === false
    ) {
      return false;
    }
    const rootID = rootSessionID(sessionID);
    if (rootID !== sessionID) return false;
    const run = currentOrchestrationRun(rootID);
    if (!run || run.category === "trivial") return false;
    const evaluation = evaluateOrchestration(rootID, run);
    if (evaluation.complete && run.gateApproved) return false;

    const max = Number(orchestrationConfig.maxAutoRemediations ?? 2);
    if (run.remediations >= max) {
      run.failedOpen = true;
      run.updatedAt = Date.now();
      log(
        `session ${rootID}: orchestration gate failed open after ` +
          `${run.remediations} remediation(s)`,
      );
      return false;
    }

    run.remediations += 1;
    run.updatedAt = Date.now();
    const missing = formatMissing(evaluation);
    const instruction = [
      "[OPENCODE DISPATCH ORCHESTRATION GATE]",
      `Completion was blocked because the task was classified as ${run.category}.`,
      missing.length
        ? `Missing required roles: ${missing.join("; ")}.`
        : "The required roles were invoked, but dispatch_complete has not approved completion.",
      "Call the missing subagents with task, incorporate their results, " +
        "and run dispatch_complete again.",
      "Do not repeat the previous answer or finish before the gate is approved.",
    ].join("\n");
    suppressNextUserTurn.add(rootID);
    await client.session.promptAsync({
      path: { id: rootID },
      body: { parts: [{ type: "text", text: instruction }] },
    });
    log(
      `session ${rootID}: orchestration remediation ` +
        `${run.remediations}/${max}; missing=${missing.join(",")}`,
    );
    scheduleLiveReport(rootID);
    return true;
  }

  function providerIsUnavailable(providerID) {
    const until = providerUnavailableUntil.get(providerID);
    return typeof until === "number" && Date.now() < until;
  }

  function isUnavailable(model) {
    if (providerIsUnavailable(model.providerID)) return true;
    const until = unavailableUntil.get(modelKey(model));
    return typeof until === "number" && Date.now() < until;
  }

  function markProviderUnavailable(providerID, reason, forcePermanent = false) {
    if (!providerID) return;
    if (forcePermanent || reason === "account_limit" || reason === "auth") {
      providerUnavailableUntil.set(providerID, Infinity);
      log(`provider ${providerID}: disabled until OpenCode restarts (reason=${reason})`);
      return;
    }
    const duration = Number(config.providerCooldownMs ?? 900000);
    providerUnavailableUntil.set(providerID, Date.now() + duration);
    log(`provider ${providerID}: cooldown ${duration}ms (reason=${reason})`);
  }

  function markUnavailable(model, reason) {
    const key = modelKey(model);
    if (reason === "permanent" || reason === "account_limit" || reason === "auth") {
      unavailableUntil.set(key, Infinity);
      return;
    }
    const duration =
      reason === "transient"
        ? Number(config.transientCooldownMs ?? 30000)
        : Number(config.cooldownMs ?? 120000);
    unavailableUntil.set(key, Date.now() + duration);
  }

  function inferGroup(current) {
    if (!current) return null;
    return config.modelGroups?.[modelKey(current)] ?? null;
  }

  function chainFor(group) {
    const specific = group ? config.fallbackGroups?.[group] : null;
    return uniqueModels(Array.isArray(specific) && specific.length ? specific : globalModels);
  }

  function pickFromChain(chain, current) {
    if (!chain.length) return null;
    const currentKey = current ? modelKey(current) : null;
    const currentIndex = currentKey
      ? chain.findIndex((candidate) => modelKey(candidate) === currentKey)
      : -1;

    for (let offset = 1; offset <= chain.length; offset += 1) {
      const index = (currentIndex + offset + chain.length) % chain.length;
      const candidate = chain[index];
      if (currentKey && modelKey(candidate) === currentKey) continue;
      if (!isUnavailable(candidate)) return candidate;
    }
    return null;
  }

  function pickNextModel(current, group) {
    const roleChain = chainFor(group);
    const roleCandidate = pickFromChain(roleChain, current);
    if (roleCandidate) return { model: roleCandidate, source: group ?? "global" };

    const globalCandidate = pickFromChain(globalModels, current);
    if (globalCandidate) return { model: globalCandidate, source: "global-emergency" };
    return null;
  }

  async function resolveCurrentModel(sessionID, messageID) {
    const remembered = sessionModel.get(sessionID);
    try {
      const result = await client.session.messages({ path: { id: sessionID } });
      const allMessages = result?.data ?? [];

      if (messageID) {
        const match = allMessages.find((message) => message.info.id === messageID);
        const metric = extractMessageInfo(match?.info);
        if (metric.providerID && metric.modelID) {
          return { providerID: metric.providerID, modelID: metric.modelID };
        }
      }

      for (const message of [...allMessages].reverse()) {
        const metric = extractMessageInfo(message?.info);
        if (metric.role === "assistant" && metric.providerID && metric.modelID) {
          return { providerID: metric.providerID, modelID: metric.modelID };
        }
      }
    } catch (error) {
      log(
        `session ${sessionID}: could not resolve current model: ` +
          `${error?.message ?? error}`,
      );
    }
    return remembered ?? null;
  }

  async function handleFailover(sessionID, messageID, reason, signal) {
    if (!sessionID) return;

    const current = await resolveCurrentModel(sessionID, messageID);
    const currentKey = current ? modelKey(current) : null;
    const previous = lastHandledFailure.get(sessionID);
    if (
      previous &&
      previous.modelKey === currentKey &&
      Date.now() - previous.at < DEBOUNCE_MS
    ) {
      log(`session ${sessionID}: duplicate signal ignored for ${currentKey}`);
      return;
    }
    lastHandledFailure.set(sessionID, { modelKey: currentKey, at: Date.now() });

    const group = sessionGroup.get(sessionID) ?? inferGroup(current);
    if (group) sessionGroup.set(sessionID, group);
    if (
      reason === "auth" &&
      !(config.authFailureFallbackProviders ?? []).includes(
        current?.providerID,
      )
    ) {
      log(
        `session ${sessionID}: authentication failure for ${currentKey}; ` +
          "fallback intentionally skipped",
      );
      return;
    }

    const providerWide =
      reason === "account_limit" ||
      reason === "auth" ||
      (reason === "rate_limit" &&
        (config.providerWideRateLimitProviders ?? []).includes(current?.providerID)) ||
      (reason === "transient" && signal?.forceProviderWide === true);

    if (providerWide && current?.providerID) {
      markProviderUnavailable(
        current.providerID,
        reason,
        reason === "account_limit" || reason === "auth",
      );
    }
    if (current) markUnavailable(current, reason);

    const selection = pickNextModel(current, group);
    if (!selection) {
      recordFallback(sessionID, {
        from: currentKey,
        to: null,
        reason,
        status: signal?.statusCode ?? null,
        source: group ?? "unknown",
        outcome: "no_model_available",
      });
      log(
        `session ${sessionID}: no fallback available; current=${currentKey}; ` +
          `group=${group ?? "unknown"}`,
      );
      return;
    }

    const next = selection.model;
    const nextKey = modelKey(next);
    recordFallback(sessionID, {
      from: currentKey,
      to: nextKey,
      reason,
      status: signal?.statusCode ?? null,
      source: selection.source,
      outcome: "selected",
    });
    log(
      `session ${sessionID}: ${currentKey ?? "unknown"} failed ` +
        `(reason=${reason}, status=${signal?.statusCode ?? "n/a"}) -> ` +
        `${nextKey} via ${selection.source}`,
    );

    try {
      const result = await client.session.messages({ path: { id: sessionID } });
      const allMessages = result?.data ?? [];
      const lastUserMessage = [...allMessages]
        .reverse()
        .find((message) => message.info.role === "user");
      if (!lastUserMessage) {
        log(`session ${sessionID}: no user message found; cannot resend`);
        return;
      }

      const parts = (lastUserMessage.parts ?? [])
        .filter((part) => part.type === "text" || part.type === "file")
        .map((part) => (part.type === "text" ? { type: "text", text: part.text } : part));
      if (!parts.length) {
        log(`session ${sessionID}: last user message has no resendable parts`);
        return;
      }

      sessionModel.set(sessionID, next);
      suppressNextUserTurn.add(sessionID);
      fallbackInProgress.add(sessionID);

      await client.session.abort({ path: { id: sessionID } }).catch(() => {});
      await new Promise((resolve) => setTimeout(resolve, 75));
      await client.session.promptAsync({
        path: { id: sessionID },
        body: {
          parts,
          model: { providerID: next.providerID, modelID: next.modelID },
        },
      });
      log(`session ${sessionID}: fallback request sent with ${nextKey}`);
    } catch (error) {
      recordFallback(sessionID, {
        from: currentKey,
        to: nextKey,
        reason: "fallback_send_failed",
        status: null,
        source: selection.source,
        outcome: "send_failed",
        detail: String(error?.message ?? error),
      });
      log(`session ${sessionID}: fallback attempt failed: ${error?.message ?? error}`);
    } finally {
      fallbackInProgress.delete(sessionID);
    }
  }

  function buildReport(rootID, final) {
    const display = readDisplayMetadata(config.opencodeConfigPath);
    const sessionIDs = sessionIDsForRoot(rootID);
    const modelStats = new Map();
    const allFallbacks = [];
    const totalTokens = emptyTokens();
    let allocatedMessages = 0;
    let tokenReportedMessages = 0;
    let aggregateModelMs = 0;
    let totalCost = 0;
    let firstTimestamp = Number.POSITIVE_INFINITY;
    let lastTimestamp = 0;

    for (const sessionID of sessionIDs) {
      const session = sessions.get(sessionID);
      if (session?.createdAt) firstTimestamp = Math.min(firstTimestamp, session.createdAt);
      if (session?.idleAt) lastTimestamp = Math.max(lastTimestamp, session.idleAt);
      if (session?.updatedAt) lastTimestamp = Math.max(lastTimestamp, session.updatedAt);

      for (const metric of messages.get(sessionID)?.values() ?? []) {
        allocatedMessages += 1;
        if (metric.tokens.available) tokenReportedMessages += 1;
        addTokens(totalTokens, metric.tokens);
        aggregateModelMs += metric.durationMs;
        totalCost += metric.cost;
        if (metric.createdAt) firstTimestamp = Math.min(firstTimestamp, metric.createdAt);
        if (metric.completedAt) lastTimestamp = Math.max(lastTimestamp, metric.completedAt);

        if (!modelStats.has(metric.modelKey)) {
          modelStats.set(metric.modelKey, {
            key: metric.modelKey,
            providerID: metric.providerID,
            modelID: metric.modelID,
            name: display.names.get(metric.modelKey) ?? metric.modelKey,
            messages: 0,
            tokenReportedMessages: 0,
            tokens: emptyTokens(),
            durationMs: 0,
            cost: 0,
            agents: new Set(),
            sessions: new Set(),
          });
        }
        const stat = modelStats.get(metric.modelKey);
        stat.messages += 1;
        if (metric.tokens.available) stat.tokenReportedMessages += 1;
        addTokens(stat.tokens, metric.tokens);
        stat.durationMs += metric.durationMs;
        stat.cost += metric.cost;
        if (metric.agent) stat.agents.add(metric.agent);
        stat.sessions.add(sessionID);
      }

      for (const entry of fallbacks.get(sessionID) ?? []) {
        allFallbacks.push({ sessionID, ...entry });
        lastTimestamp = Math.max(lastTimestamp, entry.at ?? 0);
      }
    }

    if (!Number.isFinite(firstTimestamp)) firstTimestamp = Date.now();
    if (!lastTimestamp) lastTimestamp = Date.now();

    const aggregateSessionTokens = emptyTokens();
    let aggregateSessionCost = 0;
    let aggregateUsageAvailable = false;
    for (const sessionID of sessionIDs) {
      const usage = sessionUsage.get(sessionID);
      if (!usage) continue;
      aggregateUsageAvailable ||= usage.tokens.available;
      addTokens(aggregateSessionTokens, usage.tokens);
      aggregateSessionCost += usage.cost;
    }

    const unallocatedTokens = Math.max(0, aggregateSessionTokens.total - totalTokens.total);
    const models = [...modelStats.values()]
      .map((stat) => ({
        ...stat,
        agents: [...stat.agents],
        agentDescriptions: [...stat.agents].map((agent) => display.agents.get(agent) ?? agent),
        sessions: [...stat.sessions],
        requestSharePct: allocatedMessages > 0 ? (stat.messages / allocatedMessages) * 100 : 0,
        tokenSharePct: totalTokens.total > 0 ? (stat.tokens.total / totalTokens.total) * 100 : 0,
        timeSharePct: aggregateModelMs > 0 ? (stat.durationMs / aggregateModelMs) * 100 : 0,
        fallbackFromCount: allFallbacks.filter((entry) => entry.from === stat.key).length,
        fallbackToCount: allFallbacks.filter((entry) => entry.to === stat.key).length,
      }))
      .sort((a, b) => b.tokens.total - a.tokens.total || b.durationMs - a.durationMs);

    const rootSession = sessions.get(rootID) ?? { id: rootID };
    const orchestration = orchestrationReport(rootID);
    return {
      schemaVersion: 2,
      generatedAt: new Date().toISOString(),
      final,
      rootSession: {
        id: rootID,
        title: rootSession.title ?? null,
        directory: rootSession.directory ?? directory,
        startedAt: new Date(firstTimestamp).toISOString(),
        endedAt: new Date(lastTimestamp).toISOString(),
        wallClockMs: Math.max(0, lastTimestamp - firstTimestamp),
      },
      summary: {
        sessions: sessionIDs.length,
        subagentSessions: Math.max(0, sessionIDs.length - 1),
        modelsUsed: models.length,
        assistantMessages: allocatedMessages,
        messagesWithTokenUsage: tokenReportedMessages,
        totalTokens,
        aggregateSessionTokens: aggregateUsageAvailable ? aggregateSessionTokens : null,
        unallocatedSessionTokens: aggregateUsageAvailable ? unallocatedTokens : null,
        aggregateModelMs,
        fallbackCount: allFallbacks.length,
        fallbackUsed: allFallbacks.length > 0,
        fallbackRatePct:
          allocatedMessages + allFallbacks.length > 0
            ? (allFallbacks.length / (allocatedMessages + allFallbacks.length)) * 100
            : 0,
        reportedCost: totalCost || aggregateSessionCost || 0,
        orchestrationCompliancePct: orchestration.summary.compliancePct,
        orchestrationRuns: orchestration.summary.runs,
        orchestrationRemediations: orchestration.summary.remediations,
      },
      orchestration,
      models,
      fallbacks: allFallbacks.sort((a, b) => (a.at ?? 0) - (b.at ?? 0)),
      sessions: sessionIDs.map((sessionID) => ({
        ...(sessions.get(sessionID) ?? { id: sessionID }),
        messages: messages.get(sessionID)?.size ?? 0,
        fallbackCount: fallbacks.get(sessionID)?.length ?? 0,
      })),
      notes: [
        "Per-model percentages use assistant messages, reported tokens, " +
          "and summed response duration.",
        "Subagents can run in parallel, so aggregated model time can exceed " +
          "session wall-clock time.",
        "Some providers do not return detailed usage, so tokens can be unreported or unallocated.",
        "The final report is written after session.idle; the pre-final " +
          "snapshot excludes the final response usage.",
        "Orchestration compliance measures observed role coverage, not technical correctness.",
      ],
    };
  }

  function renderMarkdown(report) {
    const lines = [];
    lines.push(`# OpenCode Dispatch report - ${report.rootSession.title ?? report.rootSession.id}`);
    lines.push("");
    lines.push(`- **Root session:** \`${report.rootSession.id}\``);
    lines.push(`- **Period:** ${report.rootSession.startedAt} -> ${report.rootSession.endedAt}`);
    lines.push(`- **Wall-clock time:** ${formatDuration(report.rootSession.wallClockMs)}`);
    lines.push(`- **Aggregated model time:** ${formatDuration(report.summary.aggregateModelMs)}`);
    lines.push(
      `- **Sessions/subagents:** ${report.summary.sessions} / ` +
        `${report.summary.subagentSessions}`,
    );
    lines.push(`- **Models used:** ${report.summary.modelsUsed}`);
    lines.push(`- **Assistant responses:** ${report.summary.assistantMessages}`);
    lines.push(`- **Reported tokens:** ${formatInteger(report.summary.totalTokens.total)}`);
    lines.push(
      `- **Fallback:** ${
        report.summary.fallbackUsed
          ? `yes, ${report.summary.fallbackCount} event(s)`
          : "no"
      }`,
    );
    lines.push(
      `- **Orchestration compliance:** ` +
        `${formatPercent(report.summary.orchestrationCompliancePct)}`,
    );
    lines.push("");
    lines.push("## Orchestration");
    lines.push("");
    if (!report.orchestration.runs.length) {
      lines.push("No orchestration plan was recorded.");
    } else {
      lines.push(
        "| Turn | Category | Required | Invoked | Completed | Missing | " +
          "Gate | Remediations | Compliance |",
      );
      lines.push("|---:|---|---|---|---|---|---|---:|---:|");
      report.orchestration.runs.forEach((run, index) => {
        const required = [
          ...run.requiredAll,
          ...run.requiredAny.map((group) => `${group.label}: ${group.roles.join("/")}`),
        ].join(", ") || "-";
        const missing = [
          ...run.missingAll,
          ...run.missingAny.map((group) => `${group.label}: ${group.roles.join("/")}`),
        ].join(", ") || "-";
        const gate = run.gateApproved ? "approved" : run.failedOpen ? "failed open" : "pending";
        lines.push(
          `| ${index + 1} | ${run.category} | ${required} | ` +
          `${run.invokedRoles.join(", ") || "-"} | ` +
            `${run.completedRoles.join(", ") || "-"} | ${missing} | ${gate} | ` +
            `${run.remediations} | ${formatPercent(run.compliancePct)} |`,
        );
      });
    }
    lines.push("");
    lines.push("## Model usage");
    lines.push("");
    lines.push(
      "| Model | Agent(s) | Responses | Response share | Tokens | " +
        "Token share | Time | Time share | Fallback out/in |",
    );
    lines.push("|---|---|---:|---:|---:|---:|---:|---:|---:|");
    for (const model of report.models) {
      lines.push(
        `| ${model.name} (\`${model.key}\`) | ${model.agents.join(", ") || "-"} | ` +
          `${model.messages} | ${formatPercent(model.requestSharePct)} | ` +
          `${formatInteger(model.tokens.total)} | ` +
          `${formatPercent(model.tokenSharePct)} | ${formatDuration(model.durationMs)} | ` +
          `${formatPercent(model.timeSharePct)} | ` +
          `${model.fallbackFromCount}/${model.fallbackToCount} |`,
      );
    }
    if (!report.models.length) {
      lines.push("| - | - | 0 | 0% | 0 | 0% | 0 ms | 0% | 0/0 |");
    }
    lines.push("");
    lines.push("## Models and roles");
    lines.push("");
    if (!report.models.length) {
      lines.push("No completed model response was recorded.");
    } else {
      for (const model of report.models) {
        const roles = model.agentDescriptions.length
          ? model.agentDescriptions.join("; ")
          : "No role description was reported by the event.";
        lines.push(`- **${model.name}** (\`${model.key}\`): ${roles}`);
      }
    }
    lines.push("");
    lines.push("## Tokens");
    lines.push("");
    lines.push(`- Input: **${formatInteger(report.summary.totalTokens.input)}**`);
    lines.push(`- Output: **${formatInteger(report.summary.totalTokens.output)}**`);
    lines.push(`- Reasoning: **${formatInteger(report.summary.totalTokens.reasoning)}**`);
    lines.push(`- Cache read: **${formatInteger(report.summary.totalTokens.cacheRead)}**`);
    lines.push(`- Cache written: **${formatInteger(report.summary.totalTokens.cacheWrite)}**`);
    if (report.summary.unallocatedSessionTokens > 0) {
      lines.push(
        "- Session-level tokens without model attribution: " +
          `**${formatInteger(report.summary.unallocatedSessionTokens)}**`,
      );
    }
    lines.push("");
    lines.push("## Fallbacks");
    lines.push("");
    if (!report.fallbacks.length) {
      lines.push("No fallback was recorded.");
    } else {
      lines.push("| Time | Session | From | To | Reason | HTTP | Route | Result |");
      lines.push("|---|---|---|---|---|---:|---|---|");
      for (const entry of report.fallbacks) {
        lines.push(
          `| ${new Date(entry.at).toISOString()} | ` +
          `\`${entry.sessionID}\` | \`${entry.from ?? "?"}\` | ` +
            `\`${entry.to ?? "-"}\` | ${entry.reason} | ${entry.status ?? "-"} | ` +
            `${entry.source ?? "-"} | ${entry.outcome ?? "-"} |`,
        );
      }
    }
    lines.push("");
    lines.push("## Notes");
    lines.push("");
    for (const note of report.notes) lines.push(`- ${note}`);
    lines.push("");
    return `${lines.join("\n")}\n`;
  }

  function writeReport(rootID, final) {
    if (!telemetryConfig.enabled) return null;
    try {
      const report = buildReport(rootID, final);
      const date = report.generatedAt.slice(0, 10);
      const folder = path.join(reportDir, date);
      const basename = safeFilename(rootID);
      const jsonFile = path.join(folder, `${basename}.json`);
      const mdFile = path.join(folder, `${basename}.md`);
      const markdown = renderMarkdown(report);
      if (telemetryConfig.writeJson !== false) {
        atomicWrite(jsonFile, `${JSON.stringify(report, null, 2)}\n`);
      }
      if (telemetryConfig.writeMarkdown !== false) {
        atomicWrite(mdFile, markdown);
      }

      const liveJson = path.join(reportDir, "active.json");
      const liveMd = path.join(reportDir, "active.md");
      atomicWrite(liveJson, `${JSON.stringify(report, null, 2)}\n`);
      atomicWrite(liveMd, markdown);

      if (final) {
        if (telemetryConfig.writeJson !== false) {
          copyFileSync(jsonFile, path.join(reportDir, "latest.json"));
        } else {
          atomicWrite(path.join(reportDir, "latest.json"), `${JSON.stringify(report, null, 2)}\n`);
        }
        if (telemetryConfig.writeMarkdown !== false) {
          copyFileSync(mdFile, path.join(reportDir, "latest.md"));
        } else {
          atomicWrite(path.join(reportDir, "latest.md"), markdown);
        }
        log(
          `session ${rootID}: telemetry report written; models=${report.summary.modelsUsed}; ` +
            `tokens=${report.summary.totalTokens.total}; ` +
            `fallbacks=${report.summary.fallbackCount}; ` +
            `wall=${report.rootSession.wallClockMs}ms; file=${mdFile}`,
        );
      }
      return { report, jsonFile, mdFile };
    } catch (error) {
      log(`session ${rootID}: telemetry report failed: ${error?.message ?? error}`);
      return null;
    }
  }

  function scheduleLiveReport(sessionID) {
    if (!telemetryConfig.enabled || telemetryConfig.writeLiveReport === false || !sessionID) return;
    const rootID = rootSessionID(sessionID);
    const existing = reportTimers.get(rootID);
    if (existing) clearTimeout(existing);
    reportTimers.set(
      rootID,
      setTimeout(async () => {
        reportTimers.delete(rootID);
        await hydrateSessionMessages(rootID);
        writeReport(rootID, false);
      }, REPORT_SETTLE_MS),
    );
  }

  function scheduleFinalReport(sessionID) {
    if (!telemetryConfig.enabled || !sessionID) return;
    const session = ensureSession(sessionID);
    session.idleAt = Date.now();
    const rootID = rootSessionID(sessionID);
    const root = ensureSession(rootID);
    if (rootID === sessionID) root.idleAt = session.idleAt;
    const existing = reportTimers.get(rootID);
    if (existing) clearTimeout(existing);
    reportTimers.set(
      rootID,
      setTimeout(async () => {
        reportTimers.delete(rootID);
        const ids = sessionIDsForRoot(rootID);
        await Promise.all(ids.map((id) => hydrateSessionMessages(id)));
        const result = writeReport(rootID, rootID === sessionID);
        if (result && rootID === sessionID && process.platform === "darwin" && $) {
          const text = `OpenCode Dispatch: ${
            result.report.summary.modelsUsed
          } model(s), ${formatInteger(
            result.report.summary.totalTokens.total,
          )} tokens, ${result.report.summary.fallbackCount} fallback(s)`;
          const script =
            `display notification ${JSON.stringify(text)} ` +
            'with title "OpenCode Dispatch"';
          Promise.resolve($`osascript -e ${script}`).catch(() => {});
        }
      },
      REPORT_SETTLE_MS,
    ),
  );
  }

  let dispatchPlanTool = null;
  let dispatchCompleteTool = null;
  if (toolFactory) {
    dispatchPlanTool = toolFactory({
      description:
        "MANDATORY at the start of every maestro task. Classifies the task " +
        "and calculates the minimum roles that must be delegated before " +
        "completion.",
      args: {
        category: toolFactory.schema.enum(ORCHESTRATION_CATEGORIES),
        rationale: toolFactory.schema.string(),
        security: toolFactory.schema.boolean().optional(),
        persistence: toolFactory.schema.boolean().optional(),
        publicApi: toolFactory.schema.boolean().optional(),
        migration: toolFactory.schema.boolean().optional(),
        concurrency: toolFactory.schema.boolean().optional(),
        multiModule: toolFactory.schema.boolean().optional(),
        externalDocs: toolFactory.schema.boolean().optional(),
        visualInput: toolFactory.schema.boolean().optional(),
      },
      async execute(args, context) {
        const rootID = rootSessionID(context.sessionID);
        const run = updateOrchestrationPlan(rootID, args, "dispatch_plan");
        const evaluation = evaluateOrchestration(rootID, run);
        const payload = {
          status: "planned",
          category: run.category,
          highRisk: run.highRisk,
          requiredAll: run.requiredAll,
          requiredAny: run.requiredAny,
          optional: run.optional,
          missing: formatMissing(evaluation),
          instruction:
            "Delegate every required role and call dispatch_complete before " +
            "finishing.",
        };
        context.metadata({
          title: `OpenCode Dispatch: ${run.category} plan`,
          metadata: payload,
        });
        return {
          title: `${run.category} plan`,
          output: JSON.stringify(payload, null, 2),
          metadata: payload,
        };
      },
    });

    dispatchCompleteTool = toolFactory({
      description:
        "MANDATORY before the maestro final answer. Blocks completion while " +
        "roles required by dispatch_plan are missing.",
      args: {
        summary: toolFactory.schema.string(),
        justification: toolFactory.schema.string().optional(),
      },
      async execute(args, context) {
        const rootID = rootSessionID(context.sessionID);
        let run = currentOrchestrationRun(rootID);
        if (!run) {
          run = startOrchestrationRun(
            rootID,
            {
              category: "analysis",
              rationale:
                "dispatch_complete called without dispatch_plan; safe default applied",
            },
            "gate-default",
          );
        }
        run.completionAttempts += 1;
        run.updatedAt = Date.now();
        const evaluation = evaluateOrchestration(rootID, run);
        if (!evaluation.complete) {
          const payload = {
            status: "blocked",
            category: run.category,
            missing: formatMissing(evaluation),
            observed: evaluation.observed,
            compliancePct: evaluation.compliancePct,
            instruction:
              "Call the missing subagents with task and run dispatch_complete " +
              "again.",
          };
          context.metadata({
            title: "OpenCode Dispatch: completion blocked",
            metadata: payload,
          });
          scheduleLiveReport(rootID);
          return {
            title: "Completion blocked",
            output: JSON.stringify(payload, null, 2),
            metadata: payload,
          };
        }
        run.gateApproved = true;
        run.gateApprovedAt = Date.now();
        run.summary = String(args.summary ?? "");
        run.justification = String(args.justification ?? "");
        const payload = {
          status: "approved",
          category: run.category,
          observed: evaluation.observed,
          compliancePct: evaluation.compliancePct,
          instruction:
            "Gate approved. The final answer may include an Orchestration " +
            "section.",
        };
        context.metadata({
          title: "OpenCode Dispatch: completion approved",
          metadata: payload,
        });
        scheduleLiveReport(rootID);
        return {
          title: "Completion approved",
          output: JSON.stringify(payload, null, 2),
          metadata: payload,
        };
      },
    });
  }

  const hooks = {
    "chat.message": async (input, output) => {
      const requested = input.model ?? output.message?.model;
      if (requested && isUnavailable(requested)) {
        const requestedModel = {
          providerID: requested.providerID,
          modelID: requested.modelID,
        };
        const group = config.agentGroups?.[input.agent] ?? inferGroup(requestedModel);
        const selection = pickNextModel(requestedModel, group);
        if (selection) {
          const next = selection.model;
          output.message.model = {
            ...(output.message.model ?? {}),
            providerID: next.providerID,
            modelID: next.modelID,
          };
          sessionModel.set(input.sessionID, next);
          if (group) sessionGroup.set(input.sessionID, group);
          recordFallback(input.sessionID, {
            from: modelKey(requestedModel),
            to: modelKey(next),
            reason: "provider_or_model_unavailable",
            status: null,
            source: `${selection.source}-preemptive`,
            outcome: "preemptive",
          });
          log(
            `session ${input.sessionID}: preemptive route ${modelKey(requestedModel)} -> ` +
              `${modelKey(next)} via ${selection.source}`,
          );
        }
      }

      if (orchestrationConfig.enabled === false || input.agent !== "maestro") return;
      if (suppressNextUserTurn.has(input.sessionID)) {
        suppressNextUserTurn.delete(input.sessionID);
        return;
      }
      const text = (output.parts ?? [])
        .filter((part) => part?.type === "text")
        .map((part) => part.text ?? "")
        .join("\n")
        .trim();
      const inferred = orchestrationConfig.autoClassify === false ? null : inferOrchestration(text);
      if (inferred) startOrchestrationRun(rootSessionID(input.sessionID), inferred, "automatic");
    },
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "task") return;
      const role = output.args?.subagent_type ?? output.args?.agent ?? output.args?.type;
      if (typeof role !== "string" || !role.trim()) return;
      const rootID = rootSessionID(input.sessionID);
      let run = currentOrchestrationRun(rootID);
      if (!run) {
        run = startOrchestrationRun(
          rootID,
          {
            category: "analysis",
            rationale: "task called without an explicit plan",
          },
          "task-default",
        );
      }
      run.invokedRoles.add(role.trim());
      run.updatedAt = Date.now();
      scheduleLiveReport(rootID);
    },
    "experimental.chat.system.transform": async (input, output) => {
      if (
        orchestrationConfig.enabled === false ||
        !dispatchPlanTool ||
        !dispatchCompleteTool ||
        !input.sessionID
      ) return;
      const rootID = rootSessionID(input.sessionID);
      if (rootID !== input.sessionID) return;
      output.system.push(
        "OPENCODE DISPATCH 1.0: call dispatch_plan before executing every maestro task. " +
          "Fulfill required roles with task. Call dispatch_complete before the final answer. " +
          "If dispatch_complete returns blocked, do not finish until the missing roles have run.",
      );
    },
    event: async ({ event }) => {
      if (event.type === "session.created" || event.type === "session.updated") {
        updateSession(event.properties?.info ?? event.properties);
      }

      if (event.type === "message.updated") {
        const info = event.properties?.info;
        recordMessage(info);
        const metric = extractMessageInfo(info);
        if (metric.providerID && metric.modelID && metric.sessionID) {
          const current = { providerID: metric.providerID, modelID: metric.modelID };
          sessionModel.set(metric.sessionID, current);
          const group = config.agentGroups?.[metric.agent] ?? inferGroup(current);
          if (group) sessionGroup.set(metric.sessionID, group);
        }
        if (metric.error && metric.sessionID) {
          const signal = signalFromError(metric.error);
          const reason = classify(config, signal);
          if (reason) await handleFailover(metric.sessionID, metric.id, reason, signal);
        }
      }

      if (event.type === "session.usage.updated") {
        const properties = event.properties ?? {};
        if (properties.sessionID) {
          sessionUsage.set(properties.sessionID, {
            tokens: normalizeTokens(properties.tokens),
            cost: number(properties.cost),
            updatedAt: Date.now(),
          });
          scheduleLiveReport(properties.sessionID);
        }
      }

      if (event.type === "session.error") {
        const properties = event.properties ?? {};
        const signal = signalFromError(properties.error);
        const reason = classify(config, signal);
        if (reason && properties.sessionID) {
          await handleFailover(properties.sessionID, undefined, reason, signal);
        }
      }

      if (event.type === "message.part.updated") {
        const part = event.properties?.part;
        if (part?.type === "retry" && part.error) {
          const signal = signalFromError(part.error);
          const reason = classify(config, signal);
          if (reason) await handleFailover(part.sessionID, part.messageID, reason, signal);
        }
      }

      if (event.type === "session.status") {
        const status = event.properties?.status;
        if (status?.type === "retry") {
          const sessionID = event.properties?.sessionID;
          const action = status.action ?? {};
          const signal = {
            text: [status.message, action.title, action.message, action.reason]
              .map(signalText)
              .filter(Boolean)
              .join(" "),
            actionReason: action.reason,
            attempt: number(status.attempt),
          };
          let reason = classify(config, signal);

          if (!reason && signal.attempt >= Number(config.retryFailoverAttempt ?? 1)) {
            const current = sessionModel.get(sessionID);
            if (current && (config.providerWideRetryProviders ?? []).includes(current.providerID)) {
              reason = "transient";
              signal.forceProviderWide = true;
            }
          }

          if (reason) {
            await handleFailover(sessionID, undefined, reason, signal);
          }
        }
      }

      if (event.type === "session.idle") {
        const sessionID = event.properties?.sessionID ?? event.properties?.id;
        if (sessionID && fallbackInProgress.has(sessionID)) {
          log(`session ${sessionID}: idle ignored while fallback is in progress`);
          return;
        }
        const remediated = sessionID ? await enforceOrchestrationOnIdle(sessionID) : false;
        if (!remediated) scheduleFinalReport(sessionID);
      }

      if (event.type === "session.deleted") {
        const sessionID = event.properties?.sessionID ?? event.properties?.info?.id;
        if (sessionID) {
          sessions.delete(sessionID);
          messages.delete(sessionID);
          fallbacks.delete(sessionID);
          sessionUsage.delete(sessionID);
          if (rootSessionID(sessionID) === sessionID) orchestrationRuns.delete(sessionID);
        }
      }
    },
  };

  if (dispatchPlanTool && dispatchCompleteTool) {
    hooks.tool = {
      dispatch_plan: dispatchPlanTool,
      dispatch_complete: dispatchCompleteTool,
    };
  }

  return hooks;
};

export default OpenCodeDispatch;
