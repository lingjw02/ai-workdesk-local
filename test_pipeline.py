import httpx
import json

def test_pipeline():
    client = httpx.Client(base_url="http://127.0.0.1:3787", timeout=120.0)
    
    # 1. Create project
    proj = client.post("/api/projects", json={
        "name": "Python 3.13 Feature Demo",
        "workers": ["researcher", "coder", "documenter"]
    }).json()
    project_id = proj["id"]
    print(f"[1] Created Workspace: {project_id} - {proj['name']}")

    # 2. Dispatch task with clarification answered
    print("[2] Dispatching goal to Main Brain and Lifetime PM (with clear scope)...")
    res = client.post(f"/api/projects/{project_id}/task", json={
        "text": "Research top 3 features of Python 3.13 and write a demo script showcasing them",
        "clarificationResponse": "Focus on free-threaded GIL-free execution, JIT compiler, and enhanced tracebacks. Deliver runnable code."
    }).json()

    print("[3] Task Execution Completed:")
    print("    Status:", res.get("status"))
    print("    PM Plan:", res.get("pmPlan"))
    print("    Deliverables Produced:", list(res.get("deliverables", {}).keys()))
    print("    QA-2 Result:", res.get("qa2Report", {}).get("result"))
    print("    QA-2 Score:", res.get("qa2Report", {}).get("score"))

if __name__ == "__main__":
    test_pipeline()
