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
"""
from __future__ import annotations

import socket
import time

import requests

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,isp,org,as"
RATE_LIMIT_SLEEP = 1.4  # ~42 req/min, com folga em relação ao limite de 45/min


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
        "hospedado_no_brasil": None,
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
    resultado["hospedado_no_brasil"] = geo.get("countryCode") == "BR"
    return resultado
