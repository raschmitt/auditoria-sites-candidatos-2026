"""
Separa, na lista bruta de endereços eletrônicos declarados por cada
candidato (campo `sites` do TSE), o que é efetivamente um "site próprio"
(domínio autônomo, potencialmente sujeito à regra de hospedagem no
Brasil) do que é apenas um perfil em rede social, plataforma de
mensageria ou agregador de links.

A Lei nº 9.504/1997, art. 57-B, fala em "sítio do candidato" — o alvo da
nossa análise de compliance é esse "sítio" (domínio próprio), não os
perfis em redes sociais de terceiros (Meta, X, Google etc.), cuja
hospedagem não é escolha do candidato.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

REDES_SOCIAIS = {
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "youtu.be", "kwai.com", "threads.com",
    "threads.net", "linkedin.com", "t.me", "telegram.me", "telegram.org",
    "whatsapp.com", "wa.me", "api.whatsapp.com", "chat.whatsapp.com",
    "discord.gg", "discord.com", "spotify.com", "open.spotify.com",
    "flickr.com", "pinterest.com", "snapchat.com",
    "bsky.app", "bsky.social", "truthsocial.com", "gettr.com",
    "twitch.tv", "sticker.ly", "deezer.com", "deezer.page.link",
    "music.amazon.com", "music.amazon.com.br", "clubhouse.com",
    "mastodon.social", "reddit.com", "telegram.dog",
}

AGREGADORES_DE_LINK = {
    "linktr.ee", "beacons.ai", "linkr.bio", "bio.link", "allmylinks.com",
    "campsite.bio", "lit.link", "carrd.co",
}

PLATAFORMAS_FINANCIAMENTO = {
    "queroapoiar.com.br", "vakinha.com.br", "catarse.me", "benfeitoria.com",
    "abacashi.com", "kickante.com.br",
}

IGNORAR = REDES_SOCIAIS | AGREGADORES_DE_LINK | PLATAFORMAS_FINANCIAMENTO


def extrair_dominio(url_bruta: str) -> str | None:
    """
    Extrai o domínio registrável (ex.: 'candidatos.pco.org.br') de uma
    string de URL potencialmente malformada (o TSE aceita entradas livres
    dos candidatos: maiúsculas, texto solto tipo 'Tik Tok - @fulano',
    URLs sem protocolo etc.).
    """
    if not url_bruta:
        return None
    s = url_bruta.strip()
    # Descarta entradas que claramente não são URLs (texto livre digitado
    # pelo candidato em vez de um endereço, ex.: "Tik Tok - @fulano")
    if " " in s and "://" not in s.lower():
        return None
    if not re.match(r"^https?://", s, re.IGNORECASE):
        s = "https://" + s
    try:
        parsed = urlparse(s.lower())
        host = parsed.netloc or parsed.path.split("/")[0]
        host = host.split("@")[-1]  # remove eventual user@ residual
        host = host.split(":")[0]  # remove porta
        if host.startswith("www."):
            host = host[len("www."):]
        # Um domínio real tem pelo menos um ponto (ex.: "exemplo.com.br").
        # Entradas sem ponto são lixo de digitação (handle solto tipo
        # "@fulano" ou nome de plataforma sem TLD, ex.: "whatsapp") e não
        # representam um site verificável.
        if "." not in host or not re.match(r"^[a-z0-9.\-]+$", host):
            return None
        return host
    except Exception:
        return None


def classificar_site(url_bruta: str) -> dict:
    """
    Classifica uma entrada bruta de `sites` em uma das categorias:
    - 'site_proprio': domínio autônomo, candidato a análise de compliance
    - 'rede_social': perfil em rede social conhecida
    - 'agregador_link': ferramenta tipo linktree
    - 'financiamento_coletivo': plataforma de doação/vaquinha
    - 'invalido': não é uma URL reconhecível
    """
    dominio = extrair_dominio(url_bruta)
    if dominio is None:
        return {"url": url_bruta, "dominio": None, "categoria": "invalido"}

    dominio_base = ".".join(dominio.split(".")[-3:]) if dominio.count(".") >= 2 else dominio
    for conjunto, categoria in (
        (REDES_SOCIAIS, "rede_social"),
        (AGREGADORES_DE_LINK, "agregador_link"),
        (PLATAFORMAS_FINANCIAMENTO, "financiamento_coletivo"),
    ):
        if dominio in conjunto or any(dominio.endswith("." + d) or dominio == d for d in conjunto):
            return {"url": url_bruta, "dominio": dominio, "categoria": categoria}

    return {"url": url_bruta, "dominio": dominio, "categoria": "site_proprio"}


def classificar_lista(sites: list[str]) -> list[dict]:
    return [classificar_site(u) for u in sites]
