import asyncio
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from playwright.async_api import async_playwright, Page

from models import MusicSearchQuery, MoodEnum, GenreEnum


@dataclass
class Song:
    title: str
    artist: Optional[str] = None
    link: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class MusicByMoodScraper:
    BASE_URL = "https://www.musicbymood.com/"

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._browser = None
        self._context = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
        finally:
            await self._pw.stop()

    async def goto(self):
        assert self._page
        await self._page.goto(self.BASE_URL, timeout=self.timeout_ms)
        # Ensure main UI is visible
        await self._page.get_by_text("MusicByMood").wait_for(timeout=self.timeout_ms)

    async def apply_query(self, query: MusicSearchQuery):
        assert self._page
        page = self._page

        # 1) Click mood button if provided
        if query.mood:
            try:
                await page.get_by_role("button", name=str(query.mood)).click(timeout=3000)
            except Exception:
                # Fallback: text locator
                await page.get_by_text(str(query.mood), exact=True).click(timeout=3000)

        # 2) Adjust sliders (Energy, Happiness) if provided
        # The page renders custom sliders with role=slider; Energy is first, Happiness is second
        sliders = page.get_by_role("slider")

        async def set_slider(idx: int, percentage: int):
            if percentage is None:
                return
            try:
                handle = sliders.nth(idx)
                box = await handle.bounding_box()
                if not box:
                    return
                # Move to x at percentage across the track
                target_x = box["x"] + (box["width"] * (percentage / 100.0))
                target_y = box["y"] + box["height"] / 2
                await page.mouse.move(box["x"] + box["width"] / 2, target_y)
                await page.mouse.down()
                await page.mouse.move(target_x, target_y, steps=10)
                await page.mouse.up()
            except Exception:
                # Fallback: try arrow keys if slider is focusable
                try:
                    await handle.focus()
                    current_steps = 50  # assume midpoint; adjust towards percentage
                    target_steps = max(0, min(100, percentage))
                    delta = target_steps - current_steps
                    key = "ArrowRight" if delta > 0 else "ArrowLeft"
                    for _ in range(abs(delta)):
                        await handle.press(key)
                except Exception:
                    pass

        if query.energy_level is not None:
            await set_slider(0, int(query.energy_level))
        if query.happiness_level is not None:
            await set_slider(1, int(query.happiness_level))

        # 3) Select genres
        if query.genres:
            for g in query.genres:
                # Site genres appear lower-case; map enum to lower-case label
                label = str(g).lower()
                try:
                    await page.locator("div", has_text=label).first.click(timeout=2000)
                except Exception:
                    # Fallback: text locator anywhere
                    try:
                        await page.get_by_text(label).first.click(timeout=1500)
                    except Exception:
                        pass

        # 4) Trigger search
        try:
            await page.get_by_role("button", name="Find My Music").click(timeout=5000)
        except Exception:
            # Fallback: click by text
            await page.get_by_text("Find My Music").click(timeout=5000)

        # Wait for results to appear: prefer the heading "Recommended for your mood"
        try:
            await page.get_by_text("Recommended for your mood").wait_for(timeout=10000)
            # Wait a bit more for the song list to populate
            await page.wait_for_timeout(3000)
        except Exception:
            # Fallback: longer delay to ensure content loads
            await page.wait_for_timeout(5000)

    async def extract_results(self, limit: int = 20) -> List[Song]:
        assert self._page
        page = self._page
        songs: List[Song] = []

        # Parse the "Recommended for your mood" section by grouping lines into entries
        def _looks_like_duration(s: str) -> bool:
            return bool(re.match(r"^\d{1,2}:\d{2}$", s))

        def _looks_like_genre(s: str) -> bool:
            # Accept mostly lowercase words with letters, spaces, '&' and apostrophes, exclude durations
            if _looks_like_duration(s):
                return False
            return s == s.lower() and any(c.isalpha() for c in s)

        def _looks_like_new_title(s: str) -> bool:
            # Titles typically contain uppercase or are not all lowercase
            # Also exclude obvious genre words and durations
            if _looks_like_duration(s):
                return False
            if _looks_like_genre(s):
                return False
            # Accept any string that has uppercase letters or mixed case
            return any(c.isupper() for c in s)

        try:
            # Try multiple selectors to find the results container
            selectors_to_try = [
                ".order-1.md\\:order-2, .md\\:order-2",
                "div:has-text('Recommended for your mood')",
                "body",  # Fallback to full page
            ]
            
            text = ""
            for selector in selectors_to_try:
                try:
                    container = page.locator(selector).first
                    text = (await container.inner_text()) or ""
                    if "Recommended for your mood" in text and len(text) > 100:
                        break
                except Exception:
                    continue
            
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            

            # Start from the heading if present
            try:
                start_idx = lines.index("Recommended for your mood") + 1
            except ValueError:
                start_idx = 0

            i = start_idx
            seen_pairs = set()
            while i < len(lines) and len(songs) < limit:
                title = lines[i]
                # Guard against non-title noise
                if not _looks_like_new_title(title):
                    i += 1
                    continue
                i += 1
                if i >= len(lines):
                    break
                artist = lines[i]
                i += 1
                

                genres: List[str] = []
                duration: Optional[str] = None
                # Collect genres until duration or next title-like line
                while i < len(lines):
                    token = lines[i]
                    if _looks_like_duration(token):
                        duration = token
                        i += 1
                        break
                    if _looks_like_genre(token):
                        genres.append(token)
                        i += 1
                        continue
                    # Probably next card begins
                    if _looks_like_new_title(token):
                        break
                    # Unknown token, move on
                    i += 1

                key = (title, artist)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    songs.append(Song(title=title, artist=artist, extra={
                        "genres": genres,
                        "duration": duration,
                    }))

            if songs:
                return songs[:limit]
        except Exception:
            # Fall back to heuristics below
            pass

        # Heuristic 1: right panel container (results) – grab links or card texts
        try:
            results_container = page.locator(".order-1.md\\:order-2, .md\\:order-2")
            if await results_container.count() > 0:
                container = results_container.first
                # Try Spotify track links first
                links = container.locator("a[href*='open.spotify.com/track']")
                count = await links.count()
                seen = set()
                for i in range(min(count, limit)):
                    a = links.nth(i)
                    href = await a.get_attribute("href")
                    text = (await a.text_content()) or ""
                    title = text.strip() or "Unknown Title"
                    key = (title, href)
                    if key in seen:
                        continue
                    seen.add(key)
                    songs.append(Song(title=title, artist=None, link=href))

                if songs:
                    return songs[:limit]

                # Fallback: find possible card items with title and artist lines
                cards = container.locator("div").filter(has_text="by ")
                count = await cards.count()
                for i in range(min(count, limit)):
                    card = cards.nth(i)
                    text = (await card.text_content()) or ""
                    parts = [p.strip() for p in text.split("by ", 1)]
                    if len(parts) == 2:
                        title, artist = parts[0], parts[1]
                        songs.append(Song(title=title, artist=artist))

                if songs:
                    return songs[:limit]
        except Exception:
            pass

        # Heuristic 2: global search for potential list items
        try:
            items = page.locator("li, div")
            count = min(await items.count(), 200)
            for i in range(count):
                node = items.nth(i)
                txt = (await node.text_content()) or ""
                txt = " ".join(txt.split())
                if " by " in txt and len(txt) < 160:
                    title, artist = txt.split(" by ", 1)
                    songs.append(Song(title=title.strip(), artist=artist.strip()))
                    if len(songs) >= limit:
                        break
        except Exception:
            pass

        return songs[:limit]


async def search_music_by_mood(query: MusicSearchQuery, *, headless: bool = True, limit: int = 20) -> List[Song]:
    """High-level utility to search songs on MusicByMood from a MusicSearchQuery.

    Note: You may need to run `playwright install` once before first use.
    """
    async with MusicByMoodScraper(headless=headless) as scraper:
        await scraper.goto()
        await scraper.apply_query(query)
        results = await scraper.extract_results(limit=limit)
        return results


if __name__ == "__main__":
    async def _demo():
        # Example run
        example = MusicSearchQuery(
            mood=MoodEnum.ENERGETIC,
            energy_level=70,
            happiness_level=70,
            genres=[GenreEnum.COUNTRY]
        )
        res = await search_music_by_mood(example, headless=True, limit=10)
        for i, s in enumerate(res, 1):
            genres = ", ".join((s.extra or {}).get("genres", []))
            duration = (s.extra or {}).get("duration", "")
            print(f"{i:02d}. {s.title} — {s.artist or ''} | genres: {genres} | duration: {duration} {s.link or ''}")

    asyncio.run(_demo())
