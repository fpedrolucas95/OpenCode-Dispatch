# OpenCode Dispatch

O OpenCode Dispatch é o meu agente pessoal que venho utilizando há mais de um mês no OpenCode. Ele instala e configura um plugin que descobre os modelos de codificação disponíveis, cria cadeias de modelos específicas por papel, redireciona automaticamente requisições que falham e gera relatórios detalhados de execução.

Como os catálogos de provedores, cotas e modelos promocionais mudam com frequência, o catálogo gerado durante a instalação se torna a fonte da verdade para a máquina e conta atuais. Tenho usado principalmente como fallback inteligente para contornar os limites do Claude Code.

## Sumário

- [O que é instalado](#o-que-é-instalado)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Credenciais de API](#credenciais-de-api)
- [APIs e provedores aceitos](#apis-e-provedores-aceitos)
- [Modelos e limites](#modelos-e-limites)
- [Estratégia de fallback](#estratégia-de-fallback)
- [Orquestrador](#orquestrador)
- [Uso](#uso)
- [Relatórios](#relatórios)
- [Configuração](#configuração)
- [Arquivos e diretórios](#arquivos-e-diretórios)
- [Segurança e privacidade](#segurança-e-privacidade)
- [Solução de problemas](#solução-de-problemas)
- [Referências oficiais](#referências-oficiais)

## O que é instalado

| Componente | Propósito |
|---|---|
| OpenCode | Instalado automaticamente quando o executável `opencode` não é encontrado |
| Plugin global | Adiciona ganchos de fallback, orquestração e telemetria |
| Configuração de provedores | Adiciona apenas provedores que podem ser descobertos ou autenticados |
| Agentes por papel | Cria `maestro`, `architect`, `backend`, `frontend`, `explorer`, `tester`, `reviewer`, `researcher` e `vision` |
| `opencode-dispatch` | Inicia o OpenCode através do lançador Dispatch seguro |
| `opencode-dispatch-report` | Lê relatórios de telemetria em tempo real e finalizados |
| Catálogo de modelos | Registra provedores descobertos, modelos, estado de autenticação e modelos iniciais por papel |

O instalador preserva a configuração existente do OpenCode, suporta JSON e JSONC e cria backups antes de gravar alterações.

## Requisitos

| Requisito | Observações |
|---|---|
| Python | Python 3.10 ou superior |
| Acesso à internet | Necessário para instalação do OpenCode e descoberta de provedores |
| OpenCode | Opcional antes da configuração; instalado automaticamente se estiver ausente |
| Credenciais de API | Pelo menos uma rota autenticada ou anônima compatível com agentes deve estar disponível |
| Sistema operacional | Windows 10+, macOS atual ou uma distribuição Linux atual |

## Instalação

### 1. Prepare as credenciais

Defina credenciais apenas para os provedores que pretende usar. As credenciais OAuth do OpenCode podem ser configuradas separadamente após a instalação.

#### Linux e macOS

```bash
export GROQ_API_KEY="sua-chave"
export GEMINI_API_KEY="sua-chave"
python3 install.py
```

#### Windows PowerShell

```powershell
$env:GROQ_API_KEY="sua-chave"
$env:GEMINI_API_KEY="sua-chave"
py -3 install.py
```

### 2. Execute o instalador

| Plataforma | Comando |
|---|---|
| Linux/macOS | `python3 install.py` |
| Windows | `py -3 install.py` |
| Qualquer plataforma com `python` mapeado para Python 3 | `python install.py` |

O instalador realiza as seguintes operações:

1. Detecta ou instala o OpenCode.
2. Lê a autenticação e as variáveis de ambiente do OpenCode.
3. Consulta o catálogo de modelos ao vivo de cada provedor configurado.
4. Remove endpoints não compatíveis com agentes, como embeddings, reranking, moderação, fala, modelos apenas de imagem e apenas de vídeo.
5. Constrói cadeias específicas por papel e uma cadeia de emergência global.
6. Atualiza a configuração JSON ou JSONC do OpenCode com backups.
7. Instala o plugin global e os lançadores multiplataforma.
8. Grava o catálogo de modelos gerado.

### Opções do instalador

| Opção | Comportamento |
|---|---|
| `--version` | Exibe a versão do Dispatch |
| `--dry-run` | Descobre provedores e imprime o relatório gerado sem alterar arquivos |
| `--no-chatgpt` | Exclui modelos OAuth do ChatGPT mesmo quando existe uma credencial OpenCode |
| `--require-chatgpt` | Interrompe a instalação caso não haja uma credencial OAuth do ChatGPT disponível |
| `--no-probe-mistral` | Pula a sonda de acessibilidade de um token do Mistral |

Exemplos:

```bash
python3 install.py --dry-run
python3 install.py --no-chatgpt
python3 install.py --require-chatgpt
```

## Credenciais de API

O OpenCode suporta `/connect` e `opencode auth login`; o OpenCode armazena as credenciais em `~/.local/share/opencode/auth.json`. O Dispatch não copia essas credenciais para seus arquivos de relatório.

### ChatGPT Plus ou Pro OAuth

Execute:

```bash
opencode auth login
```

Selecione **OpenAI** e escolha o fluxo OAuth **ChatGPT Plus/Pro**. O mesmo fluxo está disponível na TUI do OpenCode:

```text
/connect
```

O lançador Dispatch remove a variável `OPENAI_API_KEY` do processo filho para que uma chave OpenAI API não relacionada não sobrescreva a credencial OAuth do ChatGPT. O acesso por assinatura ChatGPT e a cobrança da OpenAI API são produtos separados.

### Variáveis de ambiente e locais das chaves

| Provedor | Variável de ambiente | Onde obter as credenciais | Obrigatório pelo Dispatch |
|---|---|---|---|
| ChatGPT OAuth | Armazenado pelo OpenCode | `opencode auth login` ou `/connect` | Opcional, mas com prioridade máxima quando ativado |
| NVIDIA Build | `NVIDIA_API_KEY` | [Chaves da NVIDIA API](https://build.nvidia.com/settings/api-keys) | Sim para descoberta NVIDIA |
| Google Gemini | `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Sim para descoberta Google |
| GitHub Models | `GITHUB_TOKEN` | [Tokens fine-grained do GitHub](https://github.com/settings/tokens?type=beta) | Sim, até a desativação do serviço |
| Groq | `GROQ_API_KEY` | [Groq Console](https://console.groq.com/keys) | Sim para descoberta Groq |
| Kilo Gateway | `KILO_API_KEY` | [Painel Kilo](https://app.kilo.ai) | Não; acesso gratuito anônimo é suportado |
| Mistral | `MISTRAL_API_KEY` | [Mistral Console](https://console.mistral.ai/api-keys) | Sim para descoberta Mistral |
| Cloudflare Workers AI | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | [Painel Cloudflare](https://dash.cloudflare.com/) | Ambos são obrigatórios |
| OVHcloud anônimo | Nenhuma | Nenhuma chave é usada por esta rota | Não |
| OpenRouter | `OPENROUTER_API_KEY` | [Chaves OpenRouter](https://openrouter.ai/keys) | Sim para descoberta OpenRouter |
| LLM7 | `LLM7_API_KEY` | [Painel LLM7](https://dash.llm7.io) | Sim para ativação LLM7 |
| SambaNova | `SAMBANOVA_API_KEY` | [SambaCloud](https://cloud.sambanova.ai/apis) | Sim para ativação SambaNova |
| Z.AI | `ZAI_API_KEY` ou `ZHIPU_API_KEY` | [Início rápido Z.AI](https://docs.z.ai/guides/overview/quick-start) | Uma delas é necessária |
| SiliconFlow | `SILICONFLOW_API_KEY` | [Chaves SiliconFlow](https://cloud.siliconflow.com/account/ak) | Sim para ativação SiliconFlow |
| ModelScope | `MODELSCOPE_API_KEY` | [Token de acesso ModelScope](https://modelscope.cn/docs/accounts/token) | Sim para ativação ModelScope |
| OpenCode Zen | Armazenado pelo OpenCode | [Autenticação OpenCode](https://opencode.ai/auth) através de `/connect` | Necessário antes do Zen entrar no fallback |

Não faça commit de chaves de API, arquivos de autenticação do OpenCode ou perfis de shell contendo segredos.

## APIs e provedores aceitos

O OpenCode em si suporta mais de 75 provedores e URLs base personalizadas. O Dispatch 1.0 descobre e orquestra automaticamente as seguintes 16 rotas, nesta ordem padrão de provedores:

| Prioridade | Rota Dispatch | Estilo da API | Endpoint base | Credencial | Chave obrigatória | Fonte da credencial | Resumo dos limites atuais |
|---:|---|---|---|---|---|---|---|
| 1 | `openai` | Provedor OpenAI nativo do OpenCode com OAuth ChatGPT | Endpoint nativo do provedor | `opencode auth login` ou `/connect` | Nenhuma | [Provedores OpenCode](https://opencode.ai/docs/providers/) | Elegibilidade de assinatura ChatGPT/Codex; não é cobrança da OpenAI API |
| 2 | `nvidia` | API compatível com OpenAI da NVIDIA Build | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | Obrigatória | [Chaves NVIDIA](https://build.nvidia.com/settings/api-keys) | Catálogo e cota dependem da conta/modelo |
| 3 | `groq` | API de chat compatível com OpenAI da Groq | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | Obrigatória | [Chaves Groq](https://console.groq.com/keys) | RPM/TPM por modelo; veja a tabela exata abaixo |
| 4 | `google` | API Gemini | `https://generativelanguage.googleapis.com/v1beta` | `GEMINI_API_KEY` | Obrigatória | [Chaves Google AI Studio](https://aistudio.google.com/apikey) | Por projeto, modelo e nível de uso |
| 5 | `kilo-free` | Kilo Gateway compatível com OpenAI | `https://api.kilo.ai/api/gateway` | `KILO_API_KEY` | Opcional | [Painel Kilo](https://app.kilo.ai) | Modelos gratuitos: 200 requisições/hora/IP |
| 6 | `mistral` | API nativa Mistral | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | Obrigatória | [Chaves Mistral](https://console.mistral.ai/api-keys) | Limites do modo gratuito são específicos por organização/modelo |
| 7 | `cloudflare-workers-ai` | Endpoint Workers AI compatível com OpenAI | `https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1` | `CLOUDFLARE_ACCOUNT_ID` e `CLOUDFLARE_API_TOKEN` | Obrigatória | [Configuração REST API Workers AI](https://developers.cloudflare.com/workers-ai/get-started/rest-api/) | 10.000 Neurons/dia de alocação gratuita |
| 8 | `ovh-anonymous` | Endpoints de IA OVHcloud compatíveis com OpenAI | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` | Nenhuma | Não | [Endpoints de IA OVHcloud](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-getting-started) | 2 RPM/IP/modelo no modo anônimo |
| 9 | `sambanova` | API SambaCloud compatível com OpenAI | `https://api.sambanova.ai/v1` | `SAMBANOVA_API_KEY` | Opcional | [API SambaCloud](https://cloud.sambanova.ai/apis) | RPM/RPD/TPD do nível gratuito variam por modelo |
| 10 | `zai-free` | API Z.AI compatível com OpenAI | `https://open.bigmodel.cn/api/paas/v4` | `ZAI_API_KEY` ou `ZHIPU_API_KEY` | Opcional | [Início rápido Z.AI](https://docs.z.ai/guides/overview/quick-start) | Modelos Flash gratuitos; disponibilidade ao vivo se aplica |
| 11 | `siliconflow-free` | API SiliconFlow compatível com OpenAI | `https://api.siliconflow.cn/v1` | `SILICONFLOW_API_KEY` | Opcional | [Chaves SiliconFlow](https://cloud.siliconflow.com/account/ak) | Limites de modelos gratuitos são fixos por modelo; níveis pagos variam |
| 12 | `modelscope-free` | API-Inference ModelScope compatível com OpenAI | `https://api-inference.modelscope.cn/v1` | `MODELSCOPE_API_KEY` | Opcional | [Configuração de token ModelScope](https://modelscope.cn/docs/accounts/token) | Cabeçalhos do serviço ao vivo/página da conta são autoritativos |
| 13 | `llm7-free` | API LLM7 compatível com OpenAI | `https://api.llm7.io/v1` | `LLM7_API_KEY` | Opcional, mas necessária para ativar | [Painel LLM7](https://dash.llm7.io) | Token gratuito: 2 req/s, 40 req/min, 100 req/hora, 1M tokens/24h |
| 14 | `openrouter-free` | API OpenRouter compatível com OpenAI | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | Necessária para ativar | [Chaves OpenRouter](https://openrouter.ai/keys) | Variantes gratuitas: 20 RPM; 50 ou 1.000 requisições/dia |
| 15 | `github-models` | API de inferência GitHub Models compatível com OpenAI | `https://models.github.ai/inference` | `GITHUB_TOKEN` | Obrigatória | [Tokens fine-grained do GitHub](https://github.com/settings/tokens?type=beta) | Desativa globalmente em 30 de julho de 2026 |
| 16 | `opencode` | Provedor nativo OpenCode Zen | `https://opencode.ai/zen/v1` | Credencial OpenCode | Necessária para fallback | [Autenticação OpenCode](https://opencode.ai/auth) | Catálogo gratuito/promocional é dinâmico |

Um provedor só é incluído quando o instalador obtém um catálogo utilizável ou aplica um catálogo de emergência explícito. Os modelos OpenCode Zen são listados na configuração quando disponíveis, mas entram no fallback automático somente após a detecção da autenticação OpenCode.

## Modelos e limites

### Como a disponibilidade de modelos é determinada

O Dispatch usa duas camadas:

| Camada | Significado |
|---|---|
| Catálogo ao vivo | Modelos retornados pelo provedor durante a instalação; este é o catálogo autoritativo em tempo de execução |
| Lista de candidatos curada | Modelos preferidos pelo Dispatch quando presentes no catálogo ao vivo, ou usados como lista de emergência documentada por provedores selecionados |

Apenas modelos de texto/chat compatíveis com agentes são candidatos a fallback automático. Endpoints de embeddings, rerankers, moderação, áudio, TTS, OCR, apenas-imagem e apenas-vídeo são excluídos.

Inspecione o catálogo gerado após a instalação:

```bash
python -m json.tool ~/.opencode/opencode-dispatch-catalog.json
```

No Windows PowerShell:

```powershell
Get-Content "$HOME\.opencode\opencode-dispatch-catalog.json" | ConvertFrom-Json | ConvertTo-Json -Depth 20
```

Dentro do OpenCode, use:

```text
/models
```

Você também pode usar:

```bash
opencode models
```

### Candidatos ChatGPT OAuth

Esses IDs são configurados apenas quando o OpenCode contém uma credencial OAuth do ChatGPT válida. Os limites oficiais de contexto da API abaixo descrevem as famílias de modelos; o Dispatch usa os valores configurados mais seguros mostrados quando explicitamente presentes em `install.py`.

| ID do modelo | Contexto oficial | Saída máxima oficial | Contexto Dispatch | Saída máxima Dispatch | Fonte |
|---|---:|---:|---:|---:|---|
| `gpt-5.6-sol` | 1.050.000 | 128.000 | 500.000 | 128.000 | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |
| `gpt-5.6-terra` | 1.050.000 | 128.000 | 500.000 | 128.000 | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.6-terra) |
| `gpt-5.6-luna` | 1.050.000 | 128.000 | 500.000 | 128.000 | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.6-luna) |
| `gpt-5.5` | 1.050.000 | 128.000 | 400.000 | 128.000 | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.5) |
| `gpt-5.4` | 1.050.000 | 128.000 | Metadados do provedor | Metadados do provedor | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.4) |
| `gpt-5.4-mini` | 400.000 | 128.000 | Metadados do provedor | Metadados do provedor | [Página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-5.4-mini) |
| `gpt-5.3-codex-spark` | Catálogo ao vivo | Catálogo ao vivo | Metadados do provedor | Metadados do provedor | [Página oficial do modelo](https://developers.openai.com/api/docs/models) |

O `gpt-5.3-codex-spark` é mantido como candidato de assinatura, mas seus limites efetivos e elegibilidade devem ser obtidos do catálogo ao vivo OpenCode/OpenAI da conta autenticada.

### Candidatos Google

O Dispatch ativa apenas candidatos retornados pelo catálogo `generateContent` do Gemini.

| Modelo candidato | Ativação | Contexto/saída verificados |
|---|---|---|
| `gemini-3.6-flash` | Correspondência no catálogo ao vivo | 1.048.576 tokens de entrada / 65.536 tokens de saída |
| `gemini-3.5-flash` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-3.5-flash-lite` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-3.1-flash-lite` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-3-flash-preview` | Correspondência no catálogo ao vivo | Disponibilidade de preview e limites da conta se aplicam |
| `gemini-2.5-pro` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-2.5-flash` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-2.5-flash-lite` | Correspondência no catálogo ao vivo | Metadados do modelo Google ao vivo |
| `gemini-2.5-flash-lite-preview-09-2025` | Correspondência no catálogo ao vivo | Status de preview/depreciação deve ser verificado ao vivo |

Os limites de taxa do Gemini são por projeto, modelo e nível de uso. A Google direciona os usuários ao AI Studio para os valores ativos de RPM, TPM e RPD; valores publicados não garantem capacidade.

### Candidatos preferidos Groq e limites publicados exatos

Todos os modelos Groq ao vivo compatíveis com agentes são adicionados após os candidatos preferidos.

| ID do modelo | Contexto | Conclusão máxima | Limite de taxa do plano Developer | Status |
|---|---:|---:|---|---|
| `groq/compound` | 131.072 | 8.192 | 200.000 TPM / 200 RPM | Sistema de produção |
| `groq/compound-mini` | 131.072 | 8.192 | 200.000 TPM / 200 RPM | Sistema de produção |
| `llama-3.1-8b-instant` | 131.072 | 131.072 | 250.000 TPM / 1.000 RPM | Produção |
| `llama-3.3-70b-versatile` | 131.072 | 32.768 | 300.000 TPM / 1.000 RPM | Produção |
| `openai/gpt-oss-120b` | 131.072 | 65.536 | 250.000 TPM / 1.000 RPM | Produção |
| `openai/gpt-oss-20b` | 131.072 | 65.536 | 250.000 TPM / 1.000 RPM | Produção |
| `qwen/qwen3.6-27b` | 131.072 | 16.384 | 250.000 TPM / 1.000 RPM | Preview |

Fonte: [Modelos suportados Groq](https://console.groq.com/docs/models).

### Candidatos SambaNova e limites publicados exatos

Os candidatos só são incluídos quando retornados pelo catálogo de modelos ao vivo da SambaNova.

| ID do modelo | Nível gratuito | Nível Developer | Status no catálogo |
|---|---|---|---|
| `DeepSeek-V3.1` | 20 RPM / 20 RPD / 200.000 TPD | 60 RPM / 12.000 RPD | Produção |
| `Meta-Llama-3.3-70B-Instruct` | 20 RPM / 20 RPD / 200.000 TPD | 240 RPM / 48.000 RPD | Produção |
| `gpt-oss-120b` | 20 RPM / 20 RPD / 200.000 TPD | 60 RPM / 12.000 RPD | Produção |
| `DeepSeek-V3.2` | 20 RPM / 20 RPD / 200.000 TPD | 60 RPM / 12.000 RPD | Preview |
| `gemma-4-31B-it` | 20 RPM / 20 RPD / 200.000 TPD | 60 RPM / 12.000 RPD | Preview |
| `MiniMax-M2.7` | Não listado na tabela pública do nível gratuito | 60 RPM / 12.000 RPD | Produção |
| `Llama-4-Maverick-17B-128E-Instruct` | Metadados do catálogo/conta ao vivo | Metadados do catálogo/conta ao vivo | Candidato apenas quando retornado ao vivo |

Contas do nível Developer têm um limite combinado de 20 milhões de tokens diários entre os modelos.

### Cotas por provedor

| Provedor ou rota | Limite público atual exato | Escopo e observações | Fonte |
|---|---|---|---|
| Modelos gratuitos Kilo Gateway | 200 requisições/hora/IP | Aplica-se a requisições anônimas e autenticadas de modelos gratuitos | [Uso e cobrança Kilo](https://kilo.ai/docs/gateway/usage-and-billing) |
| Endpoint anônimo OVHcloud | 2 RPM/IP/modelo | Este projeto usa a rota anônima; OVH autenticado é 400 RPM/projeto/modelo | [Limites OVHcloud](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-getting-started) |
| Cloudflare Workers AI | 10.000 Neurons/dia | Reseta às 00:00 UTC; plano pago cobra USD 0,011/1.000 Neurons acima da alocação gratuita | [Preços Cloudflare](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| Variantes gratuitas OpenRouter | 20 RPM; 50 requisições/dia abaixo de USD 10 em créditos vitalícios comprados; 1.000 requisições/dia a partir de USD 10 | Aplica-se a variantes `:free` e roteamento `openrouter/free` | [Limites OpenRouter](https://openrouter.ai/docs/api_reference/limits) |
| Token gratuito LLM7 | 2 req/s; 40 req/min; 100 req/hora; 1.000.000 tokens/24h | O contexto do modelo ainda varia conforme os metadados ao vivo | [Limites LLM7](https://docs.llm7.io/limits) |
| Nível gratuito SambaNova | 20 RPM; 20 RPD; 200.000 TPD para modelos de produção/preview gratuitos listados | Modelos elegíveis exatos são mostrados abaixo | [Limites SambaNova](https://docs.sambanova.ai/docs/en/models/rate-limits) |
| Nível Developer SambaNova | 60 RPM/12.000 RPD para a maioria dos modelos listados; 240 RPM/48.000 RPD para Meta Llama 3.3 70B; 20M tokens/dia entre modelos | Requer método de pagamento | [Limites SambaNova](https://docs.sambanova.ai/docs/en/models/rate-limits) |
| Google Gemini | RPM, TPM e RPD variam por projeto, modelo e nível de uso | Limites ativos são visíveis no Google AI Studio; RPD reseta à meia-noite do horário do Pacífico | [Limites de taxa Gemini](https://ai.google.dev/gemini-api/docs/rate-limits) |
| Modo gratuito Mistral | Dinâmico por organização e modelo | Não exige cartão de crédito; valores atuais são mostrados na página Limits da conta | [Limites Mistral](https://docs.mistral.ai/admin/billing-usage/usage-limits) |
| SiliconFlow | Limites de modelos gratuitos são fixos por modelo; níveis pagos de texto atualmente abrangem 1.000–10.000 RPM e 40.000–2.000.000 TPM por nível de conta | Valores específicos do modelo sobrescrevem níveis genéricos | [Limites SiliconFlow](https://docs.siliconflow.com/en/userguide/rate-limits/rate-limit-and-upgradation) |
| NVIDIA Build | Dinâmico por conta e modelo | O catálogo ao vivo `/v1/models` e os controles da conta NVIDIA são autoritativos | [Catálogo de modelos NVIDIA](https://build.nvidia.com/models) |
| API-Inference ModelScope | Dinâmico por conta/modelo e cabeçalhos de uso retornados | O instalador não codifica uma cota | [Limites ModelScope](https://modelscope.cn/docs/model-service/API-Inference/limits) |
| OpenCode Zen | Catálogo promocional/gratuito dinâmico | Autenticação é necessária antes que os modelos Zen entrem no fallback automático | [OpenCode Zen](https://opencode.ai/docs/zen/) |
| ChatGPT OAuth | Elegibilidade de assinatura e conta | Cotas ChatGPT/Codex são separadas das faixas de taxa da OpenAI API | [Configuração OpenAI OpenCode](https://opencode.ai/docs/providers/) |

### Catálogo gratuito atual Kilo

O instalador descobre todos os IDs ao vivo compatíveis com agentes que terminam em `:free` ou `/free`. O catálogo gratuito documentado atualmente é:

| ID do modelo | Observações |
|---|---|
| `stepfun/step-3.7-flash:free` | StepFun Step 3.7 Flash |
| `poolside/laguna-m.1:free` | Poolside Laguna M.1 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Termos de endpoint de trial NVIDIA se aplicam |
| `openrouter/free` | Roteia para um modelo gratuito disponível |

Todas as requisições gratuitas Kilo são limitadas a 200 requisições por hora por IP, seja autenticadas ou anônimas.

### Catálogo promocional/gratuito atual OpenCode Zen

A lista Zen é consultada durante a instalação. Na data de verificação, os IDs gratuitos/promocionais usados pela lista de prioridade do Dispatch eram:

| Prioridade | ID do modelo |
|---:|---|
| 1 | `deepseek-v4-flash-free` |
| 2 | `mimo-v2.5-free` |
| 3 | `ling-3.0-flash-free` |
| 4 | `nemotron-3-ultra-free` |
| 5 | `north-mini-code-free` |
| 6 | `laguna-s-2.1-free` |
| 7 | `big-pickle` |

A autenticação sob a credencial `opencode` é necessária antes que esses modelos sejam inseridos no fallback automático.

### Modelos dinâmicos OpenRouter e LLM7

| Rota | Regra de seleção |
|---|---|
| OpenRouter | Começa com `openrouter/free`, depois adiciona modelos de agentes com preço zero ou `:free` que anunciam suporte a ferramentas |
| LLM7 | Adiciona modelos ao vivo onde `model_type` é `chat`, `tier` é `free` e a chamada de ferramentas está disponível |

A lista exata de modelos é dinâmica e deve ser lida de `opencode-dispatch-catalog.json` após a instalação.

### Catálogos curados e de emergência presentes no código-fonte

As listas a seguir foram extraídas do instalador 1.0. Um candidato listado não é garantia de acesso atual ao provedor.

<details>
<summary><strong>Candidatos curados NVIDIA</strong></summary>

O instalador prioriza apenas candidatos retornados pela NVIDIA e depois anexa outros modelos ao vivo compatíveis com agentes. O `qwen/qwen3.5-397b-a17b` está programado para depreciação na API NVIDIA em 27 de julho de 2026 e não deve ser contado após essa data.

| # | ID do modelo |
|---:|---|
| 1 | `thinkingmachines/inkling` |
| 2 | `poolside/laguna-xs-2.1` |
| 3 | `z-ai/glm-5.2` |
| 4 | `minimaxai/minimax-m3` |
| 5 | `google/diffusiongemma-26b-a4b-it` |
| 6 | `nvidia/nemotron-3-ultra-550b-a55b` |
| 7 | `stepfun-ai/step-3.7-flash` |
| 8 | `moonshotai/kimi-k2.6` |
| 9 | `mistralai/mistral-medium-3.5-128b` |
| 10 | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| 11 | `deepseek-ai/deepseek-v4-flash` |
| 12 | `deepseek-ai/deepseek-v4-pro` |
| 13 | `minimaxai/minimax-m2.7` |
| 14 | `google/gemma-4-31b-it` |
| 15 | `mistralai/mistral-small-4-119b-2603` |
| 16 | `nvidia/nemotron-3-super-120b-a12b` |
| 17 | `nvidia/nemotron-3-nano-30b-a3b` |
| 18 | `qwen/qwen3.5-397b-a17b` |
| 19 | `qwen/qwen3.5-122b-a10b` |
| 20 | `qwen/qwen3-next-80b-a3b-instruct` |
| 21 | `qwen/qwen3-coder-480b-a35b-instruct` |
| 22 | `qwen/qwen2.5-coder-32b-instruct` |
| 23 | `mistralai/mistral-nemotron` |
| 24 | `nvidia/nemotron-nano-12b-v2-vl` |
| 25 | `nvidia/llama-3.3-nemotron-super-49b-v1.5` |
| 26 | `nvidia/llama-3.3-nemotron-super-49b-v1` |
| 27 | `nvidia/llama-3.1-nemotron-nano-8b-v1` |
| 28 | `nvidia/llama-3.1-nemotron-nano-vl-8b-v1` |
| 29 | `nvidia/llama-3.1-nemotron-70b-instruct` |
| 30 | `nvidia/llama-3.1-nemotron-ultra-253b-v1` |
| 31 | `openai/gpt-oss-120b` |
| 32 | `openai/gpt-oss-20b` |
| 33 | `bytedance/seed-oss-36b-instruct` |
| 34 | `moonshotai/kimi-k2-instruct-0905` |
| 35 | `meta/llama-3.3-70b-instruct` |
| 36 | `meta/llama-3.2-90b-vision-instruct` |
| 37 | `meta/llama-3.2-11b-vision-instruct` |
| 38 | `meta/llama-3.2-3b-instruct` |
| 39 | `meta/llama-3.2-1b-instruct` |
| 40 | `meta/llama-3.1-70b-instruct` |
| 41 | `meta/llama-3.1-8b-instruct` |
| 42 | `microsoft/phi-4-multimodal-instruct` |
| 43 | `microsoft/phi-4-mini-instruct` |
| 44 | `mistralai/mixtral-8x22b-instruct` |
| 45 | `mistralai/mixtral-8x7b-instruct` |
| 46 | `nvidia/nemotron-mini-4b-instruct` |
| 47 | `stepfun-ai/step-3.5-flash` |
| 48 | `google/gemma-2-2b-it` |

Rota do provedor: `nvidia`.

</details>

<details>
<summary><strong>Catálogo de emergência curado Cloudflare Workers AI</strong></summary>

A lista é usada quando o endpoint de busca Workers AI não retorna um catálogo de geração de texto utilizável. A disponibilidade atual da conta ainda se aplica.

| # | ID do modelo |
|---:|---|
| 1 | `@cf/zai-org/glm-5.2` |
| 2 | `@cf/moonshotai/kimi-k2.7-code` |
| 3 | `@cf/moonshotai/kimi-k2.6` |
| 4 | `@cf/zai-org/glm-4.7-flash` |
| 5 | `@cf/google/gemma-4-26b-a4b-it` |
| 6 | `@cf/nvidia/nemotron-3-120b-a12b` |
| 7 | `@cf/openai/gpt-oss-120b` |
| 8 | `@cf/openai/gpt-oss-20b` |
| 9 | `@cf/qwen/qwen2.5-coder-32b-instruct` |
| 10 | `@cf/qwen/qwen3-30b-a3b-fp8` |
| 11 | `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` |
| 12 | `@cf/mistralai/mistral-small-3.1-24b-instruct` |
| 13 | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
| 14 | `@cf/ibm-granite/granite-4.0-h-micro` |

Rota do provedor: `cloudflare-workers-ai`.

</details>

<details>
<summary><strong>Catálogo de emergência anônimo OVHcloud</strong></summary>

A lista é usada quando o endpoint anônimo `/v1/models` não retorna catálogo. A rota é limitada a 2 RPM por IP por modelo.

| # | ID do modelo |
|---:|---|
| 1 | `Qwen3.5-397B-A17B` |
| 2 | `gpt-oss-120b` |
| 3 | `gpt-oss-20b` |
| 4 | `Meta-Llama-3_3-70B-Instruct` |
| 5 | `Qwen3.6-27B` |
| 6 | `Qwen3.5-9B` |
| 7 | `Qwen3-32B` |
| 8 | `Qwen3-Coder-30B-A3B-Instruct` |
| 9 | `Qwen2.5-VL-72B-Instruct` |
| 10 | `Mistral-Small-3.2-24B-Instruct` |
| 11 | `Mistral-Nemo-Instruct-2407` |
| 12 | `Mistral-7B-Instruct-v0.3` |

Rota do provedor: `ovh-anonymous`.

</details>

<details>
<summary><strong>Candidatos SambaNova</strong></summary>

Apenas candidatos retornados pelo catálogo ao vivo da SambaNova são habilitados.

| # | ID do modelo |
|---:|---|
| 1 | `DeepSeek-V3.1` |
| 2 | `Meta-Llama-3.3-70B-Instruct` |
| 3 | `gpt-oss-120b` |
| 4 | `Llama-4-Maverick-17B-128E-Instruct` |
| 5 | `DeepSeek-V3.2` |
| 6 | `MiniMax-M2.7` |
| 7 | `gemma-4-31B-it` |

Rota do provedor: `sambanova`.

</details>

<details>
<summary><strong>Candidatos Flash gratuitos Z.AI</strong></summary>

O Dispatch usa o catálogo ao vivo quando disponível. Se o provedor não expõe uma lista de modelos, esses candidatos de compatibilidade são registrados.

| # | ID do modelo |
|---:|---|
| 1 | `glm-4.7-flash` |
| 2 | `glm-4-flash-250414` |
| 3 | `glm-4.6v-flash` |

Rota do provedor: `zai-free`.

</details>

<details>
<summary><strong>Candidatos gratuitos SiliconFlow</strong></summary>

Apenas candidatos retornados pelo catálogo ao vivo da SiliconFlow são habilitados.

| # | ID do modelo |
|---:|---|
| 1 | `Qwen/Qwen3-8B` |
| 2 | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` |

Rota do provedor: `siliconflow-free`.

</details>

<details>
<summary><strong>Candidatos preferidos ModelScope</strong></summary>

Modelos ao vivo compatíveis com agentes são preferidos. Esses candidatos são usados quando o endpoint de lista de modelos está indisponível.

| # | ID do modelo |
|---:|---|
| 1 | `Qwen/Qwen3.5-35B-A3B` |
| 2 | `Qwen/Qwen3.5-27B` |

Rota do provedor: `modelscope-free`.

</details>

<details>
<summary><strong>Candidatos curados Google</strong></summary>

Apenas modelos Gemini ao vivo que suportam `generateContent` e correspondem a este conjunto são habilitados.

| # | ID do modelo |
|---:|---|
| 1 | `gemini-2.5-flash` |
| 2 | `gemini-2.5-flash-lite` |
| 3 | `gemini-2.5-flash-lite-preview-09-2025` |
| 4 | `gemini-2.5-pro` |
| 5 | `gemini-3-flash-preview` |
| 6 | `gemini-3.1-flash-lite` |
| 7 | `gemini-3.5-flash` |
| 8 | `gemini-3.5-flash-lite` |
| 9 | `gemini-3.6-flash` |

Rota do provedor: `google`.

</details>

<details>
<summary><strong>Candidatos preferidos Groq</strong></summary>

Apenas candidatos ao vivo são priorizados; outros modelos Groq ao vivo compatíveis com agentes são anexados.

| # | ID do modelo |
|---:|---|
| 1 | `groq/compound` |
| 2 | `groq/compound-mini` |
| 3 | `llama-3.1-8b-instant` |
| 4 | `llama-3.3-70b-versatile` |
| 5 | `openai/gpt-oss-120b` |
| 6 | `openai/gpt-oss-20b` |
| 7 | `qwen/qwen3.6-27b` |

Rota do provedor: `groq`.

</details>

### Desativação do GitHub Models

O GitHub Models é mantido apenas para usuários existentes antes de **30 de julho de 2026**. O Dispatch pula a descoberta e remove o provedor configurado nessa data ou depois. O GitHub anunciou que o playground, o catálogo, a API de inferência e os endpoints BYOK deixarão de estar disponíveis para todos os clientes.

## Estratégia de fallback

O fallback é ativado por padrão. O Dispatch rastreia a saúde separadamente para modelos e, para falhas selecionadas, para provedores.

### Política padrão de tempo e status

| Configuração | Padrão | Significado |
|---|---:|---|
| Cooldown normal | 120.000 ms | Cooldown temporário do modelo para falhas ordinárias retriáveis |
| Cooldown transitório | 30.000 ms | Cooldown curto para HTTP 408, 500, 502, 503 e 504 |
| Cooldown do provedor | 900.000 ms | Cooldown em todo o provedor quando a política se aplica |
| Status permanentes | 402, 403, 404, 410 | Desabilita o modelo até o próximo início do processo |
| Status transitórios | 408, 500, 502, 503, 504 | Desabilita temporariamente o modelo |
| Limite de taxa | 429 | Desabilita temporariamente a rota atual |
| Autenticação | 401 | Desabilita a rota afetada; o tratamento em todo o provedor se aplica ao OpenAI |
| Tentativa de failover | 1 | Inicia o failover após o limiar configurado de tentativas falhas |

### Ordem de seleção

Quando uma requisição falha, o Dispatch seleciona o próximo modelo nesta ordem:

1. Continua após o modelo que falhou na cadeia específica do papel atual.
2. Dá a volta na mesma cadeia do papel pulando modelos indisponíveis.
3. Busca na cadeia de emergência global.
4. Para o redirecionamento automático quando nenhum modelo saudável resta.

Antes de uma requisição começar, o plugin também redireciona de forma preventiva quando o modelo selecionado já está em cooldown ou desabilitado.

### Tratamento de falhas

| Classe de falha | Ação no modelo | Ação no provedor | Recuperação |
|---|---|---|---|
| Erro de autenticação | Desabilitado até reiniciar | OpenAI pode ser desabilitado em todo o provedor | Adicione/corrija credenciais e reinicie o OpenCode |
| Limite de conta ou assinatura | Desabilitado até reiniciar | OpenAI pode ser desabilitado em todo o provedor | Restaure a elegibilidade da conta e reinicie |
| Status HTTP permanente | Desabilitado até reiniciar | Normalmente específico do modelo | Verifique o ID do modelo, política de acesso ou cobrança |
| Limite de taxa | Cooldown temporário | OpenAI pode receber cooldown em todo o provedor | Aguarde o reset da cota; o Dispatch tenta outra rota |
| Falha transitória de servidor/rede | Cooldown de 30 segundos | OpenAI pode receber tratamento de retry em todo o provedor | O Dispatch tenta outro modelo/provedor |
| Outra falha retriável | Cooldown de 120 segundos | Normalmente específico do modelo | O Dispatch avança pela cadeia |

Para um fallback, o plugin interrompe a resposta com falha, reconstrói a última requisição do usuário e a envia de forma assíncrona através do modelo de substituição selecionado. Eventos de falha duplicados são suprimidos, e apenas uma operação de fallback é permitida em andamento para a mesma resposta.

Toda mudança de rota registra o modelo anterior, o modelo de substituição, o motivo, o status HTTP, a origem e o resultado na telemetria.

## Orquestrador

O agente raiz padrão é o `maestro`. Ele deve chamar `dispatch_plan` antes de executar uma tarefa, delegar os papéis necessários através da ferramenta `task` do OpenCode e chamar `dispatch_complete` antes da resposta final.

### Papéis

| Papel | Responsabilidade |
|---|---|
| `maestro` / `orchestrator` | Classifica o trabalho, delega papéis e controla o portão de conclusão |
| `architect` | Arquitetura, interfaces, trade-offs e design entre módulos |
| `backend` | Lógica do lado do servidor, fluxo de dados, integrações e implementação não visual |
| `frontend` | Comportamento da interface do usuário e implementação do lado do cliente |
| `explorer` | Descoberta de repositório, análise de impacto e navegação no código |
| `tester` | Design de testes, execução e cobertura de regressão |
| `reviewer` | Revisão independente, verificação de riscos e validação de conclusão |
| `researcher` | Documentação externa e coleta de evidências |
| `vision` | Análise de screenshots, imagens, layouts e entradas visuais |

Cada papel recebe uma cadeia de modelos pontuada primeiro para o papel, depois pela prioridade do provedor e por último pelos modelos compatíveis restantes.

### Categorias de tarefa e portões

| Categoria | Papéis obrigatórios | Papéis condicionais ou opcionais |
|---|---|---|
| `trivial` | Nenhum; aprovado automaticamente | Nenhum |
| `analysis` | `explorer`, `architect` | `reviewer` obrigatório para alto risco, opcional caso contrário |
| `implementation` | `explorer`, `tester` e pelo menos um de `backend`, `frontend`, `vision` | `architect` e `reviewer` obrigatórios para alto risco, opcionais caso contrário |
| `bug` | `explorer`, `tester` e pelo menos um executor: `backend`, `frontend`, `vision` | `reviewer` obrigatório para alto risco, opcional caso contrário |
| `research` | `researcher` | `reviewer` obrigatório para alto risco; `architect` e `reviewer` opcionais caso contrário |
| `visual` | `explorer`, `tester` e pelo menos um de `vision`, `frontend` | `reviewer` opcional |

### Flags de risco

| Flag | Efeito |
|---|---|
| `security` | Alto risco |
| `persistence` | Alto risco |
| `publicApi` | Alto risco |
| `migration` | Alto risco |
| `concurrency` | Alto risco |
| `multiModule` | Alto risco |
| `externalDocs` | Rastreado, mas não é alto risco por si só |
| `visualInput` | Rastreado, mas não é alto risco por si só |

Se os papéis obrigatórios estiverem ausentes, o plugin envia uma instrução automática de remediação. O máximo padrão é de duas tentativas de remediação. Após o limite, o portão falha aberto para evitar deadlock, mas o relatório registra a orquestração incompleta e os papéis ausentes.

### Comandos explícitos de tarefa

| Comando | Categoria forçada | Uso |
|---|---|---|
| `/dispatch-analyze <tarefa>` | `analysis` | Arquitetura, explicação e análise de impacto |
| `/dispatch-implement <tarefa>` | `implementation` | Trabalho de funcionalidade ou refatoração |
| `/dispatch-bug <tarefa>` | `bug` | Depuração e implementação corretiva |
| `/dispatch-report` | Comando de relatório | Exibe o uso de relatórios dentro do OpenCode |

## Uso

### Iniciar em um projeto

```bash
cd /caminho/do/projeto
opencode-dispatch
```

No primeiro uso em um repositório, inicialize o OpenCode se necessário:

```text
/init
```

Use a TUI normalmente ou invoque um comando explícito do Dispatch:

```text
/dispatch-analyze Review the authentication architecture
/dispatch-implement Add request validation
/dispatch-bug Fix the intermittent session timeout
```

### Selecionar ou inspecionar modelos

```text
/models
```

O agente padrão é o `maestro`. O Dispatch também configura o `model` inicial a partir da cadeia do maestro e o `small_model` a partir da cadeia do explorer.

### Atualizar o Dispatch

Execute o instalador novamente:

```bash
python3 install.py
```

A configuração existente do OpenCode é carregada, respaldada e mesclada.

## Relatórios

O Dispatch grava um snapshot da sessão ao vivo enquanto o OpenCode está em execução e relatórios finais em Markdown/JSON quando as sessões são finalizadas.

### Comandos de relatório

| Comando | Resultado |
|---|---|
| `opencode-dispatch-report` | Lê o relatório final mais recente |
| `opencode-dispatch-report --latest` | Lê o relatório final mais recente explicitamente |
| `opencode-dispatch-report --active` | Lê o snapshot da sessão ao vivo atual |
| `opencode-dispatch-report --session <id>` | Lê o relatório de uma sessão específica |
| `opencode-dispatch-report --list` | Lista relatórios finalizados recentes |
| `opencode-dispatch-report --compact` | Imprime um resumo Markdown compacto |
| `opencode-dispatch-report --json` | Imprime JSON bruto |
| `opencode-dispatch-report --active --json` | Imprime o snapshot ativo como JSON |
| `python report.py --latest` | Executa o leitor de relatórios diretamente do diretório de origem |

Dentro do OpenCode:

```text
/dispatch-report
```

### Conteúdo dos relatórios

| Seção | Informação |
|---|---|
| Timing | Duração de wall-clock e tempo agregado de modelos |
| Tokens | Valores de entrada, saída, reasoning/cache quando fornecidos, total de tokens e cobertura |
| Modelos | Modelos e provedores usados durante a sessão |
| Fallbacks | Toda transição de rota com motivo, status e resultado |
| Sessões | Sessão raiz e sessões de subagentes incluídas |
| Orquestração | Categoria, papéis obrigatórios, papéis invocados, portão de conclusão e contagem de remediações |
| Conformidade | Se o contrato de orquestração foi concluído |

O tempo agregado de modelos pode exceder o tempo de wall-clock porque subagentes podem rodar concurrentemente. A cobertura de tokens pode ficar abaixo de 100% quando um provedor não retorna metadados de uso completos.

### Arquivos de relatório

| Arquivo | Significado |
|---|---|
| `~/.opencode/opencode-dispatch-reports/active.json` | Snapshot legível por máquina ao vivo |
| `~/.opencode/opencode-dispatch-reports/active.md` | Snapshot Markdown ao vivo |
| `~/.opencode/opencode-dispatch-reports/latest.json` | Relatório JSON final mais recente |
| `~/.opencode/opencode-dispatch-reports/latest.md` | Relatório Markdown final mais recente |
| `~/.opencode/opencode-dispatch-reports/<session-id>.json` | Relatório JSON final de uma sessão |
| `~/.opencode/opencode-dispatch-reports/<session-id>.md` | Relatório Markdown final de uma sessão |

## Configuração

O Dispatch carrega a configuração nesta ordem:

1. Valores padrão embutidos.
2. `~/.opencode/opencode-dispatch.json`.
3. `<projeto>/opencode-dispatch.json`.

As configurações do projeto sobrescrevem as configurações globais. Arquivos inválidos ou ausentes voltam para os padrões.

### Exemplo

```json
{
  "enabled": true,
  "cooldownMs": 120000,
  "transientCooldownMs": 30000,
  "providerCooldownMs": 900000,
  "retryFailoverAttempt": 1,
  "orchestration": {
    "enabled": true,
    "enforce": true,
    "autoClassify": true,
    "maxAutoRemediations": 2,
    "report": true
  },
  "telemetry": {
    "enabled": true,
    "writeLiveReport": true,
    "writeMarkdown": true,
    "writeJson": true,
    "includeSubagents": true
  }
}
```

### Principais configurações

| Configuração | Tipo | Padrão | Propósito |
|---|---|---:|---|
| `enabled` | Boolean | `true` | Ativa o processamento de fallback |
| `cooldownMs` | Integer | `120000` | Cooldown normal do modelo |
| `transientCooldownMs` | Integer | `30000` | Cooldown para falhas transitórias |
| `providerCooldownMs` | Integer | `900000` | Cooldown em todo o provedor |
| `retryFailoverAttempt` | Integer | `1` | Limiar de tentativas falhas antes do failover |
| `fallbackModels` | Array | `[]` | Referências adicionais de modelos de fallback global |
| `fallbackGroups` | Object | `{}` | Agrupamento personalizado de fallback |
| `modelGroups` | Object | `{}` | Agrupamento personalizado de modelos |
| `permanentStatusCodes` | Array | `[402, 403, 404, 410]` | Erros que desabilitam um modelo até reiniciar |
| `transientStatusCodes` | Array | `[408, 500, 502, 503, 504]` | Erros que usam o cooldown curto |
| `authFailureFallbackProviders` | Array | `["openai"]` | Provedores elegíveis para failover de autenticação em todo o provedor |
| `providerWideRateLimitProviders` | Array | `["openai"]` | Provedores elegíveis para cooldown 429 em todo o provedor |
| `providerWideRetryProviders` | Array | `["openai"]` | Provedores elegíveis para tratamento de retry em todo o provedor |

## Arquivos e diretórios

`~` representa o diretório home do usuário atual em todos os sistemas operacionais.

| Caminho | Propósito |
|---|---|
| `~/.config/opencode/opencode.json` ou `.jsonc` | Configuração global padrão do OpenCode |
| `$OPENCODE_CONFIG` | Arquivo de configuração OpenCode explícito opcional |
| `$OPENCODE_CONFIG_DIR` | Diretório OpenCode personalizado opcional para plugins, agentes e comandos |
| `~/.config/opencode/plugins/opencode-dispatch.js` | Plugin Dispatch instalado |
| `~/.local/share/opencode/auth.json` | Credenciais gerenciadas pelo OpenCode |
| `~/.opencode/opencode-dispatch.json` | Configuração global do Dispatch |
| `<projeto>/opencode-dispatch.json` | Configuração do Dispatch do projeto |
| `~/.opencode/opencode-dispatch-catalog.json` | Relatório de descoberta de provedores/modelos gerado |
| `~/.opencode/opencode-dispatch-reports/` | Relatórios de telemetria ao vivo e finais |
| `~/.opencode/opencode-dispatch.log` | Log operacional do plugin |

O instalador também cria arquivos de lançador apropriados para cada plataforma. No Windows esses incluem lançadores `.cmd`.

## Segurança e privacidade

- As chaves de API permanecem em variáveis de ambiente ou no armazenamento de autenticação do OpenCode.
- Os relatórios do Dispatch não armazenam intencionalmente chaves de API.
- Os relatórios focam em roteamento de modelos, timing, metadados de uso e estado de orquestração.
- Os termos dos provedores ainda se aplicam. Alguns endpoints gratuitos/trial podem registrar prompts ou exigir consentimento de coleta de dados.
- Não envie informações confidenciais a um provedor a menos que seus termos de tratamento de dados atendam aos seus requisitos.
- Proteja `~/.local/share/opencode/auth.json`, perfis de shell e armazenamentos de segredos de CI.

## Solução de problemas

| Problema | Resolução |
|---|---|
| Nenhum modelo foi descoberto | Defina pelo menos uma chave de API suportada, configure OAuth ChatGPT/OpenCode ou verifique a conectividade de provedores anônimos |
| `opencode-dispatch` não é encontrado | Abra um novo terminal ou adicione o diretório do lançador gerado ao `PATH` |
| OAuth do ChatGPT é ignorado | Execute `opencode auth login`; use o lançador Dispatch para que `OPENAI_API_KEY` não sobrescreva o OAuth |
| Instalação do Mistral é lenta | Use `--no-probe-mistral` para pular sondas de acessibilidade de um token |
| Um candidato listado está indisponível | Execute a instalação novamente; apenas o catálogo ao vivo gerado deve ser tratado como disponível |
| Erros 429 repetidos | Inspecione as cotas do provedor, aguarde o reset ou configure provedores adicionais |
| Relatório está faltando | Complete pelo menos uma resposta do OpenCode e depois execute `opencode-dispatch-report --latest` |
| Cobertura de tokens está incompleta | O provedor ativo não retornou metadados de uso completos |
| GitHub Models parou de funcionar | O serviço desativa globalmente em 30 de julho de 2026; execute o instalador novamente para removê-lo |
| NVIDIA Qwen 3.5 397B parou de funcionar | A NVIDIA programa esse endpoint para depreciação em 27 de julho de 2026; execute a descoberta novamente |

## Referências oficiais

| Tópico | Fonte oficial |
|---|---|
| Instalação OpenCode | https://opencode.ai/docs/ |
| Provedores e credenciais OpenCode | https://opencode.ai/docs/providers/ |
| Modelos OpenCode | https://opencode.ai/docs/models/ |
| Configuração OpenCode | https://opencode.ai/docs/config/ |
| OpenCode Zen | https://opencode.ai/docs/zen/ |
| Catálogo de modelos OpenAI | https://developers.openai.com/api/docs/models |
| Modelos Gemini | https://ai.google.dev/gemini-api/docs/models |
| Limites Gemini | https://ai.google.dev/gemini-api/docs/rate-limits |
| Modelos Groq | https://console.groq.com/docs/models |
| Modelos Kilo | https://kilo.ai/docs/gateway/models-and-providers |
| Limites Kilo | https://kilo.ai/docs/gateway/usage-and-billing |
| Limites Mistral | https://docs.mistral.ai/admin/billing-usage/usage-limits |
| Preços Cloudflare Workers AI | https://developers.cloudflare.com/workers-ai/platform/pricing/ |
| Endpoints de IA OVHcloud | https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-getting-started |
| Limites OpenRouter | https://openrouter.ai/docs/api_reference/limits |
| Limites LLM7 | https://docs.llm7.io/limits |
| Limites SambaNova | https://docs.sambanova.ai/docs/en/models/rate-limits |
| Preços Z.AI | https://docs.z.ai/guides/overview/pricing |
| Limites SiliconFlow | https://docs.siliconflow.com/en/userguide/rate-limits/rate-limit-and-upgradation |
| Limites API-Inference ModelScope | https://modelscope.cn/docs/model-service/API-Inference/limits |
| Desativação GitHub Models | https://github.blog/changelog/2026-07-01-github-models-is-being-fully-retired-on-july-30-2026/ |
| Catálogo de modelos NVIDIA | https://build.nvidia.com/models |

---

O OpenCode Dispatch não garante disponibilidade de provedores, acesso gratuito, elegibilidade de conta ou cotas inalteradas. Execute `install.py` novamente sempre que as credenciais, os catálogos de provedores ou a disponibilidade de modelos mudarem.