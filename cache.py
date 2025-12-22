"""
Caching modul for Friktionskompasset
Håndterer caching af aggregerede data og tunge beregninger
"""
import time
import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional, Dict
from threading import Lock

# Simple in-memory cache med TTL
_cache: Dict[str, dict] = {}
_cache_lock = Lock()

# Default TTL i sekunder (5 minutter)
DEFAULT_TTL = 300


def _make_key(*args, **kwargs) -> str:
    """Opret en unik cache key baseret på argumenter"""
    key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: int = DEFAULT_TTL, prefix: str = ""):
    """
    Decorator til at cache funktionsresultater med TTL

    Brug:
        @cached(ttl=300, prefix="stats")
        def get_expensive_data(unit_id, assessment_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Opret cache key
            cache_key = f"{prefix}:{func.__name__}:{_make_key(*args, **kwargs)}"

            with _cache_lock:
                # Tjek om vi har cached data
                if cache_key in _cache:
                    entry = _cache[cache_key]
                    if time.time() < entry['expires']:
                        return entry['value']
                    else:
                        # Expired - fjern
                        del _cache[cache_key]

            # Kald funktionen
            result = func(*args, **kwargs)

            # Cache resultatet
            with _cache_lock:
                _cache[cache_key] = {
                    'value': result,
                    'expires': time.time() + ttl,
                    'created': time.time()
                }

            return result

        # Tilføj metode til at invalidere cache for denne funktion
        wrapper.invalidate = lambda *args, **kwargs: invalidate_cached(
            f"{prefix}:{func.__name__}:{_make_key(*args, **kwargs)}"
        )
        wrapper.invalidate_all = lambda: invalidate_prefix(f"{prefix}:{func.__name__}")

        return wrapper
    return decorator


def invalidate_cached(cache_key: str) -> bool:
    """Invalider en specifik cache entry"""
    with _cache_lock:
        if cache_key in _cache:
            del _cache[cache_key]
            return True
    return False


def invalidate_prefix(prefix: str) -> int:
    """Invalider alle cache entries med et givent prefix"""
    count = 0
    with _cache_lock:
        keys_to_delete = [k for k in _cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del _cache[key]
            count += 1
    return count


def invalidate_all() -> int:
    """Ryd hele cachen"""
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
    return count


def get_cache_stats() -> Dict:
    """Hent cache statistik"""
    with _cache_lock:
        now = time.time()
        valid_entries = sum(1 for e in _cache.values() if e['expires'] > now)
        expired_entries = len(_cache) - valid_entries

        return {
            'total_entries': len(_cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'memory_keys': list(_cache.keys())[:10]  # Første 10 keys
        }


def cleanup_expired() -> int:
    """Fjern udløbne cache entries"""
    count = 0
    now = time.time()
    with _cache_lock:
        keys_to_delete = [k for k, v in _cache.items() if v['expires'] <= now]
        for key in keys_to_delete:
            del _cache[key]
            count += 1
    return count


# ============================================
# CAMPAIGN/RESPONSE CACHE INVALIDATION
# ============================================

def invalidate_assessment_cache(assessment_id: str):
    """Invalider al cache relateret til en kampagne"""
    invalidate_prefix(f"stats:")
    invalidate_prefix(f"analysis:")
    invalidate_prefix(f"breakdown:")


def invalidate_unit_cache(unit_id: str):
    """Invalider al cache relateret til en organisatorisk enhed"""
    invalidate_prefix(f"stats:")
    invalidate_prefix(f"analysis:")
    invalidate_prefix(f"breakdown:")


# ============================================
# PRELOAD CACHE (for common queries)
# ============================================

def preload_dashboard_cache(customer_id: Optional[str] = None):
    """
    Preload cache for dashboard queries
    Kald dette ved serverstart eller efter store ændringer
    """
    from db_hierarchical import get_db

    with get_db() as conn:
        # Hent aktive kampagner
        if customer_id:
            assessments = conn.execute("""
                SELECT c.id, c.unit_id
                FROM assessments c
                JOIN organizational_units ou ON c.unit_id = ou.id
                WHERE ou.customer_id = ?
                ORDER BY c.created_at DESC
                LIMIT 10
            """, (customer_id,)).fetchall()
        else:
            assessments = conn.execute("""
                SELECT id, unit_id FROM assessments
                ORDER BY created_at DESC
                LIMIT 10
            """).fetchall()

    # Preload stats for de seneste kampagner
    # (Selve preloading sker når funktionerne kaldes med caching)
    return len(assessments)


# ============================================
# PAGINATION HELPER
# ============================================

class Pagination:
    """
    Pagination helper til lister

    Brug:
        pagination = Pagination(total=100, page=2, per_page=20)
        items = query.offset(pagination.offset).limit(pagination.per_page).all()

        return render_template('list.html', items=items, pagination=pagination)
    """

    def __init__(self, total: int, page: int = 1, per_page: int = 20):
        self.total = total
        self.per_page = per_page
        self.page = max(1, min(page, self.total_pages or 1))

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def prev_page(self) -> Optional[int]:
        return self.page - 1 if self.has_prev else None

    @property
    def next_page(self) -> Optional[int]:
        return self.page + 1 if self.has_next else None

    @property
    def pages(self) -> list:
        """
        Returner liste af sidenumre til visning
        Viser max 7 sider med ellipsis
        """
        if self.total_pages <= 7:
            return list(range(1, self.total_pages + 1))

        pages = []
        if self.page <= 4:
            pages = list(range(1, 6)) + [None, self.total_pages]
        elif self.page >= self.total_pages - 3:
            pages = [1, None] + list(range(self.total_pages - 4, self.total_pages + 1))
        else:
            pages = [1, None, self.page - 1, self.page, self.page + 1, None, self.total_pages]

        return pages

    def to_dict(self) -> Dict:
        return {
            'page': self.page,
            'per_page': self.per_page,
            'total': self.total,
            'total_pages': self.total_pages,
            'has_prev': self.has_prev,
            'has_next': self.has_next,
            'prev_page': self.prev_page,
            'next_page': self.next_page,
            'pages': self.pages
        }


def paginate_query(query_func: Callable, count_func: Callable,
                   page: int = 1, per_page: int = 20) -> tuple:
    """
    Helper til at paginere database queries

    Args:
        query_func: Funktion der tager (offset, limit) og returnerer resultater
        count_func: Funktion der returnerer total count
        page: Side nummer (1-indexed)
        per_page: Antal per side

    Returns:
        (items, pagination)
    """
    total = count_func()
    pagination = Pagination(total=total, page=page, per_page=per_page)
    items = query_func(pagination.offset, pagination.per_page)
    return items, pagination
