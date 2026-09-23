# SportyBet provider

This adapter isolates SportyBet-specific HTTP and response normalization from the prediction engine.

Implemented operations:

- upcoming football events with markets and odds
- event lookup from the current feed
- anonymous booking/share-code creation

Booking only prepares a shareable ticket. It does not stake or place a wager.

SportyBet does not provide a stable public developer API, so endpoint details can change.
Keep provider-specific paths and payload shapes inside this adapter.
