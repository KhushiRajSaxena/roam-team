# Location and configuration fix — September 13, 2026

- Backend regression suite: 40 tests passed, one upstream Starlette deprecation warning.
- Eight demo evaluation scenarios regenerated successfully, including budget revision and incomplete budget checks.
- jsdom interface verification passed: all 3,941 suggestions, Live mode enabled, exact-code and city matching, Chennai-to-Kochi demo with streamed itinerary, same-airport rejection, disconnected backend, missing key, reconnect, and outdated server diagnostics.
- Verified all three saved API keys are configured on the server at port 8002. No credential values were logged.
- No real Groq, SerpApi or Geoapify requests were made by these regression checks. New destination geocoding was tested with fixtures, not live provider calls.
- The airport catalog download used public OurAirports data, not travel API credits.
- Browser visual screenshots were not taken. Interface behavior was verified using jsdom and the running HTTP backend.
- Existing servers on ports 8000 and 8001 could not be terminated due to OS permissions. Current run.py and VS Code launch configuration use port 8002.

## Follow-up: explicit airport dropdown and visual refresh

Replaced browser-native datalists with click-to-open airport menus, short selected labels, keyboard navigation and route swapping. Added violet, mint and peach colors, focus/hover states, and reduced-motion support. jsdom checks passed for opening, filtering, mouse selection, arrow/Enter selection, swapping, no matches, Escape, outside click, same-airport exclusion, unchanged network count while selecting, streamed demo submission, and editing after completion. Backend suite remains 40 passing tests. Visual appearance has not been screenshot-verified in a browser.
