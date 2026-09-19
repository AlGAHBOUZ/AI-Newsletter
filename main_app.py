"""
Gradio interface for AI Weekly Digest.

Replaces the Flask app entirely for HF Spaces deployment.
Gradio runs natively on HF Spaces (no Docker needed, completely free).

The pipeline logic is unchanged — same pipeline.py, same daily cache,
same email delivery. Only the UI layer changes: Gradio instead of Flask.
"""

import re
import gradio as gr
from pipeline import run_and_deliver

DESCRIPTION = """
# 🤖 AI Weekly Digest

**Stay sharp on AI. Without the noise.**

Every week we scan hundreds of posts, papers, and videos across OpenAI, Anthropic,
Google AI, Hacker News, and YouTube — then distill it into a concise, high-signal
digest you can read in under 10 minutes.

Each item is AI-summarized, scored for relevance (1–10), and organized into sections:
**Major Releases · Research · AI Tools · Tutorials · Industry News · Builder's Corner**

Enter your email below and get this week's digest sent to your inbox immediately.
"""

SOURCES = """
### 📡 Sources monitored
`OpenAI Blog` · `Anthropic News` · `Google AI Blog` · `Hacker News` · `YouTube (AllAboutAI, mreflow, Two Minute Papers)`
"""


def submit(email: str) -> str:
    email = (email or "").strip().lower()

    # Validate
    if not email:
        return "⚠️ Please enter your email address."
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return "⚠️ That doesn't look like a valid email address."

    result = run_and_deliver(to_email=email)

    if result["ok"]:
        cached = " (today's digest was already cached — delivered instantly)" if result.get("cached") else ""
        return (
            f"✅ **Sent!** Check your inbox at **{email}**.\n\n"
            f"This week's digest contains **{result['articles']} articles** across AI news, "
            f"research, tools, and more.{cached}\n\n"
            f"*(Check your spam folder if it doesn't arrive within a minute.)*"
        )
    else:
        return f"❌ Something went wrong: {result['error']}\n\nPlease try again in a few minutes."


with gr.Blocks(
    title="AI Weekly Digest",
    theme=gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="purple",
        neutral_hue="slate",
    ),
    css="""
    .main-container { max-width: 680px; margin: 0 auto; }
    .submit-btn { background: linear-gradient(135deg, #6366f1, #8b5cf6) !important; }
    """
) as demo:

    with gr.Column(elem_classes="main-container"):
        gr.Markdown(DESCRIPTION)
        gr.Markdown(SOURCES)

        with gr.Row():
            email_input = gr.Textbox(
                label="Your email address",
                placeholder="you@example.com",
                scale=4,
            )
            submit_btn = gr.Button(
                "Send me this week's digest →",
                variant="primary",
                scale=1,
                elem_classes="submit-btn",
            )

        status_output = gr.Markdown(visible=False)

        gr.Markdown(
            "_Free. No account needed. One email with this week's AI news, sent immediately._",
        )

    def on_submit(email):
        result = submit(email)
        return gr.Markdown(value=result, visible=True)

    submit_btn.click(
        fn=on_submit,
        inputs=[email_input],
        outputs=[status_output],
    )
    email_input.submit(
        fn=on_submit,
        inputs=[email_input],
        outputs=[status_output],
    )


if __name__ == "__main__":
    demo.launch()
