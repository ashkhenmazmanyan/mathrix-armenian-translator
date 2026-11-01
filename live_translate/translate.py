"""Armenian -> English translation with NLLB-200."""
import re

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MT_MODELS = {
    "nllb-600M": "facebook/nllb-200-distilled-600M",
    "nllb-1.3B": "facebook/nllb-200-distilled-1.3B",
}


class Translator:
    def __init__(self, name="nllb-600M", beams=4):
        repo = MT_MODELS[name]
        self.tok = AutoTokenizer.from_pretrained(repo, src_lang="hye_Armn")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(repo, dtype=torch.float16).cuda().eval()
        self.english = self.tok.convert_tokens_to_ids("eng_Latn")
        self.beams = beams

    def translate(self, text):
        # NLLB sometimes silently drops the 2nd sentence of a multi-sentence input,
        # so translate sentence by sentence (in one batch, so it costs little extra time).
        sentences = split_sentences(text)
        batch = self.tok(sentences, return_tensors="pt", padding=True,
                         truncation=True, max_length=256).to("cuda")
        with torch.inference_mode():
            ids = self.model.generate(**batch, forced_bos_token_id=self.english,
                                      num_beams=self.beams, max_new_tokens=200)
        return " ".join(self.tok.batch_decode(ids, skip_special_tokens=True))

    def warmup(self):
        self.translate("Բարև")


def split_sentences(text):
    """Split after Armenian full stop (։ or :), '.', '!' or '?' followed by a space."""
    parts = re.split(r"(?<=[։:.!?])\s+", text.strip())
    return [p for p in parts if p] or [text]
