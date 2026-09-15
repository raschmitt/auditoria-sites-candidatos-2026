"""
Cliente HTTP para a API pública do TSE (divulgacandcontas.tse.jus.br).

O WAF do TSE bloqueia requisições que não venham de um navegador real
renderizado (curl, requests, e até Playwright/Selenium em modo headless
retornam HTTP 403 "Access Denied"). A única forma viável encontrada foi
abrir um Chromium real, com interface gráfica (headless=False), e fazer
as chamadas via fetch() dentro da própria página carregada — exatamente
como um usuário navegando pelo site faria.

Por isso este cliente mantém UM navegador Chromium aberto (visível) e
expõe métodos para buscar JSON da API através dele, com paralelismo
controlado (várias fetch() simultâneas dentro da mesma página).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import sync_playwright, Browser, Page

BASE = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"


@dataclass
class TSEClient:
    headless: bool = False
    _pw = None
    _browser: Browser | None = None
    _page: Page | None = None

    def __enter__(self) -> "TSEClient":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        # Carrega a SPA uma vez para estabelecer contexto/cookies antes das chamadas de API
        self._page.goto(
            "https://divulgacandcontas.tse.jus.br/divulga/#/",
            wait_until="networkidle",
            timeout=30_000,
        )
        self._page.wait_for_timeout(800)
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def get_json(self, path: str, retries: int = 3, timeout_ms: int = 15_000) -> Any:
        """Busca um único endpoint JSON, com retry simples e timeout por chamada."""
        url = f"{BASE}/{path.lstrip('/')}"
        for attempt in range(retries):
            result = self._page.evaluate(
                """
                async ([url, timeoutMs]) => {
                    const ctrl = new AbortController();
                    const t = setTimeout(() => ctrl.abort(), timeoutMs);
                    try {
                        const r = await fetch(url, {signal: ctrl.signal});
                        const text = await r.text();
                        return {status: r.status, text};
                    } catch (e) {
                        return {status: 0, text: String(e)};
                    } finally {
                        clearTimeout(t);
                    }
                }
                """,
                [url, timeout_ms],
            )
            if result["status"] == 200:
                try:
                    return json.loads(result["text"])
                except json.JSONDecodeError:
                    return None
            time.sleep(0.5 * (attempt + 1))
        return None

    def get_json_many(
        self, paths: list[str], concurrency: int = 10, timeout_ms: int = 15_000,
        pausa_entre_lotes: float = 0.15,
    ) -> list[Any]:
        """
        Busca vários endpoints em paralelo (via Promise.all dentro do
        navegador), em lotes de `concurrency`, devolvendo a lista de
        respostas JSON (ou None em caso de falha) na mesma ordem de `paths`.

        Cada fetch individual tem um AbortController com timeout próprio
        (`timeout_ms`), de forma que uma única requisição travada (o WAF
        do TSE eventualmente "segura" alguma chamada sem nunca responder,
        sob carga sustentada) não trava o lote inteiro indefinidamente —
        ela simplesmente expira e volta como falha (None), sem impedir
        que as demais do lote sejam concluídas.
        """
        urls = [f"{BASE}/{p.lstrip('/')}" for p in paths]
        results: list[Any] = []
        for i in range(0, len(urls), concurrency):
            batch = urls[i : i + concurrency]
            batch_result = self._page.evaluate(
                """
                async ([urls, timeoutMs]) => {
                    const fetchOne = async (url) => {
                        const ctrl = new AbortController();
                        const t = setTimeout(() => ctrl.abort(), timeoutMs);
                        try {
                            const r = await fetch(url, {signal: ctrl.signal});
                            const text = await r.text();
                            return {status: r.status, text};
                        } catch (e) {
                            return {status: 0, text: String(e)};
                        } finally {
                            clearTimeout(t);
                        }
                    };
                    return await Promise.all(urls.map(fetchOne));
                }
                """,
                [batch, timeout_ms],
            )
            for r in batch_result:
                if r["status"] == 200:
                    try:
                        results.append(json.loads(r["text"]))
                    except json.JSONDecodeError:
                        results.append(None)
                else:
                    results.append(None)
            if pausa_entre_lotes:
                time.sleep(pausa_entre_lotes)
        return results
