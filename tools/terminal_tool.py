import asyncio
import logging
import shlex
from typing import Dict, Any, Optional
from core import config

logger = logging.getLogger("TerminalTool")

BLOCKED_COMMAND_PATTERNS = [
    "format",
    "del /f /s /q c:",
    "rmdir /s /q c:",
    "rm -rf /",
    ":(){ :|:& };:",
    "drop database",
    "powershell -encodedcommand",
]


class TerminalTool:
    def __init__(self):
        self.default_cwd = config.BASE_DIR

    async def execute_command(self, command: str, cwd: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
        """Executes a terminal command safely within a designated working directory."""
        lowered = command.lower().strip()
        for blocked in BLOCKED_COMMAND_PATTERNS:
            if blocked in lowered:
                raise PermissionError(f"Security Alert: Command contains forbidden instruction '{blocked}'")

        work_dir = cwd or str(self.default_cwd)
        logger.info(f"Terminal executing: {command} in {work_dir}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                stdout = stdout_data.decode("utf-8", errors="replace")
                stderr = stderr_data.decode("utf-8", errors="replace")
                return {
                    "command": command,
                    "exitCode": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": proc.returncode == 0,
                }
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "command": command,
                    "exitCode": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout} seconds.",
                    "success": False,
                }
        except Exception as e:
            return {
                "command": command,
                "exitCode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }


terminal_tool = TerminalTool()
