"""AI auto-categorization service for Phase 8A."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Gaming",
    "Cooking",
    "Tech",
    "Comedy",
    "Music",
    "Education",
    "Fitness",
    "Travel",
    "Fashion",
    "News",
    "Animals",
    "Vlog",
    "Other",
]

_KEYWORDS: dict[str, list[str]] = {
    "Gaming": [
        "gaming", "gameplay", "game play", "playthrough", "walkthrough", "let's play", "lets play",
        "fortnite", "minecraft", "pubg", "valorant", "apex", "cod", "call of duty", "fifa", "nba",
        "ps5", "xbox", "nintendo", "switch", "steam", "gta", "gaming setup", "gaming chair",
        "gaming mouse", "mechanical keyboard", "rgb", "game review", "gaming highlights",
        "eSports", "esports", "pro player", "speedrun", "game news", "patch notes",
    ],
    "Cooking": [
        "cooking", "recipe", "baking", "bake", "kitchen", "chef", "food", "cuisine", "delicious",
        "easy recipe", "quick recipe", "dinner", "lunch", "breakfast", "meal prep", "mealprep",
        "healthy food", "vegan", "vegetarian", "gluten free", "gluten-free", "low carb",
        "pasta", "chicken", "beef", "seafood", "dessert", "cake", "cookies", "bread",
        "smoothie", "juice", "salad", "soup", "stew", "grill", "bbq", "air fryer",
        "instant pot", "slow cooker", "cooking tips", "how to cook", "cooking tutorial",
        "restaurant", "street food", "foodie", "food review",
    ],
    "Tech": [
        "tech", "technology", "gadget", "smartphone", "iphone", "android", "samsung", "google pixel",
        "laptop", "macbook", "windows", "linux", "apple", "microsoft", "software", "hardware",
        "unboxing", "review", "hands on", "hands-on", "tutorial", "how to", "guide", "tips",
        "ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural",
        "robot", "drone", "vr", "ar", "virtual reality", "augmented reality", "metaverse",
        "crypto", "bitcoin", "blockchain", "nft", "web3", "programming", "coding", "developer",
        "javascript", "python", "rust", "golang", "cloud", "aws", "azure", "docker", "kubernetes",
        "startup", "launch", "announcement", "leak", "rumor", "beta", "update", "upgrade",
    ],
    "Comedy": [
        "comedy", "funny", "hilarious", "joke", "prank", "parody", "skit", "sketch", "meme",
        "laugh", "lol", "lmao", "roast", "stand up", "standup", "improv", "comedian",
        "funny moments", "funny fails", "fail", "epic fail", "win", "epic win", "storytime",
        "story time", "react", "reaction", "try not to laugh", "challenge", "funny challenge",
    ],
    "Music": [
        "music", "song", "album", "artist", "band", "singer", "vocal", "lyrics", "remix",
        "cover", "acoustic", "live", "concert", "tour", "music video", "mv", "official video",
        "beat", "instrumental", "piano", "guitar", "drums", "bass", "violin", "saxophone",
        "dj", "dj mix", "set", "playlist", "mix", "radio", "spotify", "apple music",
        "soundcloud", "mixtape", "ep", "single", "hip hop", "rap", "rnb", "rock", "pop",
        "jazz", "classical", "electronic", "edm", "house", "techno", "kpop", "k-pop",
        "reaction", "rate", "music review", "top 10", "top 10 songs", "billboard",
    ],
    "Education": [
        "education", "learn", "learning", "tutorial", "course", "class", "lecture", "lesson",
        "teach", "teaching", "student", "study", "exam", "test", "quiz", "homework",
        "math", "science", "physics", "chemistry", "biology", "history", "geography",
        "literature", "philosophy", "psychology", "economics", "finance", "accounting",
        "law", "medicine", "engineering", "computer science", "programming", "language",
        "english", "spanish", "french", "german", "mandarin", "japanese", "ielts", "toefl",
        "sat", "gre", "gmat", "mcat", "lsat", "online course", "udemy", "coursera",
        "edx", "khan academy", "ted talk", "ted talk", "tedx", "how to", "explained",
        "understanding", "concept", "definition", "guide", "tips and tricks",
    ],
    "Fitness": [
        "fitness", "workout", "exercise", "gym", "bodybuilding", "weightlifting", "cardio",
        "running", "marathon", "yoga", "pilates", "crossfit", "hiit", "strength",
        "muscle", "abs", "core", "leg day", "arm day", "chest day", "back day", "shoulder",
        "diet", "nutrition", "protein", "calorie", "weight loss", "fat loss", "bulk",
        "cut", "personal trainer", "coach", "transformation", "before after", "before-and-after",
        "progress", "motivation", "healthy lifestyle", "wellness", "mental health",
        "meditation", "mindfulness", "sleep", "stress relief", "flexibility", "mobility",
    ],
    "Travel": [
        "travel", "trip", "vacation", "holiday", "tour", "tourism", "destination", "hotel",
        "resort", "flight", "airline", "airport", "passport", "visa", "backpacking",
        "solo travel", "budget travel", "luxury travel", "adventure", "hiking", "trekking",
        "mountains", "beach", "island", "cruise", "road trip", "city tour", "museum",
        "food tour", "cultural", "heritage", "landmark", "sunset", "view", "landscape",
        "nature", "wildlife", "safari", "diving", "snorkeling", "skiing", "snowboarding",
        "travel guide", "travel tips", "packing", "itinerary", "travel vlog", "travel diary",
    ],
    "Fashion": [
        "fashion", "style", "outfit", "ootd", "lookbook", "haul", "shopping", "wardrobe",
        "clothing", "dress", "shoes", "sneakers", "bag", "accessory", "jewelry", "watch",
        "makeup", "beauty", "skincare", "hair", "nail", "fragrance", "perfume", "cosmetics",
        "nail art", "hair tutorial", "makeup tutorial", "grwm", "get ready with me",
        "designer", "brand", "runway", "trend", "trendy", "streetwear", "casual", "formal",
        "summer outfit", "winter outfit", "fit check", "style tips", "fashion review",
    ],
    "News": [
        "news", "breaking news", "current events", "headline", "report", "journalist",
        "interview", "analysis", "opinion", "editorial", "politics", "government", "election",
        "policy", "economy", "market", "stock", "business", "company", "ceo", "merger",
        "acquisition", "lawsuit", "court", "verdict", "crime", "investigation", "scandal",
        "press conference", "briefing", "statement", "official", "announcement",
        "world news", "national", "international", "local news", "weather", "forecast",
        "natural disaster", "earthquake", "hurricane", "fire", "accident",
    ],
    "Animals": [
        "animals", "pet", "dog", "cat", "kitten", "puppy", "bird", "parrot", "fish", "turtle",
        "hamster", "rabbit", "horse", "cow", "pig", "sheep", "goat", "chicken", "duck",
        "wildlife", "zoo", "aquarium", "safari", "exotic", "reptile", "snake", "lizard",
        "frog", "insect", "butterfly", "bee", "ant", "spider", "cute animals", "funny animals",
        "animal rescue", "adopt", "veterinarian", "vet", "grooming", "training", "obedience",
        "tricks", "toy", "treat", "food", "sleep", "play", "walk", "leash", "collar",
        "aquarium", "terrarium", "cage", "bed", "health", "vaccine", "spay", "neuter",
    ],
    "Vlog": [
        "vlog", "vlog no music", "day in the life", "day in my life", "daily vlog",
        "weekly vlog", "monthly vlog", "morning routine", "night routine", "routine",
        "life update", "update", "q&a", "qa", "tag", "challenge", "storytime", "story time",
        "react", "reaction", "wimbledon", "wrapped", "spotify wrapped", "youtube wrapped",
        "rewind", "highlights", "best moments", "favorites", "wishlist", "haul",
        "unboxing", "room tour", "house tour", "apartment", "desk setup", "workspace",
        "office", "kitchen", "garden", "pool", "car", "drive", "travel vlog", "food vlog",
        "shopping vlog", "get ready with me", "grwm", "get ready with me", "grwm",
        "trying", "first time", "experience", "event", "party", "wedding", "birthday",
    ],
}

_ROMAN_URDU: dict[str, list[str]] = {
    "Gaming": ["gaming", "game", "gameplay"],
    "Cooking": ["cooking", "khana", "pakkana", "recipe", "masala"],
    "Tech": ["tech", "technology", "mobile", "laptop", "internet"],
    "Comedy": ["comedy", "funny", "masti", "joke"],
    "Music": ["music", "song", "singer", "album"],
    "Education": ["education", "tutorial", "seekhna", "parhna"],
    "Fitness": ["fitness", "gym", "exercise", "health"],
    "Travel": ["travel", "safar", "tourism", "vacation"],
    "Fashion": ["fashion", "style", " outfit", "beauty"],
    "News": ["news", "khabar", "report", "headline"],
    "Animals": ["animals", "pet", "kutta", "billi"],
    "Vlog": ["vlog", "daily", "routine"],
}


@dataclass
class CategoryResult:
    category: str
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)


class ContentCategorizer:
    """Categorize download content using keyword matching and optional LLM."""

    def __init__(self) -> None:
        self._keyword_map = _KEYWORDS

    def categorize(
        self,
        title: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> CategoryResult:
        """Return the best category for the given content.

        Args:
            title: Media title.
            description: Media description or uploader notes.
            tags: Optional list of tags.

        Returns:
            A :class:`CategoryResult` with category, confidence, and matched keywords.
        """
        tags = tags or []
        result = self._score_keywords(title, description, tags)
        if result.category == "Other" and settings.USE_LLM_CATEGORIZE:
            result = self._try_llm(title, description, tags, fallback=result)
        return result

    def _score_keywords(
        self,
        title: str,
        description: str,
        tags: List[str],
    ) -> CategoryResult:
        text_title = (title or "").lower()
        text_desc = (description or "").lower()
        text_tags = " ".join(tags).lower()
        best_category = "Other"
        best_score = 0
        best_matches: List[str] = []
        total_score = 0

        for category, keywords in self._keyword_map.items():
            score, matches = self._match_category(keywords, text_title, text_desc, text_tags)
            total_score += score
            if score > best_score:
                best_score = score
                best_category = category
                best_matches = matches

        confidence = (best_score / total_score) if total_score > 0 else 0.0
        confidence = min(confidence, 1.0)

        if confidence < float(settings.MIN_CONFIDENCE):
            return CategoryResult(category="Other", confidence=confidence, matched_keywords=best_matches)

        return CategoryResult(category=best_category, confidence=confidence, matched_keywords=best_matches)

    def _match_category(
        self,
        keywords: List[str],
        text_title: str,
        text_desc: str,
        text_tags: str,
    ) -> tuple[int, List[str]]:
        matches: List[str] = []
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in text_title:
                score += 2
                matches.append(kw_lower)
            elif kw_lower in text_tags:
                score += 2
                matches.append(kw_lower)
            elif kw_lower in text_desc:
                score += 1
                matches.append(kw_lower)
        return score, matches

    def _try_llm(
        self,
        title: str,
        description: str,
        tags: List[str],
        fallback: CategoryResult,
    ) -> CategoryResult:
        try:
            import httpx

            prompt = (
                "Classify this media title into exactly one word category from this list: "
                + ", ".join(_CATEGORIES)
                + f"\nTitle: {title}\nDescription: {description[:200]}\nTags: {', '.join(tags)}\nCategory:"
            )
            response = httpx.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={"model": "llama3.2:1b", "prompt": prompt, "stream": False, "options": {"temperature": 0}},
                timeout=10,
            )
            if response.status_code == 200:
                body = response.json()
                text = (body.get("response") or "").strip()
                for category in _CATEGORIES:
                    if category.lower() in text.lower():
                        return CategoryResult(category=category, confidence=0.95, matched_keywords=["llm"])
        except Exception as exc:
            logger.debug("LLM categorization failed: %s", exc)
        return fallback
