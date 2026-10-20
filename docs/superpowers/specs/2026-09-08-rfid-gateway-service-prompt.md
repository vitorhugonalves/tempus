# Especificação inicial — Gateway RFID Tempus

**Data:** 2026-09-08
**Status:** Rascunho — para iniciar brainstorm/projeto separado

> Este documento é o ponto de partida (prompt) para uma sessão de brainstorming dedicada
> ao projeto do gateway, num repositório separado. Não faz parte do código do Tempus.
> O contrato de API que ele consome está fixado pelo Tempus e documentado na seção 3 —
> trate como interface externa estável, não como algo a redesenhar junto com o gateway.

---

## Contexto

O Tempus (gerenciador de timers de competições esportivas, backend FastAPI) está ganhando
cronometragem automática por estações via RFID para competições Hyrox. Um pórtico RFID UHF
lê a tag de pulseira de cada atleta na entrada e saída de cada estação do percurso. Esse
gateway é o serviço que roda num Raspberry Pi em campo, conversa com o leitor via LLRP, e
traduz cada leitura em uma chamada HTTP para a API do Tempus.

**O Tempus não sabe nada sobre LLRP, antenas ou hardware de leitor.** Toda essa
complexidade fica isolada neste projeto. O Tempus só recebe um POST simples por leitura.

## Piloto de referência (10 atletas)

- 1 leitor RFID UHF com LLRP, 2 antenas (entrada e saída de 1 única estação)
- Tags UHF em pulseira, atribuídas aos atletas no check-in (ver contrato de API)
- Raspberry Pi rodando este gateway
- Estrutura física de pórtico, energia e conectividade de backup no local
- Notebook/tablet no local com o painel de correção manual do Tempus (para quando uma
  leitura falha)

O sistema final terá N estações (múltiplos pórticos), mas o piloto valida o fluxo com uma
estação só.

---

## 1. Responsabilidades do gateway

1. Conectar ao(s) leitor(es) LLRP e receber leituras de tag em tempo real.
2. Mapear antena física → `station_id` + `direction` ("in"/"out") — configuração local,
   por dispositivo (uma Raspberry Pi pode servir mais de uma estação/leitor).
3. Debounce client-side de releituras da mesma tag na mesma antena (~2s) — **otimização de
   tráfego, não é a garantia de correção**. A API do Tempus já faz seu próprio
   dedup/debounce server-side; o gateway não precisa (e não deve tentar) ser a fonte de
   verdade de deduplicação.
4. Traduzir cada leitura aceita em uma chamada `POST /gateway/readings` (contrato na
   seção 3), com um `read_id` (UUID) único por leitura física — não por tentativa de
   envio. Se a mesma leitura for reenviada por retry de rede, reenvia o **mesmo**
   `read_id`.
5. Buffer local (disco) quando a conectividade com o Tempus cair, e replay em ordem
   quando a conexão voltar — sem perder leituras, sem duplicar (o `read_id` idempotente
   do lado do Tempus cobre replay duplicado).
6. Retry com backoff exponencial em falha de rede/5xx. Em erro 4xx do Tempus (ex: tag não
   pareada, estação desconhecida), **não** insistir infinitamente — logar e seguir (a
   leitura fica registrada localmente para diagnóstico, mas o juiz já tem o backup
   manual).
7. Relatar seu próprio estado de saúde (última leitura processada, status de conexão) —
   pelo menos em log estruturado local; se o Tempus expuser um endpoint de heartbeat no
   futuro (fora do MVP atual), reportar lá também.

## 2. Fora de escopo do gateway

- Qualquer lógica de negócio de cronometragem (fechamento automático de estação anterior,
  regra de finalização de equipe, cálculo de tempo) — isso é 100% responsabilidade da API
  do Tempus. O gateway só relata "essa tag passou por essa antena nesse instante".
- Autenticação de usuários humanos — o gateway usa um token de máquina fixo (seção 3), não
  há conceito de login aqui.
- Pareamento de tag ↔ atleta — acontece na UI do Tempus, no check-in. O gateway só conhece
  `tag_code`, nunca sabe quem é o atleta.

## 3. Contrato de API (fixado pelo Tempus — não renegociar aqui)

### Autenticação

`Authorization: Bearer <gateway_token>` — token de competição, gerado e revogável na UI do
Tempus (`GatewayToken`, um por competição). Guardar em config local do gateway, nunca em
texto plano em log.

### Endpoint

```
POST /gateway/readings
```

**Payload:**

```json
{
  "tag_code": "string",
  "station_id": 123,
  "direction": "in" | "out",
  "read_at": "2026-09-08T14:03:21.500Z",
  "read_id": "uuid-v4"
}
```

- `read_at`: horário do relógio local do Pi no momento da leitura física (não o horário do
  envio HTTP). **Requer NTP sincronizado** — o Tempus rejeita leituras com `read_at` fora
  de uma janela de tolerância em relação ao relógio do servidor.
- `read_id`: gerado uma vez por leitura física; reenviado idêntico em qualquer retry.
- `direction`: para estações do tipo "finish", o valor é ignorado pela lógica de negócio
  (qualquer leitura na estação finish conta como chegada) — mas envie `"in"` por padrão
  se a antena não distinguir.

**Respostas esperadas:**

- `201` — leitura registrada (ou já existente, se `read_id` repetido — idempotente).
- `401` — token inválido/revogado. Parar de tentar até reconfiguração manual.
- `422` — payload inválido, tag não paread, estação inexistente, ou clock skew. Logar,
  seguir (não é erro transitório de rede).
- `5xx`/timeout — erro transitório. Buffer local + retry com backoff.

### O que o gateway NÃO recebe de volta

A resposta do endpoint não informa se a estação anterior foi fechada automaticamente, se a
equipe finalizou, etc. — o gateway é "fire and forget" quanto à lógica de negócio. Se
precisar exibir status ao operador local, use o painel do Tempus (frontend), não o gateway.

---

## 4. Perguntas a resolver no brainstorm desse projeto (não decidir aqui)

- Linguagem/runtime do gateway (Python + `sllurp` é o caminho natural dado o ecossistema
  LLRP, mas vale confirmar contra o SDK do leitor específico escolhido).
- Formato do buffer local (SQLite embarcado? arquivo append-only?).
- Como a configuração antena→estação é editada em campo (arquivo local? push remoto do
  Tempus?).
- Estratégia de deploy/atualização no Raspberry Pi (imagem pré-configurada? Ansible?
  atualização manual via SSH pro piloto de 10 atletas, automatizar depois?).
- Necessidade (ou não) de um endpoint de heartbeat no Tempus para health-check do
  gateway — hoje não existe; se o painel de saúde da estação (fase 2 do lado Tempus) for
  priorizado, esse contrato precisa ser co-desenhado com o time do Tempus antes.

---

*Use este documento como prompt inicial de uma sessão `superpowers:brainstorming` no
repositório do gateway, quando esse projeto começar.*
