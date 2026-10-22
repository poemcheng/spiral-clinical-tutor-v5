"""本地 Ollama LLM 服務（v3）。

修正 v2 問題：
- 預設模型 gemma4:12b（思考型模型，預設 think=False 直接作答）。
- 改用 /api/chat 並送出完整 messages 歷史 → 虛擬病患有對話記憶。
- 啟動時可檢查 /api/tags，模型不存在時明確回報，不做靜默 fallback。
- 支援 streaming 逐字回傳。
- 失敗時回傳 ok=False，由呼叫端明確標示「AI 不可用」，不偽裝成 AI 回覆。
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, List

from .config import (OLLAMA_BASE_URL, OLLAMA_CHAT_TOKENS, OLLAMA_KEEP_ALIVE,
                     OLLAMA_MODEL, OLLAMA_TIMEOUT)


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    error: str = ""
    model: str = OLLAMA_MODEL


@dataclass
class LLMStatus:
    reachable: bool = False
    model_available: bool = False
    model: str = OLLAMA_MODEL
    available_models: List[str] = field(default_factory=list)
    error: str = ""
    busy: bool = False
    operation: str = ""
    queue_depth: int = 0

    @property
    def ready(self) -> bool:
        return self.reachable and self.model_available

    def to_dict(self) -> dict:
        return {
            "reachable": self.reachable,
            "model_available": self.model_available,
            "model": self.model,
            "available_models": self.available_models,
            "ready": self.ready,
            "error": self.error,
            "busy": self.busy,
            "operation": self.operation,
            "queue_depth": self.queue_depth,
        }


class OllamaService:
    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        # Ollama 在單張顯卡載入／推論時若同時收到多個長生成，容易造成 VRAM
        # 壓力、極慢回覆或不完整 JSON。所有真正使用模型的請求依票號排隊；
        # /api/tags 狀態查詢不佔用模型，因此不需進佇列。
        self._model_condition = threading.Condition()
        self._next_ticket = 0
        self._serving_ticket = 0
        self._model_busy = False
        self._active_operation = ""
        self._waiting = 0

    def queue_status(self) -> dict:
        with self._model_condition:
            return {
                "busy": self._model_busy,
                "operation": self._active_operation,
                "queue_depth": self._waiting,
            }

    @contextmanager
    def _model_slot(self, operation: str):
        """依到達順序取得唯一模型使用權，直到整段串流讀取完畢才釋放。"""
        with self._model_condition:
            ticket = self._next_ticket
            self._next_ticket += 1
            self._waiting += 1
            while self._model_busy or ticket != self._serving_ticket:
                self._model_condition.wait()
            self._waiting -= 1
            self._model_busy = True
            self._active_operation = operation or "AI 生成"
        try:
            yield
        finally:
            with self._model_condition:
                self._model_busy = False
                self._active_operation = ""
                self._serving_ticket += 1
                self._model_condition.notify_all()

    @contextmanager
    def model_slot(self, operation: str):
        """供 Stable Diffusion 等共用同一 GPU 的外部模型動作加入佇列。"""
        with self._model_slot(operation):
            yield

    def unload_for_next_model(self) -> None:
        """呼叫者已持有 model_slot 時，要求 Ollama 立即釋放目前模型 VRAM。"""
        try:
            payload = json.dumps({"model": self.model, "keep_alive": 0}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate", data=payload,
                headers={"Content-Type": "application/json", **self._auth_headers()}, method="POST")
            with urllib.request.urlopen(req, timeout=30):
                pass
        except Exception:
            # Ollama 不可用或舊版不支援時，仍讓 SD 回報自己的實際狀態。
            pass

    def _auth_headers(self):
        key=os.getenv("OLLAMA_API_KEY", "")
        return {"Authorization":"Bearer "+key} if key else {}

    # -- 狀態檢查 ------------------------------------------------------------
    def check(self) -> LLMStatus:
        status = LLMStatus(model=self.model)
        queue = self.queue_status()
        status.busy = queue["busy"]
        status.operation = queue["operation"]
        status.queue_depth = queue["queue_depth"]
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers=self._auth_headers(), method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            status.reachable = True
            names = [m.get("name", "") for m in data.get("models", [])]
            status.available_models = names
            base = self.model.split(":")[0]
            status.model_available = any(
                n == self.model or n == self.model+":latest" or self.model == n+":latest" for n in names
            )
            if not status.model_available:
                status.error = (
                    f"Ollama 已啟動，但找不到模型 {self.model}。"
                    f"請執行：ollama pull {self.model}"
                )
        except Exception as exc:
            status.error = f"無法連線 Ollama（{self.base_url}）：{exc}。請先啟動 Ollama。"
        return status

    # -- 對話（含記憶）--------------------------------------------------------
    def _chat_request(self, messages: List[dict], temperature: float,
                      max_tokens: int, stream: bool,
                      json_mode: bool = False) -> urllib.request.Request:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            # Ollama 原生 JSON mode，比只在 prompt 要求 JSON 穩定許多。
            payload["format"] = "json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            f"{self.base_url}/api/chat", data=data,
            headers={"Content-Type": "application/json", **self._auth_headers()}, method="POST",
        )

    def chat(self, messages: List[dict], *, temperature: float = 0.5,
             max_tokens: int = OLLAMA_CHAT_TOKENS,
             operation: str = "AI 對話") -> LLMResult:
        """非串流完整回覆。messages = [{role, content}, ...]（含 system）。"""
        with self._model_slot(operation):
            try:
                req = self._chat_request(messages, temperature, max_tokens, stream=False)
                with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
                    parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
                text = ((parsed.get("message") or {}).get("content") or "").strip()
                if not text:
                    return LLMResult(ok=False, error="Ollama 回傳空白內容", model=self.model)
                return LLMResult(ok=True, text=text, model=self.model)
            except Exception as exc:
                return LLMResult(ok=False, error=f"Ollama 呼叫失敗：{exc}", model=self.model)

    def chat_stream(self, messages: List[dict], *, temperature: float = 0.5,
                    max_tokens: int = OLLAMA_CHAT_TOKENS,
                    operation: str = "AI 對話",
                    json_mode: bool = False) -> Iterator[dict]:
        """串流回覆。逐段 yield {"token": str} 最後 yield {"done": True, "text": 全文}
        或 {"error": str}。"""
        chunks: List[str] = []
        with self._model_slot(operation):
            try:
                req = self._chat_request(messages, temperature, max_tokens, stream=True,
                                         json_mode=json_mode)
                with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        piece = (obj.get("message") or {}).get("content", "")
                        if piece:
                            chunks.append(piece)
                            yield {"token": piece}
                        if obj.get("done"):
                            break
                text = "".join(chunks).strip()
                if not text:
                    yield {"error": "Ollama 回傳空白內容"}
                else:
                    yield {"done": True, "text": text}
            except Exception as exc:
                yield {"error": f"Ollama 串流失敗：{exc}", "partial": "".join(chunks)}

    # -- 單輪生成（病患生成、影片腳本、Step 6 評分）----------------------------
    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.35,
                 max_tokens: int = 1400, operation: str = "AI 生成",
                 json_mode: bool = False) -> LLMResult:
        """單輪生成。內部改用串流接收：
        非串流模式在整段生成完成前完全沒有資料回傳，弱硬體上長生成會
        觸發 socket 逾時（timed out）；串流模式每個 token 都會重置逾時計時。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        chunks: List[str] = []
        error = ""
        for event in self.chat_stream(messages, temperature=temperature, max_tokens=max_tokens,
                                      operation=operation, json_mode=json_mode):
            if "token" in event:
                chunks.append(event["token"])
            elif "error" in event:
                error = event["error"]
        text = "".join(chunks).strip()
        if text and not error:
            return LLMResult(ok=True, text=text, model=self.model)
        return LLMResult(ok=False, text=text, error=error or "Ollama 回傳空白內容", model=self.model)

    def warm_up(self) -> LLMResult:
        """預先把模型載入 VRAM（keep_alive 讓後續呼叫不再冷啟動）。"""
        return self.generate("請回覆：ok", max_tokens=8, temperature=0.0,
                             operation="模型載入／預熱")

    def generate_json(self, prompt: str, *, system: str = "",
                      max_tokens: int = 1600, temperature: float = 0.1,
                      operation: str = "結構化 AI 生成") -> LLMResult:
        """生成並嘗試抽出第一個 JSON 物件；text 為 JSON 字串。

        逾時自動重試一次：首次呼叫常因模型冷載入而逾時，
        但 Ollama 端載入仍在進行，第二次呼叫通常已就緒。"""
        result = self.generate(prompt, system=system, temperature=temperature,
                               max_tokens=max_tokens, operation=operation, json_mode=True)
        if not result.ok and ("timed out" in result.error.lower() or "timeout" in result.error.lower()):
            result = self.generate(prompt, system=system, temperature=temperature,
                                   max_tokens=max_tokens, operation=operation, json_mode=True)
        if not result.ok:
            return result
        text = result.text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return LLMResult(ok=False, error="回覆中找不到 JSON 物件", model=self.model)
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            # 影片實測曾出現少一個逗號的 JSON。JSON mode 已大幅降低機率；
            # 若仍失敗，讓模型只修復原輸出一次，避免直接把技術錯誤丟給學員。
            repair = self.generate(
                "請修復下列 JSON 的語法，只輸出完整有效 JSON，不增刪欄位或內容：\n"
                + candidate,
                system="你是 JSON 語法修復器，只能輸出 JSON。",
                temperature=0.0, max_tokens=max_tokens,
                operation=f"{operation}（修復 JSON）", json_mode=True,
            )
            if not repair.ok:
                return LLMResult(ok=False, error=f"JSON 解析失敗：{exc}", model=self.model)
            repaired = repair.text.strip()
            r_start, r_end = repaired.find("{"), repaired.rfind("}")
            if r_start == -1 or r_end <= r_start:
                return LLMResult(ok=False, error=f"JSON 解析失敗：{exc}", model=self.model)
            candidate = repaired[r_start:r_end + 1]
            try:
                json.loads(candidate)
            except json.JSONDecodeError as repair_exc:
                return LLMResult(ok=False, error=f"JSON 修復後仍無法解析：{repair_exc}", model=self.model)
        return LLMResult(ok=True, text=candidate, model=self.model)
