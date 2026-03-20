# ADR-008 — Importação em lote de usuários e equipes via CSV

**Status:** Aceito
**Data:** 2026-03-19

---

## Contexto

Administradores precisam cadastrar rapidamente muitos usuários e equipes antes de uma competição, sem precisar fazer isso um a um pela interface.

## Decisão

Implementar dois endpoints de importação em lote (somente admin):

- `POST /api/v1/admin/bulk/users` — cria usuários em lote
- `POST /api/v1/admin/bulk/teams` — cria equipes em lote

Ambos recebem um arquivo CSV via `multipart/form-data` (campo `file`). O separador é ponto-e-vírgula (`;`) para compatibilidade com planilhas brasileiras (Excel/LibreOffice usam `;` por padrão no locale pt-BR).

**Formato usuários:** `nome_completo;email;perfil`
**Formato equipes:** `id_competicao;categoria_equipe;nome_equipe;email1;email2;...`

### Estratégia de erros por linha

Cada linha é validada completamente com SELECTs antes de qualquer mutação no banco. Linhas inválidas são acumuladas na lista de erros e o processamento continua. Linhas válidas são inseridas com `db.flush()` imediatamente, tornando-as visíveis para validações de linhas subsequentes (ex: e-mail duplicado dentro do mesmo CSV).

O `get_db` faz o `commit` final de todas as linhas válidas em uma única transação. Se ocorrer uma exceção inesperada no `flush()`, é feito `rollback()` da sessão e o erro é reportado.

### Senhas para usuários importados

Uma senha aleatória é gerada com `secrets.token_urlsafe(9)` (≈12 caracteres base64). Por ora, a senha não é enviada por e-mail — a comunicação fica a cargo do administrador. Um e-mail de boas-vindas pode ser adicionado futuramente.

## Consequências

- Limite de 1 MB por arquivo CSV para proteger o servidor
- Cabeçalho opcional (detectado pela primeira coluna da primeira linha)
- Validações de integridade referencial são feitas via SELECT antes de INSERT, evitando exceções de constraint na maioria dos casos
- Erros são relatados por linha, com identificador (e-mail ou nome da equipe) e motivo legível
