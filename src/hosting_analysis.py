"""
Verifica onde está hospedado cada "site próprio" declarado por um
candidato, para checar a exigência legal de hospedagem em servidor
localizado no Brasil (Lei nº 9.504/1997, art. 57-B, c/c Resolução
TSE nº 23.610/2019, art. 2º — propaganda eleitoral na internet deve ser
veiculada em sítio brasileiro, com endereço eletrônico comunicado à
Justiça Eleitoral).

Método: resolve o domínio para IP (DNS) e geolocaliza o IP via API
pública gratuita (ip-api.com). Não requer chave de API; limite de 45
requisições/min no plano gratuito, por isso o módulo aplica um
espaçamento entre chamadas.

⚠️ LIMITAÇÃO CRÍTICA — CDNs/proxies globais: um site atrás de Cloudflare,
Akamai, Fastly, Amazon CloudFront, Sucuri/Imperva etc. resolve para um IP
da rede *desses* provedores, não do servidor de origem real — e esses
provedores operam PoPs (pontos de presença) espalhados pelo mundo todo.
Ou seja: geolocalizar esse IP pode apontar Canadá, EUA, Alemanha etc.
mesmo quando o servidor de origem por trás do proxy está fisicamente no
Brasil. Isso é extremamente comum: Cloudflare tem plano gratuito e é
adotado em massa por sites de campanha por proteção contra DDoS. Por
isso este módulo DETECTA quando o IP pertence a um provedor de CDN/proxy
conhecido e, nesse caso, marca `hospedado_no_brasil = None`
("indeterminável por este método") em vez de `False` — nunca afirma uma
suposta violação da regra de hospedagem só com base na localização do
IP de borda de um CDN.
"""
from __future__ import annotations

import socket
import time

import requests

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,isp,org,as"
RATE_LIMIT_SLEEP = 1.4  # ~42 req/min, com folga em relação ao limite de 45/min

# Provedores de CDN/proxy/anti-DDoS cuja localização de IP não reflete o
# servidor de origem real (identificados pelo nome de ISP/organização
# retornado pela API de geolocalização).
PROVEDORES_CDN_PROXY = [
    "cloudflare", "akamai", "fastly", "amazon", "cloudfront", "sucuri",
    "imperva", "incapsula", "google", "microsoft", "azure", "stackpath",
    "keycdn", "bunny.net", "bunnycdn",
]


def _eh_cdn_proxy(isp: str | None, org: str | None) -> str | None:
    texto = f"{isp or ''} {org or ''}".lower()
    for provedor in PROVEDORES_CDN_PROXY:
        if provedor in texto:
            return provedor
    return None


def resolver_ip(dominio: str, timeout: float = 5.0) -> str | None:
    try:
        socket.setdefaulttimeout(timeout)
        return socket.gethostbyname(dominio)
    except Exception:
        return None


def geolocalizar_ip(ip: str) -> dict:
    try:
        r = requests.get(IP_API_URL.format(ip=ip), timeout=6)
        data = r.json()
        if data.get("status") != "success":
            return {"erro": data.get("message", "falha desconhecida")}
        return data
    except Exception as e:
        return {"erro": str(e)}


def analisar_hospedagem(dominio: str) -> dict:
    """
    Retorna um dicionário com:
    - dominio, ip, pais, pais_codigo, isp, org, asn
    - hospedado_no_brasil: True/False/None (None = não foi possível determinar)
    - conforme_hospedagem_brasil: mesmo valor de hospedado_no_brasil,
      exposto com o nome do critério legal avaliado
    """
    resultado = {
        "dominio": dominio, "ip": None, "pais": None, "pais_codigo": None,
        "isp": None, "org": None, "asn": None,
        "hospedado_no_brasil": None, "atras_de_cdn_proxy": None,
    }
    ip = resolver_ip(dominio)
    if not ip:
        resultado["erro"] = "DNS não resolveu (domínio inativo, digitado incorretamente, ou fora do ar)"
        return resultado
    resultado["ip"] = ip

    geo = geolocalizar_ip(ip)
    time.sleep(RATE_LIMIT_SLEEP)
    if "erro" in geo:
        resultado["erro"] = geo["erro"]
        return resultado

    resultado["pais"] = geo.get("country")
    resultado["pais_codigo"] = geo.get("countryCode")
    resultado["isp"] = geo.get("isp")
    resultado["org"] = geo.get("org")
    resultado["asn"] = geo.get("as")

    cdn = _eh_cdn_proxy(geo.get("isp"), geo.get("org"))
    resultado["atras_de_cdn_proxy"] = cdn
    if cdn:
        # IP é de borda de CDN/proxy: a localização geográfica não
        # representa o servidor de origem. Não é seguro concluir nada
        # sobre a regra de hospedagem no Brasil a partir só disso.
        resultado["hospedado_no_brasil"] = None
        resultado["nota"] = (
            f"IP pertence a rede de CDN/proxy ({cdn}); país exibido é do "
            f"ponto de presença mais próximo, não necessariamente do "
            f"servidor de origem real. Conformidade indeterminável por "
            f"este método — requer checagem manual (ex.: histórico de DNS)."
        )
    else:
        resultado["hospedado_no_brasil"] = geo.get("countryCode") == "BR"
    return resultado
