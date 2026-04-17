"""Inicializa buckets Supabase Storage (idempotente).

Uso:
    python scripts/init_supabase_storage.py

Cria os buckets padrao do imoIA:
- creatives     (privado — criativos M7, via signed URLs)
- brand-assets  (publico — logos de brand kit sao referenciados no portal)
- documents     (privado — documentos de due diligence)
- properties    (privado — fotos de propriedades)

Lanca erro se SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY nao estiverem definidas.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from src.shared.storage_provider import (
    BUCKET_BRAND_ASSETS,
    BUCKET_CREATIVES,
    BUCKET_DOCUMENTS,
    BUCKET_PROPERTIES,
    create_bucket,
    list_buckets,
)


BUCKETS_TO_CREATE = [
    # (bucket_id, public)
    (BUCKET_CREATIVES, False),
    (BUCKET_BRAND_ASSETS, True),   # logos podem ser publicos (uso em portal)
    (BUCKET_DOCUMENTS, False),
    (BUCKET_PROPERTIES, False),
]


def main() -> int:
    print("=== Init Supabase Storage ===\n")
    try:
        existing = {b["id"] for b in list_buckets()}
    except Exception as e:
        print(f"ERRO a listar buckets: {e}")
        return 1
    print(f"Buckets existentes: {sorted(existing) or '(nenhum)'}\n")

    for bucket_id, public in BUCKETS_TO_CREATE:
        if bucket_id in existing:
            print(f"  [skip] {bucket_id:15s} ja existe")
            continue
        try:
            create_bucket(bucket_id, public=public)
            print(f"  [ok]   {bucket_id:15s} criado (public={public})")
        except Exception as e:
            print(f"  [ERRO] {bucket_id:15s} falhou: {e}")
            return 1

    print("\n=== Buckets prontos ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
