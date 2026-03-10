# REQUIREMENTS.md — Tempus

> Documento de Requisitos do Projeto  
> Versão: 1.0.0 | Data: 2026-03-09

---

## 1. Visão Geral

**Tempus** é uma plataforma web para gerenciamento de timers em competições esportivas cronometradas, com foco em eventos do estilo Hyrox e CrossFit. O sistema permite que organizadores criem e controlem eventos, juízes operem timers em tempo real e competidores acompanhem seu desempenho e posicionamento.

### Público-alvo

Organizadores de eventos e competições esportivas com até **300 atletas por edição**.

### Premissas

- Sistema web-first; arquitetura preparada para app mobile de visualização no futuro
- Operação em Linux ou Windows (bare metal ou containers Docker)
- Banco de dados SQLite por padrão, com migração suportada para PostgreSQL
- Interface responsiva (desktop e mobile browser)

---

## 2. Perfis de Acesso (Roles)

### 2.1 Competidor

| Permissão | Descrição |
|-----------|-----------|
| Cadastro próprio | Pode se cadastrar individualmente ou como grupo |
| Vinculação de equipe | Pode linkar outros competidores ao seu grupo |
| Convite por e-mail | Pode enviar link para outros completarem o cadastro |
| Visualização de ranking | Pode ver seu posicionamento e tempo na competição |

### 2.2 Judge

| Permissão | Descrição |
|-----------|-----------|
| Controle de timer | Iniciar, parar e reiniciar o timer do atleta/equipe designado |
| Aplicação de penalidades | Adicionar punições (acréscimo de tempo, parada obrigatória) conforme regulamento |

### 2.3 Operador / Administrador de Evento

| Permissão | Descrição |
|-----------|-----------|
| Gestão de usuários | Cadastrar competidores, judges e outros operadores |
| Gestão de competição | Criar, editar e gerenciar a competição vigente e suas regras |
| Gestão de timers | Cadastrar, configurar e monitorar todos os timers |
| Acesso de leitura | Visualizar todos os dados da competição |

### 2.4 Administrador (Super Admin)

- Acesso irrestrito a todas as funcionalidades do sistema
- Gerenciamento de múltiplas competições e operadores
- Configurações globais da plataforma

---

## 3. Funcionalidades

### 3.1 Autenticação e Sessão

- **RF-01:** ✅ Login com e-mail e senha
- **RF-02:** ✅ Sessão server-side com cookie seguro (HttpOnly, Secure, SameSite=Lax)
- **RF-03:** ✅ Expiração de sessão configurável (padrão: 8 horas)
- **RF-04:** ✅ Logout com invalidação da sessão no servidor
- **RF-05:** 🔲 Recuperação de senha via e-mail (link com token de uso único)
- **RF-06:** 🔲 Registro de competidor via link de convite com token assinado

### 3.2 Cadastros

#### 3.2.1 Usuários do Sistema

- **RF-07:** ✅ CRUD de usuários (Operador/Admin)
- **RF-08:** ✅ Atribuição e alteração de roles por Operador ou Admin
- **RF-09:** ✅ Ativação/desativação de conta sem exclusão permanente
- **RF-10:** ✅ Campos obrigatórios: nome completo, e-mail, role, senha

#### 3.2.2 Competidores

- **RF-11:** 🔲 Cadastro individual de competidor (nome, e-mail, documento, categoria)
- **RF-12:** 🔲 Cadastro em grupo/equipe com vínculo entre membros
- **RF-13:** 🔲 Envio de e-mail de convite com link para auto-cadastro
- **RF-14:** 🔲 Edição de dados pelo próprio competidor ou por Operador
- **RF-15:** ✅ Associação de competidor a uma ou mais categorias (modelo CompetitorRegistration)

#### 3.2.3 Competições

- **RF-16:** ✅ Criar competição com nome, data, local, modalidade e número máximo de atletas
- **RF-17:** ✅ Definir regulamento: tipos de penalidade configuráveis por competição
- **RF-18:** ✅ Ativar/encerrar competição (controla quais funcionalidades ficam disponíveis)
- **RF-19:** ✅ Clonar configuração de uma competição anterior como template

#### 3.2.4 Categorias

- **RF-20:** ✅ CRUD de categorias (ex: Elite Masculino, Master 40+, Equipe Mista)
- **RF-21:** ✅ Definir se a categoria é individual ou por equipe
- **RF-22:** ✅ Associar categoria a uma competição específica

#### 3.2.5 Times / Equipes

- **RF-23:** ✅ Modelo de times com membros (Team + TeamMember)
- **RF-24:** ✅ Capitão/responsável do time definido no modelo
- **RF-25:** ✅ Validação de max_team_size pela categoria (regra de negócio)

### 3.3 Timers

- **RF-26:** ✅ Criar timer e associá-lo a um atleta, equipe e competição
- **RF-27:** ✅ Iniciar timer (Judge, Operador, Admin)
- **RF-28:** ✅ Pausar/parar/finalizar timer (Judge, Operador, Admin)
- **RF-29:** ✅ Reiniciar timer com registro de motivo obrigatório
- **RF-30:** ✅ Visualização em tempo real do timer (acesso público, elapsed calculado on-the-fly)
- **RF-31:** ✅ Histórico de eventos do timer (start, stop, restart, finish) com timestamp e usuário

### 3.4 Penalidades

