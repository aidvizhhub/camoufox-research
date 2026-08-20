#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Session-тулы MCP (вынесено из camoufox_research.py, canon/FILE-SIZE.md):
register(mcp) добавляет session_* тулы — одна живая вкладка «как человек»."""


def register(mcp, call):
    @mcp.tool()
    def session_start(url: str = "", max_chars: int = 6000) -> str:
        """Начинает ЖИВУЮ сессию: открывает URL в постоянной вкладке
        serve-воркера. Состояние (скролл, ввод, клики) живёт между командами —
        «как человек в одной вкладке». Дальше: session_navigate, session_click,
        session_type, session_scroll, session_links, session_text, session_back.
        Закрыть: session_end. session_status — состояние вкладки."""
        return call("session_start", url=url, max_chars=max_chars)


    @mcp.tool()
    def session_navigate(url: str, max_chars: int = 6000) -> str:
        """Переход на URL в ТЕКУЩЕЙ вкладке сессии (без новой страницы).
        Требует session_start."""
        return call("session_navigate", url=url, max_chars=max_chars)


    @mcp.tool()
    def session_click(selector: str = "", target_text: str = "",
                      max_chars: int = 6000) -> str:
        """Клик на живой странице сессии: CSS-селектор (selector, для кнопок —
        напр. button:has-text('Show more')) или текст ссылки (target_text).
        Возвращает текст ПОСЛЕ клика. Требует session_start."""
        return call("session_click", selector=selector, target_text=target_text,
                    max_chars=max_chars)


    @mcp.tool()
    def session_type(selector: str, text: str, max_chars: int = 6000) -> str:
        """Ввод в поле на живой странице сессии (CSS-селектор).
        Требует session_start."""
        return call("session_type", selector=selector, text=text,
                    max_chars=max_chars)


    @mcp.tool()
    def session_scroll(direction: str = "bottom", max_chars: int = 6000) -> str:
        """Скролл на живой странице сессии: bottom/top/down/up. Ждёт догрузку
        lazy-контента. Требует session_start."""
        return call("session_scroll", direction=direction, max_chars=max_chars)


    @mcp.tool()
    def session_links(max_links: int = 20) -> str:
        """Ссылки текущей страницы сессии. Требует session_start."""
        return call("session_links", max_links=max_links)


    @mcp.tool()
    def session_text(max_chars: int = 6000) -> str:
        """Текст текущей страницы сессии (без навигации). Требует session_start."""
        return call("session_text", max_chars=max_chars)


    @mcp.tool()
    def session_back(max_chars: int = 6000) -> str:
        """Назад по истории вкладки сессии. Требует session_start."""
        return call("session_back", max_chars=max_chars)


    @mcp.tool()
    def session_status() -> str:
        """Состояние сессии: URL, заголовок, жива ли вкладка."""
        return call("session_status")


    @mcp.tool()
    def session_end() -> str:
        """Закрывает вкладку сессии, сбрасывает состояние."""
        return call("session_end")
