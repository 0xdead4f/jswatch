# utils/notifier.py
import httpx
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class TelegramConfig:
    api_key: str
    chat_id: str
    thread_id: Optional[str] = None

class TelegramNotifier:
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.api_key}"

    async def send_document(self, file_path: Path, caption: str = "") -> bool:
        params = {
            "chat_id": self.config.chat_id,
            "caption": caption,
            "disable_notification": False
        }
        
        if self.config.thread_id:
            params["message_thread_id"] = self.config.thread_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(file_path, 'rb') as file:
                    files = {'document': file}
                    response = await client.post(
                        f"{self.base_url}/sendDocument",
                        data=params,
                        files=files
                    )
                    return response.status_code == 200
        except Exception:
            return False