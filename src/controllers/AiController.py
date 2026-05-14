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


# ─────────────────────────────────────────────
# Drug interaction checker
# ─────────────────────────────────────────────
def check_drug_pair(drug1, drug2):
    prompt = (
        f"<bos><start_of_turn>user\n"
        f"{drug1} + {drug2} drug interaction.\n\n"
        f"Format:\nlevel: [major/moderate/minor]\nrisk: [1 sentence]\n\n"
        f"<end_of_turn>\n<start_of_turn>model"
    )
    return query_medgemma(prompt)


class Interaction:
    def __init__(self):
        pass

    def full_interaction_check(self, current_meds: list, new_med: str):
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


# ─────────────────────────────────────────────
# ISBAR generator
# ─────────────────────────────────────────────
class ISBAR_GEN:

    def _build_prompt(self, identification: str, background: str) -> str:
        return (
            "<bos><start_of_turn>user\n"
            "You are a clinical ISBAR documentation assistant.\n"
            "Generate ONLY a JSON object with exactly these 3 keys:\n\n"

            # ── Tell the model EXACTLY what each field must contain ──
            "\"situation\":      The CURRENT clinical concern only — "
            "include patient name/bed, their active status "
            "(Stable/Unstable/Critical), and their NEWS score. "
            "Do NOT include history or medications here.\n\n"

            "\"assessment\":     The vital signs and clinical severity ONLY — "
            "include HR, BP, O2 Sat, Temp, and one sentence stating "
            "the severity level implied by these vitals. "
            "Do NOT repeat background info here.\n\n"

            "\"recommendation\": A concrete clinical action — e.g. ICU admission, "
            "increase monitoring, start IV medication, or prepare for discharge. "
            "Base it on the NEWS score and status. Be specific.\n\n"

            # ── Patient data ──
            f"Identity: {identification}\n"
            f"Background: {background}\n\n"

            # ── Output rules  ──
            "Rules:\n"
            "- situation   = WHO + current STATUS + NEWS score\n"
            "- assessment  = VITALS + severity sentence\n"
            "- recommendation = ACTION based on urgency\n"
            "- No markdown, no extra text, valid JSON only.\n"
            "<end_of_turn>\n"
            "<start_of_turn>model"
        )

    def _parse_response(self, raw: str) -> dict:
        """
        3-level fallback parser:
          1. Direct json.loads
          2. Strip ```json ... ``` fences then parse
          3. Regex-extract first {...} block
          4. Return raw text as fallback
        """
        import re

        # Level 1 — direct
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Level 2 — strip markdown fences
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.DOTALL)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Level 3 — grab first { ... } block
        match = re.search(r"\{.*?\}", stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Fallback
        return {"raw_output": raw}

    def isbar_gen(self, identification: str, background: str) -> dict:
        """
        Generate Situation, Assessment, Recommendation from Identity + Background.

        Args:
            identification : The I section — nurse name, department, patient ID/bed
            background     : The B section — age, admission reason, history, medications

        Returns:
            {
                "situation":      "...",
                "assessment":     "...",
                "recommendation": "..."
            }
        """
        prompt = self._build_prompt(identification, background)
        raw    = query_medgemma(prompt, max_tokens=300, temp=0.1)
        return self._parse_response(raw)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":

    # ── Drug interaction check ───────────────
    t    = time.time()
    prev = ["warfarin", "metformin"]
    new  = "aspirin"

    interaction = Interaction()
    interaction_results = interaction.full_interaction_check(prev, new)
    print("=== Drug Interactions ===")
    print(json.dumps(interaction_results, indent=2))

    # ── ISBAR generation ─────────────────────
    isbar = ISBAR_GEN()
    result = isbar.isbar_gen(
        identification="This is Nurse Yusuf calling from the Neurology department about Patient_1 (Bed 1).",
        background=(
            "Patient is 32 years old admitted for Fracture of the Hip. "
            "History: Chronic Kidney Disease Stage 5 on dialysis. "
            "Previous Medications: Fluticasone/Salmeterol 250/50. "
            "NEWS Score: 7. Status: Critical."
        )
    )
    print("\n=== ISBAR Generation ===")
    print(json.dumps(result, indent=2))

    print(f"\nTotal time: {time.time() - t:.2f}s")
    
    