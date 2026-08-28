#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Исследовательские тулы MCP (вынесено из camoufox_research.py, canon
FILE-SIZE.md): register(mcp, call) добавляет research*/fetch/extract-тулы
(паттерн session_tools). Сессионные тулы — в session_tools."""

def register(mcp, call):
    @mcp.tool()
    def web_search(
        query: str, max_results: int = 10, pages: int = 1, include_snippets: bool = False
    ) -> str:
        """Поиск в DuckDuckGo через анти-детект браузер: номер, заголовок,
        URL. pages>1 — пагинация (больше уникальных URL). include_snippets —
        сниппет под URL. Кэш на сутки."""
        return call(
            "web_search",
            query=query,
            max_results=max_results,
            pages=pages,
            include_snippets=include_snippets,
        )

    @mcp.tool()
    def research(
        queries: list[str],
        max_results_per_query: int = 5,
        fetch_top: int = 0,
        article_only: bool = True,
        max_chars: int = 4000,
        max_parallel: int | None = None,
        target_domains: int = 0,
        domains_limit: int = 0,
        expand: bool = False,
        fetch_all: bool = False,
        terms_wave: bool = False,
        quality_first: bool = False,
        as_json: bool = False,
        academic: bool = False,
        llm_planner: bool = False,
    ) -> str:
        """Deep-поиск ОДНИМ вызовом — норматив «10 источников» за один ход.
        queries — несколько формулировок запроса (агент сам планирует
        подзапросы, паттерн gpt-researcher); сервер ищет по каждой,
        дедуплицирует URL и возвращает список со сниппетами.
        fetch_top>0 — сразу читает топ-N источников (тексты статей).

        Режим «20+ источников, не топы» (реальный ресёрч):
        - target_domains=N — цель по РАЗНЫМ доменам (20 = двадцать разных
          сайтов). Пока не набрали — доборка волнами: базовые запросы,
          потом follow-up из термов сниппетов, потом пагинация.
        - domains_limit=K — не больше K источников с одного домена.
        - expand=True — к каждому запросу переформулировки («X comparison»,
          «X documentation») — свежие домены и углы.
        - terms_wave=True — вторая волна из РЕДКИХ ТЕРМОВ первой волны
          (имена, названия из сниппетов) — паттерн Open Deep Research.
        - quality_first=True — отбор по качеству домена: доки/GitHub/arXiv
          первыми, форумы вниз (паттерн gpt-researcher source ranking).
        - fetch_all=True — тексты ВСЕХ отобранных, а не топ-N.
        - as_json=True — машинный JSON: meta (счётчики, follow-up запросы),
          sources (title/url/domain/tier/tier_label/snippet), texts, notes.
          Идеален для автоматизации и синтеза агентом.
        - academic=True — вертикальный АКАДЕМИЧЕСКИЙ канал: arXiv +
          Semantic Scholar (бесплатные API, без ключей) — первоисточники
          (tier 0), которых DDG почти не видит (паттерн Exa vertical index).
        - llm_planner=True — LLM (DeepSeek/Ollama) генерирует 10 follow-up
          запросов как в gpt-researcher/STORM (Layer B, опционально, требует
          DEEPSEEK_API_KEY или OLLAMA_HOST, иначе пропуск).
        Пример глубокого ресёрча: research(queries=["deep research
        agents"], target_domains=20, domains_limit=2, expand=True,
        terms_wave=True, quality_first=True, academic=True, llm_planner=True,
        fetch_all=True, as_json=True, max_results_per_query=6)
        Результат кэшируется на сутки."""
        return call(
            "research",
            timeout=900,
            queries=queries,
            max_results_per_query=max_results_per_query,
            fetch_top=fetch_top,
            article_only=article_only,
            max_chars=max_chars,
            max_parallel=max_parallel,
            target_domains=target_domains,
            domains_limit=domains_limit,
            expand=expand,
            fetch_all=fetch_all,
            terms_wave=terms_wave,
            quality_first=quality_first,
            as_json=as_json,
            academic=academic,
            llm_planner=llm_planner,
        )

    @mcp.tool()
    def paper_search(query: str, sources: str = "arxiv,semantic", max_results: int = 10) -> str:
        """Поиск научных статей: arXiv + Semantic Scholar (бесплатные API,
        без ключей). Возвращает статьи с годом/авторами/цитатами —
        первоисточники (tier 0), которых общий поиск почти не видит
        (паттерн индустрии: vertical index / arxiv-канал рядом с вебом).
        Кэш на сутки. Пример: paper_search("deep research agents")"""
        return call("paper_search", query=query, sources=sources, max_results=max_results)

    @mcp.tool()
    def research_digest(
        camp_id: str, refresh: bool = True, max_age: int = 86400
    ) -> str:
        """Выжимки + верификация кампании: короткие пакеты
        (заголовок + первый абзац, ~700 символов) для синтеза и статус
        «жив/битый» каждого источника (гейт качества, паттерн DEER /
        DeepResearch Bench: verified citations). refresh=True — собрать
        выжимки и проверить живость заново (до 30 URL, параллельно);
        у фоновой кампании всё уже заполнено — refresh не нужен.
        max_age — свежесть verified в секундах (0 = проверить ВСЁ
        заново, напр. сомнение в кэше; 86400 = сутки TTL-кэш)."""
        return call(
            "research_digest", camp_id=camp_id, refresh=refresh, max_age=max_age
        )

    @mcp.tool()
    def citation_pack(camp_id: str) -> str:
        """CIT-ПАКЕТ для синтеза отчёта: только verified ✅ источники
        с выжимками, одним блоком (цитируй по номерам [1]..[N]).
        Это гейт качества DEER/DeepResearch Bench: отчёт опирается на
        живые источники, а не на мёртвые ссылки. Если verify/выжимки ещё
        не прогонялись — достроит автоматически (сеть/браузер)."""
        return call("citation_pack", camp_id=camp_id)

    @mcp.tool()
    def citation_report(camp_id: str, path: str = "") -> str:
        """Цитированный отчёт НА ДИСК: готовый MD-документ с выжимками
        verified ✅ источников (нумерация [1..N] + раздел «Ссылки»).
        Без path — exports/{camp_id}.cit.md. Отдаёт путь и размер —
        документ можно сразу отправить/приложить."""
        return call("citation_report", camp_id=camp_id, path=path)

    @mcp.tool()
    def research_start(
        topic: str,
        queries: list[str] | None = None,
        target_sources: int = 20,
        domains_limit: int = 2,
        feeds: list[str] | None = None,
        background: bool = True,
        llm_planner: bool = False,
    ) -> str:
        """КАМПАНИЯ ресёрча: цель «N РАЗНЫХ сайтов» с счётчиком прогресса.
        Фон=True — охота уходит в отдельный процесс: лог + маркер done
        (~/.cache/camoufox-research/exports/<id>.json) — ждать маркер,
        не поллить. Состояние в sqlite: сколько уникальных доменов
        реально собрано; угловые волны (лучшие практики/грабли/
        альтернативы) добирают сами. Уникальных сайтов меньше цели →
        честный статус partial. Синтез: research_report(id) → список
        источников → batch_fetch по тем, что нужны текстом.
        feeds — RSS/sitemap URL: первая нога охоты БЕЗ поисковика
        (работает даже при мёртвом DDG); queries можно опустить.
        Перед стартом проверяет пульс крона сторожа — мёртвый крон
        предупредит, а не промолчит. Финальный отчёт автоархивируется
        (CAMOUFOX_REPORT_DIR, по умолчанию exports).
        llm_planner=True — Layer B, LLM (DeepSeek/Ollama) для 20+ вопросов [1]."""
        return call(
            "research_start",
            timeout=600,
            topic=topic,
            queries=queries,
            target_sources=target_sources,
            domains_limit=domains_limit,
            feeds=feeds,
            background=background,
            llm_planner=llm_planner,
        )

    @mcp.tool()
    def research_status(camp_id: str, limit: int = 6) -> str:
        """Прогресс кампании: статус, счётчик разных сайтов vs цель,
        топ источников по качеству (доки/код первыми)."""
        return call("research_status", camp_id=camp_id, limit=limit)

    @mcp.tool()
    def research_report(camp_id: str, fmt: str = "md") -> str:
        """Отчёт кампании: список источников (титул/URL/домен/класс) в
        md-таблице или json. Сырьё для синтеза с цитатами."""
        return call("research_report", camp_id=camp_id, fmt=fmt)

    @mcp.tool()
    def tool_hint(what: str = "") -> str:
        """РОУТЕР (паттерн MegaAgent-MCP): «для чего использовать какой
        тул». what — действие/вопрос, например «анализ страницы»,
        «мониторинг», «статьи». Отвечает каким тулом и почему — вместо
        перебора 57 тулов вслепую. Сокращает выбор (индустрия: >40
        тулов = −260% selection quality, роутинг решает)."""
        _R = {
            "поиск": ("web_search / research_start",
                      "общий веб: web_search; глубокая охота на N сайтов — research_start"),
            "стать": ("paper_search",
                      "научные: arXiv/Semantic/Crossref/Wiki — первоисточники"),
            "анализ страниц": ("fetch_page / extract",
                               "текст: fetch_page; по схеме: extract"),
            "мониторинг": ("research_start(feeds=) / page_diff",
                           "следить за изменением страницы: page_diff"),
            "карта сайта": ("map_site / sitemap",
                            "все URL сайта: map_site; sitemap.xml: sitemap"),
            "выжимки": ("research_digest",
                        "verified-источники с текстом: research_digest"),
            "отчёт": ("research_report(fmt=)",
                      "md/csv/xlsx/mermaid — итог кампании"),
            "браузер": ("session_*",
                        "живая сессия: session_start → navigate/click/type/text"),
            "таблиц": ("table_extract",
                       "таблицы со страницы: table_extract (HTML → структура)"),
            "скриншот": ("screenshot",
                         "вид страницы картинкой: screenshot"),
            "ссылки": ("extract_links / session_links",
                       "ссылки страницы: extract_links; в сессии: session_links"),
            "файл": ("read_document / session_download / session_upload",
                     "PDF/DOCX/XLSX: read_document; скачать: session_download; "
                     "загрузить: session_upload"),
            "профиль": ("profile_load / profile_save",
                        "куки+localStorage сессии: profile_save/load"),
            "сеть": ("session_network / session_console",
                     "запросы вкладки: session_network; JS-ошибки: session_console"),
            "прокси": ("set_proxy",
                       "сменить прокси на лету: set_proxy (host:port)"),
            "экспорт": ("export",
                        "JSON/CSV/MD результата: export(data, format, path)"),
            "проверка ссылок": ("check_links",
                                "битые ссылки: check_links"),
            "цитаты": ("citation_pack / citation_report",
                       "verified+текст для синтеза: citation_pack"),
            "документ": ("read_document",
                         "PDF/DOCX/XLSX текст: read_document"),
            "статус": ("research_status",
                       "прогресс кампании: research_status(id)"),
            "продолжить": ("research_resume",
                           "добор кампании с места: research_resume(id)"),
        }
        if not what:
            return ("для чего? примеры: поиск, статьи, анализ страниц, "
                    "мониторинг, таблицы, цитаты, файлы, документ, статус")
        for k, v in _R.items():
            if k.lower() in what.lower():
                return f"для «{what}» → {v[0]}: {v[1]}"
        return f"для «{what}»: начни с research_start (общая охота) или web_search (быстрый поиск)"

    @mcp.tool()
    def service_route(goal: str, query: str = "", dry: bool = False) -> str:
        """СЕРВИС-РОУТЕР (авто-подбор, паттерн MegaAgent orchestration):
        НЕ подсказывает, а САМ вызывает нужный тул по цели.
        goal — цель («поиск», «статьи», «мониторинг», «выжимки»,
        «таблицы», «цитаты», «сессия», «страница», «сниппет»,
        «скриншот»); query — параметр (тема/URL/camp_id).
        dry=True — только показать план (какой тул + аргументы),
        БЕЗ вызова. Возвращает РЕЗУЛЬТАТ тула (не совет)."""
        _MAP: dict[str, tuple[str, dict]] = {
            "поиск": ("web_search", {"query": query or goal, "max_results": 10}),
            "стать": ("paper_search", {"query": query or goal, "max_results": 5}),
            "мониторинг": ("page_diff", {"url": query, "max_chars": 4000}),
            "карта": ("map_site", {"url": query, "max_links": 30}),
            "выжимки": ("research_digest", {"camp_id": query}),
            "статьи": ("paper_search", {"query": query or goal, "max_results": 5}),
            "таблиц": ("table_extract", {"url": query}),
            "цитат": ("citation_pack", {"camp_id": query}),
            "сесси": ("session_start", {"url": query, "max_chars": 4000}),
            "страниц": ("fetch_page", {"url": query, "max_chars": 6000}),
            "сниппет": ("extract_links", {"url": query, "max_links": 20}),
            "скриншот": ("screenshot", {"url": query}),
        }
        g = goal.lower().strip()
        for k, (tool, params) in _MAP.items():
            if k in g:
                if tool == "page_diff" and not query:
                    return "мониторинг: нужен URL (query=...)"
                if tool == "research_digest" and not query:
                    return "выжимки: нужен camp_id (query=...)"
                if dry:
                    return f"dry: {tool}({', '.join(f'{k}={v}' for k, v in params.items())})"
                try:
                    return call(tool, **params)
                except Exception as e:
                    return f"роутер: {tool} упал ({type(e).__name__})"
        return ("цель не распознана. goals: поиск, статьи, мониторинг, "
                "карта, выжимки, таблицы, цитаты, сессия, страница, "
                "сниппет, скриншот + query=параметр")

    @mcp.tool()
    def research_critic(camp_id: str) -> str:
        """КРИТИК-РЕВЬЮЕР (канон groundwork/DCM 2026): отчёт кампании →
        выделяет 3-5 НЕСУЩИХ утверждений и проверяет каждое против
        текстов источников (supported/unsupported/unverifiable).
        11-57% ошибок цитирования у коммерческих агентов — мы меряем
        СВОИ. Требует DEEPSEEK_API_KEY или OLLAMA_HOST (иначе честный
        ответ «недоступен»), отчёт НЕ правит — только флагает."""
        try:
            from camoufox_research.camoufox_critic import load_bearing_report
            return load_bearing_report(camp_id)
        except Exception as e:
            return f"критик упал: {type(e).__name__}: {str(e)[:80]}"

    @mcp.tool()
    def tool_usage(days: int = 0) -> str:
        """МЕТРИКА использования (28.08): какие тулы РЕАЛЬНО зовутся
        (persistent, из tool_usage.json). days>0 — показать только
        тулы с последним вызовом в пределах N дней; days=0 — топ всех.
        Внизу — «кандидаты на резку»: вызовы были >30 дней назад
        (метрика работает, а тул не используют)."""
        try:
            from camoufox_research.camoufox_research_bridge import _TOOL_USAGE
            if not _TOOL_USAGE:
                return "пока нет вызовов (usage пуст)"
            import time as _t
            now = _t.time()
            rows = sorted(
                ((t, r.get("count", 0), r.get("last")) for t, r in _TOOL_USAGE.items()),
                key=lambda x: -x[1],
            )
            if days > 0:
                rows = [r for r in rows if r[2] and (now - r[2]) < days * 86400]
            out = [f"вызовы тулов (top {min(20, len(rows))}):"]
            for t, n, last in rows[:20]:
                ago = f"{(now - last) / 86400:.0f}дн" if last else "?"
                out.append(f"  {n:5d}x  {t}  ({ago})")
            # кандидаты на резку: были вызовы, но не звались 30+ дней
            stale = [t for t, r in _TOOL_USAGE.items()
                     if r.get("last") and (now - r["last"]) > 30 * 86400]
            if stale:
                out.append("\nкандидаты на резку (>30дн не звались):")
                for t in sorted(stale)[:10]:
                    out.append(f"  - {t}")
            return "\n".join(out)
        except Exception:
            return "usage-счётчик недоступен (нет bridge)"

    @mcp.tool()
    def research_resume(camp_id: str, background: bool = False) -> str:
        """ДОБОРКА кампании с места (паттерн LangGraph resume): берёт
        partial/failed и добирает недостающие РАЗНЫЕ сайты свежими углами
        (tutorial/comparison/case study). done — откажет («нечего добирать»),
        running — откажет (двойной запуск = гонка). Нулевая волна (те же
        домены по кругу) = честный стоп. Синхронно по умолчанию; большую
        доборку — background=True (ждать маркер <id>.json)."""
        return call("research_resume", timeout=600, camp_id=camp_id, background=background)

    @mcp.tool()
    def research_index(limit: int = 50, fmt: str = "md") -> str:
        """Сводка ВСЕХ кампаний: id · тема · статус · домены/цель · когда
        обновлена. md-таблица или json. Сырьё для «что мы уже охотили»."""
        return call("research_index", limit=limit, fmt=fmt)

    @mcp.tool()
    def fetch_page(
        url: str, max_chars: int = 6000, article_only: bool = False, delta: bool = False
    ) -> str:
        """Текст страницы без HTML-мусора (статьи, доки, README). Кэш на
        сутки. article_only=True — текст статьи (Trafilatura), fallback —
        весь body. delta=True — delta-чтение: если контент не изменился
        с прошлого раза, вернёт маркер '[delta: ...]' вместо текста
        (не тратим токены на повтор)."""
        return call(
            "fetch_page", url=url, max_chars=max_chars, article_only=article_only, delta=delta
        )

    @mcp.tool()
    def batch_fetch(
        urls: list[str],
        max_chars: int = 4000,
        article_only: bool = False,
        max_parallel: int | None = None,
    ) -> str:
        """Открывает НЕСКОЛЬКО URL в одном браузере — для глубокого ресёрча
        на 30-50 источников одним вызовом вместо серии холодных стартов.
        Кэш: уже посещённые URL возвращаются мгновенно, без браузера.
        Rate limit между переходами защищает от капчи. Батч ≥8 URL —
        параллельно (пул потоков, свой браузер на поток); число воркеров
        автоопределяется по ресурсам машины (слабый ПК — 1-2, мощный — 3-4),
        max_parallel — явное ограничение. Возвращает тексты с разделителями
        '--- URL: ...'.
        article_only=True — извлечь текст статьи (Trafilatura), без меню
        и баннеров. Пример:
        batch_fetch(urls=["https://docs.python.org/3/", "https://opencode.ai/docs/"],
                    max_chars=6000, article_only=True)"""
        return call(
            "batch_fetch",
            timeout=600,
            urls=urls,
            max_chars=max_chars,
            article_only=article_only,
            max_parallel=max_parallel,
        )

    @mcp.tool()
    def extract_links(url: str, pattern: str = "", max_links: int = 20) -> str:
        """Собирает ссылки страницы (фильтр по подстроке pattern)."""
        return call("extract_links", url=url, pattern=pattern, max_links=max_links)

    @mcp.tool()
    def browser_navigate(url: str, max_links: int = 10) -> str:
        """Текст страницы + первые ссылки."""
        return call("browser_navigate", url=url, max_links=max_links)

    @mcp.tool()
    def browser_click(
        url: str, selector: str = "", target_text: str = "", ref: str = "", max_links: int = 10
    ) -> str:
        """Открывает URL и кликает по элементу: CSS-селектор (selector),
        текст ссылки/кнопки (target_text) или ref из snapshot (ref="3").
        Возвращает страницу после клика.
        Пример: browser_click(url, target_text="Продолжить")"""
        return call(
            "browser_click",
            url=url,
            selector=selector,
            target_text=target_text,
            ref=ref,
            max_links=max_links,
        )

    @mcp.tool()
    def browser_type(url: str, selector: str, text: str) -> str:
        """Открывает URL, вводит text в поле ввода (CSS-селектор), возвращает
        обновлённую страницу. Для форм поиска."""
        return call("browser_type", url=url, selector=selector, text=text)
