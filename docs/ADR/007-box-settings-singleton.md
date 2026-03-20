# ADR-007 — BoxSettings: padrão singleton para configurações do Box

**Status:** Aceito
**Data:** 2026-03-19

---

## Contexto

O sistema Tempus é operado por um único Box (Centro de Treinamento). É necessário armazenar o nome, endereço, site, Instagram e logotipo do Box para exibição na interface (página inicial, ranking, relatórios PDF).

## Decisão

Criar a tabela `box_settings` com um único registro (padrão singleton com `id = 1`). O upsert é feito via `AsyncSession.merge()`, que insere se o registro não existe ou atualiza se já existe.

O logotipo é armazenado como `BLOB` (`LargeBinary` no SQLAlchemy) diretamente no banco de dados, com o `mime_type` armazenado em coluna separada. O endpoint `GET /api/v1/admin/settings` nunca expõe os bytes do logotipo — apenas o campo `has_logo: bool`. O logotipo é servido via endpoint binário dedicado `GET /api/v1/admin/settings/logo` sem autenticação (público), pois aparece em páginas de ranking acessíveis sem login.

## Consequências

- Simplicidade: sem necessidade de sistema de arquivos externo ou bucket S3 para armazenar o logotipo
- Limitação: imagens grandes aumentam o tamanho do banco de dados; limite de 5 MB é imposto no upload
- A ausência do registro (`None`) é tratada graciosamente como defaults vazios — a UI não exibe erros se as configurações não tiverem sido configuradas

## Alternativas Consideradas

- **Armazenamento em arquivo**: requer configuração de diretório e lógica de caminho; mais complexo para Docker
- **Múltiplos registros**: não faz sentido para um único Box; complexidade desnecessária
