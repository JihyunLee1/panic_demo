from langchain_openai import OpenAI
import json
import torch
import re
import requests
import pdb


class GeminiSafer:
    """Wrapper around the Gemini model that sanitizes counselor utterances."""
    def __init__(self, config: dict, logger):
        self.model = config["gemini_model_name"]     # e.g., "gemini-pro"
        self.api_key = config["gemini_api_key"]
        self.logger = logger

    def get_prompt(self, history, system):
        prompt = (
            "You are a smart and attentive supervisor overseeing a conversation "
            "between a trainee counselor and a client experiencing a panic attack.\n"
            "Your task is to *lightly* review the counselor's latest utterance in the context of the recent dialogue, "
            "following Psychological First Aid (PFA) principles:\n"
            "  1) Ensure immediate safety\n"
            "  2) Support stabilization\n"
            "  3) When appropriate, guide the client to a qualified in-person counselor\n"
            "\n"
            "✅ Preserve the counselor’s original message as much as possible.\n"
            "   • Keep the core information and intent intact.\n"
            "   • Only adjust phrasing to enhance empathy, clarity, and natural flow.\n"
            "   • Fix harmful, irrelevant, or context-mismatched parts if they exist.\n"
            "\n"
            "If the original utterance is already appropriate, return it unchanged.\n"
            "If continuing the conversation seems unhelpful or potentially harmful, reply only with: 상담을 종료합니다.\n"
            "Add *no* explanations or comments—your response will be delivered directly to the client.\n"
            "Keep the response short and easy to understand, as the client is currently in a state of panic.\n"
            "⚠️ Your entire response must be in Korean.\n\n"
            "Conversation History:\n"
        )
        for msg in history:
            prompt += f"{msg['role'].capitalize()}: {msg['message']}\n"
        prompt += f"Counselor: {system}\n"
        prompt += (
            "\nNow review the counselor's utterance. "
            "Return a revised version if needed, the original if appropriate, "
            "or '상담을 종료합니다' if the session should end."
        )
        return prompt

    def run(self, history, system):
        prompt = self.get_prompt(history, system)
        url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }

        try:
            resp = requests.post(f"{url}?key={self.api_key}", headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self.logger.log_and_print("Original response: ", system)
            self.logger.log_and_print(">>> Sanitized response: ", data["candidates"][0]["content"]["parts"][0]["text"])
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            self.logger.log_and_print("Gemini API error:", e, "\nRaw response:", getattr(e, "response", None))
            # 안전한 fallback
            return "상담을 종료합니다"
        


class Agent():
    def __init__(self, demo_config):
        
        self.use_vllm = demo_config.get("use_vllm", False)
        if self.use_vllm:
            model_id=demo_config["model_id"]
            vLLM_server=demo_config["vllm_server"]
            
            self.llm = OpenAI(
                temperature=0.3,
                openai_api_key='EMPTY',
                openai_api_base=vLLM_server,
                max_tokens=128,
                model=model_id
            )
        else:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            model_path = demo_config["model_path"]
            self.llm = AutoModelForCausalLM.from_pretrained(model_path, trust_remote_code=True)
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True
            )
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.llm.eval()
            self.llm.to("cuda" if torch.cuda.is_available() else "cpu")
    def generate(self):
        pass



def remove_client_utterances(text: str) -> str:
    """
    Remove every utterance that begins with the speaker label `Client:`.

    The pattern matches `Client:` and everything that follows it
    **up to (but not including)** the next line that starts with another
    speaker label such as `Counselor:` (or the end of the string).

    Parameters
    ----------
    text : str
        A dialogue transcript containing speaker labels
        (e.g. “Counselor: …”, “Client: …”).

    Returns
    -------
    str
        The transcript with all `Client:` turns removed.
    """
    pattern = r"Client:.*?(?=\n[A-Za-z]+:|\Z)"   # DOTALL will make . match newlines
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    # Optional: collapse any blank lines left behind
    cleaned = re.sub(r"\n{2,}", "\n", cleaned).strip()
    return cleaned


class CounselorAgent(Agent):
    def __init__(self,  demo_config, logger=None):
        super().__init__(demo_config)
        self.gem = GeminiSafer(demo_config, logger)
        self.logger = logger
        
        
              
    def utt_prompt_template(self, history):
        prompt ="Generate counselor's next utterance in korean.\n"
        prompt +="History:\n"
        for message in history[-10:]:
            prompt += f"{message['role'].capitalize()}: {message['message']}\n"
        return prompt
        
    
    def generate(self, history):
        prompt = self.utt_prompt_template( history)
        if self.llm.__class__.__name__ == "OpenAI":
            response = self.llm.invoke(prompt)
        else:
            # For transformers model
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.llm.generate(**inputs, max_new_tokens=128)
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # self.logger.log_and_print("prompt", prompt)
        self.logger.log_and_print("prompt", prompt)

        cleaned = response.strip()
        lc = cleaned.lower()
        if "counselor" not in lc and "상담사" not in lc and "assistant" not in lc and "客人" not in lc:
            cleaned = "그러시군요. 오늘 정말 수고하셨어요. 만약 증상이 계속된다면 전문가의 도움을 받는 것이 좋습니다. 당신은 혼자가 아니에요. 언제든지 도움이 필요하면 말씀해 주세요."      
            return cleaned  
            
            
        cleaned = response.strip()
        cleaned = remove_client_utterances(cleaned)
        cleaned = cleaned.replace(":", "")
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'\([^)]*\)', '', cleaned) 
        cleaned= cleaned.replace("History:", "").replace("history:", "").replace("History","").replace("history","").replace("History", "").replace("history", "")
        cleaned= cleaned.replace("Counselor", "").replace("counselor", "").replace("상담사", "").replace("Assistant", "").replace("assistant", "").replace("客人", "").replace("상담사", "")
        cleaned = cleaned.strip()
        cleaned = cleaned.split("\n")[0]
        cleaned = self.gem.run(history, cleaned)

        return cleaned
