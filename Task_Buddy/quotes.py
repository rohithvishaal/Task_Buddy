# ─────────────────────────────────────────────
#  quotes.py  —  quote pool for the quote screen
# ─────────────────────────────────────────────
# Quote of the day: seeded by date → stable all day.
# Random quote: random pick from the rest of the pool.

import random


QUOTES = [
    ("Do the hard thing first.", ""),
    ("One rep, one page, one line.", ""),
    ("Rest is part of the work.", ""),
    ("Compound interest is everywhere.", ""),
    ("Build the system, not the goal.", ""),
    ("Slow is smooth. Smooth is fast.", ""),
    ("Every expert was once a beginner.", ""),
    ("The obstacle is the way.", "Marcus Aurelius"),
    ("Amor fati.", "Nietzsche"),
    ("Discipline equals freedom.", "Jocko Willink"),
    ("Stay hard.", "David Goggins"),
    ("Dream big. Start small. Act now.", ""),
    ("It always seems impossible until done.", "Mandela"),
    ("Focus is saying no to good ideas.", "Jobs"),
    ("Data beats opinions.", ""),
    ("ML is applied linear algebra.", ""),
    ("Sleep is the best performance drug.", ""),
    ("Walk before you run the model.", ""),
    ("Your future self is watching.", ""),
    ("One more chapter. One more set.", ""),
]


def quote_of_the_day(state):
    """Return a stable (text, author) for today, seeded by date."""
    seed = state.year * 10000 + state.month * 100 + state.day
    idx  = seed % len(QUOTES)
    return QUOTES[idx]


def random_quote(exclude_idx=-1):
    """Return (index, text, author), skipping exclude_idx."""
    pool = [i for i in range(len(QUOTES)) if i != exclude_idx]
    idx  = random.choice(pool)
    return idx, QUOTES[idx][0], QUOTES[idx][1]
