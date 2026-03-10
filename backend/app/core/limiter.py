"""Instância central do rate limiter (RNF-06).

Importar este módulo em vez de criar novas instâncias de Limiter,
para que a flag `enabled` seja compartilhada em toda a aplicação.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
