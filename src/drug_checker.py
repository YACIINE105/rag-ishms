#!/usr/bin/env python3
import requests
import time
import json

SERVER_URL = "http://localhost:8080/completion"

def query_medgemma(prompt, max_tokens=120, temp=0.1):
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temp,
        "n_gpu_layers": 99,
        "stop": ["<end_of_turn>"]
    }
    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()["content"].strip()
        return f"HTTP {resp.status_code}"
    except Exception as e:
        return f"Error: {str(e)[:100]}"

def check_drug_pair(drug1, drug2):
    prompt = f"<bos><start_of_turn>user\n{drug1} + {drug2} drug interaction.\n\nFormat:\nlevel: [major/moderate/minor]\nrisk: [1 sentence]\n\n<end_of_turn>\n<start_of_turn>model"
    return query_medgemma(prompt)


class Interaction:
    def full_interaction_check(current_meds: list, new_med: str):
        results = []

        for med in current_meds:
            interaction_text = check_drug_pair(med.strip(), new_med)

            level = ""
            risk = ""

            for line in interaction_text.splitlines():
                line = line.strip()
                if line.lower().startswith("level:"):
                    level = line.split(":", 1)[1].strip().strip("[]")
                elif line.lower().startswith("risk:"):
                    risk = line.split(":", 1)[1].strip()

            results.append({
                "drug_pair": f"{new_med} + {med.strip()}",
                "level": level,
                "risk_summary": risk
            })

        return results


if __name__ == "__main__":
    print()
    t = time.time()
    prev = ["warfarin", "metformin"]
    new = "aspirin"

    print(Interaction.full_interaction_check(prev, new))
  
