# FriendlyChessCoach

한국어 Stockfish 체스 코치 웹앱. Flask + python-chess + Stockfish.

Render Docker 배포를 지원합니다. 나머지 프로젝트 파일 업로드 중입니다.


## PGN game review

Paste one standard-chess PGN (or choose a .pgn file), select your side, and import. The app reviews four plies per request and reports partial progress; stop and resume are supported. Completed positions include both viewpoints, legal moves, engine variations and explanations. Previous/next and move-list navigation use the local snapshots without engine requests. The latest game and completed batches are stored in this browser's IndexedDB; the restore button reopens them after a refresh. If storage is unavailable, the app clearly reports that the results are only in the current tab. Clearing browser data removes the saved game; this is not account or cross-device storage.

Quick review uses 0.25-second searches (depth cap 12) with a separate root-move search for the actual move when needed. Classifications are approximate evaluation-loss thresholds, not Chess.com accuracy scores. The selected-position reanalysis button uses the normal deeper analysis settings and saves the updated explanation separately. PGN comments and side variations are not reviewed. Maximum 512 plies / 150KB per game.

Tests: `python -m unittest test_coaching test_openings test_game_review` and `node --test tests/board_render.test.cjs`.
