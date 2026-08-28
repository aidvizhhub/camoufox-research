#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Session-тулы MCP (вынесено из camoufox_research.py, canon/FILE-SIZE.md):
register(mcp) добавляет session_* тулы — одна живая вкладка «как человек»,
плюс тулы 2-й волны: snapshot/screenshot (vision), tabs, wait_for, eval,
crawl/map, extract, прокси и профили."""


def register(mcp, call):
    @mcp.tool()
    def session_start(url: str = "", max_chars: int = 6000) -> str:
        """Начинает ЖИВУЮ сессию: открывает URL в постоянной вкладке
        serve-воркера. Состояние (скролл, ввод, клики) живёт между командами —
        «как человек в одной вкладке». Дальше: session_navigate, session_click,
        session_type, session_scroll, session_links, session_text, session_back.
        Закрыть: session_end. session_status — состояние вкладки.
        КОГДА: интерактив (клики, формы, скролл, ввод) — «как человек
        в одной вкладке», состояние живёт между командами.
        НЕ КОГДА: нужен только текст → fetch_page (быстрее, кэш);
        нужен разовый клик по URL → browser_click."""
        return call("session_start", url=url, max_chars=max_chars)

    @mcp.tool()
    def session_navigate(url: str, max_chars: int = 6000) -> str:
        """Переход на URL в ТЕКУЩЕЙ вкладке сессии (без новой страницы).
        Требует session_start."""
        return call("session_navigate", url=url, max_chars=max_chars)

    @mcp.tool()
    def session_click(
        selector: str = "", target_text: str = "", ref: str = "", max_chars: int = 6000
    ) -> str:
        """Клик на живой странице сессии: CSS-селектор (selector), текст
        ссылки (target_text) или ref из snapshot (ref="3").
        Возвращает текст ПОСЛЕ клика. Требует session_start.
        КОГДА: клик по элементу уже открытой страницы (сессия жива).
        НЕ КОГДА: сессии нет → session_start сначала; нужен разовый
        «открыл-кликнул-прочитал» → browser_click; нужен только список
        элементов → snapshot (получишь ref)."""
        return call(
            "session_click",
            selector=selector,
            target_text=target_text,
            ref=ref,
            max_chars=max_chars,
        )

    @mcp.tool()
    def session_type(selector: str, text: str, max_chars: int = 6000) -> str:
        """Ввод в поле на живой странице сессии (CSS-селектор).
        Требует session_start."""
        return call("session_type", selector=selector, text=text, max_chars=max_chars)

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

    @mcp.tool()
    def session_tabs(op: str = "list", url: str = "", tab_id: str = "") -> str:
        """Вкладки сессии: op=list (все с id/url/title), op=new (url или
        пустая), op=switch (tab_id — активной), op=close (tab_id).
        Несколько вкладок — как у человека. Требует session_start."""
        return call("session_tabs", op=op, url=url, tab_id=tab_id)

    @mcp.tool()
    def session_wait_for(text: str = "", selector: str = "", timeout: int = 15) -> str:
        """Ждать на живой странице сессии появления текста (text) или
        элемента (selector). Вернёт «дождался»/«не дождался».
        Требует session_start."""
        return call("session_wait_for", text=text, selector=selector, timeout=timeout)

    @mcp.tool()
    def session_eval(expression: str) -> str:
        """Выполнить JS в активной вкладке сессии (MAIN world), вернуть JSON.
        Паттерн browser_eval. Требует session_start."""
        return call("session_eval", expression=expression)

    @mcp.tool()
    def snapshot(url: str = "", limit: int = 30) -> str:
        """Дерево интерактивных элементов с ref (aria-подобный YAML,
        ~2-5KB вместо HTML 100KB+). Клик по ref: session_click(ref="N").
        Без url — текущая вкладка сессии; с url — открыть и снять.
        КОГДА: понять структуру страницы и получить ref для кликов
        (дёшево по токенам, в отличие от HTML).
        НЕ КОГДА: нужен текст → session_text / fetch_page; нужен вид
        глазами → screenshot(som=True) — там номера совпадают с ref."""
        return call("snapshot", url=url, limit=limit)

    @mcp.tool()
    def screenshot(
        url: str = "", selector: str = "", som: bool = False, full_page: bool = True
    ) -> str:
        """Скриншот в PNG: активная вкладка сессии (без url) или страница
        по url. selector — только элемент. som=True — Set-of-Mark: красные
        рамки с номерами на интерактивных элементах (ref совпадают со
        snapshot). Возвращает путь к файлу.
        КОГДА: визуальная проверка (вёрстка, canvas, капча, картинки).
        НЕ КОГДА: нужны только тексты/ссылки → snapshot / fetch_page
        (сильно дешевле по токенам)."""
        return call("screenshot", url=url, selector=selector, som=som, full_page=full_page)

    @mcp.tool()
    def map_site(url: str, max_links: int = 50, pattern: str = "") -> str:
        """Карта сайта: все ссылки того же домена со стартовой страницы
        (без чтения содержимого). Паттерн Firecrawl map."""
        return call("map_site", url=url, max_links=max_links, pattern=pattern)

    @mcp.tool()
    def crawl(
        url: str,
        max_pages: int = 10,
        max_depth: int = 2,
        pattern: str = "",
        article_only: bool = True,
        max_chars: int = 4000,
    ) -> str:
        """BFS-обход сайта: стартовая страница + внутренние ссылки
        (depth <= max_depth, всего <= max_pages). Тексты с разделителями
        '--- URL:'. Паттерн Firecrawl crawl. Кэш: повторный обход дешёвый.
        КОГДА: собрать содержимое САЙТА целиком (BFS, своя структура).
        НЕ КОГДА: нужны только URL без текста → map_site / sitemap
        (дешевле); нужен один раздел → fetch_page; сайт огромный →
        sitemap → фильтр pattern, потом crawl."""
        return call(
            "crawl",
            url=url,
            max_pages=max_pages,
            max_depth=max_depth,
            pattern=pattern,
            article_only=article_only,
            max_chars=max_chars,
        )

    @mcp.tool()
    def extract(url: str, schema: str, llm: bool = False) -> str:
        """Извлечение по схеме (Firecrawl extract): schema — JSON
        {"поле": "css:.price"} или {"поле": {"selector": ".price",
        "attr": "text|href|src"}}. Селекторы: CSS ("css:", ".price"),
        XPath ("//div[@class='x']" или "xpath=..."). Возвращает JSON.
        llm=True — извлечение ИЗ ТЕКСТА страницы (LLM): schema —
        {"поле": подсказка} или {"поле": {"hint": "..."}}; работает, где
        селекторы хрупкие; требует LLM (DeepSeek/Ollama), иначе честный
        ответ «недоступен».
        КОГДА: нужны КОНКРЕТНЫЕ поля при СТАБИЛЬНОЙ структуре (CSS/XPath);
        структура неизвестна/меняется → llm=True.
        НЕ КОГДА: нужен сплошной текст → fetch_page / batch_fetch;
        нужны таблицы → table_extract; не знаешь селектор → snapshot
        сначала (найти элементы с ref)."""
        return call("extract", url=url, schema=schema, llm=llm)

    @mcp.tool()
    def set_proxy(proxy: str = "") -> str:
        """Прокси на лету (runtime): 'host:port', 'user:pass@host:port',
        'socks5://host:port'. Пустая строка — выключить. В serve-режиме
        браузер перезапускается с новым прокси."""
        return call("set_proxy", proxy=proxy)

    @mcp.tool()
    def profile_save(name: str = "default") -> str:
        """Сохранить куки + localStorage живого браузера в профиль <name>
        (логины не терять между сессиями). Путь: ~/.cache/camoufox-research/
        profiles/<name>.json"""
        return call("profile_save", name=name)

    @mcp.tool()
    def profile_load(name: str = "default") -> str:
        """Загрузить куки + localStorage профиля <name> в живой браузер."""
        return call("profile_load", name=name)

    @mcp.tool()
    def session_key_press(key: str, max_chars: int = 6000) -> str:
        """Нажать клавишу на активной вкладке сессии: 'Enter', 'Escape',
        'Tab', 'ArrowDown', 'F5' (имена Playwright keyboard).
        Требует session_start."""
        return call("session_key_press", key=key, max_chars=max_chars)

    @mcp.tool()
    def session_select_option(selector: str, value: str, max_chars: int = 6000) -> str:
        """Выбрать вариант в <select> по значению/метке/индексу.
        Требует session_start."""
        return call("session_select_option", selector=selector, value=value, max_chars=max_chars)

    @mcp.tool()
    def session_resize(width: int, height: int, max_chars: int = 2000) -> str:
        """Изменить размер viewport активной вкладки (адаптивные сайты).
        Требует session_start."""
        return call("session_resize", width=width, height=height, max_chars=max_chars)

    @mcp.tool()
    def session_network(limit: int = 50) -> str:
        """Сеть активной вкладки: последние запросы (status, method, type,
        url). Видно AJAX и ошибки. Паттерн network inspection.
        Требует session_start."""
        return call("session_network", limit=limit)

    @mcp.tool()
    def session_console(limit: int = 50) -> str:
        """Консоль активной вкладки: сообщения JS (error/warning/log).
        Требует session_start."""
        return call("session_console", limit=limit)

    @mcp.tool()
    def session_block(pattern: str) -> str:
        """Заблокировать запросы, URL которых содержит pattern
        (напр. 'analytics', '**.gif'). Паттерн request blocking.
        Действует на активную вкладку."""
        return call("session_block", pattern=pattern)

    @mcp.tool()
    def session_unblock(pattern: str = "") -> str:
        """Снять блокировку запросов: по pattern или все (пустая строка)."""
        return call("session_unblock", pattern=pattern)

    @mcp.tool()
    def session_download(url: str = "", selector: str = "", timeout: int = 30) -> str:
        """Скачать файл. url — прямая ссылка; selector — кликнуть и поймать
        download (кнопки «Скачать»). Сохраняет в
        ~/.cache/camoufox-research/downloads/. Возвращает путь."""
        return call("session_download", url=url, selector=selector, timeout=timeout)

    @mcp.tool()
    def read_document(source: str, max_chars: int = 6000) -> str:
        """Текст из PDF/DOCX/XLSX: source — URL или локальный путь.
        Библиотеки pypdf/python-docx/openpyxl (pip install, если нет).
        КОГДА: документ (отчёт, прайс, спецификация) — часто ссылки
        с сайтов/в рассылках.
        НЕ КОГДА: HTML-страница → fetch_page; старые .doc/.xls →
        конвертируй libreoffice --convert-to docx/xlsx (не читаются)."""
        return call("read_document", source=source, max_chars=max_chars)

    @mcp.tool()
    def session_form_fill(fields: str, submit: str = "", max_chars: int = 6000) -> str:
        """Заполнить форму РАЗОМ: fields — JSON {"селектор": "значение"}.
        submit — селектор кнопки отправки (кликнет, если задан).
        Паттерн form filling. Требует session_start."""
        return call("session_form_fill", fields=fields, submit=submit, max_chars=max_chars)

    @mcp.tool()
    def session_upload(selector: str, path: str, max_chars: int = 6000) -> str:
        """Загрузить файл в форму: selector — input[type=file], path —
        локальный путь. Паттерн form file upload. Требует session_start."""
        return call("session_upload", selector=selector, path=path, max_chars=max_chars)

    @mcp.tool()
    def stats(limit: int = 20) -> str:
        """Наблюдаемость: сколько раз вызывали каждый тул, среднее время,
        ошибки + последние вызовы (audit; секреты замаскированы)."""
        return call("stats", limit=limit)

    @mcp.tool()
    def sitemap(url: str, max_links: int = 200) -> str:
        """URL'ы из sitemap.xml (+ .xml.gz, вложенные sitemapindex).
        Готовая карта ВСЕХ страниц сайта — фид для crawl.
        Паттерн sitemap crawlers."""
        return call("sitemap", url=url, max_links=max_links)

    @mcp.tool()
    def rss(url: str, limit: int = 20) -> str:
        """Посты из RSS/Atom-фида: title, link, дата. Новости, блоги,
        changelog одним вызовом. Паттерн RSS scrapers."""
        return call("rss", url=url, limit=limit)

    @mcp.tool()
    def check_links(
        url: str, max_links: int = 50, internal_only: bool = True, timeout: int = 15
    ) -> str:
        """Проверка битых ссылок: собрать ссылки страницы, проверить
        HTTP-статусы, отчёт «[404] URL». Паттерн broken link checkers."""
        return call(
            "check_links",
            url=url,
            max_links=max_links,
            internal_only=internal_only,
            timeout=timeout,
        )

    @mcp.tool()
    def export(data: str, format: str = "json", path: str = "") -> str:
        """Сохранить результат (из extract/crawl) в файл: json/csv/md.
        path — свой или авто ~/.cache/camoufox-research/exports/.
        Паттерн data export.
        КОГДА: результат нужен на диске (CSV для таблиц, JSON для
        автоматизации, MD для отчёта).
        НЕ КОГДА: результат идёт в разговор/синтез → верни текст как
        есть; нужен готовый отчёт кампании → citation_report."""
        return call("export", data=data, format=format, path=path)

    @mcp.tool()
    def table_extract(url: str, selector: str = "table", max_tables: int = 5) -> str:
        """HTML-таблицы страницы → CSV-текст (характеристики, прайсы,
        сравнения). Паттерн table export.
        КОГДА: на странице есть <table> — прайсы/спеки/сравнения.
        НЕ КОГДА: данных нет в таблице → extract (произвольные поля);
        таблиц нет вовсе → fetch_page."""
        return call("table_extract", url=url, selector=selector, max_tables=max_tables)

    @mcp.tool()
    def page_diff(url: str, max_chars: int = 6000) -> str:
        """Дифф страницы с прошлым чтением (кэш vs свежее): мониторинг
        изменений, «что поменялось». Паттерн change detection.
        КОГДА: следить за страницей (цены, доки, новости) — второй и
        далее заходы покажут ИЗМЕНЕНИЯ.
        НЕ КОГДА: страница читается впервые (диффу не с чем сравнить)
        → fetch_page; нужна полная текстовая версия → fetch_page."""
        return call("page_diff", url=url, max_chars=max_chars)
