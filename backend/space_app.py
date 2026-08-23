# space_app.py - Gradio wrapper for Hugging Face Spaces

import os
import sys
import subprocess
import gradio as gr
import threading
import uvicorn
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app, agent
from db import get_conn

server_running = False

def start_fastapi():
    global server_running
    if not server_running:
        print("Starting FastAPI server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
        server_running = True

thread = threading.Thread(target=start_fastapi, daemon=True)
thread.start()
time.sleep(2)
print("FastAPI server started on port 8000")

def run_batch():
    try:
        print("Running agent batch...")
        results = agent.run_batch()
        total = sum(r["amount_recovered"] for r in results)
        print(f"Batch complete. Processed {len(results)} transactions. Recovered: {total}")
        return f"Processed {len(results)} transactions\nTotal recovered: {total:.2f}"
    except Exception as e:
        print(f"Error running batch: {str(e)}")
        return f"Error: {str(e)}"

def get_dashboard():
    try:
        conn = get_conn()
        total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions").fetchone()[0]
        recovered = conn.execute(
            "SELECT COALESCE(SUM(amount_recovered),0) FROM audit_log WHERE outcome='success'"
        ).fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='resolved'").fetchone()[0]
        escalated = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='escalated'").fetchone()[0]
        conn.close()
        
        rate = round((recovered/total)*100, 1) if total else 0
        
        return f"""## Revenue Recovery Dashboard

| Metric | Value |
|--------|-------|
| Total at risk | {total:,.2f} |
| Recovered | {recovered:,.2f} |
| Recovery rate | {rate}% |
| Resolved | {resolved} |
| Escalated | {escalated} |
| Pending | {pending} |"""
    except Exception as e:
        print(f"Error loading stats: {str(e)}")
        return f"Error loading stats: {str(e)}"

with gr.Blocks(title="Revenue Recovery Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Revenue Recovery Agent")
    gr.Markdown("AI-powered agent that recovers revenue from failed payments, abandoned checkouts, and overdue invoices.")
    
    with gr.Row():
        with gr.Column():
            dashboard_btn = gr.Button("Refresh Dashboard", variant="secondary")
            dashboard_output = gr.Markdown("Click refresh to load stats")
    
    with gr.Row():
        with gr.Column():
            run_btn = gr.Button("Run Agent Batch", variant="primary")
            run_output = gr.Textbox(label="Results", lines=5)
    
    dashboard_btn.click(get_dashboard, outputs=dashboard_output)
    run_btn.click(run_batch, outputs=run_output)
    
    demo.load(get_dashboard, outputs=dashboard_output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)