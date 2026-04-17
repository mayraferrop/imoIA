"""Migra criativos existentes do filesystem para Supabase Storage.

Varre `storage/creatives/{tenant_id}/` e para cada ficheiro:
1. Faz upload para bucket `creatives` em `tenants/{tenant_id}/{filename}`
2. Actualiza Document.file_path de path absoluto para `creatives:tenants/{tid}/{file}`

Idempotente:
- Se o path no Document ja estiver no formato bucket (contem ":" e nao comeca por "/"),
  salta esse document.
- O upload usa upsert=True por omissao do storage_provider.

Uso:
    python scripts/migrate_creatives_to_storage.py [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from src.database.db import get_session
from src.database.models_v2 import Document
from src.shared.storage_provider import BUCKET_CREATIVES, upload_file


CREATIVES_ROOT = Path("storage/creatives")


def main(dry_run: bool = False) -> int:
    print("=== Migracao creativos filesystem -> Supabase Storage ===\n")
    if not CREATIVES_ROOT.exists():
        print(f"Pasta {CREATIVES_ROOT} nao existe — nada a migrar")
        return 0

    migrated = 0
    skipped = 0
    errors = 0

    with get_session() as session:
        # Documentos filesystem: path absoluto (/...) ou relativo (storage/...).
        # Exclui ja migrados (formato "bucket:path" contem ":" sem comecar por "/").
        docs = (
            session.execute(
                select(Document).where(
                    (Document.file_path.like("/%"))
                    | (Document.file_path.like("storage/%"))
                )
            )
            .scalars()
            .all()
        )
        print(f"Documents com file_path filesystem: {len(docs)}\n")

        for doc in docs:
            # Resolve path relativo ao cwd do projecto
            fs_path = Path(doc.file_path)
            if not fs_path.is_absolute():
                fs_path = Path.cwd() / fs_path

            if not fs_path.exists():
                print(f"  [skip] {doc.id[:8]} ficheiro nao existe: {doc.file_path}")
                skipped += 1
                continue

            # Apenas migra criativos — extrai sub-path depois de "storage/creatives/"
            if "storage/creatives/" not in str(fs_path):
                print(f"  [skip] {doc.id[:8]} nao e criativo: {doc.file_path}")
                skipped += 1
                continue
            sub = str(fs_path).split("storage/creatives/", 1)[1]
            rel = Path(sub)

            tenant_id = doc.tenant_id or (
                rel.parts[0] if len(rel.parts) > 1 else "default"
            )
            filename = rel.name
            bucket_path = f"tenants/{tenant_id}/{filename}"

            ext = filename.rsplit(".", 1)[-1].lower()
            mime = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "pdf": "application/pdf",
            }.get(ext, "application/octet-stream")

            if dry_run:
                print(
                    f"  [dry]  {doc.id[:8]} -> {BUCKET_CREATIVES}:{bucket_path} ({mime})"
                )
                migrated += 1
                continue

            try:
                data = fs_path.read_bytes()
                upload_file(BUCKET_CREATIVES, bucket_path, data, mime)
                doc.file_path = f"{BUCKET_CREATIVES}:{bucket_path}"
                session.flush()
                print(
                    f"  [ok]   {doc.id[:8]} -> {BUCKET_CREATIVES}:{bucket_path} "
                    f"({len(data)} bytes)"
                )
                migrated += 1
            except Exception as exc:
                print(f"  [ERRO] {doc.id[:8]} {doc.file_path}: {exc}")
                errors += 1

    print(
        f"\n=== Concluido: migrados={migrated} skipped={skipped} errors={errors} "
        f"(dry_run={dry_run}) ==="
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))
