"""
Heurísticas para estimar se um site de campanha aparenta ter sido
desenvolvido por PESSOA FÍSICA (o próprio candidato, um apoiador
voluntário, ou uma ferramenta de autoatendimento tipo "monte seu site")
ou por PESSOA JURÍDICA (uma agência/empresa de desenvolvimento web).

Isso é relevante porque, pela Lei nº 9.504/1997, art. 23 c/c
Resolução TSE nº 23.610/2019, apenas PESSOA FÍSICA pode doar bens ou
serviços estimáveis em dinheiro para campanha — uma empresa (CNPJ)
está proibida de doar o desenvolvimento do site. Se o site aparenta
ter sido feito por uma empresa, isso por si só já é um sinal de alerta
que precisa ser cruzado com a prestação de contas (ver
donation_disclosure.py): ou (a) o candidato *pagou* a empresa
normalmente como prestador de serviço (despesa eleitoral regular, sem
problema), ou (b) o serviço foi uma doação não registrada da empresa,
o que é vedado.

Este módulo NÃO tenta provar automaticamente qual dos dois cenários
ocorreu — apenas identifica sinais técnicos de autoria profissional,
para orientar a etapa seguinte (checagem cruzada com a prestação de
contas).

Metodologia: cada sinal é avaliado e registrado individualmente (nunca
uma classificação "caixa-preta"), para que o relatório final seja
auditável e defensável.
"""
from __future__ import annotations

import re

import requests
import whois  # python-whois

TIMEOUT = 8

# Geradores de site associados a ferramentas de autoatendimento
# (self-service), predominantemente usadas por pessoa física sem
# contratar uma agência.
GERADORES_AUTOATENDIMENTO = [
    "wix.com", "google sites", "webnode", "canva", "carrd",
    "hotmart", "wordpress.com",  # plano gratuito/pessoal do wordpress.com
]

# Padrões de rodapé/texto que indicam desenvolvimento por terceiro
# profissional (agência/empresa), geralmente citando marca ou site
# comercial da desenvolvedora.
PADROES_AGENCIA = [
    r"desenvolvido\s+por\s*[:\-]?\s*([A-Za-zÀ-ú0-9 .]{3,60})",
    r"criado\s+por\s*[:\-]?\s*([A-Za-zÀ-ú0-9 .]{3,60})",
    r"site\s+por\s*[:\-]?\s*([A-Za-zÀ-ú0-9 .]{3,60})",
    r"powered\s+by\s*[:\-]?\s*([A-Za-zÀ-ú0-9 .]{3,60})",
]

# Termos que, aparecendo perto do rodapé, reforçam que quem assina é
# uma empresa (agência, marketing, digital, etc.) e não uma pessoa.
TERMOS_EMPRESA = [
    "agência", "agencia", "marketing digital", "assessoria digital",
    "studio", "estúdio", "tecnologia", "sites políticos",
    "sites para candidatos", "web design", "webdesign", "criação de sites",
]


def _buscar_html(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        }, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _extrair_generator(html: str) -> str | None:
    m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return m.group(1) if m else None


def _para_string(valor) -> str | None:
    """
    python-whois às vezes retorna um campo (org, name...) como lista,
    quando há múltiplas respostas/camadas de servidores WHOIS. Normaliza
    sempre para uma única string, para não quebrar código a jusante que
    espera `.lower()`/regex sobre uma string simples.
    """
    if valor is None:
        return None
    if isinstance(valor, (list, tuple, set)):
        vistos = []
        for v in valor:
            if v and v not in vistos:
                vistos.append(v)
        return "; ".join(str(v) for v in vistos) if vistos else None
    return str(valor)


def _consultar_whois(dominio: str) -> dict:
    try:
        w = whois.whois(dominio)
        org = w.get("org") if isinstance(w, dict) else getattr(w, "org", None)
        name = w.get("name") if isinstance(w, dict) else getattr(w, "name", None)
        return {"whois_org": _para_string(org), "whois_name": _para_string(name)}
    except Exception as e:
        return {"whois_erro": str(e)}


def analisar_autoria(url: str) -> dict:
    """
    Retorna um dicionário com todos os sinais encontrados e uma
    conclusão heurística (`autoria_provavel`: 'pessoa_fisica',
    'pessoa_juridica' ou 'indeterminado'), sempre acompanhada dos
    sinais que a sustentam (`evidencias`).
    """
    resultado: dict = {"url": url, "evidencias": [], "autoria_provavel": "indeterminado"}

    html = _buscar_html(url)
    if html is None:
        resultado["erro"] = "não foi possível baixar o HTML do site"
        return resultado

    html_lower = html.lower()
    pontos_pj = 0
    pontos_pf = 0

    generator = _extrair_generator(html)
    if generator:
        resultado["meta_generator"] = generator
        gen_lower = generator.lower()
        if any(g in gen_lower for g in GERADORES_AUTOATENDIMENTO):
            pontos_pf += 2
            resultado["evidencias"].append(f"meta generator de ferramenta de autoatendimento: '{generator}'")
        elif "wordpress" in gen_lower or "elementor" in gen_lower:
            # WordPress auto-hospedado/Elementor é ambíguo: tanto uma
            # agência quanto um candidato técnico podem usar. Sinal fraco.
            resultado["evidencias"].append(f"meta generator: '{generator}' (ambíguo, não pontua sozinho)")

    for padrao in PADROES_AGENCIA:
        m = re.search(padrao, html_lower)
        if m:
            trecho = m.group(1).strip()
            resultado["evidencias"].append(f"rodapé menciona autoria de terceiro: '{trecho}'")
            if any(t in trecho for t in TERMOS_EMPRESA) or any(t in html_lower for t in TERMOS_EMPRESA):
                pontos_pj += 2
            else:
                pontos_pj += 1

    if re.search(r"cnpj[:\s]*\d{2}\.?\d{3}\.?\d{3}", html_lower):
        pontos_pj += 1
        resultado["evidencias"].append("CNPJ encontrado no HTML (possível empresa desenvolvedora ou do próprio comitê)")

    dominio = re.sub(r"^https?://", "", url).split("/")[0].lstrip("www.")
    whois_info = _consultar_whois(dominio)
    resultado.update(whois_info)
    org = (whois_info.get("whois_org") or "").lower() if whois_info.get("whois_org") else ""
    if org and any(t in org for t in TERMOS_EMPRESA + ["ltda", "eireli", " sa", "s.a", "me "]):
        pontos_pj += 2
        resultado["evidencias"].append(f"WHOIS: organização registrante parece empresa: '{whois_info.get('whois_org')}'")
    elif org:
        resultado["evidencias"].append(f"WHOIS: organização registrante: '{whois_info.get('whois_org')}' (não conclusivo)")

    resultado["pontos_pessoa_juridica"] = pontos_pj
    resultado["pontos_pessoa_fisica"] = pontos_pf
    if pontos_pj > pontos_pf and pontos_pj >= 2:
        resultado["autoria_provavel"] = "pessoa_juridica"
    elif pontos_pf > pontos_pj and pontos_pf >= 2:
        resultado["autoria_provavel"] = "pessoa_fisica"

    return resultado
