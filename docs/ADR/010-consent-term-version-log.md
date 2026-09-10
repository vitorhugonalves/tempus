# ADR-010 — Termo de consentimento: log de versões append-only (não singleton)

**Status:** Aceito
**Data:** 2026-09-10

---

## Contexto

`ConsentTerm` foi introduzido como singleton por competição (`unique=True` em
`competition_id`, mesmo padrão de `BoxSettings` — ver ADR-007): upload
substituía o arquivo existente (`upsert`), remoção era `db.delete()` físico.

Uma revisão de branch levantou o problema: `CompetitorRegistration` grava
`consent_term_hash` no momento da inscrição, para provar qual versão do
termo o competidor aceitou. Com o modelo singleton, um reupload do
admin/operador sobrescreve o PDF — o hash gravado numa inscrição antiga
passa a apontar para um arquivo que não existe mais em lugar nenhum, físico
ou lógico. O mesmo vale para "remover" o termo: um `db.delete()` apaga o
único registro, e qualquer inscrição antiga perde de vez a possibilidade de
recuperar o que foi de fato aceito.

Isso importa porque o termo é de natureza legal/LGPD — a rastreabilidade do
que foi aceito precisa sobreviver a uploads e remoções subsequentes.

## Decisão

`ConsentTerm` deixa de ser singleton e passa a ser um **log de versões
append-only** por competição:

- Removido `unique=True` de `competition_id` (mantido `index=True`) —
  múltiplas linhas por competição são esperadas.
- Nova coluna `deleted_at: datetime | None` (soft delete). "Vigente" =
  linha mais recente (`id` DESC) com `deleted_at IS NULL`.
- Upload (`ConsentTermRepository.create_version`, ex-`upsert`) **sempre**
  insere uma linha nova — nunca sobrescreve `file_data` de uma linha
  existente.
- Remoção (`ConsentTermRepository.soft_delete`, ex-`delete`) apenas seta
  `deleted_at` — a linha e os bytes do PDF nunca são removidos do banco.
  Torna a competição sem exigência de aceite para *novas* inscrições, sem
  apagar histórico.
- `get_by_competition_id` (único ponto de leitura usado por todo o resto do
  código) filtra `deleted_at IS NULL`, ordena por `id DESC`, `LIMIT 1` — a
  correção de "qual é o termo vigente" fica centralizada aqui; nenhum outro
  call site precisou mudar.

## Consequências

- Um `consent_term_hash` gravado numa `CompetitorRegistration` sempre
  corresponde a uma linha recuperável em `consent_terms`, para sempre —
  mesmo depois de N reuploads ou de o termo ter sido removido.
- `consent_terms` cresce sem limite de linhas por competição (uma por
  upload). Aceitável: PDFs de termo são raros de trocar (não é um dado de
  alta frequência) e cada linha é, na pior das hipóteses, o limite de
  upload já existente de 10 MB.
- `file_data` (LargeBinary, potencialmente grande) tem `deferred=True` — não
  é carregado por padrão em nenhuma query, inclusive nas de listagem/consulta
  do histórico; só é lido explicitamente onde os bytes são de fato
  necessários (rota de download do PDF).
- `Competition.consent_term` (relacionamento escalar, `uselist=False`) virou
  `Competition.consent_terms` (lista) — com múltiplas linhas possíveis por
  competição, o relacionamento escalar arriscava `MultipleResultsFound`/
  comportamento ambíguo se algum dia fosse carregado via ORM (ex.: cascade
  de `db.delete(competition)`). Nenhum código hoje lê esse relacionamento
  diretamente (confirmado por grep) — mudança segura, sem efeito em schemas
  Pydantic ou frontend.
- A migration `20260910_consent_term` foi editada diretamente em vez de
  receber uma migration nova em cima, porque nunca havia sido aplicada fora
  de bancos de desenvolvimento/teste descartáveis desta mesma sessão de
  trabalho (nunca mesclada em `develop`/`main`, nunca implantada). Não se
  enquadra na regra de "nunca altere migrações já aplicadas" do CLAUDE.md,
  que protege contra alterar o histórico de bancos compartilhados/produção.

## Alternativas Consideradas

- **Manter singleton, guardar apenas o hash de versões antigas (sem os
  bytes)**: mais simples, mas não atende ao requisito de produto — uma
  inscrição antiga precisa de um PDF *recuperável*, não só de um hash para
  comparação.
- **Arquivar versões antigas fora do banco (ex.: bucket de arquivos)**:
  adiciona uma dependência de infraestrutura nova (mesmo argumento contra
  armazenamento em arquivo já registrado no ADR-007 para o logotipo do Box)
  para um volume de dados pequeno; não compensa neste estágio do projeto.
