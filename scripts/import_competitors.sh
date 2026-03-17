#!/usr/bin/env bash
# =============================================================================
# import_competitors.sh — Importa competidores em lote via API do Tempus
#
# Uso:
#   ./scripts/import_competitors.sh [ARQUIVO_CSV] [OPCOES]
#
# O arquivo CSV deve ter o cabeçalho:
#   full_name,email,password
#
# Opções:
#   -u, --api-url URL     URL base da API  (padrão: http://127.0.0.1:8000)
#   -a, --admin-email E   E-mail do admin  (padrão: admin@example.com)
#   -p, --admin-pass P    Senha do admin   (obrigatório, ou usar ADMIN_PASSWORD)
#   -h, --help            Exibe esta ajuda
#
# Exemplos:
#   ./scripts/import_competitors.sh competidores.csv -p "minha_senha"
#   ADMIN_PASSWORD=senha ./scripts/import_competitors.sh competidores.csv
#   ./scripts/import_competitors.sh competidores.csv \
#       --api-url http://meu-servidor:8000 \
#       --admin-email operador@example.com \
#       --admin-pass senha123
#
# Formato do CSV (sem espaços extras ao redor das vírgulas):
#   full_name,email,password
#   João Silva,joao@example.com,senha123
#   "Maria Souza",maria@example.com,outra_senha
# =============================================================================

set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Defaults ──────────────────────────────────────────────────────────────────
API_URL="http://127.0.0.1:8000"
ADMIN_EMAIL="teammianti@gmail.com"
ADMIN_PASSWORD="IP9o&5SocqgHZu7HO!u2"
CSV_FILE=""

# ── Ajuda ─────────────────────────────────────────────────────────────────────
usage() {
    sed -n '2,30p' "$0" | sed 's/^# \?//'
    exit 0
}

# ── Parse de argumentos ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -u|--api-url)   API_URL="$2";      shift 2 ;;
        -a|--admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
        -p|--admin-pass)  ADMIN_PASSWORD="$2"; shift 2 ;;
        -*)
            echo -e "${RED}Opção desconhecida: $1${RESET}" >&2
            exit 1
            ;;
        *)
            if [[ -z "$CSV_FILE" ]]; then
                CSV_FILE="$1"
                shift
            else
                echo -e "${RED}Argumento inesperado: $1${RESET}" >&2
                exit 1
            fi
            ;;
    esac
done

# ── Validações iniciais ───────────────────────────────────────────────────────
if [[ -z "$CSV_FILE" ]]; then
    echo -e "${RED}Erro: informe o arquivo CSV como primeiro argumento.${RESET}" >&2
    echo "Use --help para ver as opções." >&2
    exit 1
fi

if [[ ! -f "$CSV_FILE" ]]; then
    echo -e "${RED}Erro: arquivo '$CSV_FILE' não encontrado.${RESET}" >&2
    exit 1
fi

if [[ -z "$ADMIN_PASSWORD" ]]; then
    echo -e "${YELLOW}Senha do admin não informada via -p ou ADMIN_PASSWORD.${RESET}"
    read -rsp "Senha do admin ($ADMIN_EMAIL): " ADMIN_PASSWORD
    echo
fi

for cmd in curl jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo -e "${RED}Erro: '$cmd' não está instalado. Instale e tente novamente.${RESET}" >&2
        exit 1
    fi
done

# ── Login e obtenção do cookie de sessão ──────────────────────────────────────
echo -e "\n${BOLD}==> Autenticando como $ADMIN_EMAIL em $API_URL${RESET}"

COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

LOGIN_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
    -c "$COOKIE_JAR" \
    -X POST "$API_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": $(jq -Rn --arg v "$ADMIN_EMAIL" '$v'), \"password\": $(jq -Rn --arg v "$ADMIN_PASSWORD" '$v')}")

if [[ "$LOGIN_HTTP" != "200" ]]; then
    echo -e "${RED}Falha no login (HTTP $LOGIN_HTTP). Verifique e-mail e senha.${RESET}" >&2
    exit 1
