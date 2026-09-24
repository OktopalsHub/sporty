from datetime import datetime, timezone
from decimal import Decimal

from app.domain.markets import Market
from app.domain.provider import ProviderOutcome
from app.providers.sportybet.parse_client import ParseSportyBetClient
from app.services.prediction_service import PredictionService


def test_parse_outcomes_are_grouped_into_provider_events():
    events, total = ParseSportyBetClient._normalize_outcomes(
        [
            {
                "eventId": "sr:match:1",
                "tournament": "Premier League",
                "homeTeamName": "Arsenal",
                "awayTeamName": "Chelsea",
                "estimateStartTime": 1788202800000,
                "matchStatus": "Not start",
                "marketId": "18",
                "marketDesc": "Over/Under",
                "specifier": "total=2.5",
                "outcomeId": "12",
                "outcomeDesc": "Over",
                "odds": "1.80",
            },
            {
                "eventId": "sr:match:1",
                "tournament": "Premier League",
                "homeTeamName": "Arsenal",
                "awayTeamName": "Chelsea",
                "estimateStartTime": 1788202800000,
                "matchStatus": "Not start",
                "marketId": "18",
                "marketDesc": "Over/Under",
                "specifier": "total=2.5",
                "outcomeId": "13",
                "outcomeDesc": "Under",
                "odds": "2.00",
            },
        ]
    )

    assert total == 1
    assert len(events) == 1
    assert events[0].id == "sr:match:1"
    assert events[0].markets[0].specifier == "total=2.5"
    assert len(events[0].markets[0].outcomes) == 2
    assert events[0].markets[0].outcomes[0].odds == Decimal("1.80")


def test_parse_total_market_only_returns_requested_outcome():
    event = ParseSportyBetClient._normalize_outcomes(
        [
            {
                "eventId": "sr:match:1",
                "tournament": "Premier League",
                "homeTeamName": "Arsenal",
                "awayTeamName": "Chelsea",
                "estimateStartTime": 1788202800000,
                "matchStatus": "Not start",
                "marketId": "18",
                "marketDesc": "Over/Under",
                "specifier": "total=2.5",
                "outcomeId": "12",
                "outcomeDesc": "Over",
                "odds": "1.80",
            },
            {
                "eventId": "sr:match:1",
                "tournament": "Premier League",
                "homeTeamName": "Arsenal",
                "awayTeamName": "Chelsea",
                "estimateStartTime": 1788202800000,
                "matchStatus": "Not start",
                "marketId": "18",
                "marketDesc": "Over/Under",
                "specifier": "total=2.5",
                "outcomeId": "13",
                "outcomeDesc": "Under",
                "odds": "2.00",
            },
        ]
    )[0][0]

    predictions = PredictionService().generate([event], Market.OVER_2_5)

    assert len(predictions) == 1
    assert predictions[0].outcome_id == "12"
    assert predictions[0].selection == "Over"


def test_parse_start_time_supports_epoch_milliseconds():
    value = ParseSportyBetClient._parse_time(1788202800000)

    assert value.tzinfo == timezone.utc
    assert value > datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_btts_yes_outcome_is_supported():
    outcome = ProviderOutcome(
        id="1",
        description="Yes",
        odds=Decimal("1.50"),
        active=True,
    )

    assert PredictionService._outcome_matches(outcome, Market.BTTS)
