from __future__ import annotations

import json

from app.config import get_settings
from app.corpus import ActiveCorpusRepository
from app.refresh import CorpusRefreshService, new_refresh_run


def main() -> int:
    settings = get_settings()
    result = CorpusRefreshService(ActiveCorpusRepository(), settings).refresh(new_refresh_run())
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
