"""Run with .venv/bin/python run.py from the project folder."""
if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("ROAM_PORT", "8003")), reload=True, proxy_headers=False, limit_concurrency=64, timeout_keep_alive=5)
