"""gimbal_collector/renderers/json_renderer.py

把 RunReport 序列化成 JSON 文件。
- 文件名：run-{run_id}.json
- 输出位置：output_dir
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from ..report_data import RunReport

logger = logging.getLogger(__name__)


class JsonRenderer:
    name = "json"

    def render(self, report: RunReport, output_dir: Path) -> List[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"run-{report.run_id or 'unknown'}.json"
        path = output_dir / filename
        try:
            payload = json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            path.write_text(payload, encoding="utf-8")
        except (TypeError, ValueError) as e:
            logger.exception("[JsonRenderer] serialize failed: %s", e)
            raise
        logger.info("[JsonRenderer] wrote %s", path)
        return [path]
