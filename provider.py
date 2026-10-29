import json

import httpx


class ProviderError(Exception):
    pass


def provider_error(status):
    if status in (401, 403):
        return "دسترسی سرویس مدل رد شد؛ کلید API و مجوز مدل را بررسی کنید."
    if status == 429:
        return "سهمیه یا اعتبار سرویس مدل کافی نیست؛ کمی بعد تلاش کنید یا حساب سرویس را بررسی کنید."
    if status == 400:
        return "سرویس مدل این درخواست را نپذیرفت؛ سازگاری مدل و تنظیمات را بررسی کنید."
    return "سرویس مدل در دسترس نیست؛ دوباره تلاش کنید."


class Provider:
    def __init__(self, settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(180, connect=15), follow_redirects=False)

    async def close(self):
        await self.client.aclose()

    async def chat(self, messages, model):
        if not self.settings.api_key:
            raise ProviderError("کلید سرویس متن تنظیم نشده است. مدیر سرور باید OPENAI_API_KEY را تنظیم کند.")
        payload = {"model": model, "messages": messages, "stream": True, "max_tokens": self.settings.max_output_tokens}
        completed = False
        try:
            async with self.client.stream("POST", f"{self.settings.api_base}/chat/completions", headers={"Authorization": f"Bearer {self.settings.api_key}"}, json=payload) as response:
                if response.status_code != 200:
                    raise ProviderError(provider_error(response.status_code))
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        completed = True
                        break
                    if not data:
                        continue
                    item = json.loads(data)
                    if item.get("error"):
                        raise ProviderError("سرویس مدل هنگام تولید پاسخ خطا داد.")
                    for choice in item.get("choices", []):
                        delta = choice.get("delta", {}).get("content")
                        if isinstance(delta, str) and delta:
                            yield delta
                        if choice.get("finish_reason"):
                            completed = True
            if not completed:
                raise ProviderError("اتصال مدل پیش از تکمیل پاسخ قطع شد؛ دوباره تلاش کنید.")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise ProviderError("پاسخ معتبر از سرویس مدل دریافت نشد؛ اتصال و تنظیمات را بررسی کنید.") from exc

    async def image(self, prompt, size):
        if not self.settings.image_key:
            raise ProviderError("کلید سرویس تصویر تنظیم نشده است.")
        try:
            response = await self.client.post(f"{self.settings.image_base}/images/generations", headers={"Authorization": f"Bearer {self.settings.image_key}"}, json={"model": self.settings.image_model, "prompt": prompt, "size": size, "n": 1})
            if response.status_code != 200:
                raise ProviderError(provider_error(response.status_code))
            return response.json()["data"][0]["b64_json"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("سرویس تصویر باید خروجی تصویری b64_json برگرداند؛ تنظیمات مدل را بررسی کنید.") from exc
