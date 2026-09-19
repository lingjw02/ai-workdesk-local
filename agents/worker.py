import asyncio
import datetime
import logging
import re
import time
from typing import Dict, Any, List, Optional
from core.models import WorkerProfile, PermissionLevel
from core.router import model_router
from core.event_bus import event_bus
from tools.web_tool import web_tool
from tools.filesystem_tool import filesystem_tool
from tools.terminal_tool import terminal_tool
from tools.permission_gate import permission_gate
from memory.memory_manager import memory_manager
from agents.registry import registry

logger = logging.getLogger("WorkerEngine")


def parse_code_blocks(text: str) -> Dict[str, str]:
    """Extracts files tagged with '# FILE: name' or '// FILE: name'."""
    files: Dict[str, str] = {}
    pattern = r"```[a-zA-Z0-9_+-]*\n([\s\S]*?)```"
    matches = re.finditer(pattern, text)
    idx = 0
    for m in matches:
        idx += 1
        block = m.group(1)
        lines = block.split("\n", 1)
        first_line = lines[0] if lines else ""
        rest = lines[1] if len(lines) > 1 else ""
        fm = re.search(r"(?://|#|--)\s*FILE:\s*(.+)", first_line, re.IGNORECASE)
        if fm:
            filename = fm.group(1).strip()
            files[filename] = rest
        else:
            files[f"code_snippet_{idx}.txt"] = block
    if not files and text.strip():
        files["output.txt"] = text.strip()
    return files


class WorkerRunner:
    def __init__(self, profile: WorkerProfile):
        self.profile = profile

    def _build_system_prompt(self, project_culture: Optional[Dict[str, Any]] = None) -> str:
        culture_str = ""
        if project_culture:
            conventions = project_culture.get("conventions", [])
            avoidances = project_culture.get("avoidances", [])
            culture_str = f"\nPROJECT CONVENTIONS:\n" + "\n".join(f"- {c}" for c in conventions)
            if avoidances:
                culture_str += f"\nPROJECT AVOIDANCES:\n" + "\n".join(f"- {a}" for a in avoidances)

        p = self.profile.personality
        prompt = f"""You are {self.profile.name} ({self.profile.avatar}), a {self.profile.description}.
TEMPERAMENT: {p.temperament}
COMMUNICATION STYLE: {p.communicationStyle}
RULES:
{chr(10).join('- ' + r for r in p.behaviorRules)}
OOC BOUNDARIES:
{chr(10).join('- ' + r for r in p.oocRules)}
{culture_str}
"""
        return prompt

    async def execute(
        self,
        instruction: str,
        task_id: str,
        project_id: Optional[str] = None,
        context: Optional[str] = None,
        project_culture: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        worker_id = self.profile.id
        logger.info(f"Worker [{worker_id}] starting task {task_id}")

        await event_bus.broadcast("worker_status_changed", {
            "workerId": worker_id,
            "status": "working",
            "taskId": task_id,
            "activity": f"Executing: {instruction[:60]}...",
        })

        system = self._build_system_prompt(project_culture)
        user_content = f"Task Instruction:\n{instruction}"
        if context:
            user_content = f"Context from previous work:\n{context}\n\n{user_content}"

        deliverables: Dict[str, Any] = {}
        notes: str = ""
        success: bool = True

        try:
            if worker_id == "researcher":
                # Web search tool execution with Permission Level 0 (Automatic)
                search_results = await web_tool.search(instruction, count=5)
                search_block = web_tool.format_search_results(search_results, instruction)
                full_prompt = f"{search_block}\n\n{user_content}\n\nDeliverable: Produce clear findings with key takeaways and cited sources."
                
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": full_prompt}],
                    system=system,
                    deepthink="normal",
                )
                deliverables["research_notes.md"] = raw
                notes = raw

            elif worker_id == "coder":
                # Check permission before writing code or running builds
                existing_files = filesystem_tool.list_files(project_id=project_id)
                files_context = f"Existing files in workspace: {existing_files}\n"
                full_prompt = f"{files_context}\n{user_content}\n\nProduce complete, runnable code files. The first line of each code block MUST be '# FILE: filename.ext' or '// FILE: filename.ext'."
                
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": full_prompt}],
                    system=system,
                    model=model_router.get_model_for_role("coder", complexity="complex"),
                    deepthink="normal",
                )
                code_files = parse_code_blocks(raw)
                
                # Write code files with Level 1 (Notify) permission check
                for filename, code in code_files.items():
                    allowed = await permission_gate.evaluate_and_request(
                        worker_id=worker_id,
                        tool="filesystem",
                        action="write_file",
                        params={"path": filename, "bytes": len(code)},
                        required_level=PermissionLevel.NOTIFY,
                        max_autonomy_level=self.profile.permissions.maxAutonomyLevel,
                        project_id=project_id,
                        task_id=task_id,
                    )
                    if allowed:
                        filesystem_tool.write_file(filename, code, task_id=task_id, project_id=project_id)
                
                deliverables.update(code_files)
                notes = f"Generated/Updated {len(code_files)} files: {', '.join(code_files.keys())}"

            elif worker_id == "documenter":
                full_prompt = f"{user_content}\n\nDeliverable: Provide polished, comprehensive documentation in clean Markdown."
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": full_prompt}],
                    system=system,
                    deepthink="normal",
                )
                deliverables["project_document.md"] = raw
                notes = "Document draft updated."

            elif worker_id == "data_analyst":
                full_prompt = f"{user_content}\n\nDeliverable: Detailed quantitative data analysis, statistics, and trends."
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": full_prompt}],
                    system=system,
                    deepthink="normal",
                )
                deliverables["data_analysis_report.md"] = raw
                notes = "Data analysis generated."

            elif worker_id == "file_manager":
                files = filesystem_tool.list_files(project_id=project_id)
                tree_str = "\n".join(f"- {f}" for f in files) if files else "No files yet."
                deliverables["file_manifest.txt"] = f"Current Workspace Tree:\n{tree_str}"
                notes = f"Audited file tree: {len(files)} files present."

            elif worker_id == "worker_creator":
                # Meta-worker that creates another worker profile
                full_prompt = f"{user_content}\n\nDesign a complete WorkerProfile JSON adhering to schema."
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": full_prompt}],
                    system=system,
                    deepthink="normal",
                )
                deliverables["new_worker_spec.json"] = raw
                notes = "New worker design synthesized."

            else:
                # Generic custom worker runner
                raw = await model_router.call_openrouter(
                    messages=[{"role": "user", "content": user_content}],
                    system=system,
                    deepthink="normal",
                )
                deliverables[f"{worker_id}_output.md"] = raw
                notes = f"{self.profile.name} completed work."

        except Exception as e:
            logger.error(f"Worker {worker_id} encountered an error: {e}")
            success = False
            notes = f"Error: {e}"
            deliverables["error.txt"] = str(e)

        duration = time.time() - start_time
        memory_manager.record_worker_experience(
            worker_id=worker_id,
            task_id=task_id,
            success=success,
            duration_sec=duration,
            notes=notes[:120],
        )

        final_status = "completed" if success else "error"
        await event_bus.broadcast("worker_status_changed", {
            "workerId": worker_id,
            "status": final_status,
            "taskId": task_id,
            "activity": notes[:80],
            "durationSec": round(duration, 2),
        })

        return {
            "workerId": worker_id,
            "success": success,
            "deliverables": deliverables,
            "summary": notes,
            "durationSec": duration,
        }
