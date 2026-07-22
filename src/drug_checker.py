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
    # نستخدم الأقواس المزدوجة {{ }} داخل الـ f-string لتمثيل أقواس الـ JSON 
    # حتى لا تتعارض مع متغيرات البايثون {drug1} و {drug2}
    prompt = f"""<bos><start_of_turn>user
Evaluate the clinical drug interaction between {drug1} and {drug2}.

You MUST respond ONLY with a valid JSON object. Do not add any conversational text, explanations, or markdown formatting (like ```json).
Use exactly this format:
{{
  "level": "high/minor/none",
  "risk_summary": "Provide a 1-sentence explanation, or write 'No significant interaction' if safe."
}}
<end_of_turn>
<start_of_turn>model"""
    
    return query_medgemma(prompt)


class Interaction:
    @staticmethod
    def full_interaction_check(current_meds: list, new_med: str):
        results = []

        for med in current_meds:
            interaction_text = check_drug_pair(med.strip(), new_med)
            
            level = ""
            risk = ""

            clean_text = interaction_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            clean_text = clean_text.strip()

     
            try:
                data = json.loads(clean_text)
                level = data.get("level", "")
                risk = data.get("risk_summary", "")
            except json.JSONDecodeError:
              
                level = "Error"
                risk = f"Failed to parse JSON. Raw output: {interaction_text}"

            results.append({
                "drug_pair": f"{new_med} + {med.strip()}",
                "level": level,
                "risk_summary": risk
            })

        return results


if __name__ == "__main__":
    print()
    t = time.time()
    prev = ["Nebulized bronchodilators, controlled oxygen, steroids, and sputum culture.", "metformin"]
    new = "Tiotropium inhaler"

    print(Interaction.full_interaction_check(prev, new))
  
