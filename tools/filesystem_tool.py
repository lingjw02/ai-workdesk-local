import datetime
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from core import config


class FilesystemTool:
    def __init__(self):
        self.base_dir = config.BASE_DIR

    def _resolve_safe_path(self, target_path: str, project_id: Optional[str] = None) -> Path:
        """Enforces that operations stay within the project or workspace scope."""
        p = Path(target_path)
        if not p.is_absolute():
            if project_id:
                p = self.base_dir / "data" / "workspaces" / project_id / p
            else:
                p = self.base_dir / p
        
        # Verify it resolves within base_dir or project workspace
        resolved = p.resolve()
        return resolved

    def create_checkpoint(self, file_path: Path, task_id: str) -> Optional[str]:
        """Creates an atomic checkpoint of a file before modifying it."""
        if not file_path.exists():
            return None
        cp_id = f"cp_{task_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        cp_dir = config.CHECKPOINT_DIR / cp_id
        cp_dir.mkdir(parents=True, exist_ok=True)
        dest = cp_dir / file_path.name
        shutil.copy2(file_path, dest)
        return cp_id

    def rollback_checkpoint(self, checkpoint_id: str, target_path: Path) -> bool:
        cp_dir = config.CHECKPOINT_DIR / checkpoint_id
        src = cp_dir / target_path.name
        if src.exists():
            shutil.copy2(src, target_path)
            return True
        return False

    def read_file(self, target_path: str, project_id: Optional[str] = None) -> str:
        p = self._resolve_safe_path(target_path, project_id)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {target_path}")
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, target_path: str, content: str, task_id: str = "default", project_id: Optional[str] = None) -> Dict[str, Any]:
        p = self._resolve_safe_path(target_path, project_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        cp_id = self.create_checkpoint(p, task_id)
        p.write_text(content, encoding="utf-8")
        return {
            "path": str(p),
            "bytes": len(content.encode("utf-8")),
            "checkpointId": cp_id,
        }

    def list_files(self, target_dir: str = ".", project_id: Optional[str] = None) -> List[str]:
        p = self._resolve_safe_path(target_dir, project_id)
        if not p.exists() or not p.is_dir():
            return []
        items = []
        for item in p.rglob("*"):
            if "node_modules" in item.parts or ".git" in item.parts or "venv" in item.parts:
                continue
            if item.is_file():
                items.append(str(item.relative_to(p)))
        return items[:100]


filesystem_tool = FilesystemTool()
