from decimal import Decimal

from app.providers.sportybet.client import SportyBetClient


def test_normalize_event() -> None:
    event = SportyBetClient._normalize_event(
        {
            "eventId": "event-1",
            "estimateStartTime": 1770000000000,
            "homeTeamName": "Home FC",
            "awayTeamName": "Away FC",
            "matchStatus": "NOT_STARTED",
            "markets": [
                {
                    "id": "market-1",
                    "desc": "Over/Under",
                    "specifier": "total=2.5",
                    "status": "OPEN",
                    "outcomes": [
                        {"id": "outcome-1", "desc": "Over 2.5", "odds": "1.80"},
                    ],
                }
            ],
        },
        {"id": "tournament-1", "name": "Premier League"},
    )

    assert event.id == "event-1"
    assert event.home_team == "Home FC"
    assert event.markets[0].outcomes[0].odds == Decimal("1.80")
    assert event.tournament_name == "Premier League"