- **RF-32:** ✅ Tipos de penalidade configuráveis por competição (time_increment, mandatory_stop)
- **RF-33:** ✅ Aplicar penalidade a um atleta/equipe durante a competição (Judge+)
- **RF-34:** ✅ Justificativa obrigatória ao aplicar penalidade
- **RF-35:** ✅ Visualizar penalidades recebidas (endpoint público GET /timers/{id}/penalties)

### 3.5 Ranking e Resultados

- **RF-36:** ✅ Ranking geral em tempo real por categoria (ordenado por tempo final)
- **RF-37:** ✅ Tempo final = tempo cronometrado + penalidades acumuladas
- **RF-38:** ✅ Filtro de ranking por category_id
- **RF-39:** ✅ Exibição pública do ranking sem necessidade de login

### 3.6 Instalação e Inicialização

- **RF-44:** ✅ Na primeira execução de `alembic upgrade head`, cria admin padrão com senha aleatória
- **RF-45:** ✅ Criação automática só ocorre se não existe admin no banco
- **RF-46:** ✅ Credenciais salvas em `.temp_cred` (nunca versionado)

### 3.7 Relatórios e Exportações

- **RF-40:** ✅ Ranking exportável em CSV; PDF via WeasyPrint (fallback HTML se não instalado)
- **RF-41:** 🔲 Certificado de participação individual em PDF
- **RF-42:** 🔲 Imagem para redes sociais (PNG)
- **RF-43:** 🔲 Geração sob demanda pelo próprio competidor

---

## 4. Requisitos Não Funcionais

### 4.1 Desempenho

- **RNF-01:** Suportar até 300 atletas simultâneos com timers ativos sem degradação
- **RNF-02:** Atualização de timer em tela com latência máxima de 1 segundo (WebSocket ou polling)
- **RNF-03:** Tempo de resposta da API < 300ms para 95% das requisições em carga normal

### 4.2 Segurança

- **RNF-04:** Senhas armazenadas com bcrypt (custo ≥ 12)
- **RNF-05:** Todas as rotas protegidas verificam role antes de processar a requisição
- **RNF-06:** Rate limiting em endpoints de autenticação (máx. 10 tentativas/minuto por IP)
- **RNF-07:** Tokens de convite com expiração de 72 horas e uso único
- **RNF-14:** Documentos devem ser tokenizados e armazenados em segurança
- **RNF-15:** Todos os dados pessoais devem atender a LGPD (Lei Geral de Proteção de Dados) Brasileira

### 4.3 Portabilidade e Deploy

- **RNF-08:** Deve funcionar em Linux (Ubuntu 22.04+) e Windows 10/11
- **RNF-09:** Docker Compose deve subir todo o ambiente com um único comando
- **RNF-10:** Banco SQLite deve ser substituível por PostgreSQL via variável de ambiente sem alteração de código

### 4.4 Manutenibilidade

- **RNF-11:** Cobertura de testes automatizados ≥ 80%
- **RNF-12:** Toda alteração de schema de banco via migration Alembic versionada
- **RNF-13:** Documentação OpenAPI (Swagger UI) disponível em `/docs`

---

## 5. Regras de Negócio

- **RN-01:** Um timer só pode ser iniciado se a competição estiver com status "ativa"
- **RN-02:** Um competidor só pode ser associado a uma categoria por competição
- **RN-03:** Penalidades não podem ser removidas após aplicadas — apenas corrigidas com registro de motivo
- **RN-04:** O tempo final de um competidor é imutável após o encerramento da competição
- **RN-05:** Apenas o Administrador pode reabrir uma competição encerrada
- **RN-06:** Certificado e imagem para redes sociais só são gerados após encerramento oficial da competição
- **RN-07:** Link de convite é pessoal e não pode ser usado por outro e-mail diferente do destinatário

---

## 6. Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Backend | Python ≥ 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Banco (padrão) | SQLite (aiosqlite) |
| Banco (produção) | PostgreSQL (asyncpg) |
| Frontend | React + TypeScript + Vite |
| Estilo | TailwindCSS |
| Tempo real | WebSocket (FastAPI nativo) |
| Containers | Docker + Docker Compose |
| Testes BE | pytest + pytest-asyncio + httpx |
| Testes FE | Vitest + React Testing Library |
| E-mail | SMTP configurável (convites e recuperação de senha) |
| Geração PDF | WeasyPrint ou ReportLab |
| Geração de imagem | Pillow |

---

## 7. Integrações Futuras (Out of Scope v1)

- Aplicativo mobile para visualização de eventos em andamento (React Native)
- Integração com sistemas de inscrição externos (Eventbrite, Sympla)
- Streaming de dados em tempo real para telões no local do evento
- Autenticação via OAuth2 / SSO (Google, Facebook)

---

## 8. Glossário

| Termo | Definição |
|-------|-----------|
| Timer | Cronômetro associado a um atleta ou equipe em uma competição |
| Judge | Árbitro responsável por operar os timers em campo |
| Penalidade | Acréscimo de tempo ou parada obrigatória aplicada por infração |
| Competição | Evento esportivo com atletas, categorias, timers e regulamento |
| Categoria | Divisão de atletas por nível, gênero, faixa etária ou tipo de participação |
| Ranking | Classificação ordenada pelo tempo final (cronometrado + penalidades) |
| Certificado | Documento PDF emitido ao competidor após encerramento da competição |