fi

echo -e "${GREEN}Login realizado com sucesso.${RESET}"

# ── Processamento do CSV ──────────────────────────────────────────────────────
# Remove BOM (UTF-8 com BOM de Excel) e normaliza quebras de linha Windows
CLEAN_CSV=$(sed 's/\r//' "$CSV_FILE" | sed 's/^\xEF\xBB\xBF//')

# Valida cabeçalho
HEADER=$(echo "$CLEAN_CSV" | head -1)
if [[ "$HEADER" != "full_name,email,password" ]]; then
    echo -e "${RED}Erro: cabeçalho inválido. Esperado: full_name,email,password${RESET}" >&2
    echo -e "       Encontrado: $HEADER" >&2
    exit 1
fi

TOTAL=$(echo "$CLEAN_CSV" | tail -n +2 | grep -c '[^[:space:]]' || true)
echo -e "\n${BOLD}==> Importando $TOTAL competidor(es)...${RESET}\n"

COUNT_OK=0
COUNT_SKIP=0
COUNT_ERR=0
ERRORS=()

# Lê CSV linha por linha (suporta campos entre aspas)
while IFS= read -r line; do
    # Pula linhas em branco
    [[ -z "${line// }" ]] && continue

    # Parse de campos com suporte a aspas (usando python como parser CSV confiável)
    read -r full_name email password < <(python3 -c "
import csv, sys
row = next(csv.reader([sys.stdin.readline()]))
print('\t'.join(row))
" <<< "$line" | tr '\t' '\n' | {
        read -r fn; read -r em; read -r pw
        printf '%s\t%s\t%s' "$fn" "$em" "$pw"
    } | awk -F'\t' '{print $1; print $2; print $3}') || true

    if [[ -z "$full_name" || -z "$email" || -z "$password" ]]; then
        COUNT_ERR=$((COUNT_ERR + 1))
        ERRORS+=("LINHA INVÁLIDA: '$line'")
        echo -e "  ${RED}✗${RESET} Linha ignorada (campos vazios): $line"
        continue
    fi

    # Chamada à API
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -b "$COOKIE_JAR" \
        -X POST "$API_URL/api/v1/users" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
            --arg n "$full_name" \
            --arg e "$email" \
            --arg p "$password" \
            '{full_name: $n, email: $e, password: $p, role: "competitor"}')")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    case "$HTTP_CODE" in
        201)
            USER_ID=$(echo "$BODY" | jq -r '.id // "?"')
            echo -e "  ${GREEN}✓${RESET} [#$USER_ID] $full_name <$email>"
            COUNT_OK=$((COUNT_OK + 1))
            ;;
        409)
            echo -e "  ${YELLOW}~${RESET} Já existe: $email (ignorado)"
            COUNT_SKIP=$((COUNT_SKIP + 1))
            ;;
        *)
            DETAIL=$(echo "$BODY" | jq -r '.detail // "erro desconhecido"' 2>/dev/null || echo "$BODY")
            echo -e "  ${RED}✗${RESET} Falha [$HTTP_CODE] $email — $DETAIL"
            COUNT_ERR=$((COUNT_ERR + 1))
            ERRORS+=("[$HTTP_CODE] $email — $DETAIL")
            ;;
    esac

done < <(echo "$CLEAN_CSV" | tail -n +2)

# ── Resumo ────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}═══════════════════════════════${RESET}"
echo -e "${BOLD}  Resumo da importação${RESET}"
echo -e "${BOLD}═══════════════════════════════${RESET}"
echo -e "  ${GREEN}Criados:  $COUNT_OK${RESET}"
echo -e "  ${YELLOW}Existentes (ignorados): $COUNT_SKIP${RESET}"
echo -e "  ${RED}Erros:    $COUNT_ERR${RESET}"

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo -e "\n${RED}Detalhes dos erros:${RESET}"
    for err in "${ERRORS[@]}"; do
        echo -e "  • $err"
    done
fi

echo ""

[[ $COUNT_ERR -gt 0 ]] && exit 1 || exit 0
