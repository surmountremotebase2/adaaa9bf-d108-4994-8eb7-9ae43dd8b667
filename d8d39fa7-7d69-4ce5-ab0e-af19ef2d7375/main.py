] Starting backtest
> - Start date: 2023-10-01 00:00:00
> - End date: 2025-10-06 00:00:00
> - Initial capital: 10000.0
> - Slippage: 0.0
> - Fees: 0.0
> [INFO] Pulling source code
> [ERROR] An error occurred while running backtest:
 Traceback (most recent call last):
  File "/var/task/task_function.py", line 82, in process
    TradingStrategy = get_strategy_from_github(
                      ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/var/task/task_function.py", line 266, in get_strategy_from_github
    mod = importlib.import_module("{}.{}.{}".format(subfolder, subfolder, "main"))
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/var/lang/lib/python3.11/importlib/__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1204, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 936, in exec_module
  File "<frozen importlib._bootstrap_external>", line 1074, in get_code
  File "<frozen importlib._bootstrap_external>", line 1004, in source_to_code
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
  File "/tmp/d8d39fa7-7d69-4ce5-ab0e-af19ef2d7375/d8d39fa7-7d69-4ce5-ab0e-af19ef2d7375/main.py", line 220
    final_close = df_current['Close
                             ^
SyntaxError: unterminated string literal (detected at line 220)