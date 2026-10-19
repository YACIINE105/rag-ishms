"""Measure delivered SSE text latency and end-to-end token throughput."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import requests
from dotenv import dotenv_values


def measure(base_url, key, project, question, generator_url, generator_key):
    started = perf_counter()
    first = None
    fragments = []
    done = False
    event = None
    with requests.post(
        f"{base_url}/api/v1/nlp/index/answer/stream/{project}",
        headers={"X-API-Key": key},
        json={"text": question, "limit": 5},
        stream=True,
        timeout=180,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if event == "error":
                    raise RuntimeError("SSE generation failed")
                if event == "token" and data.get("text"):
                    first = first if first is not None else perf_counter() - started
                    fragments.append(data["text"])
                if event == "done":
                    done = True
    duration = perf_counter() - started
    text = "".join(fragments)
    count_response = requests.post(
        f"{generator_url}/tokenize",
        headers={"Authorization": f"Bearer {generator_key}"},
        json={
            "model": "qwen3-legal-final",
            "prompt": text,
            "add_special_tokens": False,
        },
        timeout=30,
    )
    count_response.raise_for_status()
    count = count_response.json()["count"]
    return dict(
        question=question,
        answer=text,
        done=done,
        first_text_seconds=first,
        duration_seconds=duration,
        output_tokens=count,
        end_to_end_output_tokens_per_second=count / duration,
        delivered_text_events=len(fragments),
        interpretation="Guardrails buffer output; first text is delivered after filtering, not model-internal TTFT.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--project", type=int, default=900102)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    settings = dotenv_values(args.env_file)
    key = next(iter(json.loads(settings["API_CLIENTS"])))
    questions = [
        "What is the age of majority under Article 44?",
        "ما سن الرشد وفق المادة 44؟",
        "What is a lease under Article 558?",
        "كيف تعرف المادة 558 عقد الإيجار؟",
        "What sources apply under Article 1 when legislation is absent?",
        "ما ترتيب مصادر الحكم عند غياب النص التشريعي وفق المادة 1؟",
    ]
    rows = []
    for question in questions:
        rows.append(
            measure(
                args.base_url,
                key,
                args.project,
                question,
                settings["GENERATION_BASE_URL"].removesuffix("/v1"),
                settings["GENERATION_API_KEY"],
            )
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        print(f"Measured streaming {len(rows)}/{len(questions)}", flush=True)


if __name__ == "__main__":
    main()
