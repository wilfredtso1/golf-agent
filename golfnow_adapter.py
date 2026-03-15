from __future__ import annotations

import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timezone
from typing import Optional

from config import SETTINGS
from course_semantic import resolve_course_candidates, score_course_match
from db import get_conn
from tools import list_courses, upsert_course_snapshot

logger = logging.getLogger("golf-agent")

_TIME_WINDOWS: dict[str, tuple[int, int]] = {
    "early_morning": (8, 10),
    "late_morning": (10, 12),
    "early_afternoon": (12, 14),
}


def _build_search_url(course_name: str, target_date: date, group_size: int) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    params = urllib.parse.urlencode(
        {
            "sortby": "Date",
            "holes": "18",
            "players": str(group_size),
            "date": date_str,
            "searchTerm": course_name,
        }
    )
    return f"https://www.golfnow.com/tee-times/search#{params}"


def _time_in_any_window(t: time, windows: list[str]) -> bool:
    for window in windows:
        bounds = _TIME_WINDOWS.get(window)
        if bounds is None:
            continue
        start_h, end_h = bounds
        if time(start_h, 0) <= t < time(end_h, 0):
            return True
    return False


def _parse_card(
    card: object,
    course_name: str,
    target_date: date,
    time_windows: list[str],
) -> Optional[dict[str, object]]:
    try:
        time_el = card.query_selector("[class*='time'], [data-time], .tee-time-time, time")
        price_el = card.query_selector("[class*='price'], [data-price], .tee-time-price")
        link_el = card.query_selector("a[href*='/tee-times']")

        time_str = time_el.inner_text().strip() if time_el else None
        price_str = price_el.inner_text().strip() if price_el else None
        href = link_el.get_attribute("href") if link_el else None

        if not time_str:
            logger.warning(
                "golfnow_card_missing_time course=%s date=%s", course_name, target_date
            )
            return None

        # Parse time (e.g. "9:24 AM", "10:00 AM")
        parsed_time: Optional[time] = None
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                parsed_time = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue

        if parsed_time is None:
            logger.warning(
                "golfnow_card_unparseable_time course=%s time_str=%r", course_name, time_str
            )
            return None

        if not _time_in_any_window(parsed_time, time_windows):
            return None

        # Parse price (e.g. "$45", "$45.00")
        price_per_player = 0.0
        if price_str:
            cleaned = price_str.replace("$", "").replace(",", "").strip().split()[0]
            try:
                price_per_player = float(cleaned)
            except (ValueError, IndexError):
                logger.warning(
                    "golfnow_card_unparseable_price course=%s price_str=%r — using 0.0",
                    course_name,
                    price_str,
                )

        # Convert local time -> UTC
        import zoneinfo

        tz = zoneinfo.ZoneInfo(SETTINGS.default_timezone)
        local_dt = datetime.combine(target_date, parsed_time, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)

        booking_url = (
            f"https://www.golfnow.com{href}"
            if href and href.startswith("/")
            else (href or f"https://www.golfnow.com/tee-times/search?searchTerm={urllib.parse.quote(course_name)}")
        )

        return {
            "course": course_name,
            "tee_time": utc_dt,
            "price_per_player": price_per_player,
            "booking_url": booking_url,
        }
    except Exception as exc:
        logger.warning("golfnow_card_parse_error course=%s error=%s", course_name, exc)
        return None


def _scrape_one_course(
    course_name: str,
    target_date: date,
    time_windows: list[str],
    group_size: int,
) -> list[dict[str, object]]:
    from playwright.sync_api import sync_playwright

    url = _build_search_url(course_name, target_date, group_size)
    results: list[dict[str, object]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=SETTINGS.golfnow_scrape_headless)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=SETTINGS.golfnow_scrape_timeout_ms)

            # Wait for tee-time cards to appear
            card_selector = "[class*='tee-time'], [data-testid*='tee-time'], .tee-time-card"
            try:
                page.wait_for_selector(
                    card_selector, timeout=SETTINGS.golfnow_scrape_timeout_ms
                )
            except Exception:
                logger.warning(
                    "golfnow_no_cards_found course=%s url=%s", course_name, url
                )
                return []

            cards = page.query_selector_all(card_selector)
            logger.info(
                "golfnow_cards_found course=%s count=%d date=%s",
                course_name,
                len(cards),
                target_date,
            )

            for card in cards:
                result = _parse_card(card, course_name, target_date, time_windows)
                if result is not None:
                    results.append(result)
        finally:
            browser.close()

    return results


def _resolve_hybrid(
    courses: list[str], catalog_names: list[str]
) -> tuple[list[str], set[str]]:
    """Return (search_names, new_course_names).

    search_names: canonical DB name if a match exists, else the raw input name.
    new_course_names: subset of search_names that had no DB match (candidates for upsert).
    """
    if not catalog_names:
        return list(courses), set(courses)

    search_names: list[str] = []
    new_course_names: set[str] = set()
    seen: set[str] = set()

    for requested in courses:
        scored = max(
            catalog_names,
            key=lambda name: score_course_match(requested, name),
            default=None,
        )
        if scored and score_course_match(requested, scored) >= 0.55:
            canonical = scored
        else:
            canonical = requested
            new_course_names.add(canonical)
            logger.info(
                "golfnow_course_not_in_db requested=%r — using raw name for GolfNow search",
                requested,
            )
        if canonical not in seen:
            search_names.append(canonical)
            seen.add(canonical)

    return search_names, new_course_names


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    catalog_names: list[str] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            catalog_names = [row["name"] for row in list_courses(cur, limit=500)]

    search_names, new_course_names = _resolve_hybrid(courses, catalog_names)

    if not search_names:
        logger.info("golfnow_no_courses_resolved requested=%s", courses)
        return []

    all_results: list[dict[str, object]] = []
    timeout_per_course = (SETTINGS.golfnow_scrape_timeout_ms / 1000) + 10  # wall-clock budget

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_course = {
            executor.submit(
                _scrape_one_course, course, target_date, time_windows, group_size
            ): course
            for course in search_names
        }

        for future in as_completed(future_to_course, timeout=timeout_per_course * len(search_names)):
            course = future_to_course[future]
            try:
                rows = future.result(timeout=timeout_per_course)
                all_results.extend(rows)
            except Exception as exc:
                logger.warning("golfnow_scrape_failed course=%s error=%s", course, exc)

    # Register newly-discovered courses into the DB catalog (idempotent upsert).
    if new_course_names and all_results:
        discovered = {r["course"] for r in all_results if r["course"] in new_course_names}
        if discovered:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for name in discovered:
                            # Use the best price/url seen for this course as the snapshot.
                            rows_for = [r for r in all_results if r["course"] == name]
                            rows_for.sort(key=lambda r: r["price_per_player"])
                            sample = rows_for[0]
                            upsert_course_snapshot(
                                cur,
                                name=name,
                                booking_url=str(sample["booking_url"]),
                                price_per_player=float(sample["price_per_player"]) or None,
                                metadata={"source": "golfnow_scraper"},
                            )
                    conn.commit()
                logger.info("golfnow_upserted_new_courses courses=%s", sorted(discovered))
            except Exception as exc:
                logger.warning("golfnow_upsert_courses_failed error=%s", exc)

    all_results.sort(key=lambda item: (item["tee_time"], item["price_per_player"]))
    return all_results[:max_results]
