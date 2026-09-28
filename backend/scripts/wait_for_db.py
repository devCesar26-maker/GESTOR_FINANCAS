"""Espera o PostgreSQL ficar disponível antes do migrate no boot.

Usado pelo entrypoint.sh em produção: no Render o serviço sobe às vezes
antes do banco (manutenção/restart do Postgres Free) — sem esta espera o
container entraria em crash-loop e o deploy nunca ficaria "live".

Uso: python scripts/wait_for_db.py [--timeout 60]
"""
import argparse
import os
import sys
import time
from pathlib import Path

# Rodar como `python scripts/wait_for_db.py` coloca scripts/ (e não a raiz
# do backend) no sys.path — o pacote finflow ficaria invisível. Garante a
# raiz (pai de scripts/) no path antes de qualquer import do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finflow.settings")
django.setup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("DB_WAIT_TIMEOUT", "60")),
        help="Segundos máximos de espera (padrão: 60 ou DB_WAIT_TIMEOUT).",
    )
    args = parser.parse_args()

    from django.db import connections
    from django.db.utils import OperationalError

    deadline = time.monotonic() + args.timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            connections["default"].ensure_connection()
            print("Banco disponível.", flush=True)
            return 0
        except OperationalError as exc:
            if time.monotonic() >= deadline:
                print(
                    f"ERRO: banco indisponível após {args.timeout}s: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            print(
                f"[tentativa {attempt}] Banco indisponível, aguardando 2s...",
                flush=True,
            )
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
